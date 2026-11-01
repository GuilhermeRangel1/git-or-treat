"""O entrypoint implantável mantém Gold, auditoria e identidade explícitos."""

import pytest

from app.config import Settings
from app.gold_runtime import create_gold_app

from .conftest import InProcessClient


def test_gold_runtime_requires_durable_audit_configuration():
    with pytest.raises(ValueError, match="auditoria"):
        create_gold_app(Settings(_env_file=None))


def test_gold_runtime_does_not_authorize_public_question_with_service_token(monkeypatch):
    from app.audit import BackendEventSink

    monkeypatch.setattr(BackendEventSink, "record", lambda self, event: None)
    token = "test-gold-runtime-service-token-000000000"
    app = create_gold_app(Settings(
        _env_file=None, service_api_token=token,
        audit_url="http://backend/api/v1/internal/genai-audit-events",
        audit_write_token="test-gold-runtime-audit-token-00000000000",
    ))
    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/questions", json={"question": "Qual foi a receita?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    assert response.json()["evidence"] == []
