"""Catálogo público confrontado com o schema físico v2 do Backend."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.agent.interpreter import QuestionInterpreter
from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanBuilder, ReadPlanValidator
from app.api.access import demo_access_context
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_mapping import (
    GRID360_GOLD_MAPPING,
    DictionarySchema,
    select_source,
    validate_mapping,
)
from app.readiness import V2_CAPABILITY_REQUIREMENTS
from app.schemas.internal import AccessScope, QuestionPlanRequest
from app.schemas.read_plan import ReadWindow, WindowKind

from .conftest import FakeModelAdapter


def backend_schema():
    root = Path(__file__).resolve().parents[2]
    code = """import json
from sqlalchemy import BigInteger,Integer,Numeric,Float,Date,DateTime,Boolean
from app.models.gold_v2 import TABLES
def kind(t):
 if isinstance(t,Float):return 'double'
 if isinstance(t,Numeric):return f'decimal({t.precision},{t.scale})'
 for c,n in ((BigInteger,'bigint'),(Integer,'integer'),
             (Date,'date'),(Boolean,'boolean')):
  if isinstance(t,c):return n
 if isinstance(t,DateTime):return 'timestamp_utc' if t.timezone else 'timestamp'
 return 'string'
tables={n:{'columns':{c.name:kind(c.type) for c in t.c},
 'key':[c.name for c in t.primary_key],
 'period_column':'competencia' if 'competencia' in t.c else None} for n,t in TABLES.items()}
