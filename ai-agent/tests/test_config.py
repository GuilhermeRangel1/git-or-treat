from app.config import Settings


def test_settings_load_prefixed_values_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GENAI_SERVICE_NAME", "Serviço de teste")
    monkeypatch.setenv("GENAI_ENVIRONMENT", "test")

    settings = Settings(_env_file=None)

    assert settings.service_name == "Serviço de teste"
    assert settings.environment == "test"


def test_settings_ignore_unrecognized_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-become-a-setting")

    Settings(_env_file=None)

    assert "unrelated_secret" not in Settings.model_fields


def test_demo_access_is_off_without_explicit_configuration() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.enable_demo_access is False


def test_model_routing_settings_parse_comma_and_json_lists(monkeypatch) -> None:
    monkeypatch.setenv("GENAI_MODEL_ROUTING_ENABLED", "true")
    monkeypatch.setenv("GENAI_MODEL_LIGHT_MODEL", " gemini-light ")
    monkeypatch.setenv("GENAI_MODEL_LIGHT_INTENTS", "consumption,revenue")
    monkeypatch.setenv("GENAI_MODEL_LIGHT_MAX_EVIDENCE_RECORDS", "25")
    settings = Settings(_env_file=None)
    assert settings.model_routing_enabled is True
    assert settings.model_light_model == "gemini-light"
    assert settings.model_light_intents == ["consumption", "revenue"]
    assert settings.model_light_max_evidence_records == 25

    monkeypatch.setenv("GENAI_MODEL_LIGHT_INTENTS", '["consumption", "revenue"]')
    assert Settings(_env_file=None).model_light_intents == ["consumption", "revenue"]


def test_model_routing_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.model_routing_enabled is False
    assert settings.model_light_model is None
    assert settings.model_light_intents == []
