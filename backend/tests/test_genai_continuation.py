"""A referência de contexto nunca concede acesso ou mistura sessões."""

from datetime import date

import pytest
from app.schemas.ai import AIConversationTurn
from app.schemas.genai_internal import AccessScope
from app.schemas.genai_plan import LogicalReadPlan, ReadFilter, ReadWindow
from app.services.genai_continuation import (
    InvalidContinuation,
    canonical_question,
    issue_continuation,
    restore_continuation,
)
from pydantic import SecretStr

from tests.test_genai_invalidation import SCOPE as ROUTE_SCOPE
from tests.test_genai_invalidation import gold_route  # noqa: F401 -- fixture pytest compartilhada

SECRET = "local-test-key-" * 4
SCOPE = AccessScope(
    caller_ref="user.test",
    profile_id="v-energy-grid-360-gold",
    source_id="gold.local",
    allowed_operations={"read"},
    allowed_metric_ids={"billing.revenue"},
    allowed_dimension_ids={"geography.municipality"},
)


def plan():
    return LogicalReadPlan(
        operation="read",
        catalog_version="v1",
        profile_id=SCOPE.profile_id,
        source_id=SCOPE.source_id,
        domain_id="revenue",
        metric_id="billing.revenue",
        dimension_ids=("geography.municipality",),
        unit="R$",
        limit=100,
        window=ReadWindow(
            kind="bounded",
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
            granularity="month",
        ),
        filters=(
            ReadFilter(
                dimension_id="geography.municipality", operator="eq", values=("RECIFE",)
            ),
        ),
    )


def test_context_contains_only_normalized_query_and_survives_roundtrip():
    token = issue_continuation(
        plan(), SCOPE, "batch-v2", session="one", conversation="chat", secret=SECRET
    )
    batch, context = restore_continuation(
        token, SCOPE, session="one", conversation="chat", secret=SECRET, context=[]
    )
    assert batch == "batch-v2"
    assert (
        context[0].content
        == "Qual foi receita faturada no município RECIFE em 2026-06?"
    )
    assert context[0].role == "user"


@pytest.mark.parametrize(
    "change", ["session", "conversation", "scope", "signature", "expired", "catalog"]
)
def test_changed_authority_or_context_rejects_token(monkeypatch, change):
    token = issue_continuation(
        plan(), SCOPE, "batch-v2", session="one", conversation="chat", secret=SECRET
    )
    session, conversation, scope = "one", "chat", SCOPE
    if change == "session":
        session = "two"
    elif change == "conversation":
        conversation = "another"
    elif change == "scope":
        scope = SCOPE.model_copy(update={"allowed_metric_ids": frozenset()})
    elif change == "signature":
        token = token[:-1] + ("a" if token[-1] != "a" else "b")
    elif change == "expired":
        monkeypatch.setattr("app.services.genai_continuation.time.time", lambda: 10**12)
    elif change == "catalog":
        monkeypatch.setattr(
            "app.services.genai_continuation._catalog_digest", lambda: "changed"
        )
    with pytest.raises(InvalidContinuation):
        restore_continuation(
            token,
            scope,
            session=session,
            conversation=conversation,
            secret=SECRET,
            context=[],
        )


def test_unrepresentable_filter_never_silently_disappears():
    sensitive = plan().model_copy(
        update={
            "filters": (
                ReadFilter(
                    dimension_id="customer.consumer_unit",
                    operator="eq",
                    values=("test-unit",),
                ),
            )
        }
    )
    assert canonical_question(sensitive) is None


def test_successful_short_turn_uses_normalized_anchor_and_pending_question_remains_available():
    token = issue_continuation(
        plan(),
        SCOPE,
        "batch",
        session="one",
        conversation="chat",
        secret=SECRET,
        response_text="Receita observada no recorte.",
    )
    recent = [
        AIConversationTurn(role="user", content="Na verdade, junho."),
        AIConversationTurn(role="assistant", content="Receita observada no recorte."),
    ]
    _, context = restore_continuation(
        token, SCOPE, session="one", conversation="chat", secret=SECRET, context=recent
    )
    assert len(context) == 1
    assert "2026-06" in context[0].content
    pending = [
        AIConversationTurn(role="user", content="E o consumo?"),
        AIConversationTurn(role="assistant", content="Qual período?"),
    ]
    _, context = restore_continuation(
        token, SCOPE, session="one", conversation="chat", secret=SECRET, context=pending
    )
    assert context[-2:] == pending


@pytest.mark.parametrize("invalid", [False, True])
def test_public_route_restores_only_valid_reference_before_coordination(
    request, monkeypatch, invalid
):
    from app.api.v1.endpoints import ai

    client, calls = request.getfixturevalue("gold_route")
    monkeypatch.setattr(ai.settings, "AI_AGENT_SERVICE_API_TOKEN", SecretStr(SECRET))
    client.cookies.set("grid360_session", "local-session")
    conversation = "00000000-0000-0000-0000-000000000000"
    token = issue_continuation(
        plan(),
        ROUTE_SCOPE,
        "batch",
        session="local-session",
        conversation=conversation,
        secret=SECRET,
    )
    if invalid:
        conversation = "11111111-1111-1111-1111-111111111111"
    response = client.post(
        "/api/v1/ai/questions",
        json={
            "question": "E em Olinda?",
            "conversation_id": conversation,
            "continuation_token": token,
        },
    )
    if invalid:
        assert response.status_code == 409
        assert calls == []
        assert token not in response.text
    else:
        assert response.status_code == 200
        forwarded, kwargs = calls[0]
        assert forwarded.context[0].content == canonical_question(plan())
        assert kwargs["expected_batch_ref"] == "batch"
        assert kwargs["request_deadline"] is not None
        assert "continuation_token" not in forwarded.model_dump()
