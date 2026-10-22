"""Trilha de auditoria das consultas SQL, sem linhas de resultado nem pergunta da pessoa.

Retenção e acesso a esta trilha ainda são decisão em aberto; por isso só há destinos em
memória (testes) e log de processo, sem persistência própria.
"""

import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

AuditStatus = Literal["accepted", "rejected", "failed"]

AUDIT_LOGGER_NAME = "app.sql.audit"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def template_fingerprint(sql_template: str) -> str:
    """Calcula a impressão de um template sanitizado, nunca do SQL com valores."""

    return hashlib.sha256(sql_template.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SqlAuditContext:
    """Identificadores controlados do plano, sem texto de filtros ou da pergunta."""

    plan_fingerprint: str
    catalog_version: str
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan_fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.plan_fingerprint
        ):
            raise ValueError("fingerprint do plano inválido")
        if not isinstance(self.catalog_version, str) or not re.fullmatch(
            r"v[1-9][0-9]{0,2}", self.catalog_version
        ):
            raise ValueError("versão do catálogo inválida")
        validate_correlation_id(self.correlation_id)


def validate_correlation_id(correlation_id: str | None) -> None:
    if correlation_id is not None and (
        not isinstance(correlation_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", correlation_id)
    ):
        raise ValueError("identificador de correlação inválido")


@dataclass(frozen=True)
class QueryAuditRecord:
    status: AuditStatus
    dialect: str
    dictionary_version: str
    received_sql_chars: int
    plan_fingerprint: str | None = None
    catalog_version: str | None = None
    correlation_id: str | None = None
    reason_code: str | None = None
    query_template: str | None = None
    query_template_sha256: str | None = None
    tables: tuple[str, ...] = ()
    original_limit: int | None = None
    applied_limit: int | None = None
    limit_adjusted: bool = False
    row_count: int | None = None
    truncated: bool = False
    duration_ms: float | None = None
    error_type: str | None = None
    query_id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["tables"] = list(self.tables)
        return data


class AuditSink(Protocol):
    def record(self, entry: QueryAuditRecord) -> None: ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[QueryAuditRecord] = []

    def record(self, entry: QueryAuditRecord) -> None:
        self.records.append(entry)


class LoggingAuditSink:
    """Escreve uma linha JSON por consulta no logger de auditoria."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(AUDIT_LOGGER_NAME)

    def record(self, entry: QueryAuditRecord) -> None:
        self._logger.info(json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True))
