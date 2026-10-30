"""B11: mesmos vetores do Backend e prova da síntese pelo núcleo composto."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.evidence import EvidenceLookupResult
from app.schemas.internal import QuestionPlanRequest, QuestionPlanResponse, QuestionSynthesisRequest
from app.schemas.questions import QuestionRequest, QuestionResponse

from .test_core_plan_synthesis import SpyModel, SpySource, _core
from .test_internal_contract_examples import _gold_profile

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
    "synthesis_response": QuestionResponse,
}


def _normalize(payload):
    if "access_scope" in payload:
        for field in ("allowed_operations", "allowed_metric_ids", "allowed_dimension_ids"):
            payload["access_scope"][field] = sorted(payload["access_scope"][field])
    return payload


@pytest.mark.parametrize("vector", FIXTURE["valid"], ids=lambda vector: vector["id"])
def test_genai_preserves_the_same_wire_envelopes_as_backend(vector):
    parsed = SCHEMAS[vector["kind"]].model_validate(vector["payload"])
    assert _normalize(parsed.model_dump(mode="json")) == vector["payload"]


@pytest.mark.parametrize("vector", FIXTURE["invalid"], ids=lambda vector: vector["id"])
def test_genai_rejects_the_same_invalid_envelopes_as_backend(vector):
    with pytest.raises(ValidationError):
        SCHEMAS[vector["kind"]].model_validate(vector["payload"])


def test_public_request_does_not_accept_backend_scope_or_publication():
    payload = next(v["payload"] for v in FIXTURE["valid"] if v["kind"] == "plan_request")
    with pytest.raises(ValidationError):
        QuestionRequest.model_validate(payload)


@pytest.mark.parametrize("status", ["no_evidence", "needs_clarification"])
def test_b9_empty_or_clarification_synthesis_uses_core_without_model_or_source(status):
    payload = next(
        v["payload"] for v in FIXTURE["valid"] if v["id"] == "request-synthesis-" + status
    )
    source, model = SpySource(), SpyModel()
    core = _core(source=source, model=model, profile=_gold_profile(), source_id="gold.local")

    response = asyncio.run(
        core.synthesize(QuestionSynthesisRequest.model_validate(payload), FIXTURE["correlation_id"])
    )

    assert response.status.value == status
    assert response.answer is None and response.evidence == []
    assert source.calls == model.calls == 0


@pytest.mark.parametrize("case", ["publication", "scope"])
def test_synthesis_core_revalidates_publication_and_scope_before_model(case):
    payload = deepcopy(
        next(v["payload"] for v in FIXTURE["valid"] if v["id"] == "request-synthesis-available")
    )
    if case == "publication":
        payload["expected_batch_ref"] = (
            "gold-csv-v1:GOLD_20250101T000000Z_aaaaaaaa:00000000-0000-4000-8000-000000000001"
        )
    else:
        payload["access_scope"]["allowed_metric_ids"] = []
    source, model = SpySource(), SpyModel()
    core = _core(source=source, model=model, profile=_gold_profile(), source_id="gold.local")
    response = asyncio.run(
        core.synthesize(QuestionSynthesisRequest.model_validate(payload), FIXTURE["correlation_id"])
    )
    assert response.status.value == ("recoverable_error" if case == "publication" else "refused")
    assert source.calls == model.calls == 0
