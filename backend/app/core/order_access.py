from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from secrets import compare_digest

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr

from app.core.config import settings

bearer = HTTPBearer(
    auto_error=False, scheme_name="OrdersServiceToken",
    description="Bearer OIDC individual em produção; serviço somente em desenvolvimento.",
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


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=3)


def _oidc_identity(token: str) -> OrderIdentity:
    if not (settings.OIDC_ISSUER and settings.OIDC_AUDIENCE and settings.OIDC_JWKS_URL):
        raise HTTPException(503, "Identidade das ordens não configurada.")
    if len(token) > 8192:
        raise _unauthorized()
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
            raise _unauthorized()
        # Trust only the configured HTTPS endpoint, never token-provided URLs.
        # Unknown kids do not force outbound refreshes of the cached key set.
        keys = _jwks_client(settings.OIDC_JWKS_URL).get_signing_keys(refresh=False)
        key = next((key for key in keys if key.key_id == kid and key.algorithm_name == "RS256"), None)
        if key is None or getattr(key.key, "key_size", 0) < 2048:
            raise _unauthorized()
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"],
            issuer=settings.OIDC_ISSUER, audience=settings.OIDC_AUDIENCE,
            leeway=15, options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        sub = claims["sub"]
        scope = claims.get("scope", "")
        if (not isinstance(sub, str) or not sub.strip() or len(sub) > 255
                or not isinstance(scope, str) or len(scope) > 2048):
            raise _unauthorized()
        if any(type(claims[name]) is not int for name in ("iat", "exp")):
            raise _unauthorized()
        if not 0 < claims["exp"] - claims["iat"] <= 3600:
            raise _unauthorized()
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Provedor de identidade indisponível.") from exc
    except (jwt.PyJWTError, ValueError, TypeError, RecursionError) as exc:
        raise _unauthorized() from exc
    permissions = frozenset(scope.split()) & {READ, WRITE}
    if WRITE in permissions:
        permissions |= {READ}
    actor = "oidc:" + sha256((settings.OIDC_ISSUER + "\0" + sub).encode()).hexdigest()
    return OrderIdentity(actor, frozenset(permissions), "oidc")


def _matches(provided: str, configured: SecretStr | None) -> bool:
    return configured is not None and compare_digest(
        provided.encode("utf-8"), configured.get_secret_value().encode("utf-8")
    )


def get_order_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> OrderIdentity:
    if credentials is None:
        raise HTTPException(401, "Autenticação obrigatória.", headers={"WWW-Authenticate": "Bearer"})
    if settings.ORDERS_AUTH_MODE == "oidc":
        return _oidc_identity(credentials.credentials)
    if settings.APP_ENV == "production":
        raise HTTPException(503, "Produção exige identidade individual nas ordens.")
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
