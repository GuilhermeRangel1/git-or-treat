from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.config import Settings
from app.providers.caching import CachingModelAdapter
from app.providers.factory import ModelConfigurationError, build_model_adapter
from app.providers.fallback import FallbackModelAdapter
from app.providers.gemini import SYSTEM_INSTRUCTION, GeminiModelAdapter
from app.providers.groq import GROQ_CHAT_COMPLETIONS_URL, GroqModelAdapter
from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.questions import (
    ConversationTurn,
    EvidenceReference,
    QuestionRequest,
    QuestionStatus,
)
from app.tools.synthetic_analytics import SyntheticScenarioTool

if TYPE_CHECKING:
    from app.tools.evidence import EvidenceResult

FAKE_KEY = "fake-groq-key-for-test"
QUESTION = "Qual foi o consumo no período de demonstração?"
ANSWER = GeneratedAnswer(status="answered", answer="O consumo foi 42 unidades fictícias.")


class DemoEvidence(BaseModel):
    """Substituto do EvidenceResult: o adaptador só serializa a evidência recebida."""

    reference: EvidenceReference
    records: list[dict[str, object]]


def _evidence() -> EvidenceResult:
    return DemoEvidence(  # type: ignore[return-value]
        reference=EvidenceReference(
            source="synthetic_fixture:consumption_demo",
            description="Resultado artificial para teste, sem dados da V-Energy.",
            is_demo=True,
        ),
        records=[{"metric": "consumption_demo", "value": 42, "unit": "unidades fictícias"}],
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
    assert prompt["question"] == QUESTION
    assert prompt["context"] == [{"role": "user", "content": "Pergunta anterior"}]
    assert prompt["evidence"]["reference"]["source"] == "synthetic_fixture:consumption_demo"


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


FAILURES = {
    "timeout": httpx.ReadTimeout(f"timeout {FAKE_KEY} {QUESTION}"),
    "network": httpx.ConnectError(f"conexão recusada {FAKE_KEY} {QUESTION}"),
    "http-400": httpx.Response(400, text=f'{{"error":"{FAKE_KEY} {QUESTION}"}}'),
    "http-401": httpx.Response(401, text=f'{{"error":"Invalid API Key {FAKE_KEY}"}}'),
    "http-429": httpx.Response(429, text=f'{{"error":"rate limit {QUESTION}"}}'),
    "http-500": httpx.Response(500, text=f"erro interno {FAKE_KEY} {QUESTION}"),
    "http-503": httpx.Response(503, text="serviço indisponível"),
    "empty-body": httpx.Response(200, content=b""),
    "empty-content": httpx.Response(200, json=_completion("")),
    "null-content": httpx.Response(200, json=_completion(None)),
    "no-choices": httpx.Response(200, json={"choices": []}),
    "body-not-json": httpx.Response(200, text=f"<html>{FAKE_KEY} {QUESTION}</html>"),
    "content-not-json": httpx.Response(200, json=_completion(f"texto {QUESTION}")),
    "invalid-status": httpx.Response(
        200, json=_completion('{"status":"invented_status","answer":"texto"}')
    ),
    "extra-field": httpx.Response(
        200, json=_completion('{"status":"answered","answer":"texto","extra":"campo"}')
    ),
    "missing-field": httpx.Response(200, json=_completion('{"status":"answered"}')),
}


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_groq_failures_become_generic_unavailable_without_secrets(
    failure: httpx.Response | Exception, caplog
) -> None:
    handler = RecordingHandler(failure)

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(ModelProviderUnavailable) as error,
    ):
        _generate(_adapter(handler))

    assert len(handler.requests) == 1
    message = str(error.value)
    assert message in {
        "O provedor de modelo está temporariamente indisponível.",
        "O provedor retornou uma resposta inválida.",
    }
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    assert FAKE_KEY not in caplog.text
    assert QUESTION not in caplog.text


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


def test_factory_chains_gemini_models_then_groq_in_order() -> None:
    settings = _chain_settings(gemini_fallback_models=["gemini-b"])

    adapter = build_model_adapter(
        settings,
        client=_gemini_client(RoutingGeminiEndpoint(set(), [])),
        groq_client=_groq_client([], httpx.Response(500)),
    )

    assert isinstance(adapter, FallbackModelAdapter)
    chain = adapter._adapters
    assert [type(item) for item in chain] == [
        GeminiModelAdapter,
        GeminiModelAdapter,
        GroqModelAdapter,
    ]
    assert [item._model_name for item in chain] == ["gemini-primary", "gemini-b", "groq-model"]


def test_factory_groq_primary_with_gemini_fallback() -> None:
    settings = _chain_settings(
        model_provider="groq",
        model_fallback_providers=["gemini"],
        gemini_fallback_models=["gemini-b"],
    )

    adapter = build_model_adapter(
        settings,
        client=_gemini_client(RoutingGeminiEndpoint(set(), [])),
        groq_client=_groq_client([], httpx.Response(500)),
    )

    # Os modelos extras do Gemini só valem quando ele é o provedor principal.
    assert [(type(item), item._model_name) for item in adapter._adapters] == [
        (GroqModelAdapter, "groq-model"),
        (GeminiModelAdapter, "gemini-primary"),
    ]


def test_factory_groq_alone_returns_plain_groq_adapter() -> None:
    settings = _chain_settings(model_provider="groq", model_fallback_providers=[])

    assert isinstance(build_model_adapter(settings), GroqModelAdapter)


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


def test_orchestrator_answers_with_groq_when_gemini_is_down() -> None:
    calls: list[str] = []
    groq_answer = GeneratedAnswer(status="answered", answer="Resposta gerada pelo Groq.")
    model_adapter = build_model_adapter(
        _chain_settings(),
        client=_gemini_client(RoutingGeminiEndpoint({"gemini-primary"}, calls)),
        groq_client=_groq_client(
            calls, httpx.Response(200, json=_completion(groq_answer.model_dump_json()))
        ),
    )
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(QuestionInterpreter(), SyntheticScenarioTool()),
        model_adapter=model_adapter,
    )

    response = asyncio.run(orchestrator.answer(QuestionRequest(question=QUESTION)))

    assert calls == ["gemini:gemini-primary", "groq:groq-model"]
    assert response.status is QuestionStatus.ANSWERED
    assert response.answer.endswith(groq_answer.answer)
    assert response.evidence


def test_orchestrator_recovers_when_gemini_and_groq_are_down() -> None:
    calls: list[str] = []
    model_adapter = build_model_adapter(
        _chain_settings(),
        client=_gemini_client(RoutingGeminiEndpoint({"gemini-primary"}, calls)),
        groq_client=_groq_client(calls, httpx.Response(429, text="rate limit")),
    )
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(QuestionInterpreter(), SyntheticScenarioTool()),
        model_adapter=model_adapter,
    )

    response = asyncio.run(orchestrator.answer(QuestionRequest(question=QUESTION)))

    assert calls == ["gemini:gemini-primary", "groq:groq-model"]
    assert response.status is QuestionStatus.RECOVERABLE_ERROR
