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
                else ["2000-01", "2000-02", "2000-03"],
            }
            for m in profile.metrics
        ],
    )
    result = asyncio.run(core.question.plan(request, "c" * 32))
    if metric is None:
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