print(json.dumps({'version':'gold-csv-v2','tables':tables,'sensitive_columns':[]}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root / "backend",
        check=True,
        capture_output=True,
        text=True,
    )
    return DictionarySchema.model_validate(json.loads(result.stdout))


def test_current_mapping_matches_actual_fifteen_table_backend_schema():
    schema = backend_schema()
    assert len(schema.tables) == 15
    assert GRID360_GOLD_MAPPING.mapping_version == "gold-catalog-v2"
    assert GRID360_GOLD_MAPPING.readiness_version == "gold-readiness-v2"
    validate_mapping(
        GRID360_GOLD_MAPPING,
        profile=GRID360_GOLD_PROFILE,
        dictionary=schema,
        requirements=V2_CAPABILITY_REQUIREMENTS,
    )


def test_every_metric_declares_its_own_bounded_or_accumulated_window():
    for logical in GRID360_GOLD_PROFILE.metrics:
        mapped = GRID360_GOLD_MAPPING.metric(logical.id)
        assert mapped.max_window_days == logical.max_window_days
        if logical.accumulated_period_phrases:
            assert logical.max_window_days is None
        else:
            assert logical.max_window_days == 366 * 5


def test_gold_plan_validator_enforces_metric_window_cap_even_if_global_cap_is_higher():
    profile = GRID360_GOLD_PROFILE
    source_id = "gold.local"
    policy = ReadAccessPolicy(profile, source_id)
    validator = ReadPlanValidator(profile, source_id, policy, max_window_days=366 * 10)
    context = demo_access_context(profile, "d" * 32, source_id=source_id)
    intent = QuestionInterpreter(profile).interpret(
        "Qual foi a receita no último trimestre?"
    ).intent
    assert intent is not None
    proposed = ReadPlanBuilder(profile, source_id).build(intent)
    long_window = proposed.model_copy(
        update={
            "window": ReadWindow(
                kind=WindowKind.BOUNDED,
                start="2000-01-01",
                end="2005-01-05",
                granularity="month",
            )
        }
    )

    with pytest.raises(PlanCapabilityUnavailable, match="limite"):
        validator.approve(long_window, context)


def test_tariff_uses_only_comparable_population_and_preserves_real_case():
    tariff = GRID360_GOLD_MAPPING.metric("billing.effective_tariff")
    assert all(s.numerator_column == "receita_base_comparavel_reais" for s in tariff.sources)
    assert all(s.denominator_column == "consumo_base_comparavel_kwh" for s in tariff.sources)
    assert (
        GRID360_GOLD_MAPPING.metric("network.equivalent_interruption_duration")
        .sources[0]
        .measure_column
        == "DEC"
    )
    assert (
        GRID360_GOLD_MAPPING.metric("network.equivalent_interruption_frequency")
        .sources[0]
        .measure_column
        == "FEC"
    )


def test_v2_profile_does_not_describe_an_intersection_of_sources():
    text = " ".join(t for m in GRID360_GOLD_PROFILE.metrics for t in m.limitation_texts)
    assert "Considera só os pares UC/mês com fatura e leitura" not in text
    assert "fontes independentes" in text


class NoLookup:
    async def retrieve(self, *args):
        raise AssertionError("Planejamento não pode executar evidência.")


def _monthly_coverage(start_year=2023, end_year=2025, end_month=4):
    return [
        f"{year:04d}-{month:02d}"
        for year in range(start_year, end_year + 1)
        for month in range(1, 13)
        if (year, month) <= (end_year, end_month)
    ]


@pytest.mark.parametrize(
    "question,metric,unit",
    [
        ("Qual foi a média da receita no último trimestre?", None, None),
        ("Qual foi o consumo por UC no último trimestre?", None, None),
        ("Quantos chamados no último trimestre?", "service.attendance", "protocolos"),
        ("Qual a satisfação no último trimestre?", "service.satisfaction", "pontos"),
        ("Qual a satisfação em pontos no último trimestre?", "service.satisfaction", "pontos"),
        (
            "Quantos chamados acumulados no histórico acumulado?",
            "service.accumulated_attendance",
            "protocolos",
        ),
        (
            "Qual a satisfação acumulada no histórico acumulado?",
            "service.accumulated_satisfaction",
            "pontos",
        ),
        ("Quantos chamados acumulados no último trimestre?", None, None),
        ("Qual foi a receita no histórico acumulado?", None, None),
        ("Qual foi a receita no último trimestre?", "billing.revenue", "R$"),
        ("Qual foi o consumo nos últimos 12 meses?", "energy.consumption", "kWh"),
        (
            "Qual foi o ticket médio no último trimestre?",
            "billing.average_ticket",
            "R$ por UC faturada no mês",
        ),
        (
            "Qual foi a tarifa média efetiva no último trimestre?",
            "billing.effective_tariff",
            "R$/kWh",
        ),
        (
            "Qual foi o consumo médio por UC no último trimestre?",
            "energy.average_consumption_per_uc",
            "kWh por UC com leitura no mês",
        ),
        (
            "Qual foi o FEC no mês passado?",
            "network.equivalent_interruption_frequency",
            "interrupções por UC",
        ),
        (
            "Qual foi o DEC no mês passado?",
            "network.equivalent_interruption_duration",
            "horas por UC",
        ),
    ],
)
def test_existing_core_plans_with_current_gold_profile_without_querying(question, metric, unit):
    profile = GRID360_GOLD_PROFILE
    scope = AccessScope(
        caller_ref="user.test",
        profile_id=profile.profile_id,
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={m.id for m in profile.metrics},
        allowed_dimension_ids={d.id for d in profile.dimensions},
    )
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionPlanRequest(
        question=question,
        remaining_timeout_ms=35000,
        access_scope=scope,
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {
                "metric_id": m.id,
                "kind": "none" if m.accumulated_period_phrases else "monthly",
                "competencies": []
                if m.accumulated_period_phrases
                else _monthly_coverage(1999, 2000, 12),
            }
            for m in profile.metrics
        ],
    )
    result = asyncio.run(core.question.plan(request, "c" * 32))
    if metric is None:
        assert result.status.value == "needs_clarification"
        assert result.plan is None
        return
    if metric.startswith("network.equivalent_interruption_"):
        assert result.status.value == "needs_clarification"
        assert result.plan is None
        return
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.metric_id == metric and result.plan.unit == unit
    assert result.plan.source_id == "gold.local"
    assert "gold_v2" not in result.plan.model_dump_json()
    if metric.startswith("service.accumulated_"):
        assert result.plan.window.start is None and result.plan.window.end is None
        assert result.plan.window.phrase == "histórico acumulado"
    elif result.plan.window.kind is WindowKind.BOUNDED:
        assert result.plan.window.granularity.value == "month"
        assert result.plan.window.end.day in (28, 29, 30, 31)
    mapping = GRID360_GOLD_MAPPING.metric(result.plan.metric_id)
    available = {r.id for r in V2_CAPABILITY_REQUIREMENTS}
    dimensions = {f.dimension_id for f in result.plan.filters}
    selected = select_source(mapping, dimensions, available)
    if mapping.required_dimension_ids:
        # DEC/FEC reconhecidos, mas a pergunta sem alimentador não autoriza fonte.
        assert selected is None
        return
    assert selected is not None
    assert mapping.unit == result.plan.unit
    assert selected.table.value in backend_schema().tables


