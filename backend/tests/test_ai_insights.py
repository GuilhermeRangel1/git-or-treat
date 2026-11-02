import asyncio
import json
from typing import Any

import httpx
import pytest

from app.main import app
from app.api.v1.endpoints.ai import get_panorama_insight_repository
from app.repositories.panorama import (
    SyntheticPanoramaRepository,
)
from app.schemas.ai_insight import AIInsightResponse, PanoramaInsightRequest
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.panorama_insights import build_panorama_insight


def _upstream_response(correlation_id: str, screen: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "correlation_id": correlation_id,
        "audit_reference": None,
        "error": None,
        "status": "answered",
        "context": {
            "metric": screen["metric"],
            "unit": screen["unit"],
            "period": screen["period"],
            "filters": screen["filters"],
        },
        "observation": {"values": screen["observations"]},
        "hypothesis": "Investigue a composição deste recorte antes de atribuir uma causa.",
        "message": None,
        "evidence": [
            {
                "source": "synthetic.screen",
                "description": "Contexto sintético de tela.",
                "is_demo": True,
            }
        ],
        "limitations": ["A hipótese é exploratória e não comprova uma causa."],
    }


class RecordingInsightGateway:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[object, str]] = []

    async def generate(self, payload, *, correlation_id: str) -> AIInsightResponse:
        self.calls.append((payload, correlation_id))
        if self.error is not None:
            raise self.error
        screen = payload.screen.model_dump(mode="json")
        return AIInsightResponse.model_validate(
            _upstream_response(correlation_id, screen)
        )


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


def _request(
    *,
    municipio: str = "Recife",
    classe: str = "Residencial",
    lote_versao: str = "panorama-sintetico-2024.04-v1",
    periodo: str = "2024-04",
    comparacao: str = "anterior",
) -> dict[str, Any]:
    return {
        "filters": {
            "periodo": periodo,
            "comparacao": comparacao,
            "municipio": municipio,
            "classe": classe,
        },
        "loteVersao": lote_versao,
    }


@pytest.fixture
def insight_repository(monkeypatch):
    repository = SyntheticPanoramaRepository()
    repository.records = [dict(row) for row in repository.records]
    monkeypatch.setitem(
        app.dependency_overrides, get_panorama_insight_repository, lambda: repository
    )
    return repository


def test_panorama_insight_context_is_recomputed_from_the_active_source():
    request = PanoramaInsightRequest.model_validate(_request())

    payload, metric, source, analysis = build_panorama_insight(
        get_panorama_insight_repository(), request
    )

    assert payload.screen.metric == "Energia Faturada"
    assert payload.screen.unit == "kWh"
    assert payload.screen.filters == _request()["filters"]
    assert payload.screen.observations[0].value == 25000
    assert payload.screen.reference.is_demo is True
    assert metric.formula
    assert source.isDemo is True
    assert source.loteVersao == "panorama-sintetico-2024.04-v1"
    assert source.limitacoes == [
        "Os números são fictícios e servem apenas para demonstração; não representam dados operacionais reais."
    ]
    assert analysis.direcao == "queda"
    assert analysis.variacaoPercentual == -13.79
    assert "PRD" not in source.limitacoes[0]
    assert "WEB-01" not in source.limitacoes[0]


def test_empty_slice_returns_no_evidence_without_calling_genai(client, monkeypatch):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)

    response = client.post("/api/v1/ai/insights", json=_request(classe="Rural"))

    assert response.status_code == 200
    body = response.json()
    assert body["insight"]["status"] == "no_evidence"
    assert body["insight"]["observation"]["values"] == []
    assert body["insight"]["hypothesis"] is None
    assert body["insight"]["evidence"] == []
    assert body["insight"]["error"] is None
    assert body["insight"]["context"]["filters"]["classe"] == "Rural"
    assert body["insight"]["correlation_id"] == response.headers["x-correlation-id"]
    assert body["source"]["loteVersao"] == _request()["loteVersao"]
    assert body["analysis"]["direcao"] == "indisponivel"
    assert gateway.calls == []


def test_observed_zero_still_reaches_genai(client, monkeypatch):
    repository = SyntheticPanoramaRepository()
    repository.records = [
        {**row, "energia_faturada_kwh": 0.0}
        for row in repository.records
    ]
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_panorama_insight_repository] = lambda: repository
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    try:
        response = client.post("/api/v1/ai/insights", json=_request())
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    assert response.status_code == 200
    assert response.json()["insight"]["status"] == "answered"
    assert response.json()["insight"]["observation"]["values"][0]["value"] == 0
    assert len(gateway.calls) == 1


def test_empty_slice_still_rejects_stale_batch(client, monkeypatch):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post(
        "/api/v1/ai/insights", json=_request(classe="Rural", lote_versao="old-batch")
    )
    assert response.status_code == 409
    assert gateway.calls == []


