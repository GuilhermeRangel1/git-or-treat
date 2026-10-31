from typing import List, Literal, Union
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        hide_input_in_errors=True,
    )

    PROJECT_NAME: str = "V-Energy Grid 360 API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    AI_AGENT_BASE_URL: AnyHttpUrl | None = None
    AI_AGENT_SERVICE_API_TOKEN: SecretStr | None = None
    AI_AGENT_TIMEOUT_SECONDS: float = Field(default=35.0, ge=0.1, le=120.0)

    # Explicitly opt in to the in-memory demonstration analytics source.
    ANALYTICS_SOURCE: str = "unavailable"

    ORDERS_READ_TOKEN: SecretStr | None = None
    ORDERS_WRITE_TOKEN: SecretStr | None = None
    APP_ENV: Literal["development", "production"] = "development"
    ORDERS_AUTH_MODE: Literal["demo", "service", "session"] = "session"
    AUTH_SESSION_LIFETIME_SECONDS: int = Field(default=3600, ge=300, le=86400)
    AUTH_LOGIN_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    AUTH_LOGIN_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_order_tokens(self):
        tokens = [token.get_secret_value() for token in (self.ORDERS_READ_TOKEN, self.ORDERS_WRITE_TOKEN) if token is not None]
        if any(len(token) < 32 for token in tokens):
            raise ValueError("Credenciais de ordens devem ter ao menos 32 caracteres.")
        if len(tokens) == 2 and tokens[0] == tokens[1]:
            raise ValueError("Credenciais de leitura e escrita devem ser distintas.")
        if self.APP_ENV == "production" and self.ORDERS_AUTH_MODE != "session":
            raise ValueError("Produção exige autenticação individual por sessão.")
        if self.ORDERS_AUTH_MODE == "demo" and self.ANALYTICS_SOURCE != "synthetic":
            raise ValueError("Modo demo exige fonte exclusivamente sintética.")
        if self.ORDERS_AUTH_MODE == "session" and tokens:
            raise ValueError("Modo session não aceita credenciais compartilhadas de serviço em paralelo.")
        if self.AI_AGENT_BASE_URL is not None:
            if self.AI_AGENT_SERVICE_API_TOKEN is None:
                raise ValueError("AI_AGENT_SERVICE_API_TOKEN é obrigatório quando AI_AGENT_BASE_URL é configurada.")
            if len(self.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()) < 32:
                raise ValueError("AI_AGENT_SERVICE_API_TOKEN deve ter ao menos 32 caracteres.")
        return self

    # Database (PostgreSQL com driver psycopg 3)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/v_energy"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    GENAI_GOLD_DATABASE_URL: SecretStr | None = None

    # Data directory (Mocks now, Gold exported CSVs later)
    GOLD_DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "gold"

    BACKEND_ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "backend", "testserver"]

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", "BACKEND_ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("ANALYTICS_SOURCE")
    @classmethod
    def validate_analytics_source(cls, value: str) -> str:
        if value not in {"unavailable", "synthetic", "gold"}:
            raise ValueError("ANALYTICS_SOURCE must be 'unavailable', 'synthetic' or 'gold'")
        return value


settings = Settings()
