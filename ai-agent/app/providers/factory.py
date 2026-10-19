"""Cria adaptadores de modelo a partir da configuração local do serviço."""

from app.config import ModelProviderName, Settings
from app.providers.caching import CachingModelAdapter
from app.providers.fallback import FallbackModelAdapter
from app.providers.protocols import ModelAdapter
from app.providers.unavailable import UnavailableModelAdapter


class ModelConfigurationError(ValueError):
    """Sinaliza configuração incompleta ou dependência opcional ausente."""


_API_KEY_SETTINGS: dict[ModelProviderName, tuple[str, str]] = {
    "gemini": ("gemini_api_key", "GENAI_GEMINI_API_KEY"),
    "groq": ("groq_api_key", "GENAI_GROQ_API_KEY"),
}
_PROVIDER_LABELS: dict[ModelProviderName, str] = {"gemini": "Gemini", "groq": "Groq"}


def build_model_adapter(settings: Settings, *, client=None, groq_client=None) -> ModelAdapter:
    """Seleciona um adaptador sem iniciar chamadas de rede.

    A cadeia tem os modelos do provedor principal seguidos de um adaptador para cada
    provedor de ``model_fallback_providers``. ``client`` substitui o cliente do SDK Gemini e
    ``groq_client`` o ``httpx.AsyncClient`` do Groq, para testes.
    """

    if settings.model_provider == "unavailable":
        return UnavailableModelAdapter()

    providers: list[ModelProviderName] = [
        settings.model_provider,
        *settings.model_fallback_providers,
    ]
    if len(set(providers)) != len(providers):
        raise ModelConfigurationError(
            "GENAI_MODEL_FALLBACK_PROVIDERS não pode repetir provedores nem incluir o "
            "provedor principal."
        )
    for provider in providers:
        _require_api_key(settings, provider)

    adapters: list[ModelAdapter] = []
    for position, provider in enumerate(providers):
        if provider == "gemini":
            model_names = [settings.gemini_model]
            if position == 0:
                model_names += settings.gemini_fallback_models
            adapters += _build_gemini_adapters(settings, model_names, client)
        else:
            adapters.append(_build_groq_adapter(settings, groq_client))

    adapter = adapters[0]
    if len(adapters) > 1:
        adapter = FallbackModelAdapter(
            adapters, total_timeout_seconds=settings.model_total_timeout_ms / 1000
        )
    if settings.model_cache_ttl_seconds > 0:
        adapter = CachingModelAdapter(
            adapter,
            ttl_seconds=settings.model_cache_ttl_seconds,
            max_entries=settings.model_cache_max_entries,
        )
    return adapter


def _require_api_key(settings: Settings, provider: ModelProviderName) -> None:
    field_name, env_name = _API_KEY_SETTINGS[provider]
    api_key = getattr(settings, field_name)
    if api_key is None or not api_key.get_secret_value().strip():
        raise ModelConfigurationError(
            f"Configure {env_name} para habilitar o provedor {_PROVIDER_LABELS[provider]}."
        )


def _build_gemini_adapters(
    settings: Settings, model_names: list[str], client
) -> list[ModelAdapter]:
    try:
        from app.providers.gemini import GeminiModelAdapter

        return [
            GeminiModelAdapter(
                model_name=model_name,
                api_key=settings.gemini_api_key.get_secret_value(),
                timeout_ms=settings.model_timeout_ms,
                client=client,
            )
            for model_name in model_names
        ]
    except ImportError:
        raise ModelConfigurationError(
            'Instale a dependência opcional com: python -m pip install -e ".[gemini]".'
        ) from None


def _build_groq_adapter(settings: Settings, client) -> ModelAdapter:
    try:
        from app.providers.groq import GroqModelAdapter
    except ImportError:
        raise ModelConfigurationError(
            'Instale a dependência opcional com: python -m pip install -e ".[groq]".'
        ) from None

    return GroqModelAdapter(
        model_name=settings.groq_model,
        api_key=settings.groq_api_key,
        timeout_ms=settings.model_timeout_ms,
        client=client,
    )
