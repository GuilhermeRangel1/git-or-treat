from dataclasses import dataclass
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.auth import permissions_for, resolve_session


bearer = HTTPBearer(
    auto_error=False,
    scheme_name="OrdersServiceToken",
    description="Bearer somente nos modos service; demo sintética local pode dispensá-lo.",
)
READ = "orders:read"
WRITE = "orders:write"


@dataclass(frozen=True)
class OrderIdentity:
    actor: str
    permissions: frozenset[str]
    auth_mode: str


def _unauthorized() -> HTTPException:
    return HTTPException(401, "Credencial inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"})


def _matches(provided: str, configured: SecretStr | None) -> bool:
    return configured is not None and compare_digest(
        provided.encode("utf-8"), configured.get_secret_value().encode("utf-8")
    )


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    return (
        origin is not None
        and origin != "null"
        and origin in settings.BACKEND_CORS_ORIGINS
        and request.headers.get("sec-fetch-site", "").lower() != "cross-site"
    )


def get_order_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> OrderIdentity:
    if settings.ORDERS_AUTH_MODE == "demo":
        if settings.APP_ENV != "development" or settings.ANALYTICS_SOURCE != "synthetic":
            raise HTTPException(503, "Demo disponível somente em desenvolvimento com dados sintéticos.")
        origin = request.headers.get("origin")
        if (request.headers.get("sec-fetch-site", "").lower() == "cross-site"
                or origin is not None and origin not in settings.BACKEND_CORS_ORIGINS):
            raise HTTPException(403, "Origem não permitida na demo local.")
        return OrderIdentity("local-demo", frozenset({READ, WRITE}), "demo")

    if settings.ORDERS_AUTH_MODE == "session":
        # A browser session is the only accepted credential in this mode.
        if credentials is not None:
            raise _unauthorized()
        token = request.cookies.get("grid360_session")
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and token and not _same_origin(request):
            raise HTTPException(403, "Origem não permitida.")
        resolved = resolve_session(db, token)
        if resolved is None:
            raise _unauthorized()
        user, _session = resolved
        return OrderIdentity(f"user:{user.id}", permissions_for(user) & {READ, WRITE}, "session")

    if settings.APP_ENV == "production":
        raise HTTPException(503, "Produção exige autenticação individual por sessão.")
    if credentials is None:
        raise HTTPException(401, "Autenticação obrigatória.", headers={"WWW-Authenticate": "Bearer"})
    if settings.ORDERS_READ_TOKEN is None and settings.ORDERS_WRITE_TOKEN is None:
        raise HTTPException(503, "Acesso às ordens não configurado.")
    if _matches(credentials.credentials, settings.ORDERS_WRITE_TOKEN):
        return OrderIdentity("orders-writer", frozenset({READ, WRITE}), "service")
    if _matches(credentials.credentials, settings.ORDERS_READ_TOKEN):
        return OrderIdentity("orders-reader", frozenset({READ}), "service")
    raise _unauthorized()


def require_orders_read(identity: OrderIdentity = Depends(get_order_identity)) -> str:
    if READ not in identity.permissions:
        raise HTTPException(403, "Permissão de leitura obrigatória.")
    return identity.actor


def require_orders_write(identity: OrderIdentity = Depends(get_order_identity)) -> str:
    if WRITE not in identity.permissions:
        raise HTTPException(403, "Permissão de escrita obrigatória.")
    return identity.actor
