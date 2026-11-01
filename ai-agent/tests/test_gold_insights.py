"""A composição oficial só aceita contexto Gold pela entrada interna autenticada."""

import asyncio

import pytest

from app import main
from app.audit import BackendEventSink
from app.config import Settings
from app.gold_runtime import create_gold_app
from app.ports.events import AuditUnavailable

from .conftest import FakeModelAdapter, InProcessClient
from .test_gold_question_filters import _setup


@pytest.mark.parametrize("case", ["answered", "scope", "audit", "token", "public", "v1", "timeout"])
def test_gold_insight_runtime(monkeypatch, case):
    calls = []

    class Model(FakeModelAdapter):
        async def generate(self, *args):
            calls.append(args[-1])
            if case == "timeout":
                await asyncio.sleep(0.05)
            return await super().generate(*args)

    def record(self, event):
        if case == "audit":
            raise AuditUnavailable("private audit detail")

    monkeypatch.setattr(main, "build_model_adapter", lambda settings: Model())
    monkeypatch.setattr(BackendEventSink, "record", record)
    token = "test-gold-insight-service-token-000000000"
    app = create_gold_app(
        Settings(
            _env_file=None,
            service_api_token=token,
            audit_url="http://backend/api/v1/internal/genai-audit-events",
            audit_write_token="test-gold-insight-audit-token-00000000000",
        )
    )
    _, request = _setup("Receita residencial em Olinda em março de 2025?")
    body = {
        "access_scope": request.access_scope.model_dump(mode="json"),
        "remaining_timeout_ms": 35000,
        "batch_ref": request.batch_ref,
        "screen": {
            "metric": "Receita comparável",
            "unit": "R$",
            "period": {"start": "2025-03-01", "end": "2025-03-31", "granularity": "month"},
            "filters": {
                "periodo": "2025-03",
                "comparacao": "nenhuma",
                "municipio": "Olinda",
                "classe": "RESIDENCIAL",
            },
            "observations": [{"label": "Março de 2025", "value": 0}],
            "reference": {
                "source": "gold.local",
                "description": "Lote autorizado.",
                "is_demo": False,
            },
            "limitations": ["Não há declaração de fechamento mensal."],
        },
    }
    if case == "scope":
        body["access_scope"]["allowed_metric_ids"] = ["energy.consumption"]
    if case == "v1":
        body["batch_ref"] = body["batch_ref"].replace("gold-csv-v2", "gold-csv-v1")
    if case == "timeout":
        body["remaining_timeout_ms"] = 1
    headers = {"Authorization": f"Bearer {token}", "X-Correlation-ID": "a" * 32}
    if case == "token":
        headers["Authorization"] = "Bearer invalid"
    path = "/api/v1/internal/insight-syntheses"
    if case == "public":
        path = "/api/v1/insights"
        body = {"screen": body["screen"]}
    with InProcessClient(app) as client:
        response = client.post(path, json=body, headers=headers)
    if case in {"token", "public", "v1"}:
        assert response.status_code in {401, 422}
        assert not calls
        return
    if case == "timeout":
        assert response.status_code == 503
        assert response.json()["error"]["retryable"] is True
        return
    assert response.status_code == 200
    result = response.json()
    if case == "answered":
        assert result["status"] == "answered"
        assert result["observation"]["values"][0]["value"] == 0
        assert result["evidence"][0]["is_demo"] is False
        assert result["evidence"][0]["source"] == "gold.local"
        assert result["limitations"] == body["screen"]["limitations"]
        assert calls[0].reference.is_demo is False
        assert "Olinda" not in str(calls[0].records)
        assert "RESIDENCIAL" not in str(calls[0].records)
    else:
        assert result["status"] == ("refused" if case == "scope" else "recoverable_error")
        assert result["evidence"] == []
        assert result["observation"]["values"] == []
        assert not calls
