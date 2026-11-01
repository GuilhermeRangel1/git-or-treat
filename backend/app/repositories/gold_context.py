"""Consistent, read-only request context for the currently published Gold batch."""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.platform_identity import PlatformIdentity, get_platform_identity, require_permission
from app.models.gold_v2_load import BATCH, SCHEMA_VERSION
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.services.analytics import AnalyticsAPIError


@dataclass(frozen=True)
class GoldContext:
    """Publication identity bound to one transaction snapshot."""

    connection: Connection
    lote: str
    schema_version: str
    fingerprint: str
    imported_at: datetime


def load_gold_context(connection: Connection, expected_lote: str | None = None,
                      expected_fingerprint: str | None = None) -> GoldContext:
    """Read current publication metadata on an existing caller-owned connection."""
    try:
        row = connection.execute(select(
            BATCH.c.lote,
            BATCH.c.schema_version,
            BATCH.c.fingerprint,
            BATCH.c.importado_em,
        ).where(BATCH.c.id == 1)).mappings().one_or_none()
    except SQLAlchemyError:
        raise AnalyticsSourceUnavailable() from None
    if row is None:
        raise AnalyticsSourceUnavailable()
    if row["schema_version"] != SCHEMA_VERSION:
        raise AnalyticsSourceUnavailable()
    if expected_lote is not None and expected_lote != row["lote"]:
        raise AnalyticsAPIError(409, "stale_batch", "A publicação Gold mudou; recarregue os dados.")
    if expected_fingerprint is not None:
        if re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint) is None:
            raise AnalyticsAPIError(422, "invalid_query", "Fingerprint esperado inválido.", [{"field": "expected_fingerprint", "message": "Informe 64 dígitos hexadecimais minúsculos."}])
        if expected_fingerprint != row["fingerprint"]:
            raise AnalyticsAPIError(409, "stale_batch", "A publicação Gold mudou; recarregue os dados.")
    return GoldContext(
        connection=connection,
        lote=row["lote"],
        schema_version=row["schema_version"],
        fingerprint=row["fingerprint"],
        imported_at=row["importado_em"],
    )


def get_gold_context_for(permission: str):
    permission_dependency = require_permission(permission)

    def dependency(
        expected_lote: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
        expected_fingerprint: Annotated[str | None, Query(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")] = None,
        _identity: PlatformIdentity = Depends(permission_dependency),
    ) -> Iterator[GoldContext]:
        """Authorize the feature before opening a Gold read snapshot."""
        if settings.ANALYTICS_SOURCE != "gold":
            raise AnalyticsSourceUnavailable()
        try:
            connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
        except SQLAlchemyError:
            raise AnalyticsSourceUnavailable() from None
        try:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                context = load_gold_context(connection, expected_lote, expected_fingerprint)
                yield context
        except SQLAlchemyError:
            raise AnalyticsSourceUnavailable() from None
        finally:
            connection.close()

    return dependency


def get_optional_gold_context_for(permission: str):
    gold_dependency = get_gold_context_for(permission)
    permission_dependency = require_permission(permission)

    def dependency(
        expected_lote: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
        expected_fingerprint: Annotated[str | None, Query(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")] = None,
        _identity: PlatformIdentity = Depends(permission_dependency),
    ) -> Iterator[GoldContext | None]:
        """Resolve Gold only after authorization; otherwise preserve synthetic behavior."""
        if settings.ANALYTICS_SOURCE != "gold":
            if settings.ANALYTICS_SOURCE == "synthetic" and (expected_lote is not None or expected_fingerprint is not None):
                raise AnalyticsAPIError(422, "invalid_query", "Expectativas de publicação só se aplicam à fonte Gold.", [{"field": "expected_lote", "message": "Remova expected_lote e expected_fingerprint no modo sintético."}])
            yield None
            return
        yield from gold_dependency(expected_lote, expected_fingerprint, _identity)

    return dependency


def get_gold_context(
    request: Request,
    expected_lote: str | None = None,
    expected_fingerprint: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = None,
    db: Session | None = None,
) -> Iterator[GoldContext]:
    """Compatibility adapter for callers using the original Panorama snapshot seam."""
    identity = get_platform_identity(request, credentials, db)  # type: ignore[arg-type]
    if "panorama:read" not in identity.permissions:
        raise HTTPException(403, "Permissão insuficiente para este recurso.")
    yield from get_gold_context_for("panorama:read")(
        expected_lote, expected_fingerprint, identity
    )


def get_optional_gold_context(
    request: Request,
    expected_lote: str | None = None,
    expected_fingerprint: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = None,
    db: Session | None = None,
) -> Iterator[GoldContext | None]:
    """Compatibility adapter; production routes use an explicit resource permission."""
    identity = get_platform_identity(request, credentials, db)  # type: ignore[arg-type]
    yield from get_optional_gold_context_for("panorama:read")(
        expected_lote, expected_fingerprint, identity
    )
