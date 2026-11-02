"""Provedores selecionam observações Gold pela composição HTTP, sem prosa numérica."""
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.gemini import GeminiModelAdapter
from app.providers.groq import GroqModelAdapter
from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_catalog_v2 import NoLookup
from .test_gold_planning_http import HEADERS, PLAN_PATH, SYNTHESIS_PATH, _application
from .test_gold_question_filters import _setup


@pytest.mark.parametrize("provider", ["gemini", "groq"])
@pytest.mark.parametrize("payload,expected", [
    ({"status": "answered", "observation_ids": ["row_1"]}, "answered"),
    ({"status": "answered", "observation_ids": ["row_99"]}, "refused"),
    ({"status": "answered", "observation_ids": ["row_1", "row_1"]}, "refused"),
    ({"status": "answered", "observation_ids": ["row_1"], "answer": "30%"},
     "recoverable_error"),
    ({"status": "answered", "observation_ids": ["row_1"], "claims": []},
     "recoverable_error"),
])
def test_gold_provider_selection_preserves_guards_at_http_boundary(provider, payload, expected):
    calls = []

    def check_schema(schema):
        assert set(schema["properties"]) == {"status", "observation_ids"}
        assert schema["additionalProperties"] is False

    class Endpoint:
        async def generate_content(self, **kwargs):
            calls.append(provider)
            check_schema(kwargs["config"]["response_json_schema"])
            return SimpleNamespace(text=json.dumps(payload))

    def transport(request):
        calls.append(provider)
        content = json.loads(request.content)["messages"][0]["content"]
        schema = json.loads(content.split("esquema JSON:\n", 1)[1])
        check_schema(schema)
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps(payload)},
        }]})

    adapter = (
        GeminiModelAdapter(model_name="test", client=SimpleNamespace(
            aio=SimpleNamespace(models=Endpoint())))
        if provider == "gemini" else GroqModelAdapter(
            model_name="test", api_key=SecretStr("fake-test-key"),
            transport=httpx.MockTransport(transport))
    )
    core = compose_core(
        profile=GRID360_GOLD_PROFILE, source_id="gold.local", evidence_source=NoLookup(),
        model_adapter=adapter, execution_controller=ExecutionController(),
    )
    _, request = _setup("Receita residencial em março de 2025?")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert planned["status"] == "planned"
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records[0]["period"] = "2025-03"
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
        )
        response = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        )
    assert calls == [provider]
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == expected, result
    if expected == "answered":
        assert "R$ 12,00" in result["answer"]
        assert "março de 2025" in result["answer"]
        assert result["evidence"] and result["analysis_context"]["unit"] == "R$"
    else:
        assert result["answer"] is None
