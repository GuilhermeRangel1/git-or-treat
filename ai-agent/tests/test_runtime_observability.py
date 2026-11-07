"""Diagnóstico operacional autenticado e metadados sem conteúdo de negócio."""

import json
import logging
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.gold_runtime import create_gold_app
from app.telemetry import record_usage

from .conftest import InProcessClient


def test_runtime_diagnostic_is_private_and_distinguishes_missing_generation():
    token = "test-runtime-service-token-000000000000000"
    app = create_gold_app(
        Settings(
            _env_file=None,
            service_api_token=token,
            audit_url="http://backend/api/v1/internal/genai-audit-events",
            audit_write_token="audit-token-not-public-0000000000000000",
        )
    )
    with InProcessClient(app) as client:
        path = "/api/v1/internal/runtime-status"
        assert client.get(path).status_code == 401
        response = client.request("GET", path, headers={"Authorization": "Bearer " + token})
        assert response.status_code == 200
        body = response.json()
        assert body["schema_version"] == "gold-csv-v2"
        assert body["audit_configured"] is True
        assert body["generation_configured"] is False
        assert body["limits"]["evidence_max_rows"] == 100
        assert token not in response.text
        assert "audit-token-not-public" not in response.text
        assert "http://backend" not in response.text


def test_usage_does_not_turn_unknown_or_invalid_metadata_into_zero(caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        record_usage("gemini", prompt=12, output=-1, cached=True, total="secret")
    payload = json.loads(caplog.messages[-1].split(" ", 1)[1])
    assert payload["prompt_tokens"] == 12
    assert set(payload["dependencies"]) == {"google-genai", "sqlglot", "psycopg"}
    assert payload["output_tokens"] is None
    assert payload["cached_tokens"] is None
    assert payload["total_tokens"] is None
    assert "secret" not in caplog.text


@pytest.mark.parametrize(
    "primary_status,selection,expected,calls_expected",
    [
        (503, "row_1", "answered", ["primary", "secondary"]),
        (503, "row_99", "refused", ["primary", "secondary"]),
        (401, "row_1", "recoverable_error", ["primary"]),
    ],
)
def test_deployed_factory_fallback_preserves_gold_evidence(
    monkeypatch,
    primary_status,
    selection,
    expected,
    calls_expected,
):
    from app.audit import BackendEventSink
    from app.providers.factory import build_model_adapter
    from app.schemas.internal import QuestionSynthesisRequest
    from app.schemas.read_plan import LogicalReadPlan

    from .test_core_plan_synthesis import _lookup
    from .test_gold_question_filters import _setup

    calls = []

    class ProviderError(Exception):
        status_code = primary_status

    async def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "primary":
            raise ProviderError("private provider details")
        return SimpleNamespace(
            text=json.dumps({"status": "answered", "observation_ids": [selection]})
        )

    sdk = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(
        "app.main.build_model_adapter", lambda settings: build_model_adapter(settings, client=sdk)
    )
    monkeypatch.setattr(BackendEventSink, "record", lambda self, event: None)
    token = "runtime-fallback-token-000000000000000000000"
    app = create_gold_app(
        Settings(
            _env_file=None,
            service_api_token=token,
            model_provider="gemini",
            gemini_api_key="fake-not-a-real-key",
            gemini_model="primary",
            gemini_fallback_models=["secondary"],
            model_max_calls=2,
            audit_url="http://backend/api/v1/internal/genai-audit-events",
            audit_write_token="audit-token-not-public-0000000000000000",
        )
    )
    _, request = _setup("Receita residencial em Olinda em março de 2025?")
    headers = {"Authorization": "Bearer " + token, "X-Correlation-ID": "a" * 32}
    with InProcessClient(app) as client:
        planned = client.post(
            "/api/v1/internal/question-plans", json=request.model_dump(mode="json"), headers=headers
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records[0].update(
            period="2025-03",
            municipality="Olinda",
            consumption_class="RESIDENCIAL",
        )
        payload = QuestionSynthesisRequest(
            question=request.question,
            access_scope=request.access_scope,
            remaining_timeout_ms=35000,
            plan=plan,
            plan_fingerprint=planned["plan_fingerprint"],
            lookup=lookup,
            expected_batch_ref=request.batch_ref,
        )
        response = client.post(
            "/api/v1/internal/question-syntheses",
            json=payload.model_dump(mode="json"),
            headers=headers,
        )
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert calls == calls_expected
    assert "private provider" not in response.text
    assert "fake-not-a-real-key" not in response.text
