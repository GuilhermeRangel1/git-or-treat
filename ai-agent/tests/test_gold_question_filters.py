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


def _setup(question):
    profile = GRID360_GOLD_PROFILE
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
