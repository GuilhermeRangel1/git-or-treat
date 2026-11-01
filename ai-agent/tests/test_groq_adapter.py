import asyncio
import hashlib
import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.config import Settings
from app.generation.prompts import SYSTEM_INSTRUCTION
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.caching import CachingModelAdapter
from app.providers.factory import (
    ModelConfigurationError,
    build_model_adapter,
    build_model_router,
)
from app.providers.fallback import FallbackModelAdapter
from app.providers.gemini import GeminiModelAdapter
from app.providers.groq import GROQ_CHAT_COMPLETIONS_URL, SYSTEM_PROMPT, GroqModelAdapter
from app.providers.protocols import (
    GeneratedAnswer,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.providers.routing import ModelTier
from app.schemas.evidence import EvidenceProvenance, EvidenceResult
from app.schemas.questions import (
    ConversationTurn,
    EvidenceReference,
    QuestionRequest,
    QuestionStatus,
)
from app.schemas.read_plan import ReadWindow, WindowKind
from app.tools.synthetic_analytics import SyntheticScenarioTool

FAKE_KEY = "fake-groq-key-for-test"
QUESTION = "Qual foi o consumo no período de demonstração?"
ANSWER = GeneratedAnswer(
    status="answered",
    answer="O consumo foi 42 unidades fictícias.",
    observation_ids=("row_1",),
)


def _evidence() -> EvidenceResult:
    source = "synthetic_fixture:consumption_demo"
    return EvidenceResult(
        reference=EvidenceReference(
            source=source,
            description="Resultado artificial para teste, sem dados da V-Energy.",
            is_demo=True,
        ),
        records=[
            {
                "observation_id": "row_1",
                "metric": "consumption_demo",
                "value": 42,
                "unit": "unidades fictícias",
            }
        ],
        provenance=EvidenceProvenance(
            source_id="synthetic_fixture",
            reference_source=source,
            plan_fingerprint="0" * 64,
            catalog_version="v1",
            metric_id="consumption_demo",
            unit="unidades fictícias",
            window=ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase="período de teste"),
        ),
        cache_scope=hashlib.sha256(b"caller-a").hexdigest(),
    )


def _completion(content: object) -> dict[str, object]:
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]}


class RecordingHandler:
    """Responde como o endpoint de chat do Groq e guarda as requisições recebidas."""

    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _adapter(handler: RecordingHandler, model_name: str = "groq-test-model") -> GroqModelAdapter:
    return GroqModelAdapter(
        model_name=model_name,
        api_key=SecretStr(FAKE_KEY),
        transport=httpx.MockTransport(handler),
    )


def _generate(adapter, question: str = QUESTION, context=None) -> GeneratedAnswer:
    return asyncio.run(adapter.generate(question, context or [], _evidence()))


class RoutingGeminiEndpoint:
    """Simula o SDK Gemini: falha para modelos listados em ``failing``."""

    def __init__(self, failing: set[str], calls: list[str]) -> None:
        self.failing = failing
        self.calls = calls

    async def generate_content(self, *, model, **kwargs):
        self.calls.append(f"gemini:{model}")
        if model in self.failing:
            raise ConnectionError(f"{FAKE_KEY} cota esgotada")
        return type("Response", (), {"text": ANSWER.model_dump_json()})()


def _gemini_client(endpoint: RoutingGeminiEndpoint):
    client = type("Client", (), {})()
    client.aio = type("AsyncClient", (), {})()
    client.aio.models = endpoint
    return client


def _groq_client(calls: list[str], response: httpx.Response) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"groq:{json.loads(request.content)['model']}")
        return response

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# Adaptador


