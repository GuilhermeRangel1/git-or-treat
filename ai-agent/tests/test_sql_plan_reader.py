"""Plano autorizado até o resultado em banco temporário inteiramente artificial."""

import asyncio
import sqlite3
from datetime import date

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import EvidenceGuard
from app.agent.interpreter import QuestionInterpreter
from app.agent.planner import QuestionAnalysisPlanner
from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator
from app.api.access import demo_access_context
from app.ports.evidence import EvidenceAccessDenied, EvidenceContractInvalid
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import (
    CatalogGranularity,
    DimensionValue,
    DomainProfile,
    FilterOperator,
)
from app.schemas.read_plan import LogicalReadPlan, ReadFilter, ReadOrder, ReadWindow, WindowKind
from app.sql.audit import InMemoryAuditSink
from app.sql.evidence import SqlArtificialEvidenceSource, project_artificial_sql_evidence
from app.sql.executors import QueryResult, SqliteReadOnlyExecutor
from app.sql.plan import SqlMetricBinding, SqlPlanCatalog, SqlPlanReader
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected
from tests.sql_support import build_gold_sqlite, load_test_dictionary

SQL_DEMO_CONTEXT = demo_access_context(GRID360_DEMO_PROFILE, "0" * 32, "synthetic.sql")
SQL_DEMO_LIMITATION = GRID360_DEMO_PROFILE.metrics[0].limitation_texts[0]
SQL_TRUNCATION_LIMITATION = "Resultado artificial limitado às primeiras observações."


def _profile_with_sql_evidence(municipality_values: tuple[str, ...]) -> DomainProfile:
    profile_data = GRID360_DEMO_PROFILE.model_dump(mode="python")
    profile_data["dimensions"][0]["values"] = [
        DimensionValue(value=value, aliases=(value,)) for value in municipality_values
    ]
    profile_data["metrics"][0]["evidence_fields"] = [
        {"name": "value", "role": "measure", "value_type": "number", "sensitivity": "internal"},
        {"name": "unit", "role": "unit", "value_type": "string", "sensitivity": "internal"},
        {"name": "period", "role": "period", "value_type": "date", "sensitivity": "internal"},
        {
            "name": "category", "role": "dimension",
            "dimension_id": "geography.municipality",
            "value_type": "string", "sensitivity": "internal",
        },
    ]
    return DomainProfile.model_validate(profile_data)


def _reader_with_approved_municipality_filter(
    tmp_path,
    *,
    municipality_values: tuple[str, ...],
    filter_values: tuple[str, ...],
    operator: FilterOperator,
    window_start: date = date(2025, 1, 1),
    window_end: date = date(2025, 1, 31),
    reader_catalog_version: str = "v1",
    plan_limit: int = 10,
    allow_value_order: bool = False,
    allowed_filter_operators: frozenset[FilterOperator] = frozenset(
        {FilterOperator.EQ, FilterOperator.IN}
    ),
    catalog_granularity: CatalogGranularity = CatalogGranularity.MONTH,
    aggregation: str = "sum",
) -> tuple[SqlPlanReader, LogicalReadPlan, InMemoryAuditSink]:
    dictionary = load_test_dictionary()
    database = build_gold_sqlite(tmp_path / "artificial.sqlite")
    executor = SqliteReadOnlyExecutor(
        database,
        max_rows=dictionary.limits.max_rows,
        timeout_ms=dictionary.limits.timeout_ms,
        dictionary=dictionary,
    )
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(dictionary, executor, audit)
    catalog = SqlPlanCatalog(
        profile_id="v-energy-grid-360-demo",
        source_id="synthetic.sql",
        version=reader_catalog_version,
        dictionary_version=dictionary.version,
        table="gold_indicadores",
        period_column="competencia",
        period_granularity=catalog_granularity,
        metrics={
            "billing.revenue": SqlMetricBinding(
                domain_id="revenue",
                unit="unidades fictícias",
                column="receita_total",
                aggregation=aggregation,
                dimension_ids=frozenset({"geography.municipality"}),
                allow_value_order=allow_value_order,
                filter_operators=allowed_filter_operators,
            )
        },
        dimensions={"geography.municipality": "municipio"},
    )
    profile_data = GRID360_DEMO_PROFILE.model_dump(mode="python")
    profile_data["dimensions"][0]["values"] = [
        DimensionValue(value=value, aliases=(value,)) for value in municipality_values
    ]
    profile = DomainProfile.model_validate(profile_data)
    proposed = LogicalReadPlan(
        catalog_version="v1",
        operation="read",
        profile_id=profile.profile_id,
        source_id="synthetic.sql",
        domain_id="revenue",
        metric_id="billing.revenue",
        dimension_ids=("geography.municipality",),
        unit="unidades fictícias",
        window=ReadWindow(
            kind=WindowKind.BOUNDED,
            start=window_start,
            end=window_end,
            granularity="month",
        ),
        filters=(
            ReadFilter(
                dimension_id="geography.municipality",
                operator=operator,
                values=filter_values,
            ),
        ),
        limit=plan_limit,
    )
    policy = ReadAccessPolicy(profile, "synthetic.sql")
    validator = ReadPlanValidator(profile, "synthetic.sql", policy)
    approved = validator.approve(proposed, SQL_DEMO_CONTEXT)
    reader = SqlPlanReader(catalog, dictionary, service, validator)
    return reader, approved, audit


