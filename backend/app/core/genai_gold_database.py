"""Credencial analítica restrita, separada da resolução da sessão operacional."""

import re
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.genai_gold_access import (
    GOLD_DIMENSIONS,
    GOLD_METRICS,
    get_genai_gold_access_resolver,
)
from app.schemas.genai_internal import AccessScope

GOLD_READER_ROLE = "venergy_genai_reader"
_TRANSPORT_OPTIONS = frozenset({
    "sslmode", "sslrootcert", "sslcert", "sslkey", "channel_binding", "application_name",
})


def create_genai_gold_engine(scope: AccessScope) -> Engine:
    """Aceita apenas escopo derivado no servidor e login dedicado provisionado."""
    if (
        scope.profile_id != "v-energy-grid-360-gold" or scope.source_id != "gold.local"
        or scope.allowed_operations != frozenset({"read"})
        or not scope.allowed_metric_ids or not scope.allowed_metric_ids <= GOLD_METRICS
        or not scope.allowed_dimension_ids <= GOLD_DIMENSIONS
        or re.fullmatch(r"session:[0-9a-f]{64}", scope.caller_ref) is None
        or settings.GENAI_GOLD_DATABASE_URL is None
    ):
        raise ValueError("Acesso Gold não configurado.")
    url = make_url(settings.GENAI_GOLD_DATABASE_URL.get_secret_value())
    operational = make_url(settings.DATABASE_URL)
    if (
        url.drivername != "postgresql+psycopg" or url.username != GOLD_READER_ROLE
        or not url.password or not url.host or not url.database
        or operational.username == GOLD_READER_ROLE
        # O dialeto incorpora a query aos argumentos DBAPI. Não permitir que
        # user/host/dbname/options/service sobrescrevam a identidade validada.
        or not set(url.query) <= _TRANSPORT_OPTIONS
        or not set(operational.query) <= _TRANSPORT_OPTIONS
        or any(not isinstance(value, str) for value in url.query.values())
        or (url.host, url.port, url.database)
        != (operational.host, operational.port, operational.database)
    ):
        raise ValueError("Credencial analítica Gold incompatível.")
    return create_engine(
        url, hide_parameters=True, echo=False, pool_pre_ping=True,
        pool_size=1, max_overflow=0, pool_timeout=2,
        connect_args={"connect_timeout": 5},
    )


def get_genai_gold_engine(
    resolve_scope: Annotated[
        Callable[[], AccessScope], Depends(get_genai_gold_access_resolver)
    ],
) -> Iterator[Engine]:
    """Pool por requisição; o consumidor revalida antes de cada consulta/cache."""
    scope = resolve_scope()
    try:
        engine = create_genai_gold_engine(scope)
    except (ValueError, TypeError, SQLAlchemyError):
        raise HTTPException(503, "Leitura Gold indisponível.") from None
    try:
        yield engine
    finally:
        engine.dispose()
