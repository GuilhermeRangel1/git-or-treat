"""Prazo global e limites por etapa, sem depender de modelo ou banco."""

import asyncio

import pytest

from app.services.genai_client import GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan"), True, "35"])
def test_invalid_total_and_stage_limits_are_rejected(seconds):
    with pytest.raises(ValueError):
        GenAIRequestDeadline.start(seconds)
    deadline = GenAIRequestDeadline.start(10, clock=lambda: 100)
    with pytest.raises(ValueError):
        deadline.remaining_seconds(seconds)


def test_three_stages_share_one_deadline_and_never_reset_it():
    now = [100.0]
    deadline = GenAIRequestDeadline.start(10, clock=lambda: now[0])
    assert deadline.remaining_seconds(6) == 6
    now[0] += 2  # planejamento
    assert deadline.remaining_seconds(20) == 8
    now[0] += 3  # consulta
    assert deadline.remaining_seconds(20) == 5
    now[0] += 5  # síntese consome o restante
    with pytest.raises(GenAITimeout):
        deadline.remaining_seconds(20)


def test_sql_timeout_rounds_down_and_never_disables_database_limit():
    now = [100.0]
    deadline = GenAIRequestDeadline.start(1, clock=lambda: now[0])
    assert deadline.sql_timeout_ms(0.25) == 250
    now[0] = 100.9985
    assert deadline.sql_timeout_ms(1) == 1
    now[0] = 100.9995
    with pytest.raises(GenAITimeout):
        deadline.sql_timeout_ms(1)


def test_exhausted_request_does_not_start_next_operation():
    now = [0.0]
    deadline = GenAIRequestDeadline.start(1, clock=lambda: now[0])
    now[0] = 2
    called = []

    async def operation():
        called.append(True)

    with pytest.raises(GenAITimeout):
        asyncio.run(deadline.run(1, operation))
    assert called == []


def test_slow_stage_is_cancelled_and_cannot_start_synthesis_after_total_deadline():
    cancelled = []

    async def scenario():
        now = [0.0]
        deadline = GenAIRequestDeadline.start(0.01, clock=lambda: now[0])

        async def blocked():
            try:
                await asyncio.Future()
            finally:
                cancelled.append(True)
                now[0] = 1

        with pytest.raises(GenAITimeout):
            await deadline.run(1, blocked)
        with pytest.raises(GenAITimeout):
            deadline.remaining_seconds(1)

    asyncio.run(scenario())
    assert cancelled == [True]


def test_stage_limit_cancels_without_consuming_whole_request_budget():
    async def scenario():
        deadline = GenAIRequestDeadline.start(60)
        with pytest.raises(GenAITimeout):
            await deadline.run(0.01, lambda: asyncio.Future())
        assert deadline.remaining_seconds(1) == 1

    asyncio.run(scenario())


def test_external_cancellation_and_operation_errors_keep_their_identity():
    async def scenario():
        deadline = GenAIRequestDeadline.start(10)

        async def fail(error):
            raise error

        for error in (TimeoutError("falha interna"), asyncio.CancelledError(), ValueError()):
            with pytest.raises(type(error)) as captured:
                await deadline.run(1, lambda error=error: fail(error))
            assert captured.value is error

    asyncio.run(scenario())


def test_finished_stage_cannot_publish_after_global_deadline():
    now = [0.0]
    deadline = GenAIRequestDeadline.start(1, clock=lambda: now[0])

    async def operation():
        now[0] = 2
        return "resultado tardio"

    with pytest.raises(GenAITimeout):
        asyncio.run(deadline.run(1, operation))


def test_completed_operation_returns_result_within_budget():
    deadline = GenAIRequestDeadline.start(10)
    assert asyncio.run(deadline.run(1, lambda: asyncio.sleep(0, result="ok"))) == "ok"


def test_operation_cannot_swallow_stage_cancellation_and_return_late_result():
    async def scenario():
        deadline = GenAIRequestDeadline.start(60)

        async def ignores_cancellation():
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                return "resultado tardio"

        with pytest.raises(GenAITimeout):
            await deadline.run(0.01, ignores_cancellation)

    asyncio.run(scenario())
