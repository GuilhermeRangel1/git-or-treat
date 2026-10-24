from typing import List, Literal, Union
from urllib.parse import urlsplit
from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


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

    # Explicitly opt in to the in-memory demonstration analytics source.
    ANALYTICS_SOURCE: str = "unavailable"

    ORDERS_READ_TOKEN: SecretStr | None = None
    ORDERS_WRITE_TOKEN: SecretStr | None = None
    APP_ENV: Literal["development", "production"] = "development"
    ORDERS_AUTH_MODE: Literal["demo", "service", "oidc"] = "service"
    OIDC_ISSUER: str | None = None
    OIDC_AUDIENCE: str | None = None
    OIDC_JWKS_URL: str | None = None

    @model_validator(mode="after")
    def validate_order_tokens(self):
        tokens = [token.get_secret_value() for token in (self.ORDERS_READ_TOKEN, self.ORDERS_WRITE_TOKEN) if token is not None]
        if any(len(token) < 32 for token in tokens):
            raise ValueError("Credenciais de ordens devem ter ao menos 32 caracteres.")
        if len(tokens) == 2 and tokens[0] == tokens[1]:
            raise ValueError("Credenciais de leitura e escrita devem ser distintas.")
        if self.APP_ENV == "production" and self.ORDERS_AUTH_MODE != "oidc":
            raise ValueError("Produção exige autenticação individual OIDC nas ordens.")
        if self.ORDERS_AUTH_MODE == "demo" and self.ANALYTICS_SOURCE != "synthetic":
            raise ValueError("Modo demo exige fonte exclusivamente sintética.")
        if self.ORDERS_AUTH_MODE == "oidc":
            if tokens:
                raise ValueError("OIDC não aceita credenciais compartilhadas de serviço em paralelo.")
            if not self.OIDC_AUDIENCE or not self.OIDC_AUDIENCE.strip():
                raise ValueError("Configure a audiência OIDC da API.")
            for value in (self.OIDC_ISSUER, self.OIDC_JWKS_URL):
                parsed = urlsplit(value or "")
                if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                        or parsed.password or parsed.query or parsed.fragment):
                    raise ValueError("Emissor e JWKS OIDC devem ser URLs HTTPS explícitas, sem credenciais ou parâmetros.")
        return self

    # Database (PostgreSQL com driver psycopg 3)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/v_energy"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # Data directory (Mocks now, Gold exported CSVs later)
    GOLD_DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data" / "gold"

    BACKEND_ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "backend", "testserver"]

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", "BACKEND_ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("ANALYTICS_SOURCE")
    @classmethod
    def validate_analytics_source(cls, value: str) -> str:
        if value not in {"unavailable", "synthetic"}:
            raise ValueError("ANALYTICS_SOURCE must be 'unavailable' or 'synthetic'")
        return value


settings = Settings()
