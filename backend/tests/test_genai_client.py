"""Cobertura do transporte Backend → GenAI nos dois contratos publicados."""

import asyncio
import json
from typing import Any

import httpx
import pytest
from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.ai_insight import AIInsightRequest, AIInsightResponse
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)

CORRELATION_ID = "a" * 32
SERVICE_TOKEN = "s" * 40


def _question_response(correlation_id: str = CORRELATION_ID) -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "correlation_id": correlation_id,
        "audit_reference": None,
        "error": None,
        "status": "answered",
        "model_tier": "light",
        "answer": "Resposta demonstrativa.",
        "message": None,
        "evidence": [
            {
                "source": "synthetic.fixture",
                "description": "Cenário sintético.",
                "is_demo": True,
            }
        ],
        "limitations": ["Os valores são fictícios."],
        "analysis_context": None,
    }


def _insight_response(correlation_id: str = CORRELATION_ID) -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "correlation_id": correlation_id,
        "audit_reference": None,
        "error": None,
        "status": "answered",
        "context": {
            "metric": "Energia faturada",
            "unit": "kWh",
            "period": {
                "start": "2024-04-01",
                "end": "2024-04-30",
                "granularity": "month",
            },
            "filters": {"municipio": "Recife"},
        },
        "observation": {"values": [{"label": "Atual", "value": 45000}]},
        "hypothesis": "Investigue a composição deste recorte.",
        "message": None,
        "evidence": [
            {
                "source": "synthetic.panorama",
                "description": "Contexto sintético.",
                "is_demo": True,
            }
        ],
        "limitations": ["A hipótese não comprova uma causa."],
    }


def _question_request() -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "question": "Qual foi o consumo?",
        "context": [],
    }


def _insight_request() -> dict[str, Any]:
    return {
        "screen": {
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
                "description": "Lote sintético.",
                "is_demo": True,
            },
            "limitations": ["Valores fictícios."],
        }
    }


CLIENT_CASES = [
    pytest.param(
        "questions",
        _question_request,
        AIQuestionRequest,
        _question_response,
        AIQuestionResponse,
        GenAIQuestionClient,
        "ask",
        "/api/v1/questions",
        id="questions",
    ),
    pytest.param(
        "insights",
        _insight_request,
        AIInsightRequest,
        _insight_response,
        AIInsightResponse,
        GenAIInsightClient,
        "generate",
        "/api/v1/insights",
        id="insights",
    ),
]


def _client(client_type: type, http_client: httpx.AsyncClient, **configuration):
    return client_type(http_client=http_client, **configuration)


@pytest.mark.parametrize(
    "name,request_factory,request_type,response_factory,response_type,client_type,operation,path",
    CLIENT_CASES,
)
@pytest.mark.parametrize("payload_kind", ["dict", "model"])
def test_genai_clients_send_typed_or_dict_payload_and_validate_response(
    name,
    request_factory,
    request_type,
    response_factory,
    response_type,
    client_type,
    operation,
    path,
    payload_kind,
):
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(
            200,
            json=response_factory(),
            headers={"X-Correlation-ID": CORRELATION_ID},
        )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        ) as http_client:
            client = _client(
                client_type,
                http_client,
                base_url="http://genai.test/",
                service_token=SERVICE_TOKEN,
            )
            request = request_factory()
            payload = request_type.model_validate(request) if payload_kind == "model" else request
            return await getattr(client, operation)(
                payload, correlation_id=CORRELATION_ID
            )

    result = asyncio.run(run())

    assert isinstance(result, response_type)
    assert result.correlation_id == CORRELATION_ID
    assert len(sent) == 1
    assert sent[0].method == "POST"
    assert sent[0].url == f"http://genai.test{path}"
    assert sent[0].headers["authorization"] == f"Bearer {SERVICE_TOKEN}"
    assert sent[0].headers["x-correlation-id"] == CORRELATION_ID
    assert json.loads(sent[0].read()) == request_factory()


