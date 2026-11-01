"""Recortes combinados pelo caso público do núcleo Gold v2."""

import asyncio

import pytest

from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.internal import AccessScope, QuestionPlanRequest
from app.schemas.questions import ConversationTurn

from .conftest import FakeModelAdapter
from .test_gold_catalog_v2 import NoLookup


def _setup(question, *, max_rows=100):
    profile = GRID360_GOLD_PROFILE
    core = compose_core(
        profile=profile,
        source_id="gold.local",
        evidence_source=NoLookup(),
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
        max_rows=max_rows,
    )
    request = QuestionPlanRequest(
        question=question,
        remaining_timeout_ms=35000,
        access_scope=AccessScope(
            caller_ref="user.test",
            profile_id=profile.profile_id,
            source_id="gold.local",
            allowed_operations={"read"},
            allowed_metric_ids={m.id for m in profile.metrics},
            allowed_dimension_ids={d.id for d in profile.dimensions},
        ),
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        temporal_coverage=[
            {
                "metric_id": m.id,
                "kind": "monthly",
                "competencies": ["2025-01", "2025-02", "2025-03"],
            }
            for m in profile.metrics
            if not m.accumulated_period_phrases
        ],
        dimension_value_coverage=[
            {"dimension_id": "geography.municipality", "values": ["Olinda", "Recife"]},
            {"dimension_id": "geography.neighborhood", "values": ["Casa Caiada"]},
            {"dimension_id": "network.feeder", "values": ["AL-01"]},
            {"dimension_id": "tariff.subgroup", "values": ["B1"]},
        ],
    )
    return core, request


