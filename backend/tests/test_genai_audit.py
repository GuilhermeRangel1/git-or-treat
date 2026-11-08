"""Persistência, expiração e contrato fechado da trilha operacional."""

from datetime import UTC, datetime, timedelta

import pytest
from app.models.genai_audit import AUDIT_EVENTS
from app.schemas.genai_audit import GenAIAuditEvent
from app.services.genai_audit import AuditStore
from pydantic import ValidationError
from sqlalchemy import create_engine


@pytest.mark.parametrize("version", [
    "genai-grounding-v1", "genai-grounding-v2", "genai-grounding-v3", "genai-grounding-v4",
])
def test_audit_persists_current_and_previous_prompt_versions(version, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'versions.db'}")
    AUDIT_EVENTS.create(engine)
    event = GenAIAuditEvent(
        correlation_id="a" * 32, stage="response", code="completed", outcome="success",
        duration_ms=1, prompt_version=version,
    )
    try:
        AuditStore(engine).record(event)
        assert AuditStore(engine).read("a" * 32)[0]["event"]["prompt_version"] == version
        with pytest.raises(ValidationError):
            GenAIAuditEvent.model_validate({**event.model_dump(), "prompt_version": "unknown"})
    finally:
        engine.dispose()


def test_audit_survives_new_store_and_expires_after_thirty_days(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    AUDIT_EVENTS.create(engine)
    now = datetime(2026, 10, 31, tzinfo=UTC)
    event = GenAIAuditEvent(
        correlation_id="a" * 32, stage="plan", code="ready", outcome="success",
        duration_ms=12, plan_id="b" * 64,
    )
    reference = AuditStore(engine).record(event, now=now)
    restarted = AuditStore(engine)
    assert restarted.read("a" * 32, now=now)[0]["event"]["plan_id"] == "b" * 64
    assert len(restarted.read_reference(reference, now=now)) == 1
    assert restarted.read_reference("f" * 32, now=now) == []
    assert restarted.read("a" * 32, now=now + timedelta(days=30)) == []
    assert restarted.read_reference(reference, now=now + timedelta(days=30)) == []
    assert restarted.purge(now=now + timedelta(days=30)) == 1
    assert restarted.purge(now=now + timedelta(days=30)) == 0
    engine.dispose()


def test_audit_reads_multiple_referenced_correlations_in_one_lookup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audit-batch.db'}")
    AUDIT_EVENTS.create(engine)
    store = AuditStore(engine)
    first = store.record(GenAIAuditEvent(
        correlation_id="a" * 32, stage="response", code="completed",
        outcome="success", duration_ms=1,
    ))
    store.record(GenAIAuditEvent(
        correlation_id="a" * 32, stage="source", code="available",
        outcome="success", duration_ms=2,
    ))
    second = store.record(GenAIAuditEvent(
        correlation_id="b" * 32, stage="response", code="completed",
        outcome="success", duration_ms=3,
    ))

    found = store.read_references([first, second, "f" * 32])
    assert len(found[first]) == 2
    assert len(found[second]) == 1
    assert set(found) == {first, second}
    assert store.read_references([]) == {}
    with pytest.raises(ValueError):
        store.read_references(["not-an-audit-reference"])
    engine.dispose()


def test_audit_contract_does_not_accept_free_text_or_nested_payloads():
    base = {"correlation_id": "a" * 32, "stage": "response", "code": "completed",
                "outcome": "success", "duration_ms": 0}
    for extra in ({"question": "segredo"}, {"records": [{"cpf": "123"}]},
                  {"code": "token=segredo"}, {"plan_id": "SELECT segredo"}):
        with pytest.raises(ValidationError):
            GenAIAuditEvent.model_validate(base | extra)


def test_internal_ingress_requires_own_token_and_confirms_persistence(client, monkeypatch):
    from app.core.config import settings
    from pydantic import SecretStr

    from tests.support.database import test_engine

    monkeypatch.setattr(settings, "GENAI_AUDIT_WRITE_TOKEN", SecretStr("a" * 40))
    event = {"correlation_id": "a" * 32, "stage": "response", "code": "completed",
                 "outcome": "success", "duration_ms": 12}
    path = "/api/v1/internal/genai-audit-events"
    assert client.post(path, json=event).status_code == 401
    headers = {"Authorization": "Bearer " + "a" * 40, "X-Correlation-ID": "a" * 32}
    assert client.post(path, json=event, headers=headers).status_code == 201
    assert len(AuditStore(test_engine).read("a" * 32)) == 1
    assert client.get(path, headers=headers).status_code == 405
    rejected = client.post(path, json=event | {"question": "segredo"}, headers=headers)
    assert rejected.status_code == 422
    assert "segredo" not in rejected.text
    assert rejected.json() == {"detail": "Evento de auditoria inválido."}
    assert len(AuditStore(test_engine).read("a" * 32)) == 1
    monkeypatch.setattr(settings, "GENAI_AUDIT_WRITE_TOKEN", None)
    assert client.post(path, json=event, headers=headers).status_code == 503