def test_approved_plan_reads_only_the_requested_artificial_month_and_municipality(
    tmp_path,
) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.columns == ("period", "value")
    assert result.rows == (("2025-01", 3500.5),)
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"
    assert "Municipio Ficticio A" not in str(audit.records[0].to_dict())


def test_approved_plan_groups_artificial_revenue_by_municipality(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    grouped_plan = LogicalReadPlan.model_validate(
        {
            **approved.model_dump(mode="python"),
            "filters": (),
            "group_by_dimension_ids": ("geography.municipality",),
        }
    )

    result = reader.read(grouped_plan, SQL_DEMO_CONTEXT)

    assert result.columns == ("period", "geography.municipality", "value")
    assert result.rows == (
        ("2025-01", "Municipio Ficticio A", 3500.5),
        ("2025-01", "Municipio Ficticio B", 800.25),
    )
    assert result.truncated is False
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"


def test_grouped_plan_orders_month_and_category_and_reports_truncation(tmp_path) -> None:
    reader, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_end=date(2025, 2, 28),
        plan_limit=3,
    )

    result = reader.read(
        approved.model_copy(
            update={
                "filters": (),
                "group_by_dimension_ids": ("geography.municipality",),
            }
        ),
        SQL_DEMO_CONTEXT,
    )

    assert result.rows == (
        ("2025-01", "Municipio Ficticio A", 3500.5),
        ("2025-01", "Municipio Ficticio B", 800.25),
        ("2025-02", "Municipio Ficticio A", 3600.75),
    )
    assert result.truncated is True