def test_groq_request_targets_chat_completions_with_bearer_key_and_json_mode() -> None:
    handler = RecordingHandler(httpx.Response(200, json=_completion(ANSWER.model_dump_json())))

    _generate(
        _adapter(handler),
        context=[ConversationTurn(role="user", content="Pergunta anterior")],
    )

    request = handler.requests[0]
    assert request.method == "POST"
    assert str(request.url) == GROQ_CHAT_COMPLETIONS_URL
    assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    body = json.loads(request.content)
    assert body["model"] == "groq-test-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    system, user = body["messages"]
    assert system["role"] == "system"
    assert system["content"].startswith(SYSTEM_INSTRUCTION)
    assert "JSON" in system["content"]
    assert json.dumps(GeneratedAnswer.model_json_schema(), ensure_ascii=False) in system["content"]
    assert user["role"] == "user"
    prompt = json.loads(user["content"])
    assert prompt["glossary"] == {
        "metric_id": "consumption_demo", "unit": "unidades fictícias",
        "source_id": "synthetic_fixture",
    }
    assert "genai-grounding-v3" in system["content"]
    assert prompt["question"] == QUESTION
    assert prompt["context"] == [{"role": "user", "content": "Pergunta anterior"}]
    assert prompt["evidence"]["reference"]["source"] == "synthetic_fixture:consumption_demo"
    assert prompt["evidence"]["records"][0]["observation_id"] == "row_1"
    assert "cache_scope" not in prompt["evidence"]


def test_groq_system_prompt_carries_current_answer_schema() -> None:
    schema = json.loads(SYSTEM_PROMPT.splitlines()[-1])

    assert schema == GeneratedAnswer.model_json_schema()
    assert "observation_ids" in schema["properties"]
    assert "observation_ids" in SYSTEM_INSTRUCTION


def test_groq_adapter_parses_structured_response() -> None:
    handler = RecordingHandler(httpx.Response(200, json=_completion(ANSWER.model_dump_json())))

    assert _generate(_adapter(handler)) == ANSWER


def test_groq_adapter_uses_injected_client() -> None:
    handler = RecordingHandler(httpx.Response(200, json=_completion(ANSWER.model_dump_json())))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = GroqModelAdapter(
                model_name="groq-test-model", api_key=SecretStr(FAKE_KEY), client=client
            )
            return await adapter.generate(QUESTION, [], _evidence())

    assert asyncio.run(run()) == ANSWER
    assert handler.requests[0].headers["Authorization"] == f"Bearer {FAKE_KEY}"


def test_groq_adapter_requires_a_key() -> None:
    with pytest.raises(ValueError):
        GroqModelAdapter(model_name="groq-test-model", api_key=SecretStr("  "))


FAILURES: dict[str, tuple[httpx.Response | Exception, type[Exception]]] = {
    "timeout": (
        httpx.ReadTimeout(f"timeout {FAKE_KEY} {QUESTION}"),
        ModelProviderUnavailable,
    ),
    "network": (
        httpx.ConnectError(f"conexão recusada {FAKE_KEY} {QUESTION}"),
        ModelProviderUnavailable,
    ),
    "http-400": (
        httpx.Response(400, text=f'{{"error":"{FAKE_KEY} {QUESTION}"}}'),
        ModelProviderRejected,
    ),
    "http-401": (
        httpx.Response(401, text=f'{{"error":"Invalid API Key {FAKE_KEY}"}}'),
        ModelProviderRejected,
    ),
    "http-404": (
        httpx.Response(404, text=f"modelo inexistente {QUESTION}"),
        ModelProviderRejected,
    ),
    "http-429": (
        httpx.Response(429, text=f'{{"error":"rate limit {QUESTION}"}}'),
        ModelProviderUnavailable,
    ),
    "http-500": (
        httpx.Response(500, text=f"erro interno {FAKE_KEY} {QUESTION}"),
        ModelProviderUnavailable,
    ),
    "http-503": (httpx.Response(503, text="serviço indisponível"), ModelProviderUnavailable),
    "empty-body": (httpx.Response(200, content=b""), ModelProviderInvalidResponse),
    "empty-content": (httpx.Response(200, json=_completion("")), ModelProviderInvalidResponse),
    "null-content": (httpx.Response(200, json=_completion(None)), ModelProviderInvalidResponse),
    "no-choices": (httpx.Response(200, json={"choices": []}), ModelProviderInvalidResponse),
    "body-not-json": (
        httpx.Response(200, text=f"<html>{FAKE_KEY} {QUESTION}</html>"),
        ModelProviderInvalidResponse,
    ),
    "content-not-json": (
        httpx.Response(200, json=_completion(f"texto {QUESTION}")),
        ModelProviderInvalidResponse,
    ),
    "invalid-status": (
        httpx.Response(200, json=_completion('{"status":"invented_status","answer":"texto"}')),
        ModelProviderInvalidResponse,
    ),
    "extra-field": (
        httpx.Response(
            200, json=_completion('{"status":"answered","answer":"texto","extra":"campo"}')
        ),
        ModelProviderInvalidResponse,
    ),
    "missing-field": (
        httpx.Response(200, json=_completion('{"status":"answered"}')),
        ModelProviderInvalidResponse,
    ),
    "invalid-observation-id": (
        httpx.Response(
            200,
            json=_completion(
                '{"status":"answered","answer":"texto","observation_ids":["linha_1"]}'
            ),
        ),
        ModelProviderInvalidResponse,
    ),
}

