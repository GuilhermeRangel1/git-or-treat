"""Transporte de teste entre serviços sem importar os respectivos módulos app."""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

_CODE = """
import asyncio, json, sys, os, httpx
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
class NoSource:
    async def retrieve(self, *args, **kwargs):
        raise AssertionError('Backend must execute Gold')
class Model:
    async def generate(self, question, context, evidence):
        if os.environ.get('GENAI_TEST_MODEL_FAILURE') == 'unavailable':
            raise ModelProviderUnavailable('private provider detail')
        return GeneratedAnswer(status='answered', answer='Resultado observado no recorte solicitado.',
                               observation_ids=('row_1',))
class Audit:
    durable = True
    def record(self, event):
        pass
incoming = json.load(sys.stdin)
audit_url = os.environ.get('GENAI_TEST_AUDIT_URL')
if audit_url:
    from app.audit import BackendEventSink
    sink = BackendEventSink(audit_url, os.environ.get(
        'GENAI_TEST_AUDIT_TOKEN', 'synthetic-audit-token-for-integration-00000000'))
else:
    sink = Audit()
app = create_app(settings=Settings(_env_file=None, enable_demo_access=False,
        service_api_token='test-coordination-service-token-0000000000'),
    domain_profile=GRID360_GOLD_PROFILE, source_id='gold.local', source_mode='external',
    evidence_source=NoSource(), model_adapter=Model(),
    access_context_resolver=lambda request: None, event_sink=sink, require_durable_audit=True)
async def send():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://genai') as c:
        r = await c.post(incoming['path'],json=incoming['payload'],headers=incoming['headers'])
        return {'status':r.status_code,'body':r.json(),'headers':dict(r.headers)}
print(json.dumps(asyncio.run(send())))
"""

GENAI_TRANSPORT_EVENTS: list[dict[str, object]] = []


def dispatch_genai(request: httpx.Request) -> httpx.Response:
    request_payload = json.loads(request.content)
    completed = subprocess.run(
        [sys.executable, "-c", _CODE],
        input=json.dumps({"path": request.url.path, "payload": request_payload,
                          "headers": {
                              "authorization": request.headers.get("authorization", ""),
                              "x-correlation-id": request.headers.get("x-correlation-id", ""),
                          }}),
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=30,
        cwd=Path(__file__).resolve().parents[3] / "ai-agent",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == 200, result
    GENAI_TRANSPORT_EVENTS.append({
        "path": request.url.path,
        "correlation_id": request.headers.get("x-correlation-id"),
        "request": request_payload,
        "response": result["body"],
    })
    return httpx.Response(result["status"], json=result["body"], headers=result["headers"])
