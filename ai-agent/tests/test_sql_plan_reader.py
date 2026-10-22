"""Plano autorizado até o resultado em banco temporário inteiramente artificial."""

import sqlite3
from datetime import date

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator
from app.api.access import demo_access_context
from app.ports.evidence import EvidenceAccessDenied
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DimensionValue, DomainProfile, FilterOperator
from app.schemas.read_plan import LogicalReadPlan, ReadFilter, ReadOrder, ReadWindow, WindowKind
from app.sql.audit import InMemoryAuditSink
from app.sql.executors import SqliteReadOnlyExecutor
from app.sql.plan import SqlMetricBinding, SqlPlanCatalog, SqlPlanReader
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected
from tests.sql_support import build_gold_sqlite, load_test_dictionary

SQL_DEMO_CONTEXT = demo_access_context(GRID360_DEMO_PROFILE, "0" * 32, "synthetic.sql")


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
        metrics={
            "billing.revenue": SqlMetricBinding(
                domain_id="revenue",
                unit="unidades fictícias",
                column="receita_total",
                aggregation="sum",
                dimension_ids=frozenset({"geography.municipality"}),
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
    restricted = SQL_DEMO_CONTEXT.model_copy(update={"allowed_metric_ids": frozenset()})

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
