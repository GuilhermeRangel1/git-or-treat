"""Confirmação de persistência e falha fechada pela composição normal."""

import asyncio
import json

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


def test_failed_durable_ingress_blocks_source_and_model():
    from app.schemas.questions import QuestionRequest
    from tests.test_core_composition import QUESTION, RecordingModel, RecordingSource
    from tests.test_safe_events import _context, _core

    sink = BackendEventSink(URL, "t" * 40, transport=httpx.MockTransport(
        lambda request: httpx.Response(503),
    ))
    source, model = RecordingSource(), RecordingModel()
    result = asyncio.run(_core(source, model, sink, require_durable=True).question.answer(
        QuestionRequest(question=QUESTION), _context(),
    ))
    assert result.status == "recoverable_error"
    assert result.error.code == "service_unavailable"
    assert source.calls == model.calls == 0