def test_grouped_plan_requires_current_dimension_access(tmp_path, monkeypatch) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    restricted = SQL_DEMO_CONTEXT.model_copy(update={"allowed_dimension_ids": frozenset()})

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("dimensão negada não deve chamar o serviço SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    with pytest.raises(EvidenceAccessDenied):
        reader.read(
            approved.model_copy(
                update={
                    "filters": (),
                    "group_by_dimension_ids": ("geography.municipality",),
                }
            ),
            restricted,
        )

    assert len(audit.records) == 1
    assert audit.records[0].reason_code == "access_denied"
    assert audit.records[0].received_sql_chars == 0


def test_unfiltered_dimension_without_explicit_grouping_is_rejected(tmp_path, monkeypatch) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("dimensão sem destino explícito não deve gerar SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    with pytest.raises(SqlRejected) as error:
        reader.read(approved.model_copy(update={"filters": ()}), SQL_DEMO_CONTEXT)

    assert error.value.code == "plan_out_of_catalog"
    assert len(audit.records) == 1
    assert audit.records[0].reason_code == "plan_out_of_catalog"
    assert audit.records[0].received_sql_chars == 0


def test_grouping_dimension_outside_the_plan_is_rejected_before_sql(tmp_path, monkeypatch) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    proposal = {
        **approved.model_dump(mode="python"),
        "group_by_dimension_ids": ("classification.consumer_class",),
    }

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("agrupamento fora do plano não deve gerar SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    with pytest.raises(PlanCapabilityUnavailable):
        reader.read(proposal, SQL_DEMO_CONTEXT)

    assert len(audit.records) == 1
    assert audit.records[0].reason_code == "unsupported_plan"
    assert audit.records[0].received_sql_chars == 0


def test_approved_plan_is_correlated_with_sql_audit_without_filter_values(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.rows == (("2025-01", 3500.5),)
    [record] = audit.records
    assert record.plan_fingerprint == approved.fingerprint()
    assert record.correlation_id == SQL_DEMO_CONTEXT.correlation_id
    assert record.catalog_version == approved.catalog_version == "v1"
    assert record.dictionary_version == "teste-1"
    assert "Municipio Ficticio A" not in str(record.to_dict())


def test_reader_rechecks_current_access_scope_before_sql_service(tmp_path, monkeypatch) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    restricted = SQL_DEMO_CONTEXT.model_copy(
        update={"allowed_metric_ids": frozenset(), "correlation_id": "1" * 32}
    )

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("acesso negado não deve chamar o serviço SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)

    for context in (restricted, None):
        with pytest.raises(EvidenceAccessDenied):
            reader.read(approved, context)

    assert [record.reason_code for record in audit.records] == [
        "access_denied",
        "access_denied",
    ]
    assert [record.correlation_id for record in audit.records] == ["1" * 32, None]
    for record in audit.records:
        assert record.status == "rejected"
        assert record.received_sql_chars == 0
        assert record.plan_fingerprint is None
        assert record.query_template is None
        assert "Municipio Ficticio A" not in str(record.to_dict())


def test_approved_in_filter_reads_all_requested_artificial_municipalities(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        operator=FilterOperator.IN,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.columns == ("period", "value")
    assert result.rows == (("2025-01", 4300.75),)
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"
    assert "Municipio Ficticio A" not in str(audit.records[0].to_dict())
    assert "Municipio Ficticio B" not in str(audit.records[0].to_dict())


@pytest.mark.parametrize(
    ("requested_operator", "allowed_operator", "filter_values"),
    [
        (FilterOperator.EQ, FilterOperator.IN, ("Municipio Ficticio A",)),
        (
            FilterOperator.IN,
            FilterOperator.EQ,
            ("Municipio Ficticio A", "Municipio Ficticio B"),
        ),
    ],
)
def test_catalog_rejects_filter_operator_not_declared_for_metric_before_sql(
    tmp_path, monkeypatch, requested_operator, allowed_operator, filter_values
) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=filter_values,
        operator=requested_operator,
        allowed_filter_operators=frozenset({allowed_operator}),
    )

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("operador fora do catálogo não deve gerar SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    with pytest.raises(SqlRejected) as error:
        reader.read(approved, SQL_DEMO_CONTEXT)

    assert error.value.code == "unsupported_filter"
    assert len(audit.records) == 1
    assert audit.records[0].reason_code == "unsupported_filter"
    assert audit.records[0].received_sql_chars == 0


def test_catalog_cannot_declare_an_operator_the_artificial_reader_cannot_compile(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="operador não implementado"):
        _reader_with_approved_municipality_filter(
            tmp_path,
            municipality_values=("Municipio Ficticio A",),
            filter_values=("Municipio Ficticio A",),
            operator=FilterOperator.EQ,
            allowed_filter_operators=frozenset({FilterOperator.GT}),
        )


@pytest.mark.parametrize(
    ("catalog_granularity", "aggregation"),
    [
        (CatalogGranularity.YEAR, "sum"),
        (CatalogGranularity.MONTH, "avg"),
    ],
)
def test_catalog_rejects_unimplemented_granularity_or_aggregation(
    tmp_path, catalog_granularity, aggregation
) -> None:
    with pytest.raises(ValueError):
        _reader_with_approved_municipality_filter(
            tmp_path,
            municipality_values=("Municipio Ficticio A",),
            filter_values=("Municipio Ficticio A",),
            operator=FilterOperator.EQ,
            catalog_granularity=catalog_granularity,
            aggregation=aggregation,
        )


def test_annual_plan_does_not_reach_monthly_artificial_sql_service(
    tmp_path, monkeypatch
) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    annual = approved.model_copy(
        update={
            "window": ReadWindow(
                kind=WindowKind.BOUNDED,
                start=date(2025, 1, 1),
                end=date(2025, 12, 31),
                granularity=CatalogGranularity.YEAR,
            )
        }
    )

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("plano anual não deve gerar SQL mensal")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    with pytest.raises(SqlRejected) as error:
        reader.read(annual, SQL_DEMO_CONTEXT)

    assert error.value.code == "unsupported_window"
    assert len(audit.records) == 1
    assert audit.records[0].reason_code == "unsupported_window"
    assert audit.records[0].received_sql_chars == 0


def test_approved_multi_month_window_returns_ordered_monthly_totals(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 3, 31),
        plan_limit=3,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.columns == ("period", "value")
    assert result.rows == (
        ("2025-01", 3500.5),
        ("2025-02", 3600.75),
        ("2025-03", 970.1),
    )
    assert result.truncated is False
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"


def test_catalog_approved_value_order_selects_highest_artificial_months(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_end=date(2025, 3, 31),
        plan_limit=2,
        allow_value_order=True,
    )
    ordered = approved.model_copy(
        update={"order": ReadOrder(field_id="billing.revenue", direction="desc")}
    )

    result = reader.read(ordered, SQL_DEMO_CONTEXT)

    assert result.rows == (("2025-02", 3600.75), ("2025-01", 3500.5))
    assert result.truncated is True
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"


def test_catalog_approved_value_order_sorts_artificial_groups(tmp_path) -> None:
    reader, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        allow_value_order=True,
    )
    ordered = approved.model_copy(
        update={
            "filters": (),
            "group_by_dimension_ids": ("geography.municipality",),
            "order": ReadOrder(field_id="billing.revenue", direction="asc"),
        }
    )

    result = reader.read(ordered, SQL_DEMO_CONTEXT)

    assert result.rows == (
        ("2025-01", "Municipio Ficticio B", 800.25),
        ("2025-01", "Municipio Ficticio A", 3500.5),
    )
    assert result.truncated is False


def test_plan_limit_truncates_the_result_and_reports_that_more_rows_exist(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 3, 31),
        plan_limit=2,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.rows == (("2025-01", 3500.5), ("2025-02", 3600.75))
    assert result.truncated is True
    assert audit.records[0].status == "accepted"


def test_plan_limit_detects_truncation_at_the_sql_service_row_cap(tmp_path) -> None:
    reader, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_start=date(2025, 1, 1),
        window_end=date(2029, 3, 31),
        plan_limit=50,
    )
    with sqlite3.connect(tmp_path / "artificial.sqlite") as connection:
        connection.executemany(
            "INSERT INTO gold_indicadores VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"{2025 + offset // 12:04d}-{offset % 12 + 1:02d}",
                    "Municipio Ficticio A",
                    "Bairro Sintetico",
                    "residencial",
                    1,
                    1,
                    1,
                )
                for offset in range(3, 51)
            ],
        )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.row_count == 50
    assert result.rows[0] == ("2025-01", 3500.5)
    assert result.rows[-1] == ("2029-02", 1.0)
    assert result.truncated is True


def test_approved_plan_preserves_a_legitimate_zero_value(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio Zero",),
        filter_values=("Municipio Ficticio Zero",),
        operator=FilterOperator.EQ,
    )
    with sqlite3.connect(tmp_path / "artificial.sqlite") as connection:
        connection.execute(
            "INSERT INTO gold_indicadores VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2025-01", "Municipio Ficticio Zero", "Bairro Zero", "residencial", 0, 0, 1),
        )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.rows == (("2025-01", 0.0),)
    assert audit.records[0].status == "accepted"


def test_approved_plan_preserves_no_rows_as_an_empty_result(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Sem Registros",),
        filter_values=("Municipio Sem Registros",),
        operator=FilterOperator.EQ,
    )

    result = reader.read(approved, SQL_DEMO_CONTEXT)

    assert result.rows == ()
    assert audit.records[0].status == "accepted"


@pytest.mark.parametrize(
    ("catalog_version", "changes", "expected_error", "expected_code"),
    [
        pytest.param(
            "v1", {"profile_id": "other-profile"}, EvidenceAccessDenied, None, id="profile"
        ),
        pytest.param("v1", {"source_id": "other-source"}, EvidenceAccessDenied, None, id="source"),
        pytest.param("v2", {}, SqlRejected, "plan_out_of_catalog", id="catalog-version"),
        pytest.param(
            "v1", {"metric_id": "billing.unknown"}, PlanCapabilityUnavailable, None, id="metric"
        ),
        pytest.param(
            "v1",
            {
                "dimension_ids": ("classification.consumer_class",),
                "filters": (
                    ReadFilter(
                        dimension_id="classification.consumer_class",
                        operator=FilterOperator.EQ,
                        values=("residential",),
                    ),
                ),
            },
            PlanCapabilityUnavailable,
            None,
            id="metric-dimension-combination",
        ),
        pytest.param(
            "v1",
            {"window": ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase="último mês")},
            PlanCapabilityUnavailable,
            None,
            id="unmapped-period-phrase",
        ),
        pytest.param(
            "v1",
            {"order": ReadOrder(field_id="billing.revenue", direction="desc")},
            SqlRejected,
            "plan_out_of_catalog",
            id="unsupported-order",
        ),
        pytest.param(
            "v1",
            {
                "filters": (
                    ReadFilter(
                        dimension_id="geography.municipality",
                        operator=FilterOperator.NE,
                        values=("Municipio Ficticio A",),
                    ),
                ),
            },
            PlanCapabilityUnavailable,
            None,
            id="unsupported-filter-operator",
        ),
    ],
)
def test_reader_rejects_unsupported_plan_before_sql_service(
    tmp_path, monkeypatch, catalog_version, changes, expected_error, expected_code
) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        reader_catalog_version=catalog_version,
    )

    def fail_if_sql_service_is_called(*_args, **_kwargs):
        raise AssertionError("plano recusado não deve chegar ao serviço SQL")

    monkeypatch.setattr(reader._service, "run", fail_if_sql_service_is_called)
    unsupported_plan = approved.model_copy(update=changes)

    with pytest.raises(expected_error) as error:
        reader.read(unsupported_plan, SQL_DEMO_CONTEXT)

    if expected_code is not None:
        assert error.value.code == expected_code
    [record] = audit.records
    assert record.status == "rejected"
    expected_reason = {
        EvidenceAccessDenied: "access_denied",
        PlanCapabilityUnavailable: "unsupported_plan",
        SqlRejected: expected_code,
    }[expected_error]
    assert record.reason_code == expected_reason
    assert record.received_sql_chars == 0
    assert record.plan_fingerprint is None
    assert record.query_template is None
    assert "Municipio Ficticio A" not in str(record.to_dict())


