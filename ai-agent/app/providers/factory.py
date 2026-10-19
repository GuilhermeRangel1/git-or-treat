"""Cria adaptadores de modelo a partir da configuração local do serviço."""

import hashlib

from app.config import Settings
from app.generation.prompts import SYSTEM_INSTRUCTION
from app.providers.caching import CachingModelAdapter
from app.providers.fallback import FallbackModelAdapter
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

        adapters: list[ModelAdapter] = [
            GeminiModelAdapter(
                model_name=model_name,
                api_key=settings.gemini_api_key.get_secret_value(),
                timeout_ms=settings.model_timeout_ms,
                client=client,
            )
            for model_name in [settings.gemini_model, *settings.gemini_fallback_models]
        ]
    except ImportError:
        raise ModelConfigurationError(
            'Instale a dependência opcional com: python -m pip install -e ".[gemini]".'
        ) from None

    adapter = adapters[0]
    if len(adapters) > settings.model_max_calls:
        raise ModelConfigurationError("A cadeia excede GENAI_MODEL_MAX_CALLS.")
    if len(adapters) > 1:
        adapter = FallbackModelAdapter(
            adapters,
            total_timeout_seconds=settings.model_total_timeout_ms / 1000,
            backoff_seconds=settings.fallback_backoff_ms / 1000,
        )
    if settings.model_cache_ttl_seconds > 0:
        model_names = ",".join([settings.gemini_model, *settings.gemini_fallback_models])
        prompt_digest = hashlib.sha256(SYSTEM_INSTRUCTION.encode("utf-8")).hexdigest()
        adapter = CachingModelAdapter(
            adapter,
            ttl_seconds=settings.model_cache_ttl_seconds,
            max_entries=settings.model_cache_max_entries,
            namespace=f"gemini:{model_names}:{prompt_digest}",
        )
    return adapter
