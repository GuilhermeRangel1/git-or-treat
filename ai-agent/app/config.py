"""Configuração do serviço carregada do ambiente."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ModelProviderName = Literal["gemini", "groq"]


class Settings(BaseSettings):
    """Configuração mínima para iniciar o serviço sem Gold ou provedor de IA."""

    service_name: str = "V-Energy Grid 360 GenAI"
    environment: str = "production"
    enable_demo_access: bool = False
    model_provider: Literal["unavailable", "gemini", "groq"] = "unavailable"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = None
    model_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)
    gemini_fallback_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    model_total_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    model_cache_ttl_seconds: int = Field(default=0, ge=0, le=86_400)
    model_cache_max_entries: int = Field(default=256, ge=1, le=10_000)
    # Provedores tentados, em ordem, depois dos modelos do provedor principal.
    model_fallback_providers: Annotated[list[ModelProviderName], NoDecode] = Field(
        default_factory=list
    )
    groq_api_key: SecretStr | None = None
    # Confira no console do Groq se este ID continua disponível e aceita JSON mode.
    groq_model: str = "llama-3.3-70b-versatile"
    request_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    source_timeout_ms: int = Field(default=10_000, ge=100, le=120_000)
    source_max_calls: int = Field(default=1, ge=1, le=10)
    evidence_max_rows: int = Field(default=100, ge=1, le=100)
    evidence_max_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)
    model_max_calls: int = Field(default=3, ge=1, le=10)
    concurrent_requests: int = Field(default=16, ge=1, le=1_000)
    concurrent_sources: int = Field(default=8, ge=1, le=1_000)
    concurrent_models: int = Field(default=8, ge=1, le=1_000)
    fallback_backoff_ms: int = Field(default=0, ge=0, le=5_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GENAI_",
        extra="ignore",
    )

    @field_validator("gemini_fallback_models", "model_fallback_providers", mode="before")
    @classmethod
    def _split_model_list(cls, value: object) -> object:
        """Aceita lista JSON ou nomes separados por vírgula."""

        if not isinstance(value, str):
            return value
        if value.strip().startswith("["):
            return json.loads(value)
        return [name.strip() for name in value.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração reutilizável do processo."""

    return Settings()