def test_grouped_sql_result_becomes_guarded_artificial_evidence(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    grouped = approved.model_copy(
        update={"filters": (), "group_by_dimension_ids": ("geography.municipality",)}
    )
    result = reader.read(grouped, SQL_DEMO_CONTEXT)
    evidence = project_artificial_sql_evidence(
        grouped, result, demo_limitation=SQL_DEMO_LIMITATION
    )

    profile = _profile_with_sql_evidence(("Municipio Ficticio A", "Municipio Ficticio B"))
    safe = EvidenceGuard(profile).validate(grouped, evidence)
    missing_category = evidence.model_copy(deep=True)
    assert missing_category.evidence is not None
    missing_category.evidence.records[0].pop("category")
    with pytest.raises(EvidenceContractInvalid):
        EvidenceGuard(profile).validate(grouped, missing_category)

    assert safe.evidence is not None
    assert safe.evidence.reference.is_demo is True
    assert safe.evidence.records == [
        {
            "observation_id": "row_1", "period": "2025-01", "value": 3500.5,
            "unit": "unidades fictícias",
            "dimensions": {"geography.municipality": "Municipio Ficticio A"},
        },
        {
            "observation_id": "row_2", "period": "2025-01", "value": 800.25,
            "unit": "unidades fictícias",
            "dimensions": {"geography.municipality": "Municipio Ficticio B"},
        },
    ]
    assert safe.evidence.provenance is not None
    assert safe.evidence.provenance.plan_fingerprint == grouped.fingerprint()
    assert len(audit.records) == 1 and audit.records[0].status == "accepted"


def test_sql_evidence_source_reads_with_current_context_and_preserves_provenance(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    source = SqlArtificialEvidenceSource(
        reader,
        demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )

    result = asyncio.run(source.retrieve(approved, SQL_DEMO_CONTEXT))

    assert result.status.value == "available"
    assert result.evidence is not None
    assert result.evidence.reference.is_demo is True
    assert result.evidence.records == [
        {"period": "2025-01", "value": 3500.5, "unit": "unidades fictícias"}
    ]
    assert result.evidence.provenance is not None
    assert result.evidence.provenance.plan_fingerprint == approved.fingerprint()
    assert len(audit.records) == 1 and audit.records[0].status == "accepted"


def test_sql_evidence_source_denies_revoked_scope_before_query(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    source = SqlArtificialEvidenceSource(
        reader,
        demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )
    revoked = SQL_DEMO_CONTEXT.model_copy(update={"allowed_metric_ids": frozenset()})

    allowed = asyncio.run(source.retrieve(approved, SQL_DEMO_CONTEXT))
    with pytest.raises(EvidenceAccessDenied):
        asyncio.run(source.retrieve(approved, revoked))

    assert allowed.status.value == "available"
    assert [record.status for record in audit.records] == ["accepted", "rejected"]
    assert audit.records[1].reason_code == "access_denied"
    assert audit.records[1].received_sql_chars == 0


def test_sql_evidence_source_explains_unsupported_window_before_query(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    source = SqlArtificialEvidenceSource(
        reader,
        demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )
    phrase_plan = approved.model_copy(
        update={
            "window": ReadWindow(
                kind=WindowKind.CATALOG_PHRASE, phrase="período de demonstração"
            )
        }
    )

    result = asyncio.run(source.retrieve(phrase_plan, SQL_DEMO_CONTEXT))

    assert result.status.value == "needs_clarification"
    assert result.evidence is None
    assert len(audit.records) == 1
    assert audit.records[0].status == "rejected"
    assert audit.records[0].reason_code == "unsupported_window"
    assert audit.records[0].received_sql_chars == 0


def test_planner_accepts_sql_evidence_only_after_guard_checks_period_and_category(tmp_path) -> None:
    reader, approved, audit = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A", "Municipio Ficticio B"),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    grouped = approved.model_copy(
        update={"filters": (), "group_by_dimension_ids": ("geography.municipality",)}
    )
    profile = _profile_with_sql_evidence(("Municipio Ficticio A", "Municipio Ficticio B"))
    source = SqlArtificialEvidenceSource(
        reader,
        demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(profile), source, ReadAccessPolicy(profile, "synthetic.sql")
    )

    validated_plan, evidence = asyncio.run(planner.execute_plan(grouped, SQL_DEMO_CONTEXT))

    assert validated_plan == grouped
    assert evidence.evidence is not None
    assert evidence.evidence.records == [
        {
            "observation_id": "row_1", "period": "2025-01", "value": 3500.5,
            "unit": "unidades fictícias",
            "dimensions": {"geography.municipality": "Municipio Ficticio A"},
        },
        {
            "observation_id": "row_2", "period": "2025-01", "value": 800.25,
            "unit": "unidades fictícias",
            "dimensions": {"geography.municipality": "Municipio Ficticio B"},
        },
    ]
    assert len(audit.records) == 1 and audit.records[0].status == "accepted"


def test_planner_accepts_filtered_sql_total_without_grouped_category(tmp_path) -> None:
    reader, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    profile = _profile_with_sql_evidence(("Municipio Ficticio A",))
    source = SqlArtificialEvidenceSource(
        reader,
        demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(profile), source, ReadAccessPolicy(profile, "synthetic.sql")
    )

    _, evidence = asyncio.run(planner.execute_plan(approved, SQL_DEMO_CONTEXT))

    assert evidence.evidence is not None
    assert evidence.evidence.records == [
        {
            "observation_id": "row_1", "period": "2025-01", "value": 3500.5,
            "unit": "unidades fictícias",
        }
    ]


def test_artificial_sql_projection_distinguishes_zero_from_no_evidence(tmp_path) -> None:
    zero_path = tmp_path / "zero"
    zero_path.mkdir()
    zero_reader, zero_plan, _ = _reader_with_approved_municipality_filter(
        zero_path,
        municipality_values=("Municipio Ficticio Zero",),
        filter_values=("Municipio Ficticio Zero",),
        operator=FilterOperator.EQ,
    )
    with sqlite3.connect(zero_path / "artificial.sqlite") as connection:
        connection.execute(
            "INSERT INTO gold_indicadores VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2025-01", "Municipio Ficticio Zero", "Bairro Zero", "residencial", 0, 0, 1),
        )
    zero = project_artificial_sql_evidence(
        zero_plan, zero_reader.read(zero_plan, SQL_DEMO_CONTEXT),
        demo_limitation=SQL_DEMO_LIMITATION,
    )

    empty_path = tmp_path / "empty"
    empty_path.mkdir()
    empty_reader, empty_plan, _ = _reader_with_approved_municipality_filter(
        empty_path,
        municipality_values=("Municipio Sem Registros",),
        filter_values=("Municipio Sem Registros",),
        operator=FilterOperator.EQ,
    )
    absent = project_artificial_sql_evidence(
        empty_plan, empty_reader.read(empty_plan, SQL_DEMO_CONTEXT),
        demo_limitation=SQL_DEMO_LIMITATION,
    )

    assert zero.status.value == "available"
    assert zero.evidence is not None
    assert zero.evidence.records == [
        {"period": "2025-01", "value": 0.0, "unit": "unidades fictícias"}
    ]
    assert absent.status.value == "no_evidence"
    assert absent.evidence is None


def test_truncated_sql_evidence_requires_an_explicit_limitation(tmp_path) -> None:
    reader, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
        window_end=date(2025, 3, 31),
        plan_limit=1,
    )
    result = reader.read(approved, SQL_DEMO_CONTEXT)
    assert result.truncated is True

    with pytest.raises(EvidenceContractInvalid):
        project_artificial_sql_evidence(approved, result, demo_limitation=SQL_DEMO_LIMITATION)
    projected = project_artificial_sql_evidence(
        approved, result, demo_limitation=SQL_DEMO_LIMITATION,
        truncation_limitation=SQL_TRUNCATION_LIMITATION,
    )
    assert projected.limitations == [SQL_DEMO_LIMITATION, SQL_TRUNCATION_LIMITATION]
    assert projected.evidence is not None
    assert projected.evidence.records == [
        {"period": "2025-01", "value": 3500.5, "unit": "unidades fictícias"}
    ]


def test_sql_projection_rejects_a_result_outside_the_approved_window(tmp_path) -> None:
    _, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    fabricated = QueryResult(
        columns=("period", "value"), rows=(("2025-02", 3500.5),), truncated=False
    )

    with pytest.raises(EvidenceContractInvalid):
        project_artificial_sql_evidence(
            approved, fabricated, demo_limitation=SQL_DEMO_LIMITATION
        )


def test_sql_projection_cannot_mark_another_source_as_demonstration(tmp_path) -> None:
    _, approved, _ = _reader_with_approved_municipality_filter(
        tmp_path,
        municipality_values=("Municipio Ficticio A",),
        filter_values=("Municipio Ficticio A",),
        operator=FilterOperator.EQ,
    )
    other_source = approved.model_copy(update={"source_id": "gold.production"})
    result = QueryResult(
        columns=("period", "value"), rows=(("2025-01", 3500.5),), truncated=False
    )

    with pytest.raises(EvidenceContractInvalid):
        project_artificial_sql_evidence(
            other_source, result, demo_limitation=SQL_DEMO_LIMITATION
        )
