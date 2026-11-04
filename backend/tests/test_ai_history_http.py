"""Rotas reais, sessões reais e isolamento sem confiar em IDs do navegador."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.api.v1.endpoints import ai_conversations as routes
from app.core.config import settings
from app.core.database import get_db
from app.models.ai_conversations import EXCHANGES as E
from app.models.auth import AuthSession, AuthUser
from app.schemas.ai import AIQuestionResponse
from app.services.ai_conversations import now
from app.services.auth import hash_token
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from tests.test_ai_history_store import storage  # noqa: F401 -- fixture compartilhada

ORIGIN = {"origin": "http://localhost:5173"}


@pytest.fixture
def client(request, monkeypatch):
    db, _, _ = request.getfixturevalue("storage")
    AuthSession.__table__.create(db.get_bind())
    db.execute(update(AuthUser).values(profile="losses", permissions=[]))
    for owner in ["one", "two"]:
        db.execute(
            insert(AuthSession).values(
                id=str(uuid4()),
                user_id=owner,
                token_hash=hash_token(owner),
                expires_at=now() + timedelta(hours=1),
            )
        )
    db.commit()
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "synthetic")
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", ["http://localhost:5173"])
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1/ai")

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = uuid4().hex
        return await call_next(request)

    def database():
        with Session(db.get_bind()) as session:
            yield session

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[routes.get_genai_question_client] = lambda: None
    calls = []

    async def answer(payload, *_):
        calls.append(payload)
        return AIQuestionResponse(
            status="needs_clarification",
            message="Qual período?",
            evidence=[],
            limitations=[],
        )

    monkeypatch.setattr(routes, "ask_genai_question", answer)
    client = TestClient(app)
    client.cookies.set("grid360_session", "one")
    yield client, db, calls
    client.close()


def create(client):
    response = client.post(
        "/api/v1/ai/conversations", json={"request_id": str(uuid4())}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["id"]


def test_anonymous_revoked_and_cross_origin_are_denied(client):
    web, db, _ = client
    web.cookies.clear()
    assert web.get("/api/v1/ai/conversations").status_code == 401
    web.cookies.set("grid360_session", "one")
    assert (
        web.post(
            "/api/v1/ai/conversations",
            json={"request_id": str(uuid4())},
            headers={"origin": "https://other.test"},
        ).status_code
        == 403
    )
    db.execute(update(AuthUser).where(AuthUser.id == "one").values(profile=None))
    db.commit()
    assert web.get("/api/v1/ai/conversations").status_code == 403


@pytest.mark.parametrize("profile", ["commercial", "customer_service", "losses", "operations", "admin"])
def test_history_uses_assistant_permission_for_each_platform_profile(client, profile):
    web, db, _ = client
    db.execute(update(AuthUser).where(AuthUser.id == "one").values(profile=profile))
    db.commit()
    conversation = create(web)
    assert web.get("/api/v1/ai/conversations").status_code == 200
    assert web.get(f"/api/v1/ai/conversations/{conversation}").status_code == 200


def test_crud_owner_and_redacted_validation(client):
    web, _db, _ = client
    conversation = create(web)
    url = f"/api/v1/ai/conversations/{conversation}"
    assert web.get(url).json()["historical"] is True
    assert (
        web.patch(
            url, json={"title": "Receita", "expected_revision": 1}, headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        web.patch(
            url, json={"title": "Perdido", "expected_revision": 1}, headers=ORIGIN
        ).status_code
        == 409
    )
    invalid = web.post(
        "/api/v1/ai/conversations",
        json={"request_id": str(uuid4()), "owner_id": "PRIVATE-MARKER"},
        headers=ORIGIN,
    )
    assert invalid.status_code == 422 and "PRIVATE-MARKER" not in invalid.text
    web.cookies.set("grid360_session", "two")
    assert web.get(url).status_code == 404
    assert web.delete(url, headers=ORIGIN).status_code == 404
    assert web.get("/api/v1/ai/conversations").json()["items"] == []
    web.cookies.set("grid360_session", "one")
    assert web.delete(url, headers=ORIGIN).status_code == 204
    assert web.get(url).status_code == 404


def test_send_replay_and_refresh_restore_association(client):
    web, _db, calls = client
    conversation = create(web)
    url = f"/api/v1/ai/conversations/{conversation}"
    payload = {"request_id": str(uuid4()), "question": "Qual receita?"}
    for _ in range(2):
        result = web.post(url + "/questions", json=payload, headers=ORIGIN)
        assert result.status_code == 200, result.text
    assert len(calls) == 1
    restored = web.get(url).json()
    assert len(restored["exchanges"]) == 1
    assert restored["exchanges"][0]["question"] == "Qual receita?"
    assert restored["exchanges"][0]["response"]["message"] == "Qual período?"


def test_revocation_during_external_call_does_not_store_answer(client, monkeypatch):
    web, db, _ = client
    conversation = create(web)

    async def revoke(*_):
        with Session(db.get_bind()) as current:
            current.execute(
                update(AuthUser).where(AuthUser.id == "one").values(profile=None)
            )
            current.commit()
        return AIQuestionResponse(
            status="needs_clarification",
            message="Private answer",
            evidence=[],
            limitations=[],
        )

    monkeypatch.setattr(routes, "ask_genai_question", revoke)
    result = web.post(
        f"/api/v1/ai/conversations/{conversation}/questions",
        json={"request_id": str(uuid4()), "question": "Private question"},
        headers=ORIGIN,
    )
    assert result.status_code == 403 and "Private" not in result.text
    entry = db.execute(select(E)).mappings().one()
    assert entry["question"] is None and entry["response"] is None
