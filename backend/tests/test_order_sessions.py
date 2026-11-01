from datetime import datetime, timedelta, timezone
import hashlib
import re
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select

from app.core.config import settings
from app.core.database import Base
from app.core.passwords import hash_password
from app.models.auth import AuthSession, AuthUser
from app.models.operational import OperationalOrderHistory
from tests.support.database import TestingSessionLocal
from scripts import bootstrap_local_auth
from scripts import set_user_profile
from tests.support.client import client_with_overrides


ROOT = "/api/v1"
ORIGIN = "http://localhost:5173"
SESSION_COOKIE = "grid360_session"


def create_user(username="reader", password="correct horse battery staple", permissions=None, *, active=True, profile=None):
    db = TestingSessionLocal()
    try:
        user = AuthUser(
            id=str(uuid4()),
            username=username,
            password_hash=hash_password(password),
            permissions=["orders:read"] if permissions is None else permissions,
            profile=profile,
            is_active=active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def test_login_returns_safe_envelope_and_opaque_hashed_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    user_id = create_user(profile="losses")

    response = client.post(
        ROOT + "/auth/login",
        json={"username": "reader", "password": "correct horse battery staple"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["user"] == {
        "id": user_id, "username": "reader", "profile": "losses",
        "permissions": ["ai:ask", "inspections:read", "orders:read", "orders:write"],
    }
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc)
    cookie = response.cookies.get("grid360_session")
    assert cookie and len(cookie) >= 43
    assert "password" not in response.text and cookie not in response.text
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/api/v1" in set_cookie
    db = TestingSessionLocal()
    try:
        stored = db.query(AuthSession).one()
        assert stored.token_hash == hashlib.sha256(cookie.encode()).hexdigest()
        assert stored.token_hash != cookie
        assert stored.user_id == user_id
    finally:
        db.close()


def test_session_endpoint_and_logout_revoke_old_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    create_user("operator", permissions=["orders:read", "orders:write"], profile="losses")
    logged_in = client.post(ROOT + "/auth/login", json={"username": "operator", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    token = logged_in.cookies["grid360_session"]
    rotated = client.post(ROOT + "/auth/login", json={"username": "operator", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    new_token = rotated.cookies["grid360_session"]
    assert new_token != token
    client.cookies.set(SESSION_COOKIE, token, path=ROOT)
    assert client.get(ROOT + "/auth/session").json()["user"] is None
    token = new_token
    client.cookies.set(SESSION_COOKIE, token, path=ROOT)

    current = client.get(ROOT + "/auth/session")
    assert current.status_code == 200
    assert current.headers["cache-control"] == "no-store"
    assert current.json()["user"]["permissions"] == [
        "ai:ask", "inspections:read", "orders:read", "orders:write",
    ]
    assert current.json()["user"]["profile"] == "losses"
    assert current.json()["user"]["id"] != token

    logged_out = client.post(ROOT + "/auth/logout", headers={"Origin": ORIGIN})
    assert logged_out.status_code == 204 and not logged_out.content
    assert 'grid360_session=""' in logged_out.headers["set-cookie"]
    client.cookies.set(SESSION_COOKIE, token, path=ROOT)
    replay = client.get(ROOT + "/auth/session")
    assert replay.json() == {"enabled": True, "user": None, "expires_at": None}
    client.cookies.clear()
    second_logout = client.post(ROOT + "/auth/logout", headers={"Origin": ORIGIN})
    assert second_logout.status_code == 204


def test_invalid_credentials_inactive_and_expired_sessions_fail_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    user_id = create_user("reader")
    assert client.post(ROOT + "/auth/login", json={"username": "reader", "password": "wrong password"}, headers={"Origin": ORIGIN}).status_code == 401
    assert client.post(ROOT + "/auth/login", json={"username": "missing", "password": "wrong password"}, headers={"Origin": ORIGIN}).status_code == 401

    logged_in = client.post(ROOT + "/auth/login", json={"username": "reader", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    token = logged_in.cookies["grid360_session"]
    db = TestingSessionLocal()
    try:
        session = db.query(AuthSession).one()
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    client.cookies.set(SESSION_COOKIE, token, path=ROOT)
    assert client.get(ROOT + "/auth/session").json()["user"] is None

    logged_in = client.post(ROOT + "/auth/login", json={"username": "reader", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    token = logged_in.cookies["grid360_session"]
    db = TestingSessionLocal()
    try:
        user = db.query(AuthUser).filter_by(id=user_id).one()
        user.is_active = False
        db.commit()
    finally:
        db.close()
    client.cookies.set(SESSION_COOKIE, token, path=ROOT)
    assert client.get(ROOT + "/inspections/access").status_code == 401


def test_session_auth_preserves_read_write_permissions_and_actor(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    reader_id = create_user("reader", profile="commercial")
    client.post(ROOT + "/auth/login", json={"username": "reader", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    access = client.get(ROOT + "/inspections/access")
    assert access.status_code == 200, access.text
    assert access.json() == {
        "auth_mode": "session", "actor": f"user:{reader_id}", "permissions": []
    }
    assert client.get(ROOT + "/inspections/access", headers={"Authorization": "Bearer " + "s" * 40}).status_code == 401
    assert client.post(ROOT + "/inspections/orders", json={"uc_id": "AUTH-READER", "reason": "test"}, headers={"Origin": ORIGIN}).status_code == 403

    operator_id = create_user("operator", permissions=["orders:read", "orders:write"], profile="losses")
    client.post(ROOT + "/auth/login", json={"username": "operator", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    created = client.post(ROOT + "/inspections/orders", json={"uc_id": "AUTH-OPERATOR", "reason": "test"}, headers={"Origin": ORIGIN})
    assert created.status_code == 201
    db = TestingSessionLocal()
    try:
        action = db.query(OperationalOrderHistory).one()
        assert action.actor == f"user:{operator_id}"
    finally:
        db.close()


def test_profileless_account_ignores_legacy_json_grants_and_profile_change_is_live(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    user_id = create_user("legacy", permissions=["orders:read", "orders:write"], profile=None)
    login = client.post(
        ROOT + "/auth/login",
        json={"username": "legacy", "password": "correct horse battery staple"},
        headers={"Origin": ORIGIN},
    )
    assert login.status_code == 200
    assert login.json()["user"] == {
        "id": user_id, "username": "legacy", "profile": None, "permissions": [],
    }
    assert client.get(ROOT + "/inspections/access").json()["permissions"] == []
    assert client.post(ROOT + "/inspections/orders", json={"uc_id": "LEGACY-DENIED", "reason": "test"}, headers={"Origin": ORIGIN}).status_code == 403

    db = TestingSessionLocal()
    try:
        user = db.query(AuthUser).filter_by(id=user_id).one()
        user.profile = "commercial"
        db.commit()
    finally:
        db.close()
    session = client.get(ROOT + "/auth/session").json()["user"]
    assert session["profile"] == "commercial"
    assert session["permissions"] == ["ai:ask", "panorama:read", "revenue:read"]
    assert client.get(ROOT + "/inspections/access").json()["permissions"] == []


def test_login_and_cookie_mutations_reject_invalid_origins(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    create_user(profile="losses")
    for headers in ({}, {"Origin": "null"}, {"Origin": "https://evil.invalid"}, {"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"}):
        response = client.post(ROOT + "/auth/login", json={"username": "reader", "password": "correct horse battery staple"}, headers=headers)
        assert response.status_code == 403

    logged_in = client.post(ROOT + "/auth/login", json={"username": "reader", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    assert client.post(ROOT + "/inspections/orders", json={"uc_id": "NO-ORIGIN", "reason": "test"}).status_code == 403
    assert client.post(ROOT + "/auth/logout", headers={"Origin": "null"}).status_code == 403


def test_auth_endpoints_disabled_in_demo_and_service(client, monkeypatch):
    for mode in ("demo", "service"):
        monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", mode)
        assert client.get(ROOT + "/auth/session").json() == {"enabled": False, "user": None, "expires_at": None}
        assert client.post(ROOT + "/auth/login", json={"username": "reader", "password": "x"}, headers={"Origin": ORIGIN}).status_code == 503


def test_login_rate_limit_and_validation_errors_do_not_echo_password(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    monkeypatch.setattr(settings, "AUTH_LOGIN_ATTEMPTS", 2)
    create_user("throttle-user")
    for _ in range(2):
        assert client.post(ROOT + "/auth/login", json={"username": "throttle-user", "password": "wrong"}, headers={"Origin": ORIGIN}).status_code == 401
    limited = client.post(ROOT + "/auth/login", json={"username": "throttle-user", "password": "wrong"}, headers={"Origin": ORIGIN})
    assert limited.status_code == 429
    assert limited.headers["retry-after"]

    secret = "SENSITIVE-PASSWORD-" * 80
    invalid = client.post(ROOT + "/auth/login", json={"username": "throttle-user", "password": secret}, headers={"Origin": ORIGIN})
    assert invalid.status_code == 422
    assert secret not in invalid.text


def test_production_requires_session_and_rejects_legacy_or_service_credentials():
    assert settings.__class__(_env_file=None, APP_ENV="production", ORDERS_AUTH_MODE="session").ORDERS_AUTH_MODE == "session"
    with pytest.raises(ValidationError):
        settings.__class__(_env_file=None, APP_ENV="production", ORDERS_AUTH_MODE="service")
    with pytest.raises(ValidationError):
        settings.__class__(_env_file=None, APP_ENV="development", ORDERS_AUTH_MODE="legacy")
    with pytest.raises(ValidationError):
        settings.__class__(_env_file=None, ORDERS_AUTH_MODE="session", ORDERS_READ_TOKEN="s" * 40)


def test_production_session_cookie_is_secure(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    create_user("production-user", profile="losses")
    response = client.post(ROOT + "/auth/login", json={"username": "production-user", "password": "correct horse battery staple"}, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_bootstrap_creates_random_credentials_once_and_preserves_existing_accounts(tmp_path: Path, monkeypatch, capsys):
    database_path = tmp_path / "local-auth.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(
        database_url,
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
    )
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    credentials_path = tmp_path / "credentials.txt"
    monkeypatch.setattr(sys, "argv", ["bootstrap_local_auth.py", "--database-url", database_url, "--output", str(credentials_path)])

    assert bootstrap_local_auth.main() == 0
    first_credentials = credentials_path.read_text(encoding="utf-8")
    assert "commercial username: commercial" in first_credentials
    assert "admin username: admin" in first_credentials
    assert re.search(r"commercial password: [A-Za-z0-9_-]{40,}", first_credentials)
    assert re.search(r"admin password: [A-Za-z0-9_-]{40,}", first_credentials)
    assert "password" not in capsys.readouterr().out.lower()

    assert bootstrap_local_auth.main() == 0
    assert credentials_path.read_text(encoding="utf-8") == first_credentials
    assert "nenhuma credencial ou permissão foi alterada" in capsys.readouterr().out
