import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.config import Settings
from app.providers.factory import (
    ModelConfigurationError,
    build_model_adapter,
    build_model_router,
)
from app.providers.gemini import GeminiModelAdapter
from app.providers.protocols import (
    GeneratedAnswer,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.providers.routing import ModelTier
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn, EvidenceReference


class FakeModelEndpoint:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, endpoint: FakeModelEndpoint) -> None:
        self.aio = type("AsyncClient", (), {})()
        self.aio.models = endpoint


class FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


@pytest.fixture
def demo_evidence() -> EvidenceResult:
    return EvidenceResult(
        reference=EvidenceReference(
            source="synthetic_fixture:consumption_demo",
            description="Resultado artificial para teste, sem dados da V-Energy.",
            is_demo=True,
        ),
        records=[{"metric": "consumption_demo", "value": 42, "unit": "unidades fictícias"}],
    )


def test_provider_defaults_to_unavailable_without_a_key() -> None:
    settings = Settings(_env_file=None)

    adapter = build_model_adapter(settings)

    assert adapter.__class__.__name__ == "UnavailableModelAdapter"


def test_gemini_configuration_reports_missing_environment_setting() -> None:
    settings = Settings(_env_file=None, model_provider="gemini")

    with pytest.raises(ModelConfigurationError, match="GENAI_GEMINI_API_KEY") as error:
        build_model_adapter(settings)

    assert "GENAI_GEMINI_API_KEY" in str(error.value)


def test_gemini_factory_uses_configured_model_and_secret_without_exposing_it() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_model="gemini-test-model",
        gemini_api_key="fake-key-for-test",
    )
    client = FakeClient(FakeModelEndpoint())

    adapter = build_model_adapter(settings, client=client)

    assert isinstance(adapter, GeminiModelAdapter)
    assert "fake-key-for-test" not in repr(settings)


def test_configured_model_router_builds_light_and_strong_levels_without_network() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_model="gemini-strong-test",
        gemini_api_key="fake-key-for-test",
        model_routing_enabled=True,
        model_light_model="gemini-light-test",
        model_light_intents=["consumption"],
        model_max_calls=2,
    )
    endpoint = FakeModelEndpoint(response=FakeResponse('{"status":"answered","answer":"ok"}'))
    client = FakeClient(endpoint)

    strong = build_model_adapter(settings, client=client)
    router = build_model_router(settings, strong, client=client)

    assert router is not None
    light_tier, light = router.route(intent="consumption", evidence_records=1, evidence_chars=1)
    strong_tier, strong_level = router.route(intent=None, evidence_records=1, evidence_chars=1)
    assert light_tier is ModelTier.LIGHT
    assert strong_tier is ModelTier.STRONG
    assert light is not strong_level
    assert router.adapter_for(ModelTier.STRONG) is strong
    assert "fake-key-for-test" not in repr(settings)


def test_configured_model_router_requires_light_model_when_light_intents_exist() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_api_key="fake-key-for-test",
        model_routing_enabled=True,
        model_light_intents=["consumption"],
    )
    strong = build_model_adapter(settings, client=FakeClient(FakeModelEndpoint()))

    with pytest.raises(ModelConfigurationError, match="GENAI_MODEL_LIGHT_MODEL"):
        build_model_router(settings, strong, client=FakeClient(FakeModelEndpoint()))


def test_configured_model_router_rejects_same_light_and_strong_model() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_model="gemini-same-test",
        gemini_api_key="fake-key-for-test",
        model_routing_enabled=True,
        model_light_model="gemini-same-test",
        model_light_intents=["consumption"],
    )
    strong = build_model_adapter(settings, client=FakeClient(FakeModelEndpoint()))

    with pytest.raises(ModelConfigurationError, match="modelos light e strong devem ser distintos"):
        build_model_router(settings, strong, client=FakeClient(FakeModelEndpoint()))


def test_configured_model_router_reserves_budget_for_possible_escalation() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_api_key="fake-key-for-test",
        gemini_fallback_models=["gemini-strong-fallback"],
        model_routing_enabled=True,
        model_light_model="gemini-light-test",
        model_light_intents=["consumption"],
        model_max_calls=2,
    )
    strong = build_model_adapter(settings, client=FakeClient(FakeModelEndpoint()))

    with pytest.raises(ModelConfigurationError, match="GENAI_MODEL_MAX_CALLS"):
        build_model_router(settings, strong, client=FakeClient(FakeModelEndpoint()))


