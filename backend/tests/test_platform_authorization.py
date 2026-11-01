from uuid import uuid4
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.passwords import hash_password
from app.models.auth import AuthUser
from app.repositories import analytics as analytics_repository
from app.schemas.ai import AIQuestionResponse
from app.main import app
from tests.support.database import TestingSessionLocal


ROOT = "/api/v1"
ORIGIN = "http://localhost:5173"
PASSWORD = "profile authorization test password"


def _create_user(profile: str) -> None:
    db = TestingSessionLocal()
    try:
        db.add(AuthUser(
            id=str(uuid4()), username=f"profile-{profile}",
            password_hash=hash_password(PASSWORD), permissions=[], profile=profile, is_active=True,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def session_synthetic_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "synthetic")
    monkeypatch.setattr(settings, "APP_ENV", "development")


def _login(client, profile: str) -> None:
    _create_user(profile)
    response = client.post(
        ROOT + "/auth/login",
        json={"username": f"profile-{profile}", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("profile", "allowed_path", "denied_path"),
    [
        ("commercial", "/panorama", "/ucs"),
        ("customer_service", "/ucs", "/panorama"),
        ("losses", "/inspections/queue", "/operations/options"),
        ("operations", "/operations/continuity?periodo=2024-01", "/revenue"),
        ("admin", "/ucs", None),
    ],
)
def test_profile_http_scope_allows_own_resource_and_denies_other_resource(
    client, profile, allowed_path, denied_path, monkeypatch,
):
    _login(client, profile)
    allowed = client.get(ROOT + allowed_path)
    assert allowed.status_code == 200

    calls = []

    def mark_provider(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("provider must not run for a denied resource")

    if denied_path in {"/ucs", "/revenue"}:
        monkeypatch.setitem(app.dependency_overrides, analytics_repository.get_analytics_repository, mark_provider)
    elif denied_path == "/panorama":
        monkeypatch.setattr("app.api.v1.endpoints.panorama.get_panorama_repository", mark_provider)
    elif denied_path == "/operations/options":
        monkeypatch.setitem(app.dependency_overrides, analytics_repository.get_analytics_repository_provider, mark_provider)

    assert calls == []
    if denied_path is not None:
        denied = client.get(ROOT + denied_path)
        assert denied.status_code == 403


@pytest.mark.parametrize("path", ["/panorama", "/revenue", "/ucs", "/inspections/queue", "/operations/options"])
def test_analytics_resources_reject_missing_session_before_repository(client, path, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("repository must not run without a session")

    monkeypatch.setitem(app.dependency_overrides, analytics_repository.get_analytics_repository, fail_if_called)
    monkeypatch.setitem(app.dependency_overrides, analytics_repository.get_analytics_repository_provider, fail_if_called)
    monkeypatch.setattr("app.api.v1.endpoints.panorama.get_panorama_repository", fail_if_called)
    response = client.get(ROOT + path)
    assert response.status_code == 401


def test_insight_requires_both_ai_and_panorama_scopes_before_model(client, monkeypatch):
    _login(client, "operations")
    calls = []
    monkeypatch.setattr(app.state, "genai_insight_client", type("Model", (), {"generate": lambda *args, **kwargs: calls.append(1)})(), raising=False)
    response = client.post(
        ROOT + "/ai/insights",
        headers={"Origin": ORIGIN},
        json={"contract_version": "v1", "metric": "energy_billed_kwh", "period": {"start": "2024-01", "end": "2024-01"}, "filters": {}},
    )
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("profile", ["commercial", "customer_service", "losses", "operations", "admin"])
def test_all_profiles_can_use_ai_question_scope(client, profile, monkeypatch):
    _login(client, profile)
    calls = []

    class Model:
        async def ask(self, payload, correlation_id):
            calls.append((payload.question, correlation_id))
            return AIQuestionResponse.model_validate({
                "status": "answered",
                "answer": "Resposta fundamentada.",
                "evidence": [{"source": "synthetic.fixture", "description": "Evidência sintética controlada.", "is_demo": True}],
            })

    monkeypatch.setattr(app.state, "genai_question_client", Model(), raising=False)
    response = client.post(
        ROOT + "/ai/questions",
        headers={"Origin": ORIGIN},
        json={"question": "Resuma o indicador atual."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert len(calls) == 1


def test_service_token_keeps_technical_read_scope_without_admin_or_ai(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr("technical-read"))
    monkeypatch.setattr(settings, "ORDERS_WRITE_TOKEN", SecretStr("technical-write"))
    calls = []
    monkeypatch.setattr(app.state, "genai_question_client", SimpleNamespace(ask=lambda *args, **kwargs: calls.append(1)), raising=False)

    analytic = client.get(ROOT + "/panorama", headers={"Authorization": "Bearer technical-read"})
    question = client.post(
        ROOT + "/ai/questions",
        headers={"Authorization": "Bearer technical-write"},
        json={"question": "Pergunta sintética válida"},
    )

    assert analytic.status_code == 200
    assert question.status_code == 403
    assert question.json()["error"]["code"] == "access_denied"
    assert calls == []


def test_demo_mode_cannot_open_gold_or_replace_session_authentication(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "demo")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    calls = []
    monkeypatch.setattr("app.repositories.gold_context.engine.connect", lambda: calls.append(1))

    response = client.get(ROOT + "/panorama")

    assert response.status_code == 503
    assert calls == []


def test_gold_resource_denial_precedes_snapshot_connection(client, monkeypatch):
    _login(client, "operations")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    calls = []
    monkeypatch.setattr("app.repositories.gold_context.engine.connect", lambda: calls.append(1))

    response = client.get(ROOT + "/panorama")

    assert response.status_code == 403
    assert calls == []


def test_admin_profile_does_not_bypass_internal_audit_token(client, monkeypatch):
    _login(client, "admin")
    monkeypatch.setattr(settings, "GENAI_AUDIT_WRITE_TOKEN", None)
    response = client.post(
        ROOT + "/internal/genai-audit-events",
        json={
            "correlation_id": "a" * 32,
            "stage": "request",
            "code": "started",
            "outcome": "started",
            "duration_ms": 0,
        },
    )
    assert response.status_code == 503
