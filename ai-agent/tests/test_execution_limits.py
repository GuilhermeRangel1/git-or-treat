"""Limites são aplicados a trabalho real, inclusive espera e cancelamento."""

import asyncio

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController, ExecutionLimitExceeded, ExecutionLimits
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.ports.evidence import EvidenceContractInvalid
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.questions import QuestionRequest, QuestionStatus
from app.tools.synthetic_analytics import SyntheticScenarioTool

QUESTION = "Qual foi o consumo no período de demonstração?"


def _limits(**overrides) -> ExecutionLimits:
    values = {
        "request_seconds": 1,
        "source_seconds": 1,
        "model_seconds": 1,
        "max_source_calls": 1,
        "max_model_calls": 1,
        "concurrent_requests": 4,
        "concurrent_sources": 1,
        "concurrent_models": 1,
    }
    return ExecutionLimits(**(values | overrides))


def test_source_timeout_cancels_work_and_releases_slot() -> None:
    async def run() -> bool:
        controller = ExecutionController(_limits(source_seconds=0.02))
        cancelled = False

        async def slow() -> None:
            nonlocal cancelled
            try:
                await asyncio.Event().wait()
            finally:
                cancelled = True

        with pytest.raises(ExecutionLimitExceeded):
            await controller.run(lambda budget: budget.source(slow))
        result = await controller.run(
            lambda budget: budget.source(lambda: asyncio.sleep(0, result=7))
        )
        return cancelled and result == 7

    assert asyncio.run(run())


def test_total_deadline_includes_wait_for_busy_source() -> None:
    async def run() -> None:
        controller = ExecutionController(
            _limits(request_seconds=0.03, source_seconds=1)
        )
        entered = asyncio.Event()
        release = asyncio.Event()

        async def holding() -> None:
            async with controller._sources:
                entered.set()
                await release.wait()

        first = asyncio.create_task(holding())
        await entered.wait()
        attempted = False

        async def waiting() -> int:
            nonlocal attempted
            attempted = True
            return 2

        with pytest.raises(ExecutionLimitExceeded):
            await controller.run(lambda budget: budget.source(waiting))
        assert not attempted
        release.set()
        await first

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["source", "model"])
def test_simultaneous_requests_respect_dependency_limit(stage: str) -> None:
    async def run() -> int:
        controller = ExecutionController(_limits())
        release = asyncio.Event()
        first_entered = asyncio.Event()
        active = peak = 0

        async def work() -> None:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            first_entered.set()
            try:
                await release.wait()
            finally:
                active -= 1

        first = asyncio.create_task(
            controller.run(lambda budget: getattr(budget, stage)(work))
        )
        await first_entered.wait()
        second = asyncio.create_task(
            controller.run(lambda budget: getattr(budget, stage)(work))
        )
        await asyncio.sleep(0)
        assert active == 1
        release.set()
        await asyncio.gather(first, second)
        return peak

    assert asyncio.run(run()) == 1


def test_request_concurrency_limit_queues_second_request() -> None:
    async def run() -> bool:
        controller = ExecutionController(_limits(concurrent_requests=1))
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release = asyncio.Event()

        async def first_action(budget) -> int:
            first_started.set()
            await release.wait()
            return 1

        async def second_action(budget) -> int:
            second_started.set()
            return 2

        first = asyncio.create_task(controller.run(first_action))
        await first_started.wait()
        second = asyncio.create_task(controller.run(second_action))
        await asyncio.sleep(0)
        assert not second_started.is_set()
        release.set()
        return await first == 1 and await second == 2 and second_started.is_set()

    assert asyncio.run(run())


def test_external_cancellation_releases_model_slot() -> None:
    async def run() -> bool:
        controller = ExecutionController(_limits())
        started = asyncio.Event()
        cancelled = False

        async def slow() -> None:
            nonlocal cancelled
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled = True

        task = asyncio.create_task(controller.run(lambda budget: budget.model(slow)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        result = await controller.run(
            lambda budget: budget.model(lambda: asyncio.sleep(0, result=3))
        )
        return cancelled and result == 3

    assert asyncio.run(run())


def test_call_counts_stop_before_extra_source_or_model_call() -> None:
    async def run() -> tuple[int, int]:
        controller = ExecutionController(_limits())
        source_calls = model_calls = 0

        async def action(budget) -> None:
            nonlocal source_calls, model_calls

            async def source() -> None:
                nonlocal source_calls
                source_calls += 1

            async def model() -> None:
                nonlocal model_calls
                model_calls += 1

            await budget.source(source)
            await budget.model(model)
            with pytest.raises(ExecutionLimitExceeded):
                await budget.source(source)
            with pytest.raises(ExecutionLimitExceeded):
                await budget.model(model)

        await controller.run(action)
        return source_calls, model_calls

    assert asyncio.run(run()) == (1, 1)


def test_configured_row_and_byte_limits_reach_plan_and_evidence_guard() -> None:
    class CapturingSource(SyntheticScenarioTool):
        plan = None

        async def retrieve(self, plan, access_context):
            self.plan = plan
            return await super().retrieve(plan, access_context)

    source = CapturingSource()
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(GRID360_DEMO_PROFILE),
        source,
        ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        max_rows=1,
        max_evidence_bytes=1,
    )
    with pytest.raises(EvidenceContractInvalid):
        asyncio.run(
            planner.prepare(
                QUESTION,
                access_context=demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
            )
        )
    assert source.plan.limit == 1


@pytest.mark.parametrize("slow_stage", ["source", "model"])
def test_question_flow_times_out_without_late_work(slow_stage: str) -> None:
    class SlowSource:
        cancelled = False

        async def retrieve(self, plan, _access_context):
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True

    class SlowModel:
        calls = 0
        cancelled = False

        async def generate(self, question, context, evidence):
            self.calls += 1
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True

    source = SlowSource() if slow_stage == "source" else SyntheticScenarioTool()
    model = SlowModel()
    controller = ExecutionController(
        _limits(source_seconds=0.02, model_seconds=0.02)
    )
    orchestrator = QuestionOrchestrator(
        QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            source,
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model,
        execution_controller=controller,
    )
    response = asyncio.run(
        orchestrator.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
        )
    )
    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error.code == "limit_exceeded"
    if slow_stage == "source":
        assert source.cancelled and model.calls == 0
    else:
        assert model.cancelled and model.calls == 1
