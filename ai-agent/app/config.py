"""Configuração do serviço carregada do ambiente."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração mínima para iniciar o serviço sem Gold ou provedor de IA."""

    service_name: str = "V-Energy Grid 360 GenAI"
    environment: str = "local"
    model_provider: Literal["unavailable", "gemini"] = "unavailable"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = None
    model_timeout_ms: int = Field(default=20_000, ge=1_000, le=120_000)
    gemini_fallback_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    model_total_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    model_cache_ttl_seconds: int = Field(default=0, ge=0, le=86_400)
    model_cache_max_entries: int = Field(default=256, ge=1, le=10_000)

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


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração reutilizável do processo."""

    return Settings()