@pytest.mark.parametrize(
    ("question", "metric", "start", "end"),
    [
        ("Qual foi a receita no último ano?", "billing.revenue", "2024-05-01", "2025-04-30"),
        ("Qual foi a receita no ano passado?", "billing.revenue", "2024-01-01", "2024-12-31"),
        ("Qual foi a receita este ano?", "billing.revenue", "2025-01-01", "2025-04-30"),
        ("Qual foi a receita no último trimestre?", "billing.revenue", "2025-02-01", "2025-04-30"),
        ("Qual foi a receita mês passado?", "billing.revenue", "2025-03-01", "2025-03-31"),
    ],
)
def test_gold_relative_windows_resolve_against_published_competencies(question, metric, start, end):
    profile = GRID360_GOLD_PROFILE
    scope = AccessScope(
        caller_ref="user.test",
        profile_id=profile.profile_id,
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={item.id for item in profile.metrics},
        allowed_dimension_ids={item.id for item in profile.dimensions},
    )
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionPlanRequest(
        question=question,
        remaining_timeout_ms=35000,
        access_scope=scope,
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {
                "metric_id": metric_item.id,
                "kind": "none" if metric_item.accumulated_period_phrases else "monthly",
                "competencies": []
                if metric_item.accumulated_period_phrases
                else _monthly_coverage(),
            }
            for metric_item in profile.metrics
        ],
    )

    result = asyncio.run(core.question.plan(request, "c" * 32))

    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.metric_id == metric
    assert result.plan.window.kind is WindowKind.BOUNDED
    assert result.plan.window.start.isoformat() == start
    assert result.plan.window.end.isoformat() == end
    assert result.plan.window.granularity.value == "month"


@pytest.mark.parametrize(
    "competencies",
    [
        ["2023-01", "2023-02", "2023-03", "2023-05", "2023-06"],
        [],
    ],
)
def test_gold_planning_clarifies_when_coverage_cannot_support_full_window(competencies):
    profile = GRID360_GOLD_PROFILE
    scope = AccessScope(
        caller_ref="user.test",
        profile_id=profile.profile_id,
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={item.id for item in profile.metrics},
        allowed_dimension_ids={item.id for item in profile.dimensions},
    )
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionPlanRequest(
        question="Qual foi a receita no último trimestre?",
        remaining_timeout_ms=35000,
        access_scope=scope,
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {
                "metric_id": metric.id,
                "kind": "monthly",
                "competencies": competencies,
            }
            for metric in profile.metrics
            if metric.id == "billing.revenue"
        ],
    )

    result = asyncio.run(core.question.plan(request, "c" * 32))

    assert result.status.value == "needs_clarification"
    assert result.plan is None


