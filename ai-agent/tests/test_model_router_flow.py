"""Roteador de níveis de modelo ligado ao fluxo de perguntas pelo QuestionOrchestrator."""

import asyncio
import json
from dataclasses import asdict, replace

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.ports.events import CoreEvent, EventCode, EventStage
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.fallback import FallbackModelAdapter
from app.providers.protocols import (
    GeneratedAnswer,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.providers.routing import ModelRouter, ModelTier, RoutingPolicy
from app.schemas.questions import QuestionRequest, QuestionStatus
from app.schemas.responses import FailureCode, map_failure
from app.tools.synthetic_analytics import SyntheticScenarioTool

# O perfil Grid 360 classifica esta pergunta no domínio "consumption", com uma observação.
QUESTION = "Qual foi o consumo no período de demonstração?"
CORRELATION_ID = "0" * 32
LIGHT_TEXT = "texto do modelo leve"
STRONG_TEXT = "texto do modelo forte"
LIGHT_POLICY = RoutingPolicy(light_intents={"consumption"})


def _grounded(text: str) -> GeneratedAnswer:
    return GeneratedAnswer(status="answered", answer=text, observation_ids=("row_1",))


def _ungrounded(text: str) -> GeneratedAnswer:
    return GeneratedAnswer(status="answered", answer=text, observation_ids=("row_999",))


class ScriptedModel:
    """Devolve sempre o mesmo resultado, levanta a exceção configurada e conta chamadas."""

    def __init__(self, outcome: GeneratedAnswer | Exception) -> None:
        self.outcome = outcome
        self.calls = 0
        self.evidence = []

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        self.calls += 1
        self.evidence.append(evidence)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class RecordingSink:
    durable = False

    def __init__(self) -> None:
        self.events: list[CoreEvent] = []

    def record(self, event: CoreEvent) -> None:
        self.events.append(event)


def _router(light, strong, policy: RoutingPolicy = LIGHT_POLICY) -> ModelRouter:
    adapters = {ModelTier.STRONG: strong}
    if light is not None:
        adapters[ModelTier.LIGHT] = light
    return ModelRouter(adapters, policy)


def _orchestrator(
    router: ModelRouter,
    *,
    max_model_calls: int = 2,
    sink: RecordingSink | None = None,
) -> QuestionOrchestrator:
    return QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            SyntheticScenarioTool(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        execution_controller=ExecutionController(
            ExecutionLimits(max_model_calls=max_model_calls)
        ),
        event_sink=sink,
        model_router=router,
    )


def _ask(orchestrator: QuestionOrchestrator):
    return asyncio.run(
        orchestrator.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID),
        )
    )


def _evidence_chars() -> int:
    """Mede a evidência que o modelo recebe para esta pergunta, como os adaptadores a enviam."""

    strong = ScriptedModel(_grounded(STRONG_TEXT))
    _ask(_orchestrator(_router(None, strong)))
    (evidence,) = strong.evidence
    return len(json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False))


# Escolha do nível


def test_empty_light_intents_sends_everything_to_strong() -> None:
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(light, strong, RoutingPolicy())))

    assert response.status is QuestionStatus.ANSWERED
    assert (light.calls, strong.calls) == (0, 1)


def test_light_intent_with_small_evidence_uses_only_light() -> None:
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(light, strong)))

    assert response.status is QuestionStatus.ANSWERED
    assert response.model_tier == "light"
    assert (light.calls, strong.calls) == (1, 0)


@pytest.mark.parametrize(
    "limits",
    [{"max_light_evidence_records": 0}, {"max_light_evidence_chars": 10}],
    ids=["records", "chars"],
)
def test_evidence_above_light_limits_goes_to_strong(limits) -> None:
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))
    policy = RoutingPolicy(light_intents={"consumption"}, **limits)

    response = _ask(_orchestrator(_router(light, strong, policy)))

    assert response.status is QuestionStatus.ANSWERED
    assert (light.calls, strong.calls) == (0, 1)


def test_char_limit_uses_size_of_serialized_evidence_sent_to_model() -> None:
    chars = _evidence_chars()
    results = []
    for limit in (chars, chars - 1):
        light = ScriptedModel(_grounded(LIGHT_TEXT))
        strong = ScriptedModel(_grounded(STRONG_TEXT))
        policy = RoutingPolicy(light_intents={"consumption"}, max_light_evidence_chars=limit)
        _ask(_orchestrator(_router(light, strong, policy)))
        results.append((light.calls, strong.calls))

    assert results == [(1, 0), (0, 1)]


def test_other_intent_in_policy_does_not_route_this_question_to_light() -> None:
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))
    policy = RoutingPolicy(light_intents={"revenue"})

    _ask(_orchestrator(_router(light, strong, policy)))

    assert (light.calls, strong.calls) == (0, 1)


def test_router_without_light_sends_everything_to_strong() -> None:
    strong = ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(None, strong), max_model_calls=1))

    assert response.status is QuestionStatus.ANSWERED
    assert strong.calls == 1


# Escalada


def test_ungrounded_light_output_escalates_once_to_strong() -> None:
    light = ScriptedModel(_ungrounded(LIGHT_TEXT))
    strong = ScriptedModel(
        GeneratedAnswer(status="refused", answer=STRONG_TEXT, observation_ids=())
    )

    response = _ask(_orchestrator(_router(light, strong)))

    # A resposta final é a do forte: aqui ele recusa, então não há resposta do leve.
    assert (light.calls, strong.calls) == (1, 1)
    assert response.status is QuestionStatus.REFUSED
    assert response.error == map_failure(FailureCode.POLICY_REFUSAL).error


