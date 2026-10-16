"""Configuração do serviço carregada do ambiente."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração mínima para iniciar o serviço sem Gold ou provedor de IA."""

    service_name: str = "V-Energy Grid 360 GenAI"
    environment: str = "local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GENAI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração reutilizável do processo."""

    return Settings()
