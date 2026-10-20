"""Cria adaptadores de modelo a partir da configuração local do serviço."""

import hashlib

from app.config import Settings
from app.generation.prompts import SYSTEM_INSTRUCTION
from app.providers.caching import CachingModelAdapter
from app.providers.fallback import FallbackModelAdapter
from app.providers.protocols import ModelAdapter
from app.providers.routing import ModelRouter, ModelTier, RoutingPolicy
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


def build_model_router(
    settings: Settings,
    strong_adapter: ModelAdapter,
    *,
    client=None,
) -> ModelRouter | None:
    """Monta o roteador opcional da pergunta a partir de configuração validada.

    O nível forte reutiliza a cadeia principal já criada, incluindo fallback e cache. O nível
    leve é opcional e, nesta etapa, usa Gemini com uma chave e um modelo próprios. O insight
    continua recebendo ``strong_adapter`` pela composição do núcleo.
    """

    if not settings.model_routing_enabled or not settings.model_light_intents:
        return None
    if settings.model_provider == "unavailable":
        # Mantém o modo padrão sem provedor inicializável; nenhuma chamada externa é feita.
        return None
    if settings.model_provider != "gemini":
        raise ModelConfigurationError(
            "O roteamento por nível está configurado apenas para o provedor Gemini."
        )
    if settings.model_light_model is None:
        raise ModelConfigurationError(
            "Configure GENAI_MODEL_LIGHT_MODEL quando GENAI_MODEL_LIGHT_INTENTS não estiver vazio."
        )
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        raise ModelConfigurationError(
            "Configure GENAI_GEMINI_API_KEY para habilitar o nível leve do roteador."
        )
    if settings.model_light_model in {settings.gemini_model, *settings.gemini_fallback_models}:
        raise ModelConfigurationError(
            "Os modelos light e strong devem ser distintos para habilitar o roteamento."
        )

    try:
        from app.providers.gemini import GeminiModelAdapter

        light_adapter: ModelAdapter = GeminiModelAdapter(
            model_name=settings.model_light_model,
            api_key=settings.gemini_api_key.get_secret_value(),
            timeout_ms=settings.model_timeout_ms,
            client=client,
        )
    except ImportError:
        raise ModelConfigurationError(
            'Instale a dependência opcional com: python -m pip install -e ".[gemini]".'
        ) from None

    if settings.model_cache_ttl_seconds > 0:
        prompt_digest = hashlib.sha256(SYSTEM_INSTRUCTION.encode("utf-8")).hexdigest()
        light_adapter = CachingModelAdapter(
            light_adapter,
            ttl_seconds=settings.model_cache_ttl_seconds,
            max_entries=settings.model_cache_max_entries,
            namespace=f"gemini:{settings.model_light_model}:{prompt_digest}",
        )

    max_attempts = getattr(strong_adapter, "max_attempts", 1) + getattr(
        light_adapter, "max_attempts", 1
    )
    if max_attempts > settings.model_max_calls:
        raise ModelConfigurationError(
            "Os níveis light e strong excedem GENAI_MODEL_MAX_CALLS no pior caso."
        )

    return ModelRouter(
        {ModelTier.LIGHT: light_adapter, ModelTier.STRONG: strong_adapter},
        RoutingPolicy(
            light_intents=frozenset(settings.model_light_intents),
            max_light_evidence_records=settings.model_light_max_evidence_records,
            max_light_evidence_chars=settings.model_light_max_evidence_chars,
        ),
    )
