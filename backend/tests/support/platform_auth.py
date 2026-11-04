"""Real session identities for HTTP behavior tests."""

from functools import cache
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.passwords import hash_password
from app.models.auth import AuthUser
from tests.support.database import TestingSessionLocal


ORIGIN = "http://localhost:5173"
PASSWORD = "correct horse battery staple"


@cache
def _test_password_hash() -> str:
    return hash_password(PASSWORD)


def login_as_profile(
    client: TestClient,
    monkeypatch,
    profile: str,
    *,
    username: str = "profiled-test-user",
) -> TestClient:
    """Create and log in an explicit test account with a persisted platform profile."""
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    client.cookies.clear()

    with TestingSessionLocal() as db:
        db.add(
            AuthUser(
                id=str(uuid4()),
                username=username,
                password_hash=_test_password_hash(),
                permissions=[],
                profile=profile,
                is_active=True,
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    client.headers.update({"Origin": ORIGIN})
    return client
