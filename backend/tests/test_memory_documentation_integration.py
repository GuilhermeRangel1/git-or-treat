"""Retomada documental atravessa histórico, coordenação e núcleo em outro processo."""
# ruff: noqa: F811 -- fixtures pytest compartilhadas.

from uuid import uuid4

import httpx
from app.api.v1.endpoints import ai_conversations as routes
from app.schemas.ai import AIQuestionRequest
from app.services.ai_conversations import ConversationStore
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_coordination import answer_gold_question

from tests.support.genai_transport import GENAI_TRANSPORT_EVENTS, dispatch_genai
from tests.test_ai_history_http import ORIGIN, client, create  # noqa: F401
from tests.test_ai_history_store import storage  # noqa: F401
from tests.test_conversation_memory import BATCH, remember
from tests.test_conversation_memory_http import memory_client  # noqa: F401
from tests.test_genai_continuation import SCOPE
from tests.test_genai_documentation import envelope
from tests.test_genai_planning_metadata import gold_v2_database  # noqa: F401


def test_document_recall_uses_current_composed_service_without_old_answer(
    memory_client, gold_v2_database, monkeypatch,
):
    web, db, calls = memory_client
    conversation = create(web)
    owner = ConversationStore(db, "one")
    remember(owner, conversation, "Receita em Recife em janeiro de 2025?", routes.history_scope(SCOPE))
    question = "Receita faturada é o valor pago?"
    events = []

    class Audit:
        def record(self, event, **_):
            events.append(event)
            return "document-recall-audit"

    async def answer(payload, request, *_):
        calls.append(payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch_genai)) as transport:
            client = GenAIQuestionClient(
                http_client=transport, base_url="http://genai",
                service_token="test-coordination-service-token-0000000000",
            )
            return await answer_gold_question(
                gold_v2_database, client, AIQuestionRequest(
                    question=payload.question, context=payload.context,
                ), resolve_scope=lambda: SCOPE,
                correlation_id=request.state.correlation_id, audit_store=Audit(),
            )

    monkeypatch.setattr(routes, "ask_genai_question", answer)
    GENAI_TRANSPORT_EVENTS.clear()
    for text in [question, "Retome a consulta 2", "Retome a consulta 3"]:
        result = web.post(f"/api/v1/ai/conversations/{conversation}/questions",
            json={"request_id": str(uuid4()), "question": text}, headers=ORIGIN)
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["answer"] == envelope().response.answer
        assert body["audit_reference"] == "document-recall-audit"
        assert body.get("analysis_context") is None and body.get("continuation_token") is None
        assert calls[-1].question == question and calls[-1].context == []
        if text != question:
            assert calls[-1].continuation_token is None
    assert len(events) == 6  # início e término de cada uma das três execuções.
    assert len({event.correlation_id for event in events}) == 3
    assert len(GENAI_TRANSPORT_EVENTS) == 3
    assert all(event["path"].endswith("question-plans") for event in GENAI_TRANSPORT_EVENTS)
    # A consulta numérica inicial continua recuperável por posição, com seu lote.
    restored = owner.memory(conversation, routes.history_scope(SCOPE), routes.memory_request(
        "Retome a primeira consulta"))
    assert restored.kind == "gold" and restored.batch == BATCH
