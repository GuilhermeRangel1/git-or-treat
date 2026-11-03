"""Isolamento, recuperação e expiração no armazenamento operacional real."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.models.ai_conversations import CONVERSATIONS as C
from app.models.ai_conversations import EXCHANGES as E
from app.models.auth import AuthUser
from app.schemas.ai import AIQuestionResponse
from app.schemas.ai_conversations import ConversationDetail
from app.services.ai_conversations import ConversationStore, now, purge_history
from fastapi import HTTPException
from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def storage():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    for table in [AuthUser.__table__, C, E]:
        table.create(engine)
    with Session(engine) as db:
        db.execute(
            insert(AuthUser).values(
                id="one",
                username="one",
                password_hash="unused",
                permissions=[],
                is_active=True,
            )
        )
        db.execute(
            insert(AuthUser).values(
                id="two",
                username="two",
                password_hash="unused",
                permissions=[],
                is_active=True,
            )
        )
        db.commit()
        yield db, ConversationStore(db, "one"), ConversationStore(db, "two")
    engine.dispose()


def response():
    return AIQuestionResponse(
        status="needs_clarification",
        message="Qual período?",
        evidence=[],
        limitations=[],
    )


def test_unresolved_draft_survives_multiple_short_answers(storage):
    _db, owner, _other = storage
    conversation = owner.create(str(uuid4()))["id"]
    for raw, draft in [
        ("Receita paga em Recife em maio e junho?", "Receita paga em Recife em maio e junho?"),
        ("faturado", "Faturamento em Recife em maio e junho?"),
    ]:
        request = str(uuid4())
        _, _, attempt = owner.reserve(conversation, request, raw, "scope")
        owner.finish(conversation, request, attempt, raw, response(), draft, "batch-v2")
    _, (anchor, recent), _ = owner.reserve(conversation, str(uuid4()), "2026", "scope")
    assert anchor["anchor"] == "Faturamento em Recife em maio e junho?"
    assert recent["question"] == "faturado"


def test_owner_is_required_for_every_storage_operation(storage):
    _db, owner, other = storage
    conversation = owner.create(str(uuid4()))["id"]
    assert other.listing()["items"] == []
    for action in [
        lambda: other.detail(conversation, "scope"),
        lambda: other.rename(conversation, "Outro", 1),
        lambda: other.remove(conversation),
        lambda: other.reserve(conversation, str(uuid4()), "receita", "scope"),
    ]:
        with pytest.raises(HTTPException) as error:
            action()
        assert error.value.status_code == 404
    assert owner.detail(conversation, "scope")["exchanges"] == []


def test_creation_and_completed_request_are_idempotent(storage):
    db, owner, _ = storage
    request = str(uuid4())
    conversation = owner.create(request)["id"]
    assert owner.create(request)["id"] == conversation
    exchange = str(uuid4())
    _, _, attempt = owner.reserve(conversation, exchange, "receita", "scope")
    assert (
        db.scalar(select(E.c.question)) is None
    )  # nenhum texto livre antes da política da IA
    owner.finish(conversation, exchange, attempt, "receita", response())
    assert owner.summary(owner.owned(conversation))["message_count"] == 2
    cached, context, attempt = owner.reserve(conversation, exchange, "receita", "scope")
    assert cached == response() and context is None and attempt is None
    assert len(owner.detail(conversation, "scope")["exchanges"]) == 1
    with pytest.raises(HTTPException):
        owner.reserve(conversation, exchange, "outro pedido", "scope")


def test_pending_request_and_late_attempt_cannot_overwrite_recovery(storage):
    db, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    request = str(uuid4())
    _, _, old = owner.reserve(conversation, request, "receita", "scope")
    with pytest.raises(HTTPException):
        owner.reserve(conversation, request, "receita", "scope")
    db.rollback()
    db.execute(update(E).values(lease_until=now() - timedelta(seconds=1)))
    db.commit()
    _, _, current = owner.reserve(conversation, request, "receita", "scope")
    assert current != old
    with pytest.raises(HTTPException):
        owner.finish(conversation, request, old, "receita", response())
    owner.finish(conversation, request, current, "receita", response())
    assert owner.detail(conversation, "scope")["exchanges"][0]["state"] == "completed"


def test_delete_is_atomic_and_late_response_does_not_resurrect(storage):
    db, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    request = str(uuid4())
    _, _, attempt = owner.reserve(conversation, request, "receita", "scope")
    owner.remove(conversation)
    with pytest.raises(HTTPException):
        owner.finish(conversation, request, attempt, "receita", response())
    assert db.scalar(select(E.c.id)) is None
    assert owner.listing()["items"] == []


def test_expiration_hides_then_physically_purges(storage):
    db, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    owner.reserve(conversation, str(uuid4()), "receita", "scope")
    db.execute(update(C).values(expires_at=now() - timedelta(seconds=1)))
    db.commit()
    assert owner.listing()["items"] == []
    with pytest.raises(HTTPException):
        owner.detail(conversation, "scope")
    db.rollback()
    purge_history(db.get_bind())
    assert db.scalar(select(E.c.id)) is None and db.scalar(select(C.c.id)) is None


def test_corruption_and_changed_scope_do_not_expose_content(storage):
    db, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    request = str(uuid4())
    _, _, attempt = owner.reserve(conversation, request, "receita", "scope")
    owner.finish(conversation, request, attempt, "receita", response())
    item = owner.detail(conversation, "other-scope")["exchanges"][0]
    assert (
        item["state"] == "unavailable"
        and item["question"] is None
        and item["response"] is None
    )
    db.execute(update(E).values(response={"unexpected": "private"}))
    db.commit()
    item = owner.detail(conversation, "scope")["exchanges"][0]
    assert item["state"] == "unavailable" and item["response"] is None
    anchor, recent = owner.context(conversation, "scope")
    assert anchor is None and recent is None


def test_rename_detects_conflict_and_does_not_extend_retention(storage):
    _db, owner, _ = storage
    initial = owner.create(str(uuid4()))
    renamed = owner.rename(initial["id"], "Receita", 1)
    assert renamed["expires_at"] == initial["expires_at"]
    with pytest.raises(HTTPException):
        owner.rename(initial["id"], "Sobrescrever", 1)


@pytest.mark.parametrize("corrupted_question", ["", "   ", "x" * 1001])
def test_invalid_stored_question_hides_only_affected_exchange(storage, corrupted_question):
    db, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    for question in ["Pergunta preservada", "Pergunta corrompida"]:
        request = str(uuid4())
        _, _, attempt = owner.reserve(conversation, request, question, "scope")
        owner.finish(conversation, request, attempt, question, response())
    db.execute(
        update(E)
        .where(E.c.request_id == request)
        .values(question=corrupted_question)
    )
    db.commit()

    detail = ConversationDetail.model_validate(owner.detail(conversation, "scope"))
    assert detail.exchanges[0].question == "Pergunta preservada"
    invalid = detail.exchanges[1]
    assert invalid.state == "unavailable"
    assert invalid.question is None and invalid.response is None