@pytest.mark.parametrize(
    "name,request_factory,request_type,response_factory,response_type,client_type,operation,path",
    CLIENT_CASES,
)
@pytest.mark.parametrize(
    "configuration",
    [
        {"base_url": None, "service_token": SERVICE_TOKEN},
        {"base_url": "http://genai.test", "service_token": None},
    ],
)
def test_genai_clients_reject_missing_configuration_without_request(
    name,
    request_factory,
    request_type,
    response_factory,
    response_type,
    client_type,
    operation,
    path,
    configuration,
):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_factory())

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        ) as http_client:
            client = _client(client_type, http_client, **configuration)
            await getattr(client, operation)(
                request_factory(), correlation_id=CORRELATION_ID
            )

    with pytest.raises(GenAIServiceUnavailable):
        asyncio.run(run())
    assert requests == []


@pytest.mark.parametrize(
    "name,request_factory,request_type,response_factory,response_type,client_type,operation,path",
    CLIENT_CASES,
)
@pytest.mark.parametrize(
    "handler,expected_error",
    [
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("private timeout", request=request)
            ),
            GenAITimeout,
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("private network detail", request=request)
            ),
            GenAIServiceUnavailable,
        ),
        (
            lambda request: httpx.Response(
                503,
                json={"detail": "private detail"},
                headers={"X-Correlation-ID": CORRELATION_ID},
            ),
            GenAIServiceUnavailable,
        ),
        (
            lambda request: httpx.Response(
                200,
                content=b"not-json",
                headers={"X-Correlation-ID": CORRELATION_ID},
            ),
            GenAIResponseInvalid,
        ),
        (
            lambda request: httpx.Response(
                200,
                json={"unexpected": "schema"},
                headers={"X-Correlation-ID": CORRELATION_ID},
            ),
            GenAIResponseInvalid,
        ),
    ],
)
def test_genai_clients_classify_transport_and_response_failures(
    name,
    request_factory,
    request_type,
    response_factory,
    response_type,
    client_type,
    operation,
    path,
    handler,
    expected_error,
):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = _client(
                client_type,
                http_client,
                base_url="http://genai.test",
                service_token=SERVICE_TOKEN,
            )
            await getattr(client, operation)(
                request_factory(), correlation_id=CORRELATION_ID
            )

    with pytest.raises(expected_error):
        asyncio.run(run())


@pytest.mark.parametrize(
    "name,request_factory,request_type,response_factory,response_type,client_type,operation,path",
    CLIENT_CASES,
)
@pytest.mark.parametrize("mismatch", ["header", "body"])
def test_genai_clients_reject_correlation_mismatch(
    name,
    request_factory,
    request_type,
    response_factory,
    response_type,
    client_type,
    operation,
    path,
    mismatch,
):
    def handle(request: httpx.Request) -> httpx.Response:
        response = response_factory("b" * 32 if mismatch == "body" else CORRELATION_ID)
        header_id = "b" * 32 if mismatch == "header" else CORRELATION_ID
        return httpx.Response(
            200,
            json=response,
            headers={"X-Correlation-ID": header_id},
        )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        ) as http_client:
            client = _client(
                client_type,
                http_client,
                base_url="http://genai.test",
                service_token=SERVICE_TOKEN,
            )
            await getattr(client, operation)(
                request_factory(), correlation_id=CORRELATION_ID
            )

    with pytest.raises(GenAIResponseInvalid):
        asyncio.run(run())


