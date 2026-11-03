"""Histórico privado coordena armazenamento e reutiliza a consulta pública existente."""

import asyncio
import logging
from collections.abc import Callable
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.ai import (
    AIQuestionRoute,
    _question_error,
    ask_genai_question,
    get_genai_question_client,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_access import get_genai_gold_access_resolver
from app.core.genai_gold_database import (
    get_question_gold_readiness_gate,
    get_question_gold_resources,
)
from app.core.order_access import READ, get_order_identity
from app.repositories.gold_publication import (
    GoldPublicationUnavailable,
    current_publication,
)
from app.schemas.ai import AIConversationTurn, AIQuestionResponse
from app.schemas.ai_conversations import (
    ConversationCreate,
    ConversationDetail,
    ConversationListing,
    ConversationQuestion,
    ConversationRename,
    ConversationSummary,
)
from app.schemas.ai_question_publication import AIQuestionPublicRequest
from app.schemas.genai_internal import AccessScope
from app.services.ai_conversations import ConversationStore
from app.services.conversation_memory import MemoryUnavailable, memory_request
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_continuation import (
    _catalog_digest,
    _scope_digest,
    issue_context_continuation,
    restore_continuation,
)

router = APIRouter(route_class=AIQuestionRoute)
Database = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


def access(request: Request, response: Response, db: Database):
    response.headers["Cache-Control"] = "no-store"
    if settings.ORDERS_AUTH_MODE != "session":
        raise HTTPException(503, "Histórico exige sessão individual.")
    identity = get_order_identity(request, None, db)
    if READ not in identity.permissions:
        raise HTTPException(403, "Histórico não autorizado.")
    return identity.actor.removeprefix("user:")


Owner = Annotated[str, Depends(access)]


def current_scope(request, db):
    return get_genai_gold_access_resolver(request, None, db)()


def history_scope(scope):
    return sha256((_scope_digest(scope) + _catalog_digest()).encode()).hexdigest()


@router.post("/conversations", response_model=ConversationSummary)
def create(payload: ConversationCreate, owner: Owner, db: Database):
    result = ConversationStore(db, owner).create(str(payload.request_id))
    logger.info("Histórico: criação confirmada.")
    return result


@router.get("/conversations", response_model=ConversationListing)
def listing(
    owner: Owner, db: Database, offset: Annotated[int, Query(ge=0, le=10000)] = 0
):
    return ConversationStore(db, owner).listing(offset)


@router.get("/conversations/{conversation}", response_model=ConversationDetail)
def detail(conversation: UUID, owner: Owner, db: Database, request: Request):
    return ConversationStore(db, owner).detail(
        str(conversation), history_scope(current_scope(request, db))
    )


@router.patch("/conversations/{conversation}", response_model=ConversationSummary)
def rename(conversation: UUID, payload: ConversationRename, owner: Owner, db: Database):
    return ConversationStore(db, owner).rename(
        str(conversation), payload.title, payload.expected_revision
    )


@router.delete("/conversations/{conversation}", status_code=204)
def remove(conversation: UUID, owner: Owner, db: Database):
    ConversationStore(db, owner).remove(str(conversation))
    logger.info("Histórico: exclusão confirmada.")


@router.post(
    "/conversations/{conversation}/questions", response_model=AIQuestionResponse
)
async def question(
    conversation: UUID,
    payload: ConversationQuestion,
    request: Request,
    owner: Owner,
    db: Database,
    genai: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    readiness_gate: Annotated[
        Callable | None, Depends(get_question_gold_readiness_gate)
    ],
):
    store = ConversationStore(db, owner)
    identity = str(conversation)
    scope = current_scope(request, db)
    try:
        cached, previous, attempt = store.reserve(
            identity,
            str(payload.request_id),
            payload.model_dump_json(exclude={"request_id"}),
            history_scope(scope),
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        return _question_error(
            request,
            status_code=409,
            code="conversation_conflict",
            retryable=True,
            message=exc.detail,
        )
    if cached is not None:
        batch = (
            cached.analysis_context.batch_reference if cached.analysis_context else None
        )
        if batch is not None and gold_resources is not None:
            try:
                with gold_resources[0].connect() as connection:
                    current_publication(connection, batch)
            except GoldPublicationUnavailable:
                return _question_error(
                    request,
                    status_code=409,
                    code="conversation_conflict",
                    retryable=False,
                    message="Esta resposta pertence a dados anteriores. Envie uma nova pergunta para atualizar.",
                )
        return cached
    anchor, recent = previous
    context = []
    token = None
    secret = settings.AI_AGENT_SERVICE_API_TOKEN
    if anchor is not None:
        context = [AIConversationTurn(role="user", content=anchor["anchor"])]
        if not payload.refresh_context and secret is not None:
            token = issue_context_continuation(
                anchor["anchor"],
                scope,
                anchor["batch"],
                session=request.cookies.get("grid360_session", ""),
                conversation=identity,
                secret=secret.get_secret_value(),
                kind=("pending" if anchor["response"]["status"] == "needs_clarification"
                      else "executed"),
                response_text=anchor["response"].get("answer")
                or anchor["response"].get("message", ""),
            )
            context = []
    if (
        recent is not None
        and recent["response"]
        and recent["response"].get("status") == "needs_clarification"
    ):
        context += [
            AIConversationTurn(role="user", content=recent["anchor"] or recent["question"]),
            AIConversationTurn(
                role="assistant", content=recent["response"]["message"][:1000]
            ),
        ]
    question_text = payload.question
    if settings.GENAI_CONVERSATION_MEMORY_ENABLED:
        try:
            reference = memory_request(payload.question)
            if reference is not None:
                if secret is None or gold_resources is None:
                    raise MemoryUnavailable
                remembered = store.memory(identity, history_scope(scope), reference)
                db.commit()  # Não manter snapshot/lock durante consulta ou modelo.
                token = None
                if remembered.kind == "gold":
                    token = issue_context_continuation(
                        remembered.question, scope, remembered.batch,
                        session=request.cookies.get("grid360_session", ""),
                        conversation=identity, secret=secret.get_secret_value(),
                    )
                    if token is None:
                        raise MemoryUnavailable
                context = []
                question_text = reference.follow_up or remembered.question
                logger.info("Memória: versão %s, sequência de origem %s.",
                            remembered.version, remembered.source_sequence)
        except MemoryUnavailable:
            store.interrupt(identity, str(payload.request_id), attempt)
            return _question_error(
                request, status_code=409, code="conversation_conflict", retryable=False,
                message="Não foi possível retomar essa consulta com o acesso atual. "
                        "Informe novamente o indicador, o período e o local desejados.",
            )
    question_payload = AIQuestionPublicRequest(
        question=question_text,
        context=context,
        conversation_id=identity,
        continuation_token=token,
        expected_publication=payload.expected_publication,
    )
    try:
        result = await ask_genai_question(
            question_payload, request, genai, gold_resources, readiness_gate, db
        )
        # Uma nova sessão/transação verifica revogação após a chamada externa.
        current_scope(request, db)
        if isinstance(result, JSONResponse):
            store.interrupt(identity, str(payload.request_id), attempt)
            return result
        normalized, batch = None, None
        if result.continuation_token and secret is not None:
            batch, restored = restore_continuation(
                result.continuation_token,
                scope,
                session=request.cookies.get("grid360_session", ""),
                conversation=identity,
                secret=secret.get_secret_value(),
                context=[],
            )
            normalized = restored[0].content
        elif any(item.source == "documentation.indicators" for item in result.evidence):
            # Conserva a pergunta executada, inclusive após retomadas sucessivas.
            # A resposta antiga nunca é usada para reconstruir a intenção.
            normalized = question_text
        store.finish(
            identity,
            str(payload.request_id),
            attempt,
            payload.question,
            result,
            normalized,
            batch,
        )
        return result
    except (Exception, asyncio.CancelledError) as exc:
        db.rollback()
        store.interrupt(identity, str(payload.request_id), attempt)
        if isinstance(exc, HTTPException) and exc.status_code == 409:
            return _question_error(
                request,
                status_code=409,
                code="conversation_conflict",
                retryable=True,
                message=exc.detail,
            )
        raise
