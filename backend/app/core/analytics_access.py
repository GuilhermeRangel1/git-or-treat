"""Autoriza o catálogo de filtros compartilhado pelos recursos analíticos."""
from typing import Annotated

from fastapi import Depends, HTTPException
from app.core.platform_identity import PlatformIdentity, get_platform_identity


def require_gold_analytics_read(
    identity: Annotated[PlatformIdentity, Depends(get_platform_identity)],
) -> None:
    if not identity.permissions & {"revenue:read", "ucs:read", "inspections:read"}:
        raise HTTPException(403, "Permissão insuficiente para consultar os filtros analíticos.")
