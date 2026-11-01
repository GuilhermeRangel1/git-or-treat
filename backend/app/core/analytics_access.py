"""Exige identidade de leitura nas rotas legadas que consultam a Gold."""
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.order_access import bearer, get_order_identity, require_orders_read


def require_gold_analytics_read(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if settings.ANALYTICS_SOURCE == "gold":
        require_orders_read(get_order_identity(request, credentials, db))
