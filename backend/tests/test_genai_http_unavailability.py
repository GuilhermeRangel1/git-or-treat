"""Regressões pela API pública com transporte privado controlado."""

import asyncio

import httpx
import pytest

from tests.support.platform_auth import login_as_profile

from app.main import app
from app.services.genai_client import GenAIInsightClient, GenAIQuestionClient


@pytest.fixture(autouse=True)
def authenticated_commercial_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial")


@pytest.mark.parametrize("kind", ["questions", "insights"])
@pytest.mark.parametrize(
    "upstream_status,structured,retryable,expected_status,expected_retryable,fault",
    [
        (503, False, True, 503, True, None),
        (503, False, True, 503, True, {"status": 503}),
        (503, True, True, 503, True, None),
        (503, True, False, 503, False, None),
        (502, False, True, 502, False, None),
        (401, False, True, 502, False, None),
        (200, False, True, 502, False, None),
        (503, True, True, 502, False, {"contract_version": "v2"}),
        (503, True, True, 502, False, {"correlation_id": "b" * 32}),
        (
            503,
            True,
            True,
            502,
            False,
            {"error": {"code": "service_unavailable", "retryable": "yes"}},
        ),
    ],
)
def test_public_api_classifies_upstream_failures(
    client,
    monkeypatch,
    kind,
    upstream_status,
    structured,
    retryable,
    expected_status,
    expected_retryable,
    fault,
):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")
    calls = []

    def handle(request):
        calls.append(request)
        cid = request.headers["x-correlation-id"]
        body = (
            {
                "contract_version": "v1",
                "status": "error",
                "correlation_id": cid,
                "message": "private diagnostic",
                "error": {"code": "service_unavailable", "retryable": retryable},
            }
            if structured
            else {"detail": "private diagnostic"}
        )
        if fault:
            body.update(fault)
        return httpx.Response(
            upstream_status, json=body, headers={"X-Correlation-ID": cid}
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    gateway_type = GenAIQuestionClient if kind == "questions" else GenAIInsightClient
    attribute = (
        "genai_question_client" if kind == "questions" else "genai_insight_client"
    )
    monkeypatch.setattr(
        app.state,
        attribute,
        gateway_type(
            http_client=transport, base_url="http://genai.test", service_token="s" * 40
        ),
    )
    payload = (
        {"question": "Qual o consumo?"}
        if kind == "questions"
        else {
            "filters": {
                "periodo": "2024-04",
                "comparacao": "anterior",
                "municipio": "Recife",
                "classe": "Residencial",
            },
            "loteVersao": "panorama-sintetico-2024.04-v1",
        }
    )
    try:
        response = client.post(f"/api/v1/ai/{kind}", json=payload)
    finally:
        asyncio.run(transport.aclose())

    assert response.status_code == expected_status
    assert response.json()["error"] == {
        "code": "service_unavailable"
        if expected_status == 503
        else "invalid_upstream_response",
        "retryable": expected_retryable,
    }
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert "private diagnostic" not in response.text
    assert len(calls) == 1