def test_gold_vocabulary_filters_use_batch_values_and_preserve_accents():
    profile = GRID360_GOLD_PROFILE
    scope = AccessScope(
        caller_ref="user.test",
        profile_id=profile.profile_id,
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={item.id for item in profile.metrics},
        allowed_dimension_ids={item.id for item in profile.dimensions},
    )
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionPlanRequest(
        question="Qual foi a receita comercial em Jaboatão no último trimestre?",
        remaining_timeout_ms=35000,
        access_scope=scope,
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {"metric_id": metric.id, "kind": "monthly", "competencies": _monthly_coverage()}
            for metric in profile.metrics
            if not metric.accumulated_period_phrases
        ],
        dimension_value_coverage=[
            {"dimension_id": "geography.municipality", "values": ["Olinda", "Jaboatão"]}
        ],
    )

    result = asyncio.run(core.question.plan(request, "c" * 32))

    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.metric_id == "billing.revenue"
    filters = {item.dimension_id: item.values for item in result.plan.filters}
    assert filters == {
        "customer.consumption_class": ("COMERCIAL",),
        "geography.municipality": ("Jaboatão",),
    }

    # A correção simples de período percorre o caso público, mantendo o recorte.
    from app.schemas.questions import ConversationTurn

    coverage = [
        {"metric_id": "billing.revenue", "kind": "monthly",
         "competencies": ["2025-01", "2025-02", "2025-03"]}
    ]
    original = request.model_copy(update={
        "question": "Qual foi a receita comercial em Jaboatão no último ano?"
    })
    original = QuestionPlanRequest.model_validate({
        **original.model_dump(mode="python"), "temporal_coverage": coverage
    })
    clarification = asyncio.run(core.question.plan(original, "d" * 32))
    assert clarification.status.value == "needs_clarification"
    follow_up = QuestionPlanRequest.model_validate({
        **original.model_dump(mode="python"),
        "question": "último trimestre",
        "context": [
            ConversationTurn(role="user", content=original.question),
            ConversationTurn(role="assistant", content=clarification.response.message),
        ],
    })
    corrected = asyncio.run(core.question.plan(follow_up, "e" * 32))
    assert corrected.status.value == "planned", corrected.model_dump_json()
    assert corrected.plan.metric_id == "billing.revenue"
    assert {item.dimension_id: item.values for item in corrected.plan.filters} == filters
    assert corrected.plan.window.start.isoformat() == "2025-01-01"
    assert corrected.plan.window.end.isoformat() == "2025-03-31"

    # Histórico autorizado anteriormente não mantém uma permissão revogada.
    revoked_scope = scope.model_copy(update={
        "allowed_dimension_ids": scope.allowed_dimension_ids - {"geography.municipality"}
    })
    revoked = QuestionPlanRequest.model_validate({
        **follow_up.model_dump(mode="python"),
        "access_scope": revoked_scope,
        "dimension_value_coverage": [],
    })
    denied = asyncio.run(core.question.plan(revoked, "f" * 32))
    assert denied.plan is None
    assert denied.status.value in {"refused", "needs_clarification"}

    # O valor físico publicado prevalece sobre a grafia de exemplo do perfil.
    published_class = QuestionPlanRequest.model_validate({
        **request.model_dump(mode="python"),
        "dimension_value_coverage": [
            {"dimension_id": "geography.municipality", "values": ["Jaboatão"]},
            {"dimension_id": "customer.consumption_class", "values": ["Comercial"]},
        ],
    })
    canonical = asyncio.run(core.question.plan(published_class, "a" * 32))
    assert canonical.status.value == "planned"
    assert next(
        item.values for item in canonical.plan.filters
        if item.dimension_id == "customer.consumption_class"
    ) == ("Comercial",)


@pytest.mark.parametrize(
    "question",
    [
        "Qual foi a receita em Olinda e Jaboatão no último trimestre?",
        "Qual bairro mais perdeu consumo residencial no último ano?",
        "Quanto cresceu a receita comercial em Jaboatão no último trimestre?",
        "Qual foi o valor pago em Jaboatão no último trimestre?",
        "Qual foi a energia faturada em Olinda no último trimestre?",
        "Quantas UCs com solar em Olinda tiveram queda de consumo no último ano?",
    ],
)
def test_gold_planning_clarifies_when_comparison_ranking_or_metric_is_unsupported(question):
    profile = GRID360_GOLD_PROFILE
    scope = AccessScope(
        caller_ref="user.test",
        profile_id=profile.profile_id,
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={item.id for item in profile.metrics},
        allowed_dimension_ids={item.id for item in profile.dimensions},
    )
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionPlanRequest(
        question=question,
        remaining_timeout_ms=35000,
        access_scope=scope,
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {
                "metric_id": metric.id,
                "kind": "none" if metric.accumulated_period_phrases else "monthly",
                "competencies": []
                if metric.accumulated_period_phrases
                else _monthly_coverage(),
            }
            for metric in profile.metrics
        ],
        dimension_value_coverage=[
            {"dimension_id": "geography.municipality", "values": ["Olinda", "Jaboatão"]},
            {"dimension_id": "geography.neighborhood", "values": ["Casa Caiada"]},
        ],
    )

    result = asyncio.run(core.question.plan(request, "c" * 32))

    assert result.status.value == "needs_clarification"
    assert result.plan is None


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "column",
        "type",
        "grain",
        "period",
        "dimension_type",
        "period_type",
        "decimal_shape",
        "timestamp_timezone",
        "sensitive_column",
    ],
)
def test_v2_mapping_rejects_backend_schema_drift(mutation):
    schema = backend_schema().model_dump()
    table = schema["tables"]["indicadores_dec_fec"]
    if mutation == "version":
        schema["version"] = "gold-csv-v1"
    if mutation == "column":
        table["columns"]["dec"] = table["columns"].pop("DEC")
    if mutation == "type":
        table["columns"]["DEC"] = "string"
    if mutation == "grain":
        table["key"] = ("competencia",)
    if mutation == "period":
        table["period_column"] = None
    if mutation == "dimension_type":
        table["columns"]["municipio"] = "double"
    if mutation == "period_type":
        table["columns"]["competencia"] = "bigint"
    if mutation == "decimal_shape":
        schema["tables"]["diagnostico_receita"]["columns"][
            "receita_total_reais"
        ] = "decimal(38,0)"
    if mutation == "timestamp_timezone":
        schema["tables"]["atendimentos_uc"]["columns"][
            "data_abertura"
        ] = "timestamp"
    if mutation == "sensitive_column":
        schema["sensitive_columns"] = ["DEC"]
    from app.profiles.grid360_gold_mapping import CatalogMappingError

    with pytest.raises(CatalogMappingError):
        validate_mapping(
            GRID360_GOLD_MAPPING,
            profile=GRID360_GOLD_PROFILE,
            dictionary=DictionarySchema.model_validate(schema),
            requirements=V2_CAPABILITY_REQUIREMENTS,
        )