@pytest.mark.parametrize(
    "question,expected",
    [
        (
            "Receita residencial em Olinda no bairro Casa Caiada no último trimestre?",
            {
                "geography.municipality": ("Olinda",),
                "geography.neighborhood": ("Casa Caiada",),
                "customer.consumption_class": ("RESIDENCIAL",),
            },
        ),
        (
            "Consumo residencial com GD no último trimestre?",
            {
                "customer.consumption_class": ("RESIDENCIAL",),
                "generation.distributed": ("Sim",),
            },
        ),
        (
            "Receita residencial sem GD no subgrupo B1 no último trimestre?",
            {
                "customer.consumption_class": ("RESIDENCIAL",),
                "generation.distributed": ("Não",),
                "tariff.subgroup": ("B1",),
            },
        ),
        ("DEC no alimentador AL-01 mês passado?", {"network.feeder": ("AL-01",)}),
        (
            "Receita em Olinda, não, em Recife no último trimestre?",
            {"geography.municipality": ("Recife",)},
        ),
    ],
)
def test_combined_filters_reach_the_approved_plan(question, expected):
    core, request = _setup(question)
    result = asyncio.run(core.question.plan(request, "a" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert {f.dimension_id: f.values for f in result.plan.filters} == expected


@pytest.mark.parametrize(
    "question",
    [
        "Receita no subgrupo DESCONHECIDO no último trimestre?",
        "Consumo da UC 123456 no último trimestre?",
        "DEC no alimentador DESCONHECIDO mês passado?",
        "Receita com GD e sem GD no último trimestre?",
        "Receita residencial e comercial no último trimestre?",
        "Receita em Olinda e Recife no último trimestre?",
        "Receita exceto residencial no último trimestre?",
        "Receita não residencial no último trimestre?",
        "Receita em kWh no último trimestre?",
        "Consumo em reais no último trimestre?",
        "Quantos chamados em Olinda no último trimestre?",
        "DEC mês passado?",
        "FEC em Olinda mês passado?",
    ],
)
def test_unknown_or_conflicting_filters_never_produce_a_broader_plan(question):
    core, request = _setup(question)
    result = asyncio.run(core.question.plan(request, "b" * 32))
    assert result.status.value == "needs_clarification", result.model_dump_json()
    assert result.plan is None


def test_follow_up_preserves_each_dimension_and_rechecks_revoked_access():
    original = "Receita residencial com GD em Olinda no último trimestre?"
    core, request = _setup(original)
    follow = QuestionPlanRequest.model_validate(
        {
            **request.model_dump(mode="python"),
            "question": "E em Recife?",
            "context": [ConversationTurn(role="user", content=original)],
        }
    )
    result = asyncio.run(core.question.plan(follow, "c" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert {f.dimension_id: f.values for f in result.plan.filters} == {
        "customer.consumption_class": ("RESIDENCIAL",),
        "generation.distributed": ("Sim",),
        "geography.municipality": ("Recife",),
    }
    denied = QuestionPlanRequest.model_validate(
        {
            **follow.model_dump(mode="python"),
            "access_scope": request.access_scope.model_copy(
                update={
                    "allowed_dimension_ids": request.access_scope.allowed_dimension_ids
                    - {"generation.distributed"}
                }
            ),
        }
    )
    result = asyncio.run(core.question.plan(denied, "d" * 32))
    assert result.status.value == "refused"
    assert result.plan is None


def test_same_name_in_two_dimensions_requires_clarification():
    core, request = _setup("Receita em Olinda no último trimestre?")
    ambiguous = QuestionPlanRequest.model_validate(
        {
            **request.model_dump(mode="python"),
            "dimension_value_coverage": [
                {"dimension_id": "geography.municipality", "values": ["Olinda"]},
                {"dimension_id": "geography.neighborhood", "values": ["Olinda"]},
            ],
        }
    )
    result = asyncio.run(core.question.plan(ambiguous, "e" * 32))
    assert result.status.value == "needs_clarification"
    assert result.plan is None


@pytest.mark.parametrize('explicit_class', [False, True])
def test_full_feeder_identifier_does_not_invent_a_class_from_its_suffix(explicit_class):
    question = 'DEC no alimentador AL-TESTE mês passado?'
    if explicit_class:
        question += ' Na classe TESTE.'
    core, request = _setup(question)
    payload = request.model_dump(mode='python')
    payload['dimension_value_coverage'] = [
        {'dimension_id': 'network.feeder', 'values': ['AL-TESTE']},
        {'dimension_id': 'customer.consumption_class', 'values': ['TESTE']},
    ]
    result = asyncio.run(core.question.plan(QuestionPlanRequest.model_validate(payload), 'f' * 32))
    if explicit_class:
        assert result.status.value == 'needs_clarification'
        assert result.plan is None
    else:
        assert result.status.value == 'planned', result.model_dump_json()
        assert {f.dimension_id: f.values for f in result.plan.filters} == {
            'network.feeder': ('AL-TESTE',),
        }


@pytest.mark.parametrize(
    "original,answer,metric,expected",
    [
        (
            "Valor pago residencial em Olinda no último trimestre?",
            "Receita faturada",
            "billing.revenue",
            {"customer.consumption_class": ("RESIDENCIAL",), "geography.municipality": ("Olinda",)},
        ),
        (
            "Energia faturada em Olinda no último trimestre?",
            "Consumo medido",
            "energy.consumption",
            {"geography.municipality": ("Olinda",)},
        ),
        (
            "Falta de luz no alimentador AL-01 mês passado?",
            "DEC",
            "network.equivalent_interruption_duration",
            {"network.feeder": ("AL-01",)},
        ),
    ],
)
def test_metric_clarification_preserves_the_original_period_and_filters(
    original, answer, metric, expected
):
    core, request = _setup(original)
    first = asyncio.run(core.question.plan(request, "f" * 32))
    assert first.status.value == "needs_clarification"
    follow = QuestionPlanRequest.model_validate(
        {
            **request.model_dump(mode="python"),
            "question": answer,
            "context": [
                ConversationTurn(role="user", content=original),
                ConversationTurn(role="assistant", content=first.response.message),
            ],
        }
    )
    result = asyncio.run(core.question.plan(follow, "a" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.metric_id == metric
    assert {f.dimension_id: f.values for f in result.plan.filters} == expected


def test_planned_envelope_crosses_backend_contract_without_losing_filters_or_limits():
    """Wire real entre processos; não simula executor nem consulta ao banco."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    core, request = _setup(
        "Receita residencial em Olinda no bairro Casa Caiada no último trimestre?"
    )
    result = asyncio.run(core.question.plan(request, "a" * 32))
    assert result.status.value == "planned"
    payload = result.model_dump(mode="json")
    code = """
import json, sys
from app.schemas.genai_internal import QuestionPlanResponse
response = QuestionPlanResponse.model_validate(json.load(sys.stdin))
assert response.plan_fingerprint == response.plan.fingerprint()
print(response.model_dump_json())
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2] / "backend",
        timeout=30,
        encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    accepted = json.loads(completed.stdout)
    assert accepted == payload
    assert accepted["plan"]["limit"] == 100
    assert accepted["plan"]["order"] is None
    assert accepted["plan"]["window"] == {
        "kind": "bounded",
        "phrase": None,
        "start": "2025-01-01",
        "end": "2025-03-31",
        "granularity": "month",
    }


@pytest.mark.parametrize(
    "period,start,end",
    [
        ("janeiro de 2025", "2025-01-01", "2025-01-31"),
        ("MARÇO 2025", "2025-03-01", "2025-03-31"),
        ("2025-02", "2025-02-01", "2025-02-28"),
        ("de janeiro de 2025 a março de 2025", "2025-01-01", "2025-03-31"),
        ("de 2025-01 até 2025-03", "2025-01-01", "2025-03-31"),
    ],
)
def test_explicit_calendar_months_use_published_coverage(period, start, end):
    core, request = _setup(f"Receita residencial em Olinda em {period}?")
    result = asyncio.run(core.question.plan(request, "a" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.window.start.isoformat() == start
    assert result.plan.window.end.isoformat() == end
    assert {f.dimension_id: f.values for f in result.plan.filters} == {
        "customer.consumption_class": ("RESIDENCIAL",),
        "geography.municipality": ("Olinda",),
    }


@pytest.mark.parametrize(
    "period",
    [
        "janeiro",
        "ano 2025",
        "abril de 2025",
        "de março de 2025 a janeiro de 2025",
        "15 de março de 2025",
        "2025-03-15",
        "15/03/2025",
        "janeiro de 2025 e março de 2025",
        "de janeiro de 2025 a abril de 2025",
        "até março de 2025",
        "desde março de 2025",
        "de janeiro a março de 2025",
        "março de 2025 até agora",
    ],
)
def test_unsupported_or_uncovered_explicit_period_never_widens_the_window(period):
    core, request = _setup(f"Receita em {period}?")
    result = asyncio.run(core.question.plan(request, "b" * 32))
    assert result.status.value == "needs_clarification", result.model_dump_json()
    assert result.plan is None


def test_explicit_month_can_answer_a_period_clarification():
    original = "Receita residencial em Olinda?"
    core, request = _setup(original)
    first = asyncio.run(core.question.plan(request, "c" * 32))
    assert first.status.value == "needs_clarification"
    follow = QuestionPlanRequest.model_validate(
        {
            **request.model_dump(mode="python"),
            "question": "fevereiro de 2025",
            "context": [
                ConversationTurn(role="user", content=original),
                ConversationTurn(role="assistant", content=first.response.message),
            ],
        }
    )
    result = asyncio.run(core.question.plan(follow, "d" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.window.end.isoformat() == "2025-02-28"
    assert len(result.plan.filters) == 2


@pytest.mark.parametrize(
    "question",
    [
        "Receita em Olinda no último trimestre?",
        "Receita em fevereiro de 2025?",
    ],
)
def test_enriched_profile_keeps_the_configured_row_limit(question):
    core, request = _setup(question, max_rows=7)
    result = asyncio.run(core.question.plan(request, "e" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.limit == 7


def test_feeder_clarification_keeps_metric_and_explicit_month():
    original = "DEC em fevereiro de 2025?"
    core, request = _setup(original)
    first = asyncio.run(core.question.plan(request, "a" * 32))
    assert first.status.value == "needs_clarification"
    assert "alimentador" in first.response.message
    follow = QuestionPlanRequest.model_validate(
        {
            **request.model_dump(mode="python"),
            "question": "AL-01",
            "context": [
                ConversationTurn(role="user", content=original),
                ConversationTurn(role="assistant", content=first.response.message),
            ],
        }
    )
    result = asyncio.run(core.question.plan(follow, "b" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.metric_id == "network.equivalent_interruption_duration"
    assert result.plan.window.start.isoformat() == "2025-02-01"
    assert result.plan.window.end.isoformat() == "2025-02-28"
    assert {f.dimension_id: f.values for f in result.plan.filters} == {
        "network.feeder": ("AL-01",),
    }


def test_validator_rejects_a_plan_with_the_required_feeder_removed():
    from app.agent.access import ReadAccessPolicy
    from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator

    core, request = _setup("DEC no alimentador AL-01 em fevereiro de 2025?")
    result = asyncio.run(core.question.plan(request, "c" * 32))
    assert result.status.value == "planned"
    validator = ReadPlanValidator(
        GRID360_GOLD_PROFILE, "gold.local", ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local")
    )
    altered = result.plan.model_copy(update={"filters": (), "dimension_ids": ()})
    with pytest.raises(PlanCapabilityUnavailable, match="filtros obrigatórios"):
        validator.approve(altered, request.access_scope.to_context("d" * 32))


@pytest.mark.parametrize("question", [
    "Receita da classe desconhecida e residencial no último trimestre?",
    "Receita residencial no subgrupo B1 e no subgrupo desconhecido no último trimestre?",
    "Receita no bairro Casa Caiada e no bairro desconhecido no último trimestre?",
    "Receita no município desconhecido e em Olinda no último trimestre?",
    "DEC no alimentador AL-01 e no alimentador desconhecido mês passado?",
])
def test_one_known_value_does_not_hide_another_unknown_filter(question):
    core, request = _setup(question)
    result = asyncio.run(core.question.plan(request, "e" * 32))
    assert result.status.value == "needs_clarification", result.model_dump_json()
    assert result.plan is None


def test_follow_up_reconstructs_the_resolved_intent_within_three_context_turns():
    original = "Receita residencial em Olinda?"
    core, request = _setup(original)
    first = asyncio.run(core.question.plan(request, "a" * 32))
    follow = QuestionPlanRequest.model_validate({
        **request.model_dump(mode="python"), "question": "E em Recife?",
        "context": [ConversationTurn(role="user", content=original),
                    ConversationTurn(role="assistant", content=first.response.message),
                    ConversationTurn(role="user", content="fevereiro de 2025")],
    })
    result = asyncio.run(core.question.plan(follow, "b" * 32))
    assert result.status.value == "planned", result.model_dump_json()
    assert result.plan.window.start.isoformat() == "2025-02-01"
    assert {f.dimension_id: f.values for f in result.plan.filters} == {
        "customer.consumption_class": ("RESIDENCIAL",),
        "geography.municipality": ("Recife",),
    }


@pytest.mark.parametrize("question", [
    "Receita sem leitura no último trimestre?",
    "Receita com leitura no último trimestre?",
    "Consumo sem fatura no último trimestre?",
    "Receita com estornos no último trimestre?",
    "Receita das faturas vencidas no último trimestre?",
    "Receita acima de 1000 reais no último trimestre?",
    "Consumo abaixo de 100 kWh no último trimestre?",
    "Receita top 5 no último trimestre?",
    "Ordene a receita no último trimestre?",
    "Receita em ordem decrescente no último trimestre?",
])
def test_unrepresented_qualifiers_never_turn_into_an_unfiltered_total(question):
    core, request = _setup(question)
    result = asyncio.run(core.question.plan(request, "c" * 32))
    assert result.status.value == "needs_clarification", result.model_dump_json()
    assert result.plan is None


@pytest.mark.parametrize("mutation", ["group_by", "order"])
def test_revalidation_refuses_unsupported_grouping_or_ordering(mutation):
    from app.agent.access import ReadAccessPolicy
    from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator
    from app.schemas.read_plan import LogicalReadPlan

    core, request = _setup("Receita em Olinda no último trimestre?")
    result = asyncio.run(core.question.plan(request, "d" * 32))
    assert result.status.value == "planned"
    payload = result.plan.model_dump(mode="json")
    if mutation == "group_by":
        payload["group_by_dimension_ids"] = ["geography.municipality"]
    else:
        payload["order"] = {"field_id": "billing.revenue", "direction": "desc"}
    proposed = LogicalReadPlan.model_validate(payload)
    validator = ReadPlanValidator(
        GRID360_GOLD_PROFILE, "gold.local", ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local")
    )
    with pytest.raises(PlanCapabilityUnavailable, match="agrupamento|ordenação"):
        validator.approve(proposed, request.access_scope.to_context("e" * 32))


@pytest.mark.parametrize("question", [
    "Receita recebida em Olinda no último trimestre?",
    "Receita paga em Olinda no último trimestre?",
    "Arrecadação em Olinda no último trimestre?",
    "Receita das faturas pagas no último trimestre?",
    "Consumo injetado em Olinda no último trimestre?",
    "Energia compensada em Olinda no último trimestre?",
    "Energia entregue em Olinda no último trimestre?",
])
def test_business_synonyms_do_not_change_the_measure_population(question):
    core, request = _setup(question)
    result = asyncio.run(core.question.plan(request, "f" * 32))
    assert result.status.value == "needs_clarification", result.model_dump_json()
    assert result.plan is None


def test_explicit_municipality_qualifier_disambiguates_shared_neighborhood_name():
    from app.schemas.internal import DimensionValueCoverage
    core, request = _setup("Receita no município de Recife em março de 2025?")
    request = request.model_copy(update={"dimension_value_coverage": (
        *[v for v in request.dimension_value_coverage
          if v.dimension_id != "geography.neighborhood"],
        DimensionValueCoverage(dimension_id="geography.neighborhood", values=["Recife"]),
    )})
    result = asyncio.run(core.question.plan(request, "f" * 32))
    assert result.status.value == "planned"
    assert {f.dimension_id: f.values for f in result.plan.filters} == {
        "geography.municipality": ("Recife",),
    }
