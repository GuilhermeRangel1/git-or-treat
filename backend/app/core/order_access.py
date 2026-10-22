from secrets import compare_digest

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr

from app.core.config import settings

bearer = HTTPBearer(auto_error=False, scheme_name="OrdersServiceToken")


def _matches(provided: str, configured: SecretStr | None) -> bool:
    return configured is not None and compare_digest(
        provided.encode("utf-8"), configured.get_secret_value().encode("utf-8")
    )


def _authorize(credentials: HTTPAuthorizationCredentials | None, write: bool) -> str:
    if credentials is None:
        raise HTTPException(401, "Credencial de serviço obrigatória.", headers={"WWW-Authenticate": "Bearer"})
    if settings.ORDERS_READ_TOKEN is None and settings.ORDERS_WRITE_TOKEN is None:
        raise HTTPException(503, "Acesso às ordens não configurado.")
    can_write = _matches(credentials.credentials, settings.ORDERS_WRITE_TOKEN)
    can_read = _matches(credentials.credentials, settings.ORDERS_READ_TOKEN)
    if not can_write and not can_read:
        raise HTTPException(401, "Credencial inválida.", headers={"WWW-Authenticate": "Bearer"})
    if write and not can_write:
        raise HTTPException(403, "Credencial sem permissão de escrita.")
    return "orders-writer" if can_write else "orders-reader"


def require_orders_read(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    return _authorize(credentials, write=False)


def require_orders_write(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    return _authorize(credentials, write=True)
