"""Vetores de wire v1 usados também pela suíte GenAI, sem importar outro serviço."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_evidence import EvidenceLookupResult
from app.schemas.genai_internal import (
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionSynthesisRequest,
)
from app.services.genai_client import GenAIResponseInvalid
from app.services.genai_contracts import validate_plan_response, validate_synthesis_response
from app.services.genai_flow import should_synthesize

FIXTURE = json.loads(
    (
        Path(__file__).parents[2] / "docs/contracts/examples/genai-internal-contract-v1.json"
    ).read_text(encoding="utf-8")
)
SCHEMAS = {
    "plan_request": QuestionPlanRequest,
    "plan_response": QuestionPlanResponse,
    "lookup": EvidenceLookupResult,
    "synthesis_request": QuestionSynthesisRequest,
    "synthesis_response": AIQuestionResponse,
}


def _normalize(payload):
    if "access_scope" in payload:
        scope = payload["access_scope"]
        for field in ("allowed_operations", "allowed_metric_ids", "allowed_dimension_ids"):
            scope[field] = sorted(scope[field])
    return payload


@pytest.mark.parametrize("vector", FIXTURE["valid"], ids=lambda vector: vector["id"])
def test_backend_preserves_valid_wire_envelopes(vector):
    parsed = SCHEMAS[vector["kind"]].model_validate(vector["payload"])
    assert _normalize(parsed.model_dump(mode="json")) == vector["payload"]


@pytest.mark.parametrize("vector", FIXTURE["invalid"], ids=lambda vector: vector["id"])
def test_backend_rejects_invalid_shared_envelopes(vector):
    with pytest.raises(ValidationError):
        SCHEMAS[vector["kind"]].model_validate(vector["payload"])


RESPONSES = [v for v in FIXTURE["valid"] if v["kind"] in {"plan_response", "synthesis_response"}]


@pytest.mark.parametrize("vector", RESPONSES, ids=lambda vector: vector["id"])
def test_response_helpers_require_matching_body_and_header_correlation(vector):
    validate = (
        validate_plan_response if vector["kind"] == "plan_response" else validate_synthesis_response
    )
    correlation = FIXTURE["correlation_id"]
    assert (
        validate(
            vector["payload"], correlation_id=correlation, header_correlation_id=correlation
        ).correlation_id
        == correlation
    )
    for header in (None, "a" * 32):
        with pytest.raises(GenAIResponseInvalid):
            validate(vector["payload"], correlation_id=correlation, header_correlation_id=header)
    for body_correlation in (None, "a" * 32):
        payload = {**vector["payload"], "correlation_id": body_correlation}
        with pytest.raises(GenAIResponseInvalid):
            validate(payload, correlation_id=correlation, header_correlation_id=correlation)
    with pytest.raises(GenAIResponseInvalid):
        validate(
            {**vector["payload"], "contract_version": "v2"},
            correlation_id=correlation,
            header_correlation_id=correlation,
        )


def test_public_request_does_not_accept_internal_scope_or_publication():
    payload = next(v["payload"] for v in FIXTURE["valid"] if v["kind"] == "plan_request")
    with pytest.raises(ValidationError):
        AIQuestionRequest.model_validate(payload)


def test_public_http_route_rejects_internal_envelope(client):
    payload = next(v["payload"] for v in FIXTURE["valid"] if v["kind"] == "plan_request")
    response = client.post("/api/v1/ai/questions", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    "vector",
    [v for v in FIXTURE["valid"] if v["kind"] == "lookup"],
    ids=lambda vector: vector["id"],
)
def test_b9_decision_accepts_the_same_lookups_as_genai(vector):
    assert should_synthesize(
        planning_status="planned", lookup=deepcopy(vector["payload"]), policy="completed_lookup"
    )