GENERIC_MESSAGES = {
    ModelProviderUnavailable: "O provedor de modelo está temporariamente indisponível.",
    ModelProviderRejected: "O provedor rejeitou a solicitação.",
    ModelProviderInvalidResponse: "O provedor retornou uma resposta inválida.",
}


@pytest.mark.parametrize(("failure", "expected"), FAILURES.values(), ids=FAILURES.keys())
def test_groq_failures_are_classified_with_generic_messages(
    failure: httpx.Response | Exception, expected: type[Exception], caplog
) -> None:
    handler = RecordingHandler(failure)

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(expected) as error,
    ):
        _generate(_adapter(handler))

    assert type(error.value) is expected
    assert len(handler.requests) == 1
    message = str(error.value)
    assert message == GENERIC_MESSAGES[expected]
    assert FAKE_KEY not in message
    assert QUESTION not in message
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    assert FAKE_KEY not in caplog.text
    assert QUESTION not in caplog.text


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_groq_rejection_does_not_fall_back_to_next_provider(status: int) -> None:
    calls: list[str] = []
    adapter = FallbackModelAdapter(
        [
            GroqModelAdapter(
                model_name="groq-test-model",
                api_key=SecretStr(FAKE_KEY),
                client=_groq_client(calls, httpx.Response(status)),
            ),
            GeminiModelAdapter(
                model_name="gemini-later",
                client=_gemini_client(RoutingGeminiEndpoint(set(), calls)),
            ),
        ]
    )

    with pytest.raises(ModelProviderRejected):
        asyncio.run(adapter.generate(QUESTION, [], _evidence()))

    assert calls == ["groq:groq-test-model"]


def test_groq_key_is_not_exposed_by_adapter_or_settings() -> None:
    adapter = _adapter(RecordingHandler(httpx.Response(500)))
    settings = Settings(_env_file=None, model_provider="groq", groq_api_key=FAKE_KEY)

    assert FAKE_KEY not in repr(vars(adapter))
    assert FAKE_KEY not in repr(settings)


# Configuração


def test_groq_settings_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GENAI_MODEL_PROVIDER", "groq")
    monkeypatch.setenv("GENAI_GROQ_API_KEY", "fake-env-key")
    monkeypatch.setenv("GENAI_GROQ_MODEL", "groq-configured-test")

    settings = Settings(_env_file=None)

    assert settings.model_provider == "groq"
    assert settings.groq_model == "groq-configured-test"
    assert settings.groq_api_key.get_secret_value() == "fake-env-key"
    assert "fake-env-key" not in repr(settings)


