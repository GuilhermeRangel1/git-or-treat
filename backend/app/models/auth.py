"""Operational user accounts and opaque browser sessions."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, JSON, String, func, true

from app.db.base import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(String(36), primary_key=True)
    username = Column(String(128), nullable=False, unique=True)
    password_hash = Column(String(512), nullable=False)
    permissions = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    user_id = Column(String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),)
