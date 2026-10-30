from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.auth import AuthUser
from app.schemas.auth import LoginRequest, SessionEnvelope, SessionUser
from app.services import auth as auth_service


router = APIRouter()
COOKIE_NAME = "grid360_session"
COOKIE_PATH = "/api/v1"
MAX_LOGIN_BUCKETS = 4096
_login_attempts: OrderedDict[str, list[float]] = OrderedDict()
_login_attempts_lock = Lock()
Database = Annotated[Session, Depends(get_db)]


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if (
        origin is None
        or origin == "null"
        or origin not in settings.BACKEND_CORS_ORIGINS
        or request.headers.get("sec-fetch-site", "").lower() == "cross-site"
    ):
        raise HTTPException(403, "Origem não permitida.")


def _session_user(user: AuthUser) -> SessionUser:
    permissions = sorted(auth_service.permissions_for(user))
    return SessionUser(id=user.id, username=user.username, permissions=permissions)


def _envelope(user: AuthUser | None, expires_at: datetime | None = None) -> SessionEnvelope:
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return SessionEnvelope(
        enabled=settings.ORDERS_AUTH_MODE == "session",
        user=_session_user(user) if user is not None else None,
        expires_at=expires_at.isoformat().replace("+00:00", "Z") if expires_at is not None else None,
    )


def _check_login_rate(request: Request, username: str) -> str:
    now = monotonic()
    peer = request.client.host if request.client is not None else "unknown"
    key = f"{peer}:{auth_service.normalize_username(username)}"
    cutoff = now - settings.AUTH_LOGIN_WINDOW_SECONDS
    with _login_attempts_lock:
        attempts = [attempt for attempt in _login_attempts.get(key, []) if attempt > cutoff]
        if len(attempts) >= settings.AUTH_LOGIN_ATTEMPTS:
            _login_attempts[key] = attempts
            _login_attempts.move_to_end(key)
            raise HTTPException(429, "Muitas tentativas. Aguarde antes de tentar novamente.", headers={"Retry-After": str(settings.AUTH_LOGIN_WINDOW_SECONDS)})
        attempts.append(now)
        if key not in _login_attempts and len(_login_attempts) >= MAX_LOGIN_BUCKETS:
            _login_attempts.popitem(last=False)
        _login_attempts[key] = attempts
        _login_attempts.move_to_end(key)
    return key


@router.get("/session", response_model=SessionEnvelope)
def get_session(request: Request, response: Response, db: Database) -> SessionEnvelope:
    response.headers["Cache-Control"] = "no-store"
    if settings.ORDERS_AUTH_MODE != "session":
        return _envelope(None)
    resolved = auth_service.resolve_session(db, request.cookies.get(COOKIE_NAME))
    if resolved is None:
        return _envelope(None)
    user, session = resolved
    return _envelope(user, session.expires_at)


@router.post("/login", response_model=SessionEnvelope)
def login(payload: LoginRequest, request: Request, response: Response, db: Database) -> SessionEnvelope:
    if settings.ORDERS_AUTH_MODE != "session":
        raise HTTPException(503, "Login individual não está habilitado.")
    _require_same_origin(request)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(415, "Content-Type application/json obrigatório.")
    limiter_key = _check_login_rate(request, payload.username)
    result = auth_service.login(db, payload.username, payload.password.get_secret_value(), request.cookies.get(COOKIE_NAME))
    if result is None:
        raise HTTPException(401, "Usuário ou senha inválidos.")
    with _login_attempts_lock:
        _login_attempts.pop(limiter_key, None)
    user, session, token = result
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.AUTH_SESSION_LIFETIME_SECONDS,
        path=COOKIE_PATH,
        secure=settings.APP_ENV == "production",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return _envelope(user, session.expires_at)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database) -> None:
    _require_same_origin(request)
    if settings.ORDERS_AUTH_MODE == "session":
        auth_service.revoke(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        secure=settings.APP_ENV == "production",
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
