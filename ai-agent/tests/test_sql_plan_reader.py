"""Plano autorizado até o resultado em banco temporário inteiramente artificial."""

from datetime import date

from app.agent.access import ReadAccessPolicy
from app.agent.read_plan import ReadPlanValidator
from app.api.access import demo_access_context
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DimensionValue, DomainProfile
from app.schemas.read_plan import LogicalReadPlan, ReadFilter, ReadWindow, WindowKind
from app.sql.audit import InMemoryAuditSink
from app.sql.executors import SqliteReadOnlyExecutor
from app.sql.plan import SqlMetricBinding, SqlPlanCatalog, SqlPlanReader
from app.sql.service import ReadOnlySqlService
from tests.sql_support import build_gold_sqlite, load_test_dictionary


def test_approved_plan_reads_only_the_requested_artificial_month_and_municipality(tmp_path) -> None:
    dictionary = load_test_dictionary()
    database = build_gold_sqlite(tmp_path / "artificial.sqlite")
    executor = SqliteReadOnlyExecutor(
        database,
        max_rows=dictionary.limits.max_rows,
        timeout_ms=dictionary.limits.timeout_ms,
    )
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(dictionary, executor, audit)
    catalog = SqlPlanCatalog(
        profile_id="v-energy-grid-360-demo",
        source_id="synthetic.sql",
        version="v1",
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
        DimensionValue(value="Municipio Ficticio A", aliases=("Municipio Ficticio A",))
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
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
            granularity="month",
        ),
        filters=(
            ReadFilter(
                dimension_id="geography.municipality",
                operator="eq",
                values=("Municipio Ficticio A",),
            ),
        ),
        limit=10,
    )
    policy = ReadAccessPolicy(profile, "synthetic.sql")
    approved = ReadPlanValidator(profile, "synthetic.sql", policy).approve(
        proposed,
        demo_access_context(profile, "0" * 32, "synthetic.sql"),
    )

    result = SqlPlanReader(catalog, dictionary, service).read(approved)

    assert result.columns == ("period", "value")
    assert result.rows == (("2025-01", 3500.5),)
    assert len(audit.records) == 1
    assert audit.records[0].status == "accepted"
    assert "Municipio Ficticio A" not in str(audit.records[0].to_dict())