def test_escalated_strong_answer_is_published() -> None:
    light = ScriptedModel(_ungrounded(LIGHT_TEXT))
    strong = ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(light, strong)))

    assert (light.calls, strong.calls) == (1, 1)
    assert response.status is QuestionStatus.ANSWERED
    assert response.model_tier == "strong"
    assert response.error is None


@pytest.mark.parametrize(
    "observation_ids",
    [(), ("row_1", "row_1"), ("row_999",)],
    ids=["empty", "repeated", "unknown"],
)
def test_light_and_strong_ungrounded_is_refused(observation_ids) -> None:
    output = GeneratedAnswer(status="answered", answer="sem base", observation_ids=observation_ids)
    light, strong = ScriptedModel(output), ScriptedModel(output)

    response = _ask(_orchestrator(_router(light, strong)))

    assert (light.calls, strong.calls) == (1, 1)
    assert response.status is QuestionStatus.REFUSED
    assert response.error == map_failure(FailureCode.UNGROUNDED_OUTPUT).error


def test_ungrounded_strong_without_escalation_path_is_refused() -> None:
    strong = ScriptedModel(_ungrounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(None, strong)))

    assert strong.calls == 1
    assert response.error == map_failure(FailureCode.UNGROUNDED_OUTPUT).error


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (ModelProviderUnavailable("indisponível"), FailureCode.MODEL_UNAVAILABLE),
        (ModelProviderRejected("negado"), FailureCode.MODEL_REJECTED),
        (ModelProviderInvalidResponse("inválida"), FailureCode.INVALID_MODEL_OUTPUT),
    ],
)
def test_light_provider_errors_do_not_escalate(failure, code) -> None:
    light, strong = ScriptedModel(failure), ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(light, strong)))

    assert (light.calls, strong.calls) == (1, 0)
    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error == map_failure(code).error


def test_strong_error_during_escalation_keeps_its_own_handling() -> None:
    light = ScriptedModel(_ungrounded(LIGHT_TEXT))
    strong = ScriptedModel(ModelProviderUnavailable("indisponível"))

    response = _ask(_orchestrator(_router(light, strong)))

    assert (light.calls, strong.calls) == (1, 1)
    assert response.error == map_failure(FailureCode.MODEL_UNAVAILABLE).error


# Orçamento


def test_construction_rejects_light_plus_strong_above_model_max_calls() -> None:
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))

    with pytest.raises(ValueError, match="limite de chamadas"):
        _orchestrator(_router(light, strong), max_model_calls=1)


def test_construction_counts_fallback_chains_of_both_tiers() -> None:
    light = FallbackModelAdapter([ScriptedModel(_grounded("a")), ScriptedModel(_grounded("b"))])
    strong = ScriptedModel(_grounded(STRONG_TEXT))

    with pytest.raises(ValueError, match="limite de chamadas"):
        _orchestrator(_router(light, strong), max_model_calls=2)
    assert _orchestrator(_router(light, strong), max_model_calls=3)


def test_escalation_is_counted_by_the_request_budget() -> None:
    light = ScriptedModel(_ungrounded(LIGHT_TEXT))
    strong = ScriptedModel(_grounded(STRONG_TEXT))
    orchestrator = _orchestrator(_router(light, strong), max_model_calls=2)
    # Reduz o limite depois da construção para forçar o estouro durante a escalada.
    controller = orchestrator._execution
    controller.limits = replace(controller.limits, max_model_calls=1)

    response = _ask(orchestrator)

    assert (light.calls, strong.calls) == (1, 0)
    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error == map_failure(FailureCode.EXECUTION_LIMIT).error


def test_orchestrator_requires_exactly_one_model_source() -> None:
    strong = ScriptedModel(_grounded(STRONG_TEXT))
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE),
        SyntheticScenarioTool(),
        ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
    )

    with pytest.raises(ValueError, match="exatamente um"):
        QuestionOrchestrator(planner)
    with pytest.raises(ValueError, match="exatamente um"):
        QuestionOrchestrator(planner, strong, model_router=_router(None, strong))


# Eventos


def test_escalation_emits_distinct_safe_event_and_counts_model_calls() -> None:
    sink = RecordingSink()
    light = ScriptedModel(_ungrounded(LIGHT_TEXT))
    strong = ScriptedModel(_grounded(STRONG_TEXT))

    response = _ask(_orchestrator(_router(light, strong), sink=sink))

    model_events = [
        (event.code, event.model_calls) for event in sink.events if event.stage is EventStage.MODEL
    ]
    assert model_events == [
        (EventCode.STARTED, 1),
        (EventCode.COMPLETED, 1),
        (EventCode.ESCALATED, 2),
        (EventCode.COMPLETED, 2),
    ]
    assert sink.events[-1].model_calls == 2
    serialized = json.dumps([asdict(event) for event in sink.events], default=str)
    evidence = light.evidence[0]
    for private in (
        QUESTION,
        LIGHT_TEXT,
        STRONG_TEXT,
        "row_1",
        "row_999",
        evidence.records[0]["unit"],
        evidence.reference.source,
    ):
        assert private not in serialized
    assert response.status is QuestionStatus.ANSWERED


def test_no_escalation_event_when_light_output_is_grounded() -> None:
    sink = RecordingSink()
    light, strong = ScriptedModel(_grounded(LIGHT_TEXT)), ScriptedModel(_grounded(STRONG_TEXT))

    _ask(_orchestrator(_router(light, strong), sink=sink))

    assert all(event.code is not EventCode.ESCALATED for event in sink.events)
    assert sink.events[-1].model_calls == 1