@pytest.mark.parametrize(
    "metric_id,dimensions,available",
    [
        ("billing.revenue", {"customer.consumer_unit"}, {"consumo.mensal_uc"}),
        ("billing.effective_tariff", {"customer.consumer_unit"}, {"consumo.mensal_uc"}),
        ("energy.consumption", set(), {"faturamento.receita"}),
    ],
)
def test_source_requires_readiness_of_metric_domain(metric_id, dimensions, available):
    assert select_source(GRID360_GOLD_MAPPING.metric(metric_id), dimensions, available) is None


def test_mapping_rejects_unknown_readiness_dependency():
    from app.profiles.grid360_gold_mapping import CatalogMappingError

    data = GRID360_GOLD_MAPPING.model_dump()
    data["metrics"][0]["required_capability_ids"] = ("unknown.capacity",)
    with pytest.raises(CatalogMappingError, match="unknown.capacity"):
        validate_mapping(
            type(GRID360_GOLD_MAPPING).model_validate(data),
            profile=GRID360_GOLD_PROFILE,
            dictionary=backend_schema(),
        )


@pytest.mark.parametrize("mutation", ["unit", "unit_kind", "numerator", "denominator"])
def test_v2_validator_rejects_semantic_changes_with_physically_valid_columns(mutation):
    from app.profiles.grid360_gold_mapping import CatalogMappingError

    data = GRID360_GOLD_MAPPING.model_dump(mode="json")
    metric = next(m for m in data["metrics"] if m["metric_id"] == "billing.effective_tariff")
    if mutation == "unit":
        metric["unit"] = "kWh"
    elif mutation == "unit_kind":
        metric["unit_kind"] = "energy"
    elif mutation == "numerator":
        metric["sources"][0]["numerator_column"] = "receita_total_reais"
    else:
        metric["sources"][0]["denominator_column"] = "consumo_total_kwh"
    with pytest.raises(CatalogMappingError):
        validate_mapping(
            type(GRID360_GOLD_MAPPING).model_validate(data),
            profile=GRID360_GOLD_PROFILE,
            dictionary=backend_schema(),
        )


def test_mapping_validator_uses_immutable_signature_after_nested_mutation():
    from app.profiles.grid360_gold_mapping import CatalogMappingError

    source = GRID360_GOLD_MAPPING.metric("network.equivalent_interruption_duration").sources[0]
    dimension_id = "network.feeder"
    original = source.dimension_columns[dimension_id]
    try:
        source.dimension_columns[dimension_id] = "municipio"
        with pytest.raises(CatalogMappingError, match="definição semântica versionada"):
            validate_mapping(
                GRID360_GOLD_MAPPING,
                profile=GRID360_GOLD_PROFILE,
                dictionary=backend_schema(),
            )
        with pytest.raises(CatalogMappingError, match="definição semântica versionada"):
            select_source(
                GRID360_GOLD_MAPPING.metric("network.equivalent_interruption_duration"),
                {dimension_id},
                {"interrupcoes.dec_fec"},
            )
    finally:
        source.dimension_columns[dimension_id] = original


def test_source_selection_rejects_unknown_metric_even_with_existing_source():
    from app.profiles.grid360_gold_mapping import CatalogMappingError

    unknown = GRID360_GOLD_MAPPING.metric("billing.revenue").model_copy(
        update={"metric_id": "billing.unapproved_revenue"}
    )
    with pytest.raises(CatalogMappingError, match="fora do catálogo"):
        select_source(unknown, set(), {r.id for r in V2_CAPABILITY_REQUIREMENTS})
