import asyncio

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.interpreter import QuestionInterpreter
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.ports.evidence import EvidenceToolUnavailable
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.analysis import AnalysisIntent
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.tools.synthetic_analytics import SyntheticScenarioTool


class CountingScenarioTool:
    def __init__(self) -> None:
        self.calls: list[AnalysisIntent] = []

    async def retrieve(self, intent: AnalysisIntent, _access_context) -> EvidenceLookupResult:
        self.calls.append(intent)
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Fixture sem correspondência para este teste.",
        )


class InvalidSource:
    def __init__(self, result) -> None:
        self.result = result

    async def retrieve(self, intent: AnalysisIntent, _access_context):
        return self.result


def _prepare(planner: QuestionAnalysisPlanner, question: str):
    return asyncio.run(
        planner.prepare(
            question,
            access_context=demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
        )
    )


def _policy() -> ReadAccessPolicy:
    return ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID)


def test_ambiguous_question_is_clarified_before_any_tool_is_called() -> None:
    tool = CountingScenarioTool()
    planner = QuestionAnalysisPlanner(QuestionInterpreter(GRID360_DEMO_PROFILE), tool, _policy())

    plan = _prepare(planner, "Minha conta de luz subiu?")

    assert plan.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
    assert plan.evidence_result is None
    assert tool.calls == []


def test_corrected_filter_is_the_only_filter_sent_to_the_tool() -> None:
    tool = CountingScenarioTool()
    planner = QuestionAnalysisPlanner(QuestionInterpreter(GRID360_DEMO_PROFILE), tool, _policy())

    plan = _prepare(
        planner, "Qual foi a receita em Olinda, não, em Jaboatão no período de demonstração?"
    )

    assert plan.status is AnalysisPlanStatus.NO_EVIDENCE
    assert plan.interpretation.intent is not None
    assert plan.interpretation.intent.geography_phrase == "Jaboatão"
    assert len(tool.calls) == 1
    assert tool.calls[0].filters[0].dimension_id == "geography.municipality"
    assert tool.calls[0].filters[0].values == ("Jaboatão dos Guararapes",)


def test_planner_accepts_an_evidence_source_without_synthetic_request_types() -> None:
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE), SyntheticScenarioTool(), _policy()
    )

    plan = _prepare(planner, "Qual foi o consumo no período de demonstração?")

    assert plan.status is AnalysisPlanStatus.READY
    assert plan.evidence_result is not None
    assert plan.evidence_result.evidence is not None
    assert plan.evidence_result.evidence.reference.is_demo is True


def test_explicit_demo_question_reaches_synthetic_tool_and_returns_evidence() -> None:
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE), SyntheticScenarioTool(), _policy()
    )

    plan = _prepare(planner, "Qual foi o consumo no período de demonstração?")

    assert plan.status is AnalysisPlanStatus.READY
    assert plan.evidence_result is not None
    assert plan.evidence_result.evidence is not None
    assert plan.evidence_result.evidence.records == [
        {"observation_id": "row_1", "value": 420, "unit": "unidades fictícias"}
    ]


@pytest.mark.parametrize("invalid_result", [None, object(), {"status": "unknown"}])
def test_planner_rejects_invalid_source_return_as_controlled_failure(invalid_result) -> None:
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE), InvalidSource(invalid_result), _policy()
    )

    with pytest.raises(EvidenceToolUnavailable):
        _prepare(planner, "Qual foi o consumo no período de demonstração?")


def test_planner_revalidates_constructed_source_result_before_using_it() -> None:
    invalid = EvidenceLookupResult.model_construct(
        status=EvidenceLookupStatus.AVAILABLE,
        evidence=None,
    )
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE), InvalidSource(invalid), _policy()
    )

    with pytest.raises(EvidenceToolUnavailable):
        _prepare(planner, "Qual foi o consumo no período de demonstração?")


def test_unknown_filter_is_a_clarification_not_an_empty_result() -> None:
    class ClarifyingSource:
        async def retrieve(self, intent: AnalysisIntent, _access_context) -> EvidenceLookupResult:
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                message="O filtro solicitado não está disponível neste catálogo.",
            )

    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE), ClarifyingSource(), _policy()
    )
    plan = _prepare(planner, "Qual foi o consumo no período de demonstração?")

    assert plan.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
    assert plan.evidence_result is not None
    assert plan.evidence_result.status is EvidenceLookupStatus.NEEDS_CLARIFICATION
    assert plan.evidence_result.evidence is None


def test_async_source_can_process_concurrent_lookups() -> None:
    class ConcurrentSource:
        def __init__(self) -> None:
            self.started = 0
            self.active = 0
            self.max_active = 0
            self.both_started = asyncio.Event()
            self.release = asyncio.Event()

        async def retrieve(self, intent: AnalysisIntent, _access_context) -> EvidenceLookupResult:
            self.started += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.started == 2:
                self.both_started.set()
            try:
                await self.release.wait()
                return EvidenceLookupResult(
                    status=EvidenceLookupStatus.NO_EVIDENCE,
                    message="Sem registros no cenário de concorrência.",
                )
            finally:
                self.active -= 1

    async def run() -> list:
        source = ConcurrentSource()
        planner = QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE), source, _policy()
        )
        first = asyncio.create_task(
            planner.prepare(
                "Qual foi o consumo no período de demonstração?",
                access_context=demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
            )
        )
        second = asyncio.create_task(
            planner.prepare(
                "Qual foi a receita no período de demonstração?",
                access_context=demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
            )
        )
        await asyncio.wait_for(source.both_started.wait(), timeout=1)
        source.release.set()
        plans = await asyncio.gather(first, second)
        assert source.max_active == 2
        return plans

    assert len(asyncio.run(run())) == 2


def test_cancelling_planner_cancels_async_source_lookup() -> None:
    class CancellableSource:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.cancelled = False

        async def retrieve(self, intent: AnalysisIntent, _access_context) -> EvidenceLookupResult:
            self.started.set()
            try:
                await asyncio.Future()
            finally:
                self.cancelled = True

    async def run() -> bool:
        source = CancellableSource()
        planner = QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE), source, _policy()
        )
        task = asyncio.create_task(
            planner.prepare(
                "Qual foi o consumo no período de demonstração?",
                access_context=demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
            )
        )
        await source.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return source.cancelled

    assert asyncio.run(run()) is True
