"""Transporte de teste entre serviços sem importar os respectivos módulos app."""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

_CODE = """
import asyncio, json, sys, httpx
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.protocols import GeneratedAnswer
class NoSource:
    async def retrieve(self, *args, **kwargs):
        raise AssertionError('Backend must execute Gold')
class Model:
    async def generate(self, question, context, evidence):
        return GeneratedAnswer(status='answered', answer='Resultado observado no recorte solicitado.',
                               observation_ids=('row_1',))
class Audit:
    durable = True
    def record(self, event):
        pass
incoming = json.load(sys.stdin)
app = create_app(settings=Settings(_env_file=None, enable_demo_access=False,
        service_api_token='test-coordination-service-token-0000000000'),
    domain_profile=GRID360_GOLD_PROFILE, source_id='gold.local', source_mode='external',
    evidence_source=NoSource(), model_adapter=Model(),
    access_context_resolver=lambda request: None, event_sink=Audit(), require_durable_audit=True)
async def send():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://genai') as c:
        r = await c.post(incoming['path'],json=incoming['payload'],headers=incoming['headers'])
        return {'status':r.status_code,'body':r.json(),'headers':dict(r.headers)}
print(json.dumps(asyncio.run(send())))
"""


def dispatch_genai(request: httpx.Request) -> httpx.Response:
    completed = subprocess.run(
        [sys.executable, "-c", _CODE],
        input=json.dumps({"path": request.url.path,
                          "payload": json.loads(request.content),
                          "headers": dict(request.headers)}),
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=30,
        cwd=Path(__file__).resolve().parents[3] / "ai-agent",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == 200, result
    return httpx.Response(result["status"], json=result["body"], headers=result["headers"])
