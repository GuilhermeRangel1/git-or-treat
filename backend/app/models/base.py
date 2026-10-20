from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from app.db.base import Base


class TimestampMixin:
    """Mixin que adiciona timestamps com fuso horário (TIMESTAMPTZ no PostgreSQL)."""
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
