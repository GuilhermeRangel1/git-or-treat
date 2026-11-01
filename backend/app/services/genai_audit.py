"""Confirma cada evento antes de reconhecer escrita; leitura apenas administrativa."""

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, insert, select, text
from sqlalchemy.engine import Engine

from app.models.genai_audit import AUDIT_EVENTS
from app.schemas.genai_audit import BackendAuditEvent, GenAIAuditEvent

RETENTION_DAYS = 30


class AuditStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def record(self, event: GenAIAuditEvent, *, service="genai", now=None) -> str:
        schema = BackendAuditEvent if service == "backend" else GenAIAuditEvent
        event = schema.model_validate(event.model_dump(mode="json"))
        if service not in {"backend", "genai"}:
            raise ValueError("serviço de auditoria inválido")
        now = now or datetime.now(UTC)
        reference = uuid4().hex
        with self._engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET LOCAL statement_timeout = '2s'"))
                connection.execute(text("SET LOCAL lock_timeout = '500ms'"))
            connection.execute(insert(AUDIT_EVENTS).values(
                id=reference, correlation_id=event.correlation_id, service=service,
                created_at=now, expires_at=now + timedelta(days=RETENTION_DAYS),
                event=event.model_dump(mode="json"),
            ))
        return reference

    def read(self, correlation_id: str, *, now=None) -> list[dict]:
        now = now or datetime.now(UTC)
        with self._engine.connect() as connection:
            rows = connection.execute(select(AUDIT_EVENTS).where(
                AUDIT_EVENTS.c.correlation_id == correlation_id,
                AUDIT_EVENTS.c.expires_at > now,
            ).order_by(AUDIT_EVENTS.c.created_at, AUDIT_EVENTS.c.id)).mappings().all()
        return [dict(row) for row in rows]

    def purge(self, *, now=None) -> int:
        with self._engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET LOCAL statement_timeout = '2s'"))
                connection.execute(text("SET LOCAL lock_timeout = '500ms'"))
            result = connection.execute(delete(AUDIT_EVENTS).where(
                AUDIT_EVENTS.c.expires_at <= (now or datetime.now(UTC)),
            ))
        return result.rowcount

    def read_reference(self, reference: str, *, now=None) -> list[dict]:
        if re.fullmatch(r"[a-f0-9]{32}", reference) is None:
            raise ValueError("Referência inválida.")
        now = now or datetime.now(UTC)
        with self._engine.connect() as connection:
            correlation = connection.execute(select(AUDIT_EVENTS.c.correlation_id).where(
                AUDIT_EVENTS.c.id == reference, AUDIT_EVENTS.c.expires_at > now,
            )).scalar_one_or_none()
        return [] if correlation is None else self.read(correlation, now=now)
