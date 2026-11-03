"""Histórico operacional privado; nunca acessado pelo leitor Gold."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
)

from app.db.base import Base

CONVERSATIONS = Table(
    "ai_conversations",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "owner_id",
        String(36),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_id", String(36), nullable=False),
    Column("title", String(120), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("owner_id", "request_id", name="uq_ai_conversation_creation"),
    Index("ix_ai_conversation_owner_updated", "owner_id", "updated_at"),
    Index("ix_ai_conversation_expiry", "expires_at"),
)

EXCHANGES = Table(
    "ai_conversation_exchanges",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "conversation_id",
        String(36),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_id", String(36), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("attempt_id", String(36), nullable=False),
    Column("format_version", Integer, nullable=False),
    Column("request_digest", String(64), nullable=False),
    Column("scope_digest", String(64), nullable=False),
    Column("state", String(16), nullable=False),
    Column("lease_until", DateTime(timezone=True), nullable=False),
    Column("question", String(1000), nullable=True),
    Column("response", JSON, nullable=True),
    Column("anchor", String(1000), nullable=True),
    Column("batch", String(200), nullable=True),
    UniqueConstraint("conversation_id", "request_id", name="uq_ai_exchange_request"),
    UniqueConstraint("conversation_id", "sequence", name="uq_ai_exchange_sequence"),
)