@pytest.mark.parametrize("comparacao", ["anterior", "ano_anterior", "nenhuma"])
@pytest.mark.parametrize(
    "periodo,classe,end",
    [
        ("2024-04", "Rural", "2024-04-30"),
        ("2024-06", "Residencial", "2024-06-30"),
        ("2024-02", "Residencial", "2024-02-29"),
    ],
)
def test_empty_period_or_class_preserves_context_without_observations(
    client, monkeypatch, comparacao, periodo, classe, end
):
    gateway = RecordingInsightGateway(error=RuntimeError("must not be called"))
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    payload = _request(periodo=periodo, classe=classe, comparacao=comparacao)

    response = client.post("/api/v1/ai/insights", json=payload)

    assert response.status_code == 200
    body = response.json()
    insight = body["insight"]
    assert insight["status"] == "no_evidence"
    assert insight["context"] == {
        "metric": "Energia Faturada", "unit": "kWh",
        "period": {"start": f"{periodo}-01", "end": end, "granularity": "month"},
        "filters": payload["filters"],
    }
    assert insight["observation"]["values"] == []
    assert insight["evidence"] == []
    assert insight["hypothesis"] is None
    assert insight["message"]
    assert insight["error"] is None
    assert insight["audit_reference"] is None
    assert insight["correlation_id"] == response.headers["x-correlation-id"]
    assert body["source"]["loteVersao"] == payload["loteVersao"]
    assert body["source"]["isDemo"] is True
    assert body["source"]["dataAtualizacao"] == "2024-04-30T18:00:00Z"
    assert body["metric"]["formula"]
    assert body["analysis"]["direcao"] == "indisponivel"
    assert body["analysis"]["variacaoPercentual"] is None
    assert gateway.calls == []


def test_empty_repository_returns_absence_with_its_own_batch(
    client, monkeypatch, insight_repository
):
    insight_repository.records = []
    insight_repository.source_version = "empty-batch-v2"
    insight_repository.source_limitations = ["Sem cobertura nesta extração sintética."]
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post("/api/v1/ai/insights", json=_request(
        municipio="todos", classe="todas", lote_versao="empty-batch-v2"
    ))
    assert response.status_code == 200
    body = response.json()
    assert body["insight"]["status"] == "no_evidence"
    assert body["insight"]["observation"]["values"] == []
    assert body["source"]["loteVersao"] == "empty-batch-v2"
    assert "Sem cobertura nesta extração sintética." in body["insight"]["limitations"]
    assert gateway.calls == []


@pytest.mark.parametrize("changes", [
    {"periodo": "2024-13"}, {"municipio": "Cidade inexistente"},
    {"classe": "Classe inexistente"}, {"comparacao": "inexistente"},
])
def test_invalid_empty_slice_is_not_misclassified_as_no_evidence(
    client, monkeypatch, changes
):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    payload = _request(classe="Rural")
    payload["filters"].update(changes)
    response = client.post("/api/v1/ai/insights", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert gateway.calls == []


def test_unsupported_source_precedes_absence(client, monkeypatch, insight_repository):
    insight_repository.source_is_demo = False
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post("/api/v1/ai/insights", json=_request(classe="Rural"))
    assert response.status_code == 503
    assert response.json()["error"] == {"code": "service_unavailable", "retryable": False}
    assert gateway.calls == []


def test_unconfigured_source_precedes_absence(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post("/api/v1/ai/insights", json=_request(classe="Rural"))
    assert response.status_code == 503
    assert gateway.calls == []


@pytest.mark.parametrize("zero_previous,expected", [
    (False, [0, 29000, -29000]), (True, [0, 0, 0]),
])
def test_observed_zero_keeps_comparison_values(
    client, monkeypatch, insight_repository, zero_previous, expected
):
    for row in insight_repository.records:
        if row["competencia"] == "2024-04" or zero_previous:
            row["energia_faturada_kwh"] = 0.0
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post("/api/v1/ai/insights", json=_request())
    assert response.status_code == 200
    insight = response.json()["insight"]
    assert insight["status"] == "answered"
    assert [item["value"] for item in insight["observation"]["values"]] == expected
    assert len(gateway.calls) == 1


def test_current_data_without_comparison_is_not_absence(client, monkeypatch):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)
    response = client.post("/api/v1/ai/insights", json=_request(comparacao="ano_anterior"))
    assert response.status_code == 200
    insight = response.json()["insight"]
    assert insight["status"] == "answered"
    assert [item["value"] for item in insight["observation"]["values"]] == [25000]
    assert len(gateway.calls) == 1


def test_panorama_insight_explains_largest_class_contribution_to_decline():
    request = PanoramaInsightRequest.model_validate(
        _request(municipio="Olinda", classe="todas")
    )

    _, _, _, analysis = build_panorama_insight(get_panorama_insight_repository(), request)

    assert analysis.direcao == "queda"
    assert analysis.variacaoPercentual == -10.17
    assert analysis.principalContribuicao.model_dump() == {
        "dimension": "classe",
        "segmento": "Residencial",
        "variacaoAbsoluta": -2500.0,
        "participacaoPercentual": 83.3,
    }
    assert analysis.compensacao is None


def test_panorama_insight_explains_municipal_decline_without_offsetting_increase():
    request = PanoramaInsightRequest.model_validate(
        _request(municipio="todos", classe="todas")
    )

    _, _, _, analysis = build_panorama_insight(get_panorama_insight_repository(), request)

    assert analysis.direcao == "queda"
    assert analysis.variacaoPercentual == -10.0
    assert analysis.principalContribuicao.segmento == "Recife"
    assert analysis.principalContribuicao.variacaoAbsoluta == -5000.0
    assert analysis.principalContribuicao.participacaoPercentual == 50.0
    assert analysis.compensacao is None


def test_panorama_insight_uses_server_built_observations_and_validated_filters(
    client, monkeypatch
):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)

    response = client.post("/api/v1/ai/insights", json=_request())

    assert response.status_code == 200
    body = response.json()
    assert body["insight"]["status"] == "answered"
    assert body["insight"]["context"]["metric"] == "Energia Faturada"
    assert body["insight"]["context"]["unit"] == "kWh"
    assert body["insight"]["context"]["filters"] == _request()["filters"]
    assert body["insight"]["observation"]["values"][0]["value"] == 25000
    assert body["source"]["loteVersao"] == "panorama-sintetico-2024.04-v1"
    assert body["source"]["isDemo"] is True
    assert body["analysis"]["direcao"] == "queda"
    assert body["analysis"]["variacaoPercentual"] == -13.79
    assert body["metric"]["formula"]
    assert len(gateway.calls) == 1
    payload, correlation_id = gateway.calls[0]
    assert payload.screen.filters["municipio"] == "Recife"
    assert payload.screen.observations[0].value == 25000
    assert payload.screen.reference.is_demo is True
    assert correlation_id == response.headers["x-correlation-id"]


