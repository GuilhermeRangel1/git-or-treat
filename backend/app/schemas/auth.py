from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator


Permission = Literal["orders:read", "orders:write"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    password: SecretStr

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome de usuário obrigatório.")
        return value

    @field_validator("password")
    @classmethod
    def limit_password(cls, value: SecretStr) -> SecretStr:
        if not 1 <= len(value.get_secret_value()) <= 1024:
            raise ValueError("Credenciais inválidas.")
        return value


class SessionUser(BaseModel):
    id: str
    username: str
    permissions: list[Permission]


class SessionEnvelope(BaseModel):
    enabled: bool
    user: SessionUser | None
    expires_at: str | None
