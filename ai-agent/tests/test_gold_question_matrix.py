"""Matriz de perguntas Gold (GENAI-04, parte 04a) pela composição pública do núcleo.

Cada caso de ``fixtures/gold_question_matrix.json`` passa por pergunta -> intenção -> plano
aprovado -> fonte. A fonte é um espião que só captura o plano e responde sem evidência; nada lê
lote real. Os esperados da matriz vêm do case, do dicionário e do catálogo.
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.agent.interpreter import QuestionInterpreter
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING, select_source
from app.readiness import CAPABILITY_REQUIREMENTS
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.interpretation import InterpretationStatus
from app.schemas.questions import ConversationTurn, QuestionRequest

from .conftest import FakeModelAdapter

MATRIX = json.loads(
    (Path(__file__).parent / "fixtures" / "gold_question_matrix.json").read_text(encoding="utf-8")
)
CASES = MATRIX["cases"]
CORRELATION_ID = "d" * 32
FILTER_DIMENSIONS = {
    "municipality": "geography.municipality",
    "consumption_class": "customer.consumption_class",
    "distributed_generation": "generation.distributed",
    "feeder": "network.feeder",
}
APPROVED = frozenset(
    source.capability_id for metric in GRID360_GOLD_MAPPING.metrics for source in metric.sources
)
UNAVAILABLE = frozenset(item.capability_id for item in GRID360_GOLD_MAPPING.unavailable)
# Grupos de capacidades indisponíveis com mensagem própria no perfil (GENAI-04).
UNAVAILABLE_GROUPS = UNAVAILABLE - {"interrupcoes.uc_acumulado"}
UNAVAILABLE_MARK = "na Gold carregada"


class PlanSpy:
    """Fonte que só registra o plano aprovado e nunca devolve dado."""

    def __init__(self) -> None:
        self.plans = []

    async def retrieve(self, plan, _access_context):
        self.plans.append(plan)
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE, message="Espião sem evidência."
        )


def _ask(case: dict):
    spy = PlanSpy()
    core = compose_core(
        profile=GRID360_GOLD_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        evidence_source=spy,
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    request = QuestionRequest(
        question=case["question"],
        context=[ConversationTurn(**turn) for turn in case.get("context", [])],
    )
    response = asyncio.run(
        core.question.answer(request, demo_access_context(GRID360_GOLD_PROFILE, CORRELATION_ID))
    )
    return response, spy.plans


def _expected_filters(case: dict) -> dict[str, tuple[str, ...]]:
    return {
        FILTER_DIMENSIONS[name]: (value,)
        for name, value in case["expected_filters"].items()
        if value is not None
    }


def _mismatches(case: dict, response, plans) -> list[str]:
    if case["expected_status"] == "needs_clarification":
        problems = []
        if response.status != "needs_clarification":
            problems.append(f"status {response.status}")
        if plans:
            problems.append("plano chegou à fonte")
        message = (response.message or "").casefold()
        problems.extend(
            f"mensagem sem {fragment!r}"
            for fragment in case["expected_message_fragments"]
            if fragment.casefold() not in message
        )
        return problems

    if len(plans) != 1:
        return [f"status {response.status}, {len(plans)} plano(s) na fonte"]
    plan = plans[0]
    filters = _expected_filters(case)
    actual = {
        "status": response.status,
        "domain": plan.domain_id,
        "metric": plan.metric_id,
        "period": plan.window.phrase,
        "filters": {item.dimension_id: item.values for item in plan.filters},
        "dimensions": set(plan.dimension_ids),
        "group_by": plan.group_by_dimension_ids,
    }
    expected = {
        "status": "no_evidence",
        "domain": case["expected_domain"],
        "metric": case["expected_metric_id"],
        "period": case["expected_period"],
        "filters": filters,
        "dimensions": set(filters),
        "group_by": (),
    }
    return [
        f"{key}: {actual[key]!r} != {expected[key]!r}"
        for key in expected
        if actual[key] != expected[key]
    ]


def _param(case: dict):
    """Lacuna conhecida vira xfail estrito: corrigida, o teste falha até remover known_gap."""

    gap = case.get("known_gap")
    marks = (
        (pytest.mark.xfail(strict=True, raises=AssertionError, reason=gap["reason"]),)
        if gap
        else ()
    )
    return pytest.param(case, id=case["id"], marks=marks)


GAP_CASES = [case for case in CASES if case.get("known_gap")]


@pytest.mark.parametrize("case", [_param(case) for case in CASES])
def test_gold_question_matrix_case(case: dict) -> None:
    response, plans = _ask(case)

    problems = _mismatches(case, response, plans)
    assert not problems, problems


@pytest.mark.parametrize("case", GAP_CASES, ids=[case["id"] for case in GAP_CASES])
def test_known_gap_keeps_its_recorded_current_status(case: dict) -> None:
    """A lacuna não muda de forma em silêncio; mudou, a matriz precisa ser revista."""

    response, plans = _ask(case)

    assert response.status == case["known_gap"]["current_status"], response.message
    if response.status == "needs_clarification":
        assert plans == []


# --- coerência da matriz ------------------------------------------------------------------


def test_matrix_shape_and_coverage() -> None:
    ids = [case["id"] for case in CASES]
    statuses = [case["expected_status"] for case in CASES]
    capability_ids = {requirement.id for requirement in CAPABILITY_REQUIREMENTS}

    assert 35 <= len(CASES) <= 51
    assert len(ids) == len(set(ids))
    assert set(statuses) == {"ready", "needs_clarification"}
    assert statuses.count("needs_clarification") >= statuses.count("ready")
    assert sum(case["group"] == "case_prd_7_6" for case in CASES) == 3
    for case in CASES:
        assert set(case["expected_filters"]) <= set(FILTER_DIMENSIONS), case["id"]
        assert case["rationale"].strip(), case["id"]
        assert case["readiness_capability"] in capability_ids, case["id"]
        if case["expected_status"] == "ready":
            assert case["expected_metric_id"] and case["expected_period"], case["id"]
            assert not case["expected_message_fragments"], case["id"]
        else:
            assert case["expected_metric_id"] is None, case["id"]
            assert case["expected_message_fragments"], case["id"]
    covered_unavailable = {
        case["readiness_capability"]
        for case in CASES
        if case["group"] in {"unavailable_capability", "case_prd_7_6"}
    }
    assert covered_unavailable >= UNAVAILABLE_GROUPS


def test_ready_cases_have_one_physical_source_for_the_expected_capability() -> None:
    for case in CASES:
        if case["expected_status"] != "ready":
            continue
        metric = GRID360_GOLD_MAPPING.metric(case["expected_metric_id"])
        source = select_source(metric, set(_expected_filters(case)), APPROVED)
        assert source is not None, case["id"]
        assert source.capability_id == case["readiness_capability"], case["id"]


def test_filter_values_are_declared_in_the_profile() -> None:
    declared = {
        dimension.id: {value.value for value in dimension.values}
        for dimension in GRID360_GOLD_PROFILE.dimensions
    }
    for case in CASES:
        for dimension_id, (value,) in _expected_filters(case).items():
            assert value in declared[dimension_id], (case["id"], dimension_id)


def test_unavailable_capability_cases_say_the_data_is_not_loaded() -> None:
    for case in CASES:
        if case["readiness_capability"] in UNAVAILABLE and case["group"] != "context":
            assert case["expected_status"] == "needs_clarification", case["id"]
            assert any(
                UNAVAILABLE_MARK in fragment for fragment in case["expected_message_fragments"]
            ), case["id"]


# --- vocabulário do perfil ----------------------------------------------------------------


def test_unavailability_messages_are_specific_honest_and_offer_an_alternative() -> None:
    messages = [
        rule.clarification
        for rule in GRID360_GOLD_PROFILE.ambiguities
        if UNAVAILABLE_MARK in rule.clarification
    ]

    assert len(messages) == len(UNAVAILABLE_GROUPS)
    for message in messages:
        lowered = message.casefold()
        assert "ainda não" in lowered, message
        assert not any(term in lowered for term in ("não existe", "em breve", "prazo")), message
        assert "posso mostrar" in lowered or "quer " in lowered, message


def test_unavailability_rules_are_evaluated_before_the_other_rules() -> None:
    rules = GRID360_GOLD_PROFILE.ambiguities
    unavailable = [
        index for index, rule in enumerate(rules) if UNAVAILABLE_MARK in rule.clarification
    ]

    assert unavailable == list(range(len(unavailable)))


def test_every_metric_alias_reaches_its_metric() -> None:
    """Nenhuma regra de ambiguidade, detalhe ou quebra engole um alias de métrica."""

    interpreter = QuestionInterpreter(profile=GRID360_GOLD_PROFILE)
    for metric in GRID360_GOLD_PROFILE.metrics:
        for alias in metric.aliases:
            result = interpreter.interpret(f"Qual foi o {alias} no mês passado?")
            assert result.status is InterpretationStatus.READY, (alias, result)
            assert result.intent.metric_id == metric.id, alias


@pytest.mark.parametrize(
    "question",
    [
        "Qual foi o consumo no último ano?",
        "Qual foi a receita no último ano?",
        "Qual foi o consumo de energia em Olinda no último ano?",
    ],
)
def test_plain_metric_words_do_not_trigger_unavailability_rules(question: str) -> None:
    result = QuestionInterpreter(profile=GRID360_GOLD_PROFILE).interpret(question)

    assert result.status is InterpretationStatus.READY, result


@pytest.mark.parametrize(
    "phrase",
    ["jaboatão", "jaboatao", "jaboatão dos guararapes", "jaboatao dos guararapes", "JABOATAO"],
)
def test_jaboatao_with_or_without_accent_filters_the_accented_physical_value(phrase: str) -> None:
    response, plans = _ask({"question": f"Qual foi a receita em {phrase} no último ano?"})

    assert response.status == "no_evidence", response.message
    assert [item.values for item in plans[0].filters] == [("JABOATÃO DOS GUARARAPES",)]