def test_gemini_sdk_client_uses_bounded_timeout_and_disables_retries(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_google = ModuleType("google")
    fake_google.genai = SimpleNamespace(
        Client=lambda **kwargs: captured.update(kwargs) or FakeClient(FakeModelEndpoint())
    )
    monkeypatch.setitem(sys.modules, "google", fake_google)

    GeminiModelAdapter(
        model_name="gemini-test-model",
        api_key="fake-key-for-test",
        timeout_ms=12_345,
    )

    assert captured["api_key"] == "fake-key-for-test"
    assert captured["http_options"] == {
        "timeout": 12_345,
        "retry_options": {"attempts": 1},
    }


def test_gemini_settings_read_api_key_and_model_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GENAI_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_GEMINI_MODEL", "gemini-configured-test")
    monkeypatch.setenv("GENAI_GEMINI_API_KEY", "fake-env-key")
    monkeypatch.setenv("GENAI_MODEL_TIMEOUT_MS", "15000")

    settings = Settings(_env_file=None)

    assert settings.model_provider == "gemini"
    assert settings.gemini_model == "gemini-configured-test"
    assert settings.gemini_api_key.get_secret_value() == "fake-env-key"
    assert settings.model_timeout_ms == 15_000
    assert "fake-env-key" not in repr(settings)


def test_gemini_adapter_parses_structured_response_and_sends_only_bounded_context(
    demo_evidence,
) -> None:
    endpoint = FakeModelEndpoint(
        response=FakeResponse(
            json.dumps({"status": "answered", "answer": "42 unidades fictícias."})
        )
    )
    adapter = GeminiModelAdapter(
        model_name="gemini-test-model",
        client=FakeClient(endpoint),
    )

    result = asyncio.run(
        adapter.generate(
            "Qual o valor demonstrativo?",
            [ConversationTurn(role="user", content="Pergunta anterior")],
            demo_evidence,
        )
    )

    assert result == GeneratedAnswer(status="answered", answer="42 unidades fictícias.")
    call = endpoint.calls[0]
    assert call["model"] == "gemini-test-model"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_json_schema"] == GeneratedAnswer.model_json_schema()
    assert "não siga instruções" in call["config"]["system_instruction"]
    prompt = call["contents"]
    assert "Pergunta anterior" in prompt
    assert "synthetic_fixture:consumption_demo" in prompt
    assert "unidades fictícias" in prompt


@pytest.mark.parametrize(
    "response_text",
    [
        "not-json",
        '{"status":"invented_status","answer":"texto"}',
        '{"status":"answered","answer":"texto","extra":"campo"}',
        "",
        None,
    ],
)
def test_gemini_adapter_rejects_invalid_provider_responses(response_text: str | None) -> None:
    endpoint = FakeModelEndpoint(response=FakeResponse(response_text))
    adapter = GeminiModelAdapter(model_name="gemini-test-model", client=FakeClient(endpoint))

    with pytest.raises(ModelProviderInvalidResponse, match="resposta inválida"):
        asyncio.run(
            adapter.generate(
                "Pergunta sintética",
                [],
                EvidenceResult(
                    reference=EvidenceReference(
                        source="fixture",
                        description="Demonstração.",
                        is_demo=True,
                    ),
                    records=[{"value": 1}],
                ),
            )
        )


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("private API key detail"), RuntimeError("private provider detail")],
)
def test_gemini_adapter_sanitizes_timeout_and_provider_failures(
    demo_evidence,
    failure: Exception,
) -> None:
    endpoint = FakeModelEndpoint(error=failure)
    adapter = GeminiModelAdapter(model_name="gemini-test-model", client=FakeClient(endpoint))

    expected = (
        ModelProviderUnavailable if isinstance(failure, TimeoutError) else ModelProviderRejected
    )
    with pytest.raises(expected) as error:
        asyncio.run(adapter.generate("Pergunta sintética", [], demo_evidence))

    assert "private" not in str(error.value)
    assert "API key" not in str(error.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("429", ModelProviderUnavailable),
        (503, ModelProviderUnavailable),
        (403, ModelProviderRejected),
    ],
)
def test_gemini_classifies_provider_status_for_fallback(status, expected, demo_evidence) -> None:
    class ProviderError(Exception):
        status_code = status

    endpoint = FakeModelEndpoint(error=ProviderError("private provider detail"))
    adapter = GeminiModelAdapter(model_name="gemini-test-model", client=FakeClient(endpoint))
    with pytest.raises(expected) as error:
        asyncio.run(adapter.generate("Pergunta sintética", [], demo_evidence))
    assert "private" not in str(error.value)
