import asyncio
import copy
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from app.schemas.sql_generation import SqlGenerationRequest
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/contracts/examples/text-to-sql-f1-http-v1.json").read_text(
    encoding="utf-8"
))


async def send(transport, *, timeout_ms=30000):
    payload = SqlGenerationRequest.model_validate({
        **DATA["request"], "remaining_timeout_ms": timeout_ms,
    })
    async with httpx.AsyncClient(transport=transport) as http:
        client = GenAIQuestionClient(http_client=http, base_url="http://genai",
                                     service_token="synthetic-service-token-0000000000")
        return await client.generate_sql_candidate(payload, correlation_id="b" * 32)


def test_client_sends_only_typed_context_to_new_internal_endpoint():
    def handler(request):
        assert request.url.path == "/api/v1/internal/sql-candidates"
        assert request.headers["authorization"] == "Bearer synthetic-service-token-0000000000"
        assert request.headers["x-correlation-id"] == "b" * 32
        assert json.loads(request.content) == DATA["request"]
        return httpx.Response(200, json=DATA["response"], headers={"x-correlation-id": "b" * 32})

    result = asyncio.run(send(httpx.MockTransport(handler)))
    assert result.candidate.status == "sql_candidate"


@pytest.mark.parametrize("mutation", ["correlation", "context", "extra", "header"])
def test_client_rejects_unbound_or_unexpected_response(mutation):
    response = copy.deepcopy(DATA["response"])
    headers = {"x-correlation-id": "b" * 32}
    if mutation == "correlation":
        response["correlation_id"] = "c" * 32
    elif mutation == "context":
        response["candidate"]["context_version"] = "c" * 64
    elif mutation == "extra":
        response["validated"] = True
    else:
        headers = {}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response, headers=headers))
    with pytest.raises(GenAIResponseInvalid):
        asyncio.run(send(transport))


def test_unavailable_transport_does_not_become_clarification():
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable"))
    with pytest.raises(GenAIServiceUnavailable):
        asyncio.run(send(transport))


def test_client_respects_remaining_budget_during_transport():
    async def handler(request):
        await asyncio.Event().wait()

    with pytest.raises(GenAITimeout):
        asyncio.run(send(httpx.MockTransport(handler), timeout_ms=10))


def test_backend_client_reaches_official_gold_factory_in_independent_process():
    code = """
import asyncio, json, sys, httpx
from app.config import Settings
from app.gold_runtime import create_gold_app
from app import main
from app.audit import BackendEventSink
from app.schemas.sql_generation import SqlGenerationCandidate
incoming = json.load(sys.stdin)
class Generator:
    async def generate(self, contents, **kwargs):
        return SqlGenerationCandidate.model_validate(incoming['candidate'])
class Model:
    async def generate(self, *args, **kwargs):
        raise AssertionError('Legacy model must not be called')
main.build_model_adapter = lambda settings: Model()
main.build_sql_generator = lambda settings: Generator()
BackendEventSink.record = lambda self, event: None
app = create_gold_app(Settings(_env_file=None,
    service_api_token='synthetic-service-token-0000000000',sql_generation_enabled=True,
    documentation_search_enabled=False,
    audit_url='http://backend/api/v1/internal/genai-audit-events',
    audit_write_token='synthetic-audit-token-000000000000000'))
async def run():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://genai') as c:
        r = await c.post('/api/v1/internal/sql-candidates',json=incoming['payload'],
            headers={'authorization':'Bearer synthetic-service-token-0000000000','x-correlation-id':'b'*32})
        return {'status':r.status_code,'body':r.json(),'headers':dict(r.headers)}
print(json.dumps(asyncio.run(run())))
"""

    def handler(request):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code], cwd=ROOT / "ai-agent",
            input=json.dumps({"payload": json.loads(request.content),
                              "candidate": DATA["response"]["candidate"]}),
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        )
        assert result.returncode == 0, result.stderr
        actual = json.loads(result.stdout)
        return httpx.Response(actual["status"], json=actual["body"], headers=actual["headers"])

    result = asyncio.run(send(httpx.MockTransport(handler)))
    assert result.correlation_id == "b" * 32
    assert result.candidate.sql == DATA["response"]["candidate"]["sql"]
