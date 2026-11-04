"""HTTP identity and per-request authorization for platform resources."""
from dataclasses import dataclass
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.platform_access import ALL_PERMISSIONS, PlatformProfile


bearer = HTTPBearer(auto_error=False, scheme_name="PlatformServiceToken")
_SERVICE_READ_PERMISSIONS = ALL_PERMISSIONS - {"orders:write", "ai:ask"}


@dataclass(frozen=True)
class PlatformIdentity:
    actor: str
    profile: PlatformProfile | None
    permissions: frozenset[str]
    auth_mode: str


def _unauthorized() -> HTTPException:
    return HTTPException(401, "Credencial inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"})


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    return (
        origin is not None
        and origin != "null"
        and origin in settings.BACKEND_CORS_ORIGINS
        and request.headers.get("sec-fetch-site", "").lower() != "cross-site"
    )


def _matches(provided: str, configured: SecretStr | None) -> bool:
    return configured is not None and compare_digest(
        provided.encode("utf-8"), configured.get_secret_value().encode("utf-8")
    )


def get_platform_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformIdentity:
    """Revalidate credentials and derive the persisted profile on every request."""
    if settings.ORDERS_AUTH_MODE == "demo":
        if settings.APP_ENV != "development" or settings.ANALYTICS_SOURCE != "synthetic":
            raise HTTPException(503, "Demo disponível somente em desenvolvimento com dados sintéticos.")
        origin = request.headers.get("origin")
        if (
            request.headers.get("sec-fetch-site", "").lower() == "cross-site"
            or origin is not None and origin not in settings.BACKEND_CORS_ORIGINS
        ):
            raise HTTPException(403, "Origem não permitida na demo local.")
        return PlatformIdentity("local-demo", None, ALL_PERMISSIONS, "demo")

    if settings.ORDERS_AUTH_MODE == "session":
        if credentials is not None:
            raise _unauthorized()
        token = request.cookies.get("grid360_session")
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and token and not _same_origin(request):
            raise HTTPException(403, "Origem não permitida.")
        from app.services.auth import permissions_for, resolve_session

        resolved = resolve_session(db, token)
        if resolved is None:
            raise _unauthorized()
        user, _session = resolved
        try:
            profile = PlatformProfile(user.profile) if user.profile is not None else None
        except ValueError:
            profile = None
        return PlatformIdentity(f"user:{user.id}", profile, permissions_for(user), "session")

    if settings.APP_ENV == "production":
        raise HTTPException(503, "Produção exige autenticação individual por sessão.")
    if credentials is None:
        raise HTTPException(401, "Autenticação obrigatória.", headers={"WWW-Authenticate": "Bearer"})
    if _matches(credentials.credentials, settings.ORDERS_WRITE_TOKEN):
        return PlatformIdentity(
            "orders-writer", None, _SERVICE_READ_PERMISSIONS | {"orders:write"}, "service"
        )
    if _matches(credentials.credentials, settings.ORDERS_READ_TOKEN):
        return PlatformIdentity("orders-reader", None, _SERVICE_READ_PERMISSIONS, "service")
    if settings.ORDERS_READ_TOKEN is None and settings.ORDERS_WRITE_TOKEN is None:
        raise HTTPException(503, "Acesso aos serviços não configurado.")
    raise _unauthorized()


def require_permission(permission: str):
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Permissão desconhecida: {permission}")

    def dependency(
        identity: Annotated[PlatformIdentity, Depends(get_platform_identity)],
    ) -> PlatformIdentity:
        if permission not in identity.permissions:
            raise HTTPException(403, "Permissão insuficiente para este recurso.")
        return identity

    return dependency
