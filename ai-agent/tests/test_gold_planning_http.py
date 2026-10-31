"""Fronteiras reais do planejamento v2, sem modelo remoto ou dataset privado."""

import pytest

from app.api.application import create_api_application
from app.config import Settings
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_question_filters import _setup

TOKEN = "test-internal-gold-token-000000000000"
PLAN_PATH = "/api/v1/internal/question-plans"
SYNTHESIS_PATH = "/api/v1/internal/question-syntheses"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Correlation-ID": "a" * 32}


def _application(core, *, token=TOKEN, mode="external"):
    # Borda real com o mesmo núcleo composto; não simula os handlers HTTP.
    return create_api_application(
        settings=Settings(_env_file=None, enable_demo_access=False, service_api_token=token),
        question_handler=core.question,
        insight_handler=core.insight,
        domain_profile=GRID360_GOLD_PROFILE,
        source_id="gold.local",
        source_mode=mode,
        access_context_resolver=None,
    )


def test_http_plan_preserves_canonical_filters_and_partial_calendar():
    core, request = _setup("Receita residencial em Olinda este ano?")
    with InProcessClient(_application(core)) as client:
        response = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "a" * 32
    result = response.json()
    assert result["status"] == "planned"
    assert result["correlation_id"] == "a" * 32
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["window"]["start"] == "2025-01-01"
    assert plan["window"]["end"] == "2025-03-31"
    assert plan["limit"] == 100
    assert plan["order"] is None
    assert plan["group_by_dimension_ids"] == []
    assert {f["dimension_id"]: f["values"] for f in plan["filters"]} == {
        "geography.municipality": ["Olinda"],
        "customer.consumption_class": ["RESIDENCIAL"],
    }


@pytest.mark.parametrize("path", [PLAN_PATH, SYNTHESIS_PATH])
def test_internal_operations_require_token_and_external_composition(path):
    core, request = _setup("Receita em Olinda em março de 2025?")
    payload = request.model_dump(mode="json")
    with InProcessClient(_application(core)) as client:
        assert client.post(path, json=payload).status_code == 401
    for options in ({"token": None}, {"mode": "demo"}):
        with InProcessClient(_application(core, **options)) as client:
            assert client.post(path, json=payload, headers=HEADERS).status_code == 503


def test_http_plan_reapplies_scope_and_returns_specific_clarification():
    core, request = _setup("Receita residencial em Olinda em março de 2025?")
    with InProcessClient(_application(core)) as client:
        payload = request.model_dump(mode="json")
        payload["access_scope"]["allowed_dimension_ids"].remove("generation.distributed")
        payload["question"] = "Receita com GD em março de 2025?"
        denied = client.post(PLAN_PATH, json=payload, headers=HEADERS)
        assert denied.json()["status"] == "refused"
        payload = request.model_dump(mode="json")
        payload["question"] = "Receita em Olinda em junho de 2025?"
        absent = client.post(PLAN_PATH, json=payload, headers=HEADERS)
        assert absent.json()["status"] == "needs_clarification"
        assert absent.json()["plan"] is None


def test_http_synthesis_preserves_zero_and_rejects_changed_publication():
    core, request = _setup("Receita residencial em Olinda em março de 2025?")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref, value=0)
        lookup.evidence.records[0]["period"] = "2025-03"
        lookup.evidence.records[0]["municipality"] = "Olinda"
        lookup.evidence.records[0]["consumption_class"] = "RESIDENCIAL"
        synthesis = QuestionSynthesisRequest(
            question=request.question,
            access_scope=request.access_scope,
            remaining_timeout_ms=35000,
            plan=plan,
            plan_fingerprint=planned["plan_fingerprint"],
            lookup=lookup,
            expected_batch_ref=request.batch_ref,
        ).model_dump(mode="json")
        result = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert result.status_code == 200
        assert result.json()["status"] == "answered"
        assert "0 R$" in result.json()["answer"]
        assert result.json()["analysis_context"]["period"] == "2025-03-01 a 2025-03-31"
        # Ausência de medida não pode virar o zero observado acima.
        record = synthesis["lookup"]["evidence"]["records"][0]
        for missing_value in (None, "absent"):
            if missing_value is None:
                record["value"] = None
            else:
                record.pop("value")
            missing = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
            assert missing.status_code == 200
            assert missing.json()["status"] == "recoverable_error"
            assert missing.json()["evidence"] == []
        record["value"] = 0
        comparison = request.model_dump(mode="json")
        comparison["question"] = (
            "Compare a receita residencial em Olinda de fevereiro de 2025 "
            "com março de 2025, com base zero."
        )
        unsupported = client.post(PLAN_PATH, json=comparison, headers=HEADERS)
        assert unsupported.status_code == 200
        assert unsupported.json()["status"] == "needs_clarification"
        assert unsupported.json()["plan"] is None
        synthesis["lookup"]["evidence"]["records"][0]["municipality"] = "Recife"
        outside = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert outside.json()["status"] == "recoverable_error"
        synthesis["lookup"]["evidence"]["records"][0]["municipality"] = "Olinda"
        synthesis["expected_batch_ref"] = request.batch_ref.replace("12345678", "87654321")
        changed = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert changed.json()["status"] == "recoverable_error"