def test_settings_default_has_no_fallback_providers() -> None:
    settings = Settings(_env_file=None)

    assert settings.model_fallback_providers == []
    assert settings.groq_api_key is None
    assert settings.groq_model


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("groq", ["groq"]),
        ("gemini, groq", ["gemini", "groq"]),
        ('["groq", "gemini"]', ["groq", "gemini"]),
        ("", []),
    ],
)
def test_fallback_providers_accept_comma_separated_or_json(monkeypatch, raw, expected) -> None:
    monkeypatch.setenv("GENAI_MODEL_FALLBACK_PROVIDERS", raw)

    assert Settings(_env_file=None).model_fallback_providers == expected


@pytest.mark.parametrize("raw", ["openai", "groq,unavailable", '["gemini", "outro"]'])
def test_fallback_providers_reject_unknown_names(monkeypatch, raw) -> None:
    monkeypatch.setenv("GENAI_MODEL_FALLBACK_PROVIDERS", raw)

    with pytest.raises(ValueError):
        Settings(_env_file=None)


# Factory


def _chain_settings(**overrides) -> Settings:
    values = {
        "model_provider": "gemini",
        "gemini_model": "gemini-primary",
        "gemini_api_key": "fake-gemini-key",
        "groq_model": "groq-model",
        "groq_api_key": FAKE_KEY,
        "model_fallback_providers": ["groq"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _build(settings: Settings, calls: list[str] | None = None):
    calls = [] if calls is None else calls
    return build_model_adapter(
        settings,
        client=_gemini_client(RoutingGeminiEndpoint(set(), calls)),
        groq_client=_groq_client(calls, httpx.Response(500)),
    )


def test_factory_chains_gemini_models_then_groq_in_order() -> None:
    adapter = _build(_chain_settings(gemini_fallback_models=["gemini-b"]))

    assert isinstance(adapter, FallbackModelAdapter)
    chain = adapter._adapters
    assert [type(item) for item in chain] == [
        GeminiModelAdapter,
        GeminiModelAdapter,
        GroqModelAdapter,
    ]
    assert [item._model_name for item in chain] == ["gemini-primary", "gemini-b", "groq-model"]


def test_factory_groq_primary_with_gemini_fallback() -> None:
    adapter = _build(
        _chain_settings(
            model_provider="groq",
            model_fallback_providers=["gemini"],
            gemini_fallback_models=["gemini-b"],
        )
    )

    # Os modelos extras do Gemini só valem quando ele é o provedor principal.
    assert [(type(item), item._model_name) for item in adapter._adapters] == [
        (GroqModelAdapter, "groq-model"),
        (GeminiModelAdapter, "gemini-primary"),
    ]


def test_factory_groq_alone_returns_plain_groq_adapter() -> None:
    settings = _chain_settings(model_provider="groq", model_fallback_providers=[])

    assert isinstance(build_model_adapter(settings), GroqModelAdapter)


def test_factory_passes_fallback_backoff_to_multi_provider_chain() -> None:
    adapter = _build(_chain_settings(fallback_backoff_ms=250))

    assert isinstance(adapter, FallbackModelAdapter)
    assert adapter._backoff_seconds == 0.25


@pytest.mark.parametrize(
    ("overrides", "env_name"),
    [
        ({"groq_api_key": None}, "GENAI_GROQ_API_KEY"),
        ({"groq_api_key": "   "}, "GENAI_GROQ_API_KEY"),
        ({"gemini_api_key": None}, "GENAI_GEMINI_API_KEY"),
        (
            {"model_provider": "groq", "model_fallback_providers": [], "groq_api_key": None},
            "GENAI_GROQ_API_KEY",
        ),
        (
            {
                "model_provider": "groq",
                "model_fallback_providers": ["gemini"],
                "gemini_api_key": None,
            },
            "GENAI_GEMINI_API_KEY",
        ),
    ],
)
def test_factory_reports_missing_key_for_any_provider_in_chain(overrides, env_name) -> None:
    with pytest.raises(ModelConfigurationError, match=env_name):
        build_model_adapter(_chain_settings(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_fallback_providers": ["gemini"]},
        {"model_fallback_providers": ["groq", "groq"]},
    ],
)
def test_factory_rejects_repeated_providers(overrides) -> None:
    with pytest.raises(ModelConfigurationError, match="GENAI_MODEL_FALLBACK_PROVIDERS"):
        build_model_adapter(_chain_settings(**overrides))


@pytest.mark.parametrize(
    ("overrides", "chain_size"),
    [
        ({"gemini_fallback_models": ["gemini-b"], "model_max_calls": 2}, 3),
        ({"model_max_calls": 1}, 2),
        (
            {
                "model_provider": "groq",
                "model_fallback_providers": ["gemini"],
                "gemini_fallback_models": ["ignorado"],
                "model_max_calls": 1,
            },
            2,
        ),
    ],
)
def test_factory_counts_every_provider_against_model_max_calls(overrides, chain_size) -> None:
    calls: list[str] = []

    with pytest.raises(ModelConfigurationError, match="GENAI_MODEL_MAX_CALLS"):
        _build(_chain_settings(**overrides), calls)

    allowed = _build(_chain_settings(**{**overrides, "model_max_calls": chain_size}), calls)
    assert allowed.max_attempts == chain_size
    assert calls == []


def _namespace(**overrides) -> str:
    adapter = _build(_chain_settings(model_cache_ttl_seconds=300, **overrides))
    assert isinstance(adapter, CachingModelAdapter)
    return adapter._namespace


def test_cache_namespace_separates_provider_order_models_and_prompt() -> None:
    prompt_digest = hashlib.sha256(SYSTEM_INSTRUCTION.encode("utf-8")).hexdigest()
    variants = {
        "gemini-then-groq": _namespace(),
        "groq-then-gemini": _namespace(
            model_provider="groq", model_fallback_providers=["gemini"]
        ),
        "groq-only": _namespace(model_provider="groq", model_fallback_providers=[]),
        "gemini-only": _namespace(model_fallback_providers=[]),
        "other-groq-model": _namespace(groq_model="groq-other"),
        "other-gemini-model": _namespace(gemini_model="gemini-other"),
        "extra-gemini-model": _namespace(gemini_fallback_models=["gemini-b"]),
    }

    assert len(set(variants.values())) == len(variants)
    assert all(prompt_digest in namespace for namespace in variants.values())
    assert _namespace() == variants["gemini-then-groq"]
    assert FAKE_KEY not in repr(variants)


def _router(settings: Settings, calls: list[str] | None = None):
    calls = [] if calls is None else calls
    client = _gemini_client(RoutingGeminiEndpoint(set(), calls))
    groq_client = _groq_client(calls, httpx.Response(500))
    strong = build_model_adapter(settings, client=client, groq_client=groq_client)
    return build_model_router(settings, strong, client=client, groq_client=groq_client)


def _routing_settings(**overrides) -> Settings:
    return _chain_settings(
        model_routing_enabled=True,
        model_light_model="gemini-light",
        model_light_intents=["consumption"],
        **overrides,
    )


def test_router_adds_groq_as_fallback_of_each_tier() -> None:
    calls: list[str] = []

    with pytest.raises(ModelConfigurationError, match="GENAI_MODEL_MAX_CALLS"):
        _router(_routing_settings(model_max_calls=3), calls)

    router = _router(_routing_settings(model_max_calls=4), calls)
    light = router.adapter_for(ModelTier.LIGHT)
    strong = router.adapter_for(ModelTier.STRONG)

    assert isinstance(light, FallbackModelAdapter)
    assert [item._model_name for item in light._adapters] == ["gemini-light", "groq-model"]
    assert isinstance(light._adapters[1], GroqModelAdapter)
    assert [item._model_name for item in strong._adapters] == ["gemini-primary", "groq-model"]
    assert calls == []


def test_router_light_cache_namespace_includes_groq_only_when_configured() -> None:
    with_groq = _router(_routing_settings(model_max_calls=4, model_cache_ttl_seconds=300))
    without_groq = _router(
        _routing_settings(model_fallback_providers=[], model_cache_ttl_seconds=300)
    )
    with_groq_namespace = with_groq.adapter_for(ModelTier.LIGHT)._namespace
    without_groq_namespace = without_groq.adapter_for(ModelTier.LIGHT)._namespace

    assert "groq:groq-model" in with_groq_namespace
    assert with_groq_namespace != with_groq.adapter_for(ModelTier.STRONG)._namespace
    assert without_groq_namespace.startswith("gemini:gemini-light:")


def test_factory_unavailable_ignores_fallback_providers() -> None:
    settings = Settings(_env_file=None, model_fallback_providers=["groq"])

    assert build_model_adapter(settings).__class__.__name__ == "UnavailableModelAdapter"


# Integração


def test_gemini_failure_falls_back_to_groq_through_cache(caplog) -> None:
    calls: list[str] = []
    endpoint = RoutingGeminiEndpoint({"gemini-primary", "gemini-b"}, calls)
    settings = _chain_settings(gemini_fallback_models=["gemini-b"], model_cache_ttl_seconds=300)
    adapter = build_model_adapter(
        settings,
        client=_gemini_client(endpoint),
        groq_client=_groq_client(
            calls, httpx.Response(200, json=_completion(ANSWER.model_dump_json()))
        ),
    )

    async def run():
        first = await adapter.generate(QUESTION, [], _evidence())
        second = await adapter.generate(QUESTION, [], _evidence())
        return first, second

    with caplog.at_level(logging.DEBUG):
        first, second = asyncio.run(run())

    assert isinstance(adapter, CachingModelAdapter)
    assert first == second == ANSWER
    assert calls == ["gemini:gemini-primary", "gemini:gemini-b", "groq:groq-model"]
    assert FAKE_KEY not in caplog.text
    assert QUESTION not in caplog.text


def _orchestrator(model_adapter) -> QuestionOrchestrator:
    return QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            SyntheticScenarioTool(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model_adapter=model_adapter,
        execution_controller=ExecutionController(ExecutionLimits(max_model_calls=2)),
    )


def _ask(orchestrator: QuestionOrchestrator):
    return asyncio.run(
        orchestrator.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
        )
    )


def test_orchestrator_answers_with_groq_when_gemini_is_down() -> None:
    calls: list[str] = []
    groq_answer = GeneratedAnswer(
        status="answered", answer="Resposta gerada pelo Groq.", observation_ids=("row_1",)
    )
    model_adapter = build_model_adapter(
        _chain_settings(),
        client=_gemini_client(RoutingGeminiEndpoint({"gemini-primary"}, calls)),
        groq_client=_groq_client(
            calls, httpx.Response(200, json=_completion(groq_answer.model_dump_json()))
        ),
    )

    response = _ask(_orchestrator(model_adapter))

    assert calls == ["gemini:gemini-primary", "groq:groq-model"]
    # O serviço monta o texto a partir das observações escolhidas pelo Groq.
    assert response.status is QuestionStatus.ANSWERED
    assert response.evidence


def test_orchestrator_recovers_when_gemini_and_groq_are_down() -> None:
    calls: list[str] = []
    model_adapter = build_model_adapter(
        _chain_settings(),
        client=_gemini_client(RoutingGeminiEndpoint({"gemini-primary"}, calls)),
        groq_client=_groq_client(calls, httpx.Response(429, text="rate limit")),
    )

    response = _ask(_orchestrator(model_adapter))

    assert calls == ["gemini:gemini-primary", "groq:groq-model"]
    assert response.status is QuestionStatus.RECOVERABLE_ERROR


@pytest.mark.parametrize("reason", ["length", "tool_calls", "content_filter"])
def test_incomplete_completion_rejects_even_valid_json(reason):
    payload = _completion(ANSWER.model_dump_json())
    payload["choices"][0]["finish_reason"] = reason
    handler = RecordingHandler(httpx.Response(200, json=payload))
    with pytest.raises(ModelProviderInvalidResponse):
        _generate(_adapter(handler))