def test_panorama_insight_rejects_client_supplied_observations(client, monkeypatch):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)

    response = client.post(
        "/api/v1/ai/insights",
        json={**_request(), "observations": [{"label": "fake", "value": 999999}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "999999" not in response.text
    assert gateway.calls == []


def test_panorama_insight_rejects_a_batch_that_changed_since_the_screen_loaded(
    client, monkeypatch
):
    gateway = RecordingInsightGateway()
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)

    response = client.post(
        "/api/v1/ai/insights", json=_request(lote_versao="old-batch")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_context"
    assert gateway.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "error_code", "retryable"),
    [
        (GenAIServiceUnavailable(), 503, "service_unavailable", True),
        (GenAITimeout(), 504, "service_unavailable", True),
        (GenAIResponseInvalid(), 502, "invalid_upstream_response", False),
    ],
)
def test_panorama_insight_maps_upstream_failures_to_safe_http_errors(
    client, monkeypatch, error, status_code, error_code, retryable
):
    gateway = RecordingInsightGateway(error=type(error)("upstream private diagnostic"))
    monkeypatch.setattr(app.state, "genai_insight_client", gateway, raising=False)

    response = client.post("/api/v1/ai/insights", json=_request())

    assert response.status_code == status_code
    assert response.json()["error"] == {"code": error_code, "retryable": retryable}
    assert "upstream private diagnostic" not in response.text


def test_genai_insight_client_uses_existing_contract_auth_and_correlation():
    request_log: list[httpx.Request] = []
    correlation_id = "a" * 32
    screen = {
        "metric": "Energia faturada",
        "unit": "kWh",
        "period": {
            "start": "2024-04-01",
            "end": "2024-04-30",
            "granularity": "month",
        },
        "filters": {"municipio": "Recife"},
        "observations": [{"label": "Atual", "value": 45000}],
        "reference": {
            "source": "synthetic.panorama",
            "description": "Lote sintético dev03-v1.",
            "is_demo": True,
        },
        "limitations": ["A hipótese não comprova uma causa."],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        request_log.append(request)
        return httpx.Response(
            200,
            json=_upstream_response(correlation_id, screen),
            headers={"X-Correlation-ID": correlation_id},
        )

    async def run() -> AIInsightResponse:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), timeout=httpx.Timeout(2.5)
        ) as http_client:
            gateway = GenAIInsightClient(
                http_client=http_client,
                base_url="http://genai.test",
                service_token="s" * 40,
            )
            return await gateway.generate(
                {"screen": screen}, correlation_id=correlation_id
            )

    result = asyncio.run(run())

    assert result.status == "answered"
    assert len(request_log) == 1
    sent = request_log[0]
    assert sent.method == "POST"
    assert sent.url.path == "/api/v1/insights"
    assert sent.headers["authorization"] == f"Bearer {'s' * 40}"
    assert sent.headers["x-correlation-id"] == correlation_id
    assert json.loads(sent.read()) == {"screen": screen}
