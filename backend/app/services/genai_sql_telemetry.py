"""Telemetria estruturada e sanitizada do fluxo Text-to-SQL F1."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, distribution
from time import perf_counter
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("uvicorn.error")

Stage = Literal[
    "context", "generation", "semantic_review", "readiness_admission",
    "admission_revalidation", "sql_execution", "materialization", "evidence",
    "publication", "presentation", "http", "runtime",
]
Outcome = Literal["success", "clarification", "unsupported", "error", "cancelled"]

_CORRELATION = re.compile(r"^[a-f0-9]{32}$")
_REASONS = {
    "TimeoutError": "deadline_exceeded",
    "GenAITimeout": "deadline_exceeded",
    "SqlContextUnavailable": "context_unavailable",
    "ModelProviderUnavailable": "provider_unavailable",
    "ModelProviderRejected": "provider_rejected",
    "ModelProviderInvalidResponse": "provider_invalid_response",
    "SqlAdmissionDenied": "admission_denied",
    "GoldExecutionDenied": "scope_denied",
    "GoldPublicationChanged": "publication_changed",
    "GoldPublicationUnavailable": "publication_unavailable",
    "GoldCoverageUnavailable": "coverage_unavailable",
    "SQLAlchemyError": "database_error",
    "SqlResultRejected": "result_rejected",
    "SqlResultLimitExceeded": "result_limit_exceeded",
    "GenAIResponseInvalid": "invalid_response",
    "GenAIServiceUnavailable": "dependency_unavailable",
}


def _version(value: str | None) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9._:-]{1,100}", value):
        return value
    return None


def record_sql_runtime(correlation_id: str) -> None:
    """Registra dependências efetivas do Backend sem revelar caminhos/configuração."""
    if not _CORRELATION.fullmatch(correlation_id):
        correlation_id = "invalid"
    dependencies = {}
    for package_name in ("sqlglot", "SQLAlchemy", "psycopg"):
        try:
            found = distribution(package_name)
            dependencies[package_name.lower()] = _version(found.metadata.get("Version"))
        except PackageNotFoundError:
            dependencies[package_name.lower()] = None
    event = {
        "service": "backend",
        "strategy": "text_to_sql_f1",
        "contract_version": "text-to-sql-f1-v1",
        "correlation_id": correlation_id,
        "stage": "runtime",
        "elapsed_ms": 0,
        "outcome": "success",
        "dependencies": dependencies,
    }
    logger.info("genai_execution %s", json.dumps(event, separators=(",", ":")))


def record_sql_stage(
    *,
    correlation_id: str,
    stage: Stage,
    elapsed_ms: int,
    outcome: Outcome,
    reason: str | None = None,
    contract_version: str = "text-to-sql-f1-v1",
    context_version: str | None = None,
    mapping_version: str | None = None,
    dictionary_version: str | None = None,
    rows: int | None = None,
    http_status: int | None = None,
) -> None:
    """Emite apenas códigos, durações, versões e contagens; nunca conteúdo da consulta."""
    if not _CORRELATION.fullmatch(correlation_id):
        correlation_id = "invalid"
    event = {
        "service": "backend",
        "strategy": "text_to_sql_f1",
        "contract_version": contract_version,
        "correlation_id": correlation_id,
        "stage": stage,
        "elapsed_ms": max(0, min(int(elapsed_ms), 86_400_000)),
        "outcome": outcome,
        "reason": reason if reason in set(_REASONS.values()) | {
            "invalid_request", "audit_unavailable", "request_cancelled", "internal_error",
            "http_error",
        } else None,
        "context_version": _version(context_version),
        "mapping_version": _version(mapping_version),
        "dictionary_version": _version(dictionary_version),
        "rows": rows if type(rows) is int and 0 <= rows <= 2_147_483_647 else None,
        "http_status": http_status if type(http_status) is int and 100 <= http_status <= 599 else None,
    }
    logger.info("genai_execution %s", json.dumps(event, separators=(",", ":")))


@contextmanager
def sql_stage(
    correlation_id: str,
    stage: Stage,
    *,
    context_version: str | None = None,
    contract_version: str = "text-to-sql-f1-v1",
) -> Iterator[None]:
    """Mede uma etapa e converte falhas para motivos permitidos, sem logar exceções."""
    started = perf_counter()
    outcome: Outcome = "success"
    reason = None
    try:
        yield
    except asyncio.CancelledError:
        outcome, reason = "cancelled", "request_cancelled"
        raise
    except Exception as exc:
        outcome = "error"
        reason = _REASONS.get(type(exc).__name__, "internal_error")
        if isinstance(exc, SQLAlchemyError):
            reason = "database_error"
        raise
    finally:
        record_sql_stage(
            correlation_id=correlation_id,
            stage=stage,
            elapsed_ms=int((perf_counter() - started) * 1000),
            outcome=outcome,
            reason=reason,
            context_version=context_version,
            contract_version=contract_version,
        )
