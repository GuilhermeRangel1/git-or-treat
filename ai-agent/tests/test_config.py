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
