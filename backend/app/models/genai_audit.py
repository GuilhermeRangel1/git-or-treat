"""Trilha operacional separada dos fatos Gold e sem conteúdo livre."""

from sqlalchemy import JSON, Column, DateTime, Index, String, Table

from app.db.base import Base

AUDIT_EVENTS = Table(
    "genai_audit_events", Base.metadata,
    Column("id", String(32), primary_key=True),
    Column("correlation_id", String(32), nullable=False),
    Column("service", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("event", JSON, nullable=False),
    Index("ix_genai_audit_correlation", "correlation_id", "created_at"),
    Index("ix_genai_audit_expiry", "expires_at"),
)
