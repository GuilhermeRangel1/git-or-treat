"""Confirmação de persistência e falha fechada pela composição normal."""

import asyncio
import json
from threading import Event, get_ident

import httpx
import pytest

from app.audit import BackendEventSink
from app.ports.events import AuditUnavailable, CoreEvent, EventCode, EventOutcome, EventStage

URL = "http://backend/api/v1/internal/genai-audit-events"


def test_backend_sink_requires_committed_reference_and_sends_only_event_contract():
    received = []

    def committed(request):
        received.append(json.loads(request.content))
        assert request.headers["X-Correlation-ID"] == "a" * 32
        return httpx.Response(201, json={"audit_reference": "b" * 32})

    event = CoreEvent("question", EventStage.REQUEST, EventCode.STARTED,
                      EventOutcome.STARTED, "a" * 32, 0)
    sink = BackendEventSink(URL, "t" * 40, transport=httpx.MockTransport(committed))
    sink.record(event)
    assert received[0]["stage"] == "request"
    assert "question" not in received[0]
    for status, payload in ((200, {}), (503, {}), (201, {"audit_reference": "segredo"})):
        sink = BackendEventSink(URL, "t" * 40, transport=httpx.MockTransport(
            lambda request, status=status, payload=payload: httpx.Response(status, json=payload),
        ))
        with pytest.raises(AuditUnavailable, match="Auditoria indisponível"):
            sink.record(event)


@pytest.mark.parametrize("stage,source_calls,model_calls", [
    ("request", 0, 0), ("plan", 0, 0), ("source", 0, 0),
    ("model", 1, 0), ("response", 1, 1),
])
def test_failed_durable_ingress_blocks_source_and_model(stage, source_calls, model_calls):
    from app.schemas.questions import QuestionRequest
    from tests.test_core_composition import QUESTION, RecordingModel, RecordingSource
    from tests.test_safe_events import _context, _core

    def ingress(request):
        if json.loads(request.content)["stage"] == stage:
            return httpx.Response(503)
        return httpx.Response(201, json={"audit_reference": "b" * 32})

    sink = BackendEventSink(URL, "t" * 40, transport=httpx.MockTransport(ingress))
    source, model = RecordingSource(), RecordingModel()
    result = asyncio.run(_core(source, model, sink, require_durable=True).question.answer(
        QuestionRequest(question=QUESTION), _context(),
    ))
    assert result.status == "recoverable_error"
    assert result.error.code == "service_unavailable"
    assert (source.calls, model.calls) == (source_calls, model_calls)


@pytest.mark.parametrize("stage,source_calls,model_calls", [
    ("request", 0, 0), ("plan", 0, 0), ("source", 0, 0),
    ("model", 1, 0), ("response", 1, 1),
])
def test_slow_durable_ingress_keeps_loop_free_and_waits_for_confirmation(
    stage, source_calls, model_calls,
):
    from app.schemas.questions import QuestionRequest
    from tests.test_core_composition import QUESTION, RecordingModel, RecordingSource
    from tests.test_safe_events import _context, _core

    async def run():
        entered, release = Event(), Event()
        loop_thread = get_ident()
        source, model = RecordingSource(), RecordingModel()

        def ingress(request):
            assert get_ident() != loop_thread
            if json.loads(request.content)["stage"] == stage and not entered.is_set():
                entered.set()
                if not release.wait(2):
                    raise AssertionError("O loop não liberou a confirmação da auditoria.")
            return httpx.Response(201, json={"audit_reference": "b" * 32})

        sink = BackendEventSink(URL, "t" * 40, transport=httpx.MockTransport(ingress))
        task = asyncio.create_task(_core(
            source, model, sink, require_durable=True,
        ).question.answer(QuestionRequest(question=QUESTION), _context()))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            await asyncio.sleep(0)
            assert not task.done()
            assert (source.calls, model.calls) == (source_calls, model_calls)
        finally:
            release.set()
        result = await asyncio.wait_for(task, 2)
        assert result.status == "answered"

    asyncio.run(run())
