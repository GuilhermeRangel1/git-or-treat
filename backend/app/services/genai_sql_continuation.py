"""Contexto F1 portátil e autenticado; não persiste respostas nem autoriza SQL."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.schemas.ai import AIConversationTurn
from app.schemas.genai_internal import AccessScope
from app.services.gold_catalog import load_gold_catalog

TTL_SECONDS = 1800
MAX_TOKEN_LENGTH = 16000
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SqlContinuationState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(strict=True, ge=1, le=1)
    expires_at: int = Field(strict=True, gt=0)
    session_digest: Digest
    conversation_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9-]{36}$")]
    scope_digest: Digest
    catalog_digest: Digest
    batch_ref: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    context: tuple[AIConversationTurn, ...] = Field(max_length=3)


class InvalidSqlContinuation(ValueError):
    """Token expirado, adulterado ou de outra sessão/publicação."""


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scope_digest(scope: AccessScope) -> str:
    values = scope.model_dump(mode="json")
    for key, value in values.items():
        if isinstance(value, list):
            values[key] = sorted(value)
    return _canonical_digest(values)


def _key(secret: str) -> bytes:
    return hmac.digest(secret.encode("utf-8"), b"grid360:genai:sql-continuation:v1", "sha256")


def _catalog_digest() -> str:
    catalog = load_gold_catalog().model_dump(mode="json")
    return _canonical_digest({"contract": "text-to-sql-f1-v1", "catalog": catalog})


def issue_sql_continuation(
    *,
    question: str,
    response: str,
    previous_context: Sequence[AIConversationTurn],
    scope: AccessScope,
    batch_ref: str,
    session: str,
    conversation_id: str,
    secret: str,
    now: int | None = None,
) -> str | None:
    """Assina turnos exibidos ao usuário; SQL, parâmetros e linhas não entram no token."""
    turns = [*previous_context, AIConversationTurn(role="user", content=question),
             AIConversationTurn(role="assistant", content=response[:1000])]
    return issue_sql_context_continuation(
        context=turns,
        scope=scope,
        batch_ref=batch_ref,
        session=session,
        conversation_id=conversation_id,
        secret=secret,
        now=now,
    )


def issue_sql_context_continuation(
    *,
    context: Sequence[AIConversationTurn],
    scope: AccessScope,
    batch_ref: str,
    session: str,
    conversation_id: str,
    secret: str,
    now: int | None = None,
) -> str | None:
    """Assina turnos previamente carregados pelo armazenamento privado da conversa."""
    if not session or not secret or not conversation_id or not context:
        return None
    state = SqlContinuationState(
        version=1,
        expires_at=(int(time.time()) if now is None else now) + TTL_SECONDS,
        session_digest=hashlib.sha256(session.encode("utf-8")).hexdigest(),
        conversation_id=conversation_id,
        scope_digest=_scope_digest(scope),
        catalog_digest=_catalog_digest(),
        batch_ref=batch_ref,
        context=tuple(context[-3:]),
    )
    data = base64.urlsafe_b64encode(state.model_dump_json().encode("utf-8")).decode("ascii")
    token = data + "." + hmac.digest(_key(secret), data.encode("ascii"), "sha256").hex()
    return token if len(token) <= MAX_TOKEN_LENGTH else None


def restore_sql_continuation(
    token: str,
    *,
    scope: AccessScope,
    batch_ref: str,
    session: str,
    conversation_id: str,
    secret: str,
    now: int | None = None,
) -> list[AIConversationTurn]:
    """Restaura apenas contexto assinado após validar identidade, publicação e catálogo."""
    try:
        if not token or len(token) > MAX_TOKEN_LENGTH:
            raise ValueError
        data, signature = token.split(".")
        expected = hmac.digest(_key(secret), data.encode("ascii"), "sha256").hex()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        raw = base64.b64decode(data, altchars=b"-_", validate=True)
        state = SqlContinuationState.model_validate_json(raw)
        current_time = int(time.time()) if now is None else now
        if (
            state.expires_at <= current_time
            or state.session_digest != hashlib.sha256(session.encode("utf-8")).hexdigest()
            or state.conversation_id != conversation_id
            or state.scope_digest != _scope_digest(scope)
            or state.catalog_digest != _catalog_digest()
            or state.batch_ref != batch_ref
            or not state.context
            or state.context[-1].role != "assistant"
        ):
            raise ValueError
        return list(state.context)
    except (ValueError, KeyError, TypeError, UnicodeError, ValidationError):
        raise InvalidSqlContinuation from None
