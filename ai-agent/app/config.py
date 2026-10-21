"""Configuração do serviço carregada do ambiente."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração mínima para iniciar o serviço sem Gold ou provedor de IA."""

    service_name: str = "V-Energy Grid 360 GenAI"
    environment: str = "production"
    enable_demo_access: bool = False
    model_provider: Literal["unavailable", "gemini"] = "unavailable"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = None
    model_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)
    gemini_fallback_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    model_routing_enabled: bool = False
    model_light_model: str | None = None
    model_light_intents: Annotated[list[str], NoDecode] = Field(default_factory=list)
    model_light_max_evidence_records: int = Field(default=50, ge=0, le=100)
    model_light_max_evidence_chars: int = Field(default=8_000, ge=0, le=1_048_576)
    model_total_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    model_cache_ttl_seconds: int = Field(default=0, ge=0, le=86_400)
    model_cache_max_entries: int = Field(default=256, ge=1, le=10_000)
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

    @field_validator("gemini_fallback_models", mode="before")
    @classmethod
    def _split_model_list(cls, value: object) -> object:
        """Aceita lista JSON ou nomes separados por vírgula."""

        if not isinstance(value, str):
            return value
        if value.strip().startswith("["):
            return json.loads(value)
        return [name.strip() for name in value.split(",") if name.strip()]

    @field_validator("model_light_intents", mode="before")
    @classmethod
    def _split_light_intents(cls, value: object) -> object:
        """Aceita domínios permitidos como lista JSON ou nomes separados por vírgula."""

        if not isinstance(value, str):
            return value
        if value.strip().startswith("["):
            return json.loads(value)
        return [name.strip() for name in value.split(",") if name.strip()]

    @field_validator("model_light_intents")
    @classmethod
    def _normalize_light_intents(cls, value: list[str]) -> list[str]:
        """Normaliza domínios para o formato usado pelo interpretador."""

        return list(dict.fromkeys(item.strip().casefold() for item in value if item.strip()))

    @field_validator("model_light_model")
    @classmethod
    def _normalize_light_model(cls, value: str | None) -> str | None:
        """Trata texto em branco como ausência de modelo leve."""

        normalized = value.strip() if value is not None else None
        return normalized or None


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração reutilizável do processo."""

    return Settings()
