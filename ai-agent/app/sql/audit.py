"""Trilha de auditoria das consultas SQL, sem linhas de resultado nem pergunta da pessoa.

Retenção e acesso a esta trilha ainda são decisão em aberto; por isso só há destinos em
memória (testes) e log de processo, sem persistência própria.
"""

import hashlib
import json
import logging
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
class QueryAuditRecord:
    status: AuditStatus
    dialect: str
    dictionary_version: str
    received_sql_chars: int
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