@pytest.mark.parametrize("change", ["none", "scope", "batch", "observation", "filters", "expired", "namespace"])
def test_gold_insight_reuses_only_same_authorized_context(monkeypatch, change):
    from app.services import genai_client as module
    now = [100.0]
    monkeypatch.setattr(module, "monotonic", lambda: now[0])
    calls = []
    response = _insight_response()
    response["evidence"][0].update(source="gold.local", is_demo=False)
    screen = {
        **response["context"], "observations": response["observation"]["values"],
        "reference": response["evidence"][0], "limitations": response["limitations"],
    }
    payload = {"screen": screen, "access_scope": {"caller_ref": "reader.one"},
               "batch_ref": "batch.one", "remaining_timeout_ms": 60000}

    async def transport(**kwargs):
        import copy
        calls.append(kwargs["payload"])
        result = copy.deepcopy(response)
        result["correlation_id"] = kwargs["correlation_id"]
        result["observation"]["values"] = kwargs["payload"]["screen"]["observations"]
        result["context"] = {k: v for k, v in kwargs["payload"]["screen"].items()
                             if k not in {"observations", "reference", "limitations"}}
        return result
    monkeypatch.setattr(module, "_post_genai_json", transport)

    async def run():
        import copy
        async with httpx.AsyncClient() as http:
            client = GenAIInsightClient(http_client=http, base_url="http://genai", service_token=SERVICE_TOKEN)
            first = await client.synthesize_gold(payload, correlation_id=CORRELATION_ID)
            # Consuming code must not mutate the cached copy.
            first.hypothesis = "modified locally"
            newer = copy.deepcopy(payload)
            newer["remaining_timeout_ms"] = 40000
            if change == "scope": newer["access_scope"]["caller_ref"] = "reader.two"
            if change == "batch": newer["batch_ref"] = "batch.two"
            if change == "filters": newer["screen"]["filters"]["comparacao"] = "ano_anterior"
            if change == "observation": newer["screen"]["observations"][0]["value"] = 123
            if change == "expired": now[0] += 121
            if change == "namespace": client._cache_namespace = "another-model-prompt-version"
            second = await client.synthesize_gold(newer, correlation_id="b" * 32)
            assert second.correlation_id == "b" * 32
            assert second.hypothesis != "modified locally"
            assert second.audit_reference is None
        assert len(calls) == (1 if change == "none" else 2)
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["shared", "disabled", "oversized", "cancel_one", "cancel_all", "failure"])
def test_gold_insight_cache_concurrency_and_limits(monkeypatch, mode):
    from app.services import genai_client as module
    calls = []
    response = _insight_response()
    response["evidence"][0].update(source="gold.local", is_demo=False)
    payload = {"screen": {**response["context"],
        "observations": response["observation"]["values"],
        "reference": response["evidence"][0], "limitations": response["limitations"]},
        "access_scope": {"caller_ref": "reader.one"}, "batch_ref": "batch.one"}
    started = None
    release = None

    async def transport(**kwargs):
        import copy
        calls.append(1)
        started.set()
        await release.wait()
        if mode == "failure" and len(calls) == 1:
            raise GenAIServiceUnavailable()
        result = copy.deepcopy(response)
        result["correlation_id"] = kwargs["correlation_id"]
        return result
    monkeypatch.setattr(module, "_post_genai_json", transport)

    async def run():
        nonlocal started, release
        started, release = asyncio.Event(), asyncio.Event()
        async with httpx.AsyncClient() as http:
            client = GenAIInsightClient(http_client=http, base_url="http://genai",
                service_token=SERVICE_TOKEN, cache_ttl_seconds=0 if mode == "disabled" else 120,
                cache_max_bytes=1 if mode == "oversized" else 1048576)
            leader = asyncio.create_task(client.synthesize_gold(payload, correlation_id=CORRELATION_ID))
            await started.wait()
            follower = asyncio.create_task(client.synthesize_gold(payload, correlation_id="b" * 32))
            await asyncio.sleep(0)
            if mode == "cancel_all":
                leader.cancel()
                follower.cancel()
                await asyncio.gather(leader, follower, return_exceptions=True)
                await asyncio.sleep(0)
                assert not client._gold_pending and not client._gold_waiters
                release.set()
                await client.synthesize_gold(payload, correlation_id="c" * 32)
                return
            if mode == "cancel_one":
                leader.cancel()
            release.set()
            results = await asyncio.gather(leader, follower, return_exceptions=True)
            if mode == "failure":
                assert all(isinstance(r, GenAIServiceUnavailable) for r in results)
            else:
                assert results[1].correlation_id == "b" * 32
            await client.synthesize_gold(payload, correlation_id="c" * 32)
            assert not client._gold_pending and not client._gold_waiters
            assert client._cache_bytes <= client._cache_bytes_limit
    asyncio.run(run())
    assert len(calls) == {"shared": 1, "disabled": 3, "oversized": 2,
                          "cancel_one": 1, "cancel_all": 2, "failure": 2}[mode]
