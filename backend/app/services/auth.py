"""Database-backed local login and revocable opaque browser sessions."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import TypeAlias
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.models.auth import AuthSession, AuthUser


ALLOWED_PERMISSIONS = frozenset({"orders:read", "orders:write"})
LoginResult: TypeAlias = tuple[AuthUser, AuthSession, str]
_dummy_password_hash = hash_password(token_urlsafe(32))


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def login(db: Session, username: str, password: str, current_token: str | None) -> LoginResult | None:
    user = db.scalar(select(AuthUser).where(AuthUser.username == normalize_username(username)))
    password_hash = user.password_hash if user is not None else _dummy_password_hash
    password_valid = verify_password(password, password_hash)
    if user is None or not user.is_active or not password_valid:
        return None

    revoke(db, current_token, commit=False)
    token = token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.AUTH_SESSION_LIFETIME_SECONDS)
    session = AuthSession(
        id=str(uuid4()),
        token_hash=hash_token(token),
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(user)
    return user, session, token


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def revoke(db: Session, token: str | None, *, commit: bool = True) -> None:
    if not token:
        return
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is not None:
        db.delete(session)
        if commit:
            db.commit()


def resolve_session(db: Session, token: str | None) -> tuple[AuthUser, AuthSession] | None:
    if not token or len(token) > 256:
        return None
    now = datetime.now(timezone.utc)
    result = db.execute(
        select(AuthUser, AuthSession)
        .join(AuthSession, AuthSession.user_id == AuthUser.id)
        .where(
            AuthSession.token_hash == hash_token(token),
            AuthUser.is_active.is_(True),
        )
    ).one_or_none()
    if result is None:
        return None
    user, session = result
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return None
    return user, session


def permissions_for(user: AuthUser) -> frozenset[str]:
    permissions = frozenset(user.permissions or ()) & ALLOWED_PERMISSIONS
    if "orders:write" in permissions:
        permissions |= {"orders:read"}
    return permissions
