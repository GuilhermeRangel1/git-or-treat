"""Rotas reais, sessões reais e isolamento sem confiar em IDs do navegador."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.api.v1.endpoints import ai_conversations as routes
from app.core.config import settings
from app.core.database import get_db
from app.models.ai_conversations import EXCHANGES as E
from app.models.auth import AuthSession, AuthUser
from app.models.genai_audit import AUDIT_EVENTS
from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.sql_analysis import SqlAnalysisResponse
from app.services.ai_conversations import now
from app.services.auth import hash_token
from app.services.genai_audit import AuditStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, insert, select, update
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


def test_legacy_conversation_refuses_external_subject_before_gold_or_genai(client):
    web, db, calls = client
    AUDIT_EVENTS.create(db.get_bind(), checkfirst=True)
    conversation = create(web)
    response = web.post(
        f"/api/v1/ai/conversations/{conversation}/questions",
        json={
            "request_id": str(uuid4()),
            "question": "Qual a receita de miojo de janeiro de 2026?",
            "strategy": "legacy",
        },
        headers=ORIGIN,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "refused"
    assert response.json()["error"] == {"code": "out_of_scope", "retryable": False}
    assert "fora do domínio de energia elétrica" in response.json()["message"]
    assert calls == []
    event = db.execute(
        select(AUDIT_EVENTS).where(
            AUDIT_EVENTS.c.correlation_id == response.json()["correlation_id"]
        )
    ).mappings().one()
    assert event["event"]["stage"] == "policy"
    assert event["event"]["code"] == "refused"
    assert event["event"]["model_calls"] == event["event"]["source_calls"] == 0


def test_sql_f1_saved_conversation_regenerates_context_and_replays_audited_response(
    client, monkeypatch,
):
    web, db, _legacy_calls = client
    db.execute(update(AuthUser).where(AuthUser.id == "one").values(profile="commercial"))
    db.commit()
    batch = "gold-csv-v2:GOLD_20261106T120000Z_deadbeef:12345678-1234-4234-8234-123456789abc"
    current_batch = {"value": batch}
    gold_engine = create_engine("sqlite://")
    AUDIT_EVENTS.create(db.get_bind(), checkfirst=True)
    monkeypatch.setattr(
        settings, "AI_AGENT_SERVICE_API_TOKEN", SecretStr("continuation-secret-for-tests"),
    )
    monkeypatch.setattr(
        routes.GoldPublicationContext,
        "capture",
        lambda _engine: type("Publication", (), {"batch_ref": current_batch["value"]})(),
    )
    monkeypatch.setattr(
        routes,
        "current_publication",
        lambda *_: type("Publication", (), {"batch_ref": current_batch["value"]})(),
    )
    monkeypatch.setattr(
        routes,
        "create_genai_gold_engine",
        lambda _scope: gold_engine,
    )
    web.app.dependency_overrides[routes.get_question_gold_resources] = (
        lambda: (gold_engine, lambda: None)
    )
    generated = []

    async def generate(payload, request, _genai, _resources, current_db, *,
                       trusted_context=None, trusted_batch_ref=None):
        generated.append((payload.question, trusted_context, trusted_batch_ref))
        scope = routes.current_scope(request, current_db)
        correlation = f"{len(generated):032x}"
        reference = AuditStore(db.get_bind()).record(
            BackendAuditEvent(
                correlation_id=correlation,
                stage="response",
                code="clarification",
                outcome="success",
                duration_ms=1,
                batch_ref=current_batch["value"],
                caller_ref=scope.caller_ref,
                metric_id="billing.revenue",
                source_id="gold.local",
            ),
            service="backend",
        )
        return SqlAnalysisResponse(
            correlation_id=correlation,
            audit_reference=reference,
            status="needs_clarification",
            clarification={
                "question": "Qual período você quer consultar?",
                "missing_fields": ["period"],
            },
        )

    monkeypatch.setattr(routes, "_run_f1_sql_analysis_impl", generate)
    conversation = create(web)
    url = f"/api/v1/ai/conversations/{conversation}/questions"
    first = {
        "request_id": str(uuid4()),
        "question": "Qual foi o faturamento de Recife?",
        "strategy": "sql_f1",
    }
    response_one = web.post(url, json=first, headers=ORIGIN)
    assert response_one.status_code == 200, response_one.text
    assert response_one.json()["status"] == "needs_clarification"

    second = {
        "request_id": str(uuid4()),
        "question": "Em junho de 2026",
        "strategy": "sql_f1",
    }
    response_two = web.post(url, json=second, headers=ORIGIN)
    assert response_two.status_code == 200, response_two.text
    replay = web.post(url, json=second, headers=ORIGIN)
    assert replay.status_code == 200, replay.text
    assert replay.json()["audit_reference"] == response_two.json()["audit_reference"]
    assert len(generated) == 2
    assert generated[0][1] == []
    assert generated[0][2] == batch
    assert [(turn.role, turn.content) for turn in generated[1][1]] == [
        ("user", "Qual foi o faturamento de Recife?"),
        ("assistant", "Qual período você quer consultar?"),
    ]

    history = web.get(f"/api/v1/ai/conversations/{conversation}")
    assert history.status_code == 200, history.text
    assert [item["sql_response"]["status"] for item in history.json()["exchanges"]] == [
        "needs_clarification", "needs_clarification",
    ]
    first_audit = response_one.json()["audit_reference"]
    db.execute(delete(AUDIT_EVENTS).where(AUDIT_EVENTS.c.id == first_audit))
    db.commit()
    audit_missing_history = web.get(f"/api/v1/ai/conversations/{conversation}")
    assert audit_missing_history.status_code == 200
    assert audit_missing_history.json()["exchanges"][0]["sql_response"] is None
    assert audit_missing_history.json()["exchanges"][0]["question"] is None
    assert audit_missing_history.json()["exchanges"][1]["sql_response"] is not None

    refresh = {
        "request_id": str(uuid4()),
        "question": "Só quero uma análise nova, sem herdar o contexto",
        "strategy": "sql_f1",
        "refresh_context": True,
    }
    refreshed = web.post(url, json=refresh, headers=ORIGIN)
    assert refreshed.status_code == 200, refreshed.text
    assert generated[-1][1] == []

    current_batch["value"] = "gold-csv-v2:GOLD_20261107T120000Z_deadbeef:12345678-1234-4234-8234-123456789abc"
    stale_replay = web.post(url, json=second, headers=ORIGIN)
    assert stale_replay.status_code == 409
    stale_history = web.get(f"/api/v1/ai/conversations/{conversation}")
    assert stale_history.status_code == 200
    assert all(item["sql_response"] is None for item in stale_history.json()["exchanges"])
    assert all(item["question"] is None for item in stale_history.json()["exchanges"])

    current_batch["value"] = batch
    monkeypatch.setattr(settings, "AI_AGENT_SERVICE_API_TOKEN", SecretStr("continuation-secret-for-tests"))
    revoke = {
        "request_id": str(uuid4()),
        "question": "revoke access now",
        "strategy": "sql_f1",
    }
    original_generate = generate

    async def revoke_during_generation(payload, request, genai, resources, current_db, **kwargs):
        result = await original_generate(payload, request, genai, resources, current_db, **kwargs)
        if payload.question == "revoke access now":
            current_db.execute(
                update(AuthUser).where(AuthUser.id == "one").values(profile=None)
            )
            current_db.commit()
        return result

    monkeypatch.setattr(routes, "_run_f1_sql_analysis_impl", revoke_during_generation)
    revoked = web.post(url, json=revoke, headers=ORIGIN)
    assert revoked.status_code == 403
    interrupted = db.execute(
        select(E).where(E.c.request_id == revoke["request_id"])
    ).mappings().one()
    assert interrupted["state"] == "interrupted"
    assert interrupted["question"] is None and interrupted["response"] is None
    gold_engine.dispose()


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
