"""Smoke test da inicialização isolada do serviço."""

from app.config import Settings
from app.main import create_app


def test_application_factory_builds_without_gold_or_external_provider() -> None:
    settings = Settings(_env_file=None, service_name="GenAI de teste")
    app = create_app(settings)
    schema = app.openapi()

    assert schema["info"]["title"] == "GenAI de teste"
    assert schema["info"]["version"] == "0.1.0"
