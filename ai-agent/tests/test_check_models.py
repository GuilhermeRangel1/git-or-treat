"""Checagem de modelos configurados: cliente falso, sem rede e sem chave real."""

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.providers.protocols import GeneratedAnswer

from .test_gemini_adapter import FakeClient, FakeModelEndpoint, FakeResponse

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_models.py"
_spec = importlib.util.spec_from_file_location("check_models", SCRIPT)
check_models = importlib.util.module_from_spec(_spec)
sys.modules["check_models"] = check_models
_spec.loader.exec_module(check_models)

FAKE_KEY = "AQ.fake-secret"
VALID = FakeResponse(GeneratedAnswer(status="answered", answer="Valor fictício.").model_dump_json())


def _settings(**values) -> Settings:
    return Settings(
        _env_file=None, model_provider="gemini", gemini_api_key=FAKE_KEY,
        gemini_model="gemini-test-model", **values,
    )


def _provider_error(**attributes) -> Exception:
    return type("ProviderError", (Exception,), attributes)(f"detalhe privado {FAKE_KEY}")


def _never_asked(prompt: str) -> str:
    raise AssertionError("a confirmação não deveria ser pedida")


@pytest.mark.parametrize(("endpoint", "result", "code"), [
    (FakeModelEndpoint(response=VALID), "ok", 0),
    (FakeModelEndpoint(error=_provider_error(status_code=429)), "quota", 1),
    (FakeModelEndpoint(error=_provider_error(status_code=404)), "model_not_found", 1),
    (FakeModelEndpoint(error=_provider_error(code="503")), "overloaded", 1),
    (FakeModelEndpoint(error=_provider_error(status_code=403)), "rejected", 1),
    (FakeModelEndpoint(error=TimeoutError(FAKE_KEY)), "timeout_or_network", 1),
    (FakeModelEndpoint(response=FakeResponse("não é JSON")), "invalid_response", 1),
], ids=lambda value: value if isinstance(value, str) else None)
def test_each_model_reports_its_classified_result(endpoint, result, code, capsys):
    exit_code = check_models.main(
        ["--yes"], settings=_settings(), client=FakeClient(endpoint), ask=_never_asked,
    )

    assert exit_code == code
    assert len(endpoint.calls) == 1
    line = capsys.readouterr().out.splitlines()[-1]
    assert line.startswith(f"gemini gemini-test-model: {result} (")
    assert line.endswith(" ms)")


def test_chain_follows_the_service_factory_and_stops_only_after_every_model(capsys):
    endpoint = FakeModelEndpoint(error=_provider_error(status_code=429))
    groq = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    settings = _settings(
        gemini_fallback_models=["gemini-test-fallback"], model_fallback_providers=["groq"],
        groq_api_key="fake-groq-key", groq_model="groq-test-model",
    )

    assert check_models.main(
        ["--yes"], settings=settings, client=FakeClient(endpoint), groq_client=groq,
    ) == 1

    out = capsys.readouterr().out
    assert "1. gemini gemini-test-model\n" in out and "3. groq groq-test-model\n" in out
    assert "gemini gemini-test-fallback: quota (" in out
    assert "groq groq-test-model: model_not_found (" in out
    assert len(endpoint.calls) == 2


def test_list_shows_the_chain_without_calling_any_model(capsys):
    endpoint = FakeModelEndpoint(response=VALID)

    assert check_models.main(
        ["--list"], settings=_settings(gemini_fallback_models=["gemini-test-fallback"]),
        client=FakeClient(endpoint), ask=_never_asked,
    ) == 0

    out = capsys.readouterr().out
    assert "1. gemini gemini-test-model" in out and "2. gemini gemini-test-fallback" in out
    assert "cota" not in out
    assert endpoint.calls == []


@pytest.mark.parametrize("answer", ["n", "não", "nao"])
def test_declined_confirmation_makes_no_call(answer, capsys):
    endpoint = FakeModelEndpoint(response=VALID)
    prompts = []

    exit_code = check_models.main(
        [], settings=_settings(), client=FakeClient(endpoint),
        ask=lambda prompt: prompts.append(prompt) or answer,
    )

    assert exit_code == 1
    assert prompts == ["Continuar? [S/n] "]
    assert endpoint.calls == []
    out = capsys.readouterr().out
    assert "Cada modelo consome 1 requisição da cota" in out
    assert "Cancelado; nenhuma chamada foi feita." in out


def test_fake_key_from_environment_never_reaches_the_output(monkeypatch, capsys, caplog):
    monkeypatch.setenv("GENAI_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GENAI_GEMINI_MODEL", "gemini-test-model")
    endpoint = FakeModelEndpoint(error=_provider_error(status_code=401))

    exit_code = check_models.main(
        ["--yes"], settings=Settings(_env_file=None), client=FakeClient(endpoint),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "gemini gemini-test-model: rejected (" in captured.out
    for text in (captured.out, captured.err, caplog.text):
        assert FAKE_KEY not in text
        assert "detalhe privado" not in text


def test_missing_key_is_a_short_configuration_error(capsys):
    settings = Settings(_env_file=None, model_provider="gemini")

    assert check_models.main(["--list"], settings=settings) == 1
    assert capsys.readouterr().out == "Erro de configuração: chave não configurada.\n"
