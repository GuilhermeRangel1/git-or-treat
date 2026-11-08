"""Continuidade F1 autenticada e isolada da execução/candidato SQL."""

import base64
import json

import pytest
from app.schemas.ai import AIConversationTurn
from app.schemas.genai_internal import AccessScope
from app.services.genai_sql_continuation import (
    InvalidSqlContinuation,
    issue_sql_continuation,
    restore_sql_continuation,
)

SECRET = "test-only-continuation-secret-0123456789"
SESSION = "opaque-browser-session"
CONVERSATION = "8abf4322-17ab-4a75-98f1-29481ee9f456"
BATCH = "gold-csv-v2:batch-42"
SCOPE = AccessScope(
    caller_ref="session:" + "a" * 64,
    profile_id="v-energy-grid-360-gold",
    source_id="gold.local",
    allowed_operations={"read"},
    allowed_metric_ids={"billing.revenue"},
    allowed_dimension_ids={"geography.municipality", "customer.consumption_class"},
)


def issue(**overrides):
    values = {
        "question": "Faturamento de Recife em junho de 2026",
        "response": "O faturamento foi R$ 123,45.",
        "previous_context": (),
        "scope": SCOPE,
        "batch_ref": BATCH,
        "session": SESSION,
        "conversation_id": CONVERSATION,
        "secret": SECRET,
        "now": 1000,
    }
    values.update(overrides)
    return issue_sql_continuation(**values)


def restore(token, **overrides):
    values = {
        "scope": SCOPE,
        "batch_ref": BATCH,
        "session": SESSION,
        "conversation_id": CONVERSATION,
        "secret": SECRET,
        "now": 1001,
    }
    values.update(overrides)
    return restore_sql_continuation(token, **values)


def test_signed_context_preserves_followup_and_only_bounded_visible_turns():
    previous = (
        AIConversationTurn(role="user", content="Faturamento por município em 2025"),
        AIConversationTurn(role="assistant", content="Recife ficou em primeiro."),
    )
    token = issue(previous_context=previous, question="E no ano anterior?")

    restored = restore(token)

    assert [(turn.role, turn.content) for turn in restored] == [
        ("assistant", "Recife ficou em primeiro."),
        ("user", "E no ano anterior?"),
        ("assistant", "O faturamento foi R$ 123,45."),
    ]
    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[0]))
    assert not {"sql", "parameters", "rows", "evidence"} & payload.keys()


@pytest.mark.parametrize(
    "changes",
    [
        {"session": "different-session"},
        {"conversation_id": "00000000-0000-0000-0000-000000000001"},
        {"batch_ref": "gold-csv-v2:batch-43"},
        {"scope": SCOPE.model_copy(update={"allowed_metric_ids": frozenset()})},
        {"secret": "different-secret"},
        {"now": 2801},
    ],
)
def test_rejects_context_when_identity_policy_publication_or_ttl_changes(changes):
    token = issue()

    with pytest.raises(InvalidSqlContinuation):
        restore(token, **changes)


def test_rejects_tampering_and_keeps_context_from_client_out_of_restore():
    token = issue()
    data, signature = token.split(".")
    tampered = data[:-2] + ("AA" if data[-2:] != "AA" else "BB") + "." + signature

    with pytest.raises(InvalidSqlContinuation):
        restore(tampered)


def test_limits_token_context_to_three_turns_and_size():
    history = tuple(
        AIConversationTurn(role="user" if index % 2 == 0 else "assistant",
                           content=f"turno {index}")
        for index in range(8)
    )
    token = issue(previous_context=history)

    assert len(token) <= 16000
    assert len(restore(token)) == 3
