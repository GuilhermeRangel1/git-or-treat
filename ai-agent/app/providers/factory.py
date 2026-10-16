"""Cria adaptadores de modelo a partir da configuração local do serviço."""

from app.config import Settings
from app.providers.protocols import ModelAdapter
from app.providers.unavailable import UnavailableModelAdapter


class ModelConfigurationError(ValueError):
    """Sinaliza configuração incompleta ou dependência opcional ausente."""


def build_model_adapter(settings: Settings, *, client=None) -> ModelAdapter:
    """Seleciona um adaptador sem iniciar chamadas de rede."""

    if settings.model_provider == "unavailable":
        return UnavailableModelAdapter()

    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        raise ModelConfigurationError(
            "Configure GENAI_GEMINI_API_KEY para habilitar o provedor Gemini."
        )

    try:
        from app.providers.gemini import GeminiModelAdapter

        return GeminiModelAdapter(
            model_name=settings.gemini_model,
            api_key=settings.gemini_api_key.get_secret_value(),
            timeout_ms=settings.model_timeout_ms,
            client=client,
        )
    except ImportError:
        raise ModelConfigurationError(
            'Instale a dependência opcional com: python -m pip install -e ".[gemini]".'
        ) from None
