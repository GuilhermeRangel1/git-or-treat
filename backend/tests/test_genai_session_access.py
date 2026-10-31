from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import delete, update
from starlette.requests import Request

from app.core.config import settings
from app.core.genai_gold_access import GOLD_DIMENSIONS, get_genai_gold_access_resolver
from app.core.genai_gold_database import create_genai_gold_engine
from app.main import app
from app.models.auth import AuthSession, AuthUser
from tests.support.database import TestingSessionLocal
from tests.test_order_sessions import ORIGIN, create_user


def test_gold_question_requires_existing_session_and_never_calls_demo(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    ask = AsyncMock(side_effect=AssertionError("Gold não pode chamar a demo"))
    monkeypatch.setattr(app.state.genai_question_client, "ask", ask)
    payload = {"question": "Qual o faturamento?"}
    assert client.post("/api/v1/ai/questions", json=payload).status_code == 401
    assert client.post("/api/v1/ai/questions", json=payload, headers={
        "Origin": ORIGIN, "Cookie": "grid360_session=invalid-cookie",
    }).status_code == 401
    create_user("operator", permissions=["orders:write"])
    login = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={
        "username": "operator", "password": "correct horse battery staple",
    })
    assert login.status_code == 200
    result = client.post("/api/v1/ai/questions", json=payload, headers={"Origin": ORIGIN})
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "service_unavailable"
    ask.assert_not_called()


@pytest.mark.parametrize("change,expected", [
    ("logout", 401), ("expired", 401), ("inactive", 401), ("permission", 403),
])
def test_resolver_observes_committed_revocation_instead_of_cached_user(
    client, monkeypatch, change, expected,
):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    user_id = create_user()
    login = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={
        "username": "reader", "password": "correct horse battery staple",
    })
    token = login.cookies["grid360_session"]
    request = Request({"type": "http", "method": "POST", "headers": [
        (b"cookie", ("grid360_session=" + token).encode()),
        (b"origin", ORIGIN.encode()),
        (b"x-access-scope", b"admin"),
    ]})
    with TestingSessionLocal() as request_db:
        # Mesmo um objeto mantido no identity map da requisição não deve autorizar.
        cached = request_db.get(AuthUser, user_id)
        resolve = get_genai_gold_access_resolver(request, None, request_db)
        scope = resolve()
        assert "read" in scope.allowed_operations
        assert user_id not in scope.caller_ref and token not in scope.model_dump_json()
        assert "customer.consumer_unit" not in scope.allowed_dimension_ids
        assert scope.allowed_dimension_ids == GOLD_DIMENSIONS
        with TestingSessionLocal() as writer:
            if change == "logout":
                writer.execute(delete(AuthSession))
            elif change == "expired":
                writer.execute(update(AuthSession).values(
                    expires_at=datetime.now(UTC) - timedelta(seconds=1),
                ))
            elif change == "inactive":
                writer.execute(update(AuthUser).values(is_active=False))
            else:
                writer.execute(update(AuthUser).values(permissions=[]))
            writer.commit()
        assert cached is not None
        with pytest.raises(HTTPException) as error:
            resolve()
        assert error.value.status_code == expected


def test_two_real_sessions_produce_distinct_callers_and_reject_unsafe_database(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    scopes = []
    for name in ("reader", "operator"):
        create_user(name)
        response = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={
            "username": name, "password": "correct horse battery staple",
        })
        request = Request({"type": "http", "method": "GET", "headers": [
            (b"cookie", ("grid360_session=" + response.cookies["grid360_session"]).encode()),
        ]})
        with TestingSessionLocal() as db:
            scopes.append(get_genai_gold_access_resolver(request, None, db)())
    assert scopes[0].caller_ref != scopes[1].caller_ref
    assert scopes[0].allowed_metric_ids == scopes[1].allowed_metric_ids
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://owner:fake@localhost/db")
    monkeypatch.setattr(settings, "GENAI_GOLD_DATABASE_URL", SecretStr(
        "postgresql+psycopg://owner:fake@localhost/db",
    ))
    with pytest.raises(ValueError):
        create_genai_gold_engine(scopes[0])
