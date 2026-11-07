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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.ai import (
    AIQuestionRoute,
    enforce_explicit_question_domain,
    _question_error,
    _run_f1_sql_analysis_impl,
    ask_genai_question,
    get_genai_question_client,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_access import get_genai_gold_access_resolver
from app.core.genai_gold_database import (
    create_genai_gold_engine,
    get_question_gold_readiness_gate,
    get_question_gold_resources,
)
from app.core.platform_identity import get_platform_identity
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
from app.schemas.sql_analysis import SqlAnalysisRequest, SqlAnalysisResponse
from app.services.ai_conversations import ConversationStore, sql_replay_audit_matches
from app.services.conversation_memory import MemoryUnavailable, memory_request
from app.services.genai_audit import AuditStore
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_continuation import (
    _catalog_digest,
    _scope_digest,
    issue_context_continuation,
    restore_continuation,
)
from app.services.genai_expected_publication import (
    ExpectedPublicationMismatch,
    resolve_expected_batch_ref,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_continuation import issue_sql_context_continuation

router = APIRouter(route_class=AIQuestionRoute)
Database = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


def access(request: Request, response: Response, db: Database):
    response.headers["Cache-Control"] = "no-store"
    if settings.ORDERS_AUTH_MODE != "session":
        raise HTTPException(503, "Histórico exige sessão individual.")
    if request.headers.get("authorization"):
        raise HTTPException(401, "Credencial inválida ou expirada.")
    identity = get_platform_identity(request, None, db)
    if "ai:ask" not in identity.permissions:
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
    scope = current_scope(request, db)
    result = ConversationStore(db, owner).detail(str(conversation), history_scope(scope))
    visual_responses = [e["response"] for e in result["exchanges"] if e["response"] and e["response"].get("visualization")]
    sql_responses = [e["sql_response"] for e in result["exchanges"] if e.get("sql_response")]
    if visual_responses or sql_responses:
        current_batch = None
        engine = None
        try:
            engine = create_genai_gold_engine(scope)
            with engine.connect() as connection:
                current_batch = current_publication(connection).batch_ref
        except (GoldPublicationUnavailable, SQLAlchemyError, ValueError, TypeError):
            current_batch = None
        finally:
            if engine is not None:
                engine.dispose()
        for response in visual_responses:
            context = response.get("analysis_context") or {}
            if current_batch is None or context.get("batch_reference") != current_batch:
                response.pop("visualization", None)
        audit_by_reference = {}
        if sql_responses:
            try:
                audit_by_reference = AuditStore(db.get_bind()).read_references(
                    response["audit_reference"] for response in sql_responses
                )
            except (SQLAlchemyError, ValueError, TypeError):
                # Fail closed: saved quantitative output needs its original audit.
                audit_by_reference = {}
        for exchange in result["exchanges"]:
            response = exchange.get("sql_response")
            batch_ref = exchange.get("batch_ref")
            try:
                parsed = SqlAnalysisResponse.model_validate(response) if response else None
            except (ValueError, TypeError):
                parsed = None
            if response is not None and (
                parsed is None
                or current_batch is None
                or batch_ref != current_batch
                or not sql_replay_audit_matches(
                    parsed,
                    audit_by_reference.get(parsed.audit_reference, []),
                    reference=parsed.audit_reference,
                    scope=scope,
                    batch=batch_ref,
                )
            ):
                exchange["sql_response"] = None
                exchange["question"] = None
                exchange["batch_ref"] = None
                exchange["state"] = "unavailable"
        if history_scope(current_scope(request, db)) != history_scope(scope):
            raise HTTPException(403, "Acesso ao histórico alterado.")
    return result


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
    "/conversations/{conversation}/questions",
    response_model=AIQuestionResponse | SqlAnalysisResponse,
)
async def question(
    conversation: UUID,
    payload: ConversationQuestion,
    request: Request,
    owner: Owner,
    db: Database,
    _domain_policy: Annotated[None, Depends(enforce_explicit_question_domain)],
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
    if payload.strategy == "sql_f1":
        request.state.genai_strategy = "text_to_sql_f1"
        return await _sql_f1_conversation_question(
            identity=identity,
            payload=payload,
            request=request,
            scope=scope,
            owner=owner,
            db=db,
            store=store,
            genai=genai,
            gold_resources=gold_resources,
        )
    try:
        cached, previous, attempt = store.reserve(
            identity,
            str(payload.request_id),
            # `strategy` was added after legacy exchanges already existed.
            # Keep the legacy request fingerprint unchanged.
            payload.model_dump_json(exclude={"request_id", "strategy"}),
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


async def _sql_f1_conversation_question(
    *, identity, payload, request, scope, owner, db, store, genai, gold_resources,
):
    if gold_resources is None or gold_resources[0] is None:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=False,
            message="Leitura Gold indisponível para esta conversa.",
        )
    try:
        publication = GoldPublicationContext.capture(gold_resources[0])
        if payload.expected_publication is not None:
            expected_batch = resolve_expected_batch_ref(
                db.get_bind(), payload.expected_publication,
            )
            if expected_batch != publication.batch_ref:
                raise ExpectedPublicationMismatch
    except ExpectedPublicationMismatch:
        return _question_error(
            request, status_code=409, code="invalid_context", retryable=False,
            message="Os dados da tela foram atualizados. Recarregue a tela antes de perguntar.",
        )
    except GoldPublicationUnavailable:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=False,
            message="A publicação Gold não está disponível para esta conversa.",
        )
    scope_key = history_scope(scope)
    try:
        cached, context, attempt, cached_batch = store.reserve_sql(
            identity,
            str(payload.request_id),
            payload.question,
            scope_key,
            batch_ref=publication.batch_ref,
            refresh_context=payload.refresh_context,
            expected_publication=(
                payload.expected_publication.model_dump(mode="json")
                if payload.expected_publication is not None else None
            ),
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        return _question_error(
            request, status_code=409, code="conversation_conflict", retryable=True,
            message=exc.detail,
        )
    secret = settings.AI_AGENT_SERVICE_API_TOKEN
    session = request.cookies.get("grid360_session", "")
    if cached is not None:
        try:
            if not cached_batch or cached_batch != publication.batch_ref:
                raise GoldPublicationUnavailable
            with gold_resources[0].connect() as connection:
                current_publication(connection, cached_batch)
            if history_scope(current_scope(request, db)) != scope_key:
                raise HTTPException(403, "Acesso ao histórico alterado.")
            audit_events = AuditStore(db.get_bind()).read_reference(cached.audit_reference)
            if not sql_replay_audit_matches(
                cached, audit_events, reference=cached.audit_reference,
                scope=scope, batch=cached_batch,
            ):
                return _question_error(
                    request, status_code=409, code="conversation_conflict", retryable=False,
                    message="A evidência histórica não pôde ser validada. Faça uma nova pergunta.",
                )
        except GoldPublicationUnavailable:
            return _question_error(
                request, status_code=409, code="conversation_conflict", retryable=False,
                message="Esta resposta pertence a uma publicação anterior. Faça uma nova pergunta.",
            )
        token = None
        if secret is not None and session and context:
            token = issue_sql_context_continuation(
                context=context, scope=scope, batch_ref=cached_batch, session=session,
                conversation_id=identity, secret=secret.get_secret_value(),
            )
        return cached.model_copy(update={"continuation_token": token})

    try:
        publication = GoldPublicationContext.capture(gold_resources[0])
        result = await _run_f1_sql_analysis_impl(
            SqlAnalysisRequest(question=payload.question, conversation_id=identity),
            request,
            genai,
            gold_resources,
            db,
            trusted_context=context if not payload.refresh_context else [],
            trusted_batch_ref=publication.batch_ref,
        )
        if isinstance(result, JSONResponse):
            store.interrupt(identity, str(payload.request_id), attempt)
            return result
        if history_scope(current_scope(request, db)) != scope_key:
            raise HTTPException(403, "Acesso ao histórico alterado.")
        store.finish_sql(
            identity, str(payload.request_id), attempt, payload.question, result,
            publication.batch_ref,
        )
        return result
    except (Exception, asyncio.CancelledError):
        db.rollback()
        store.interrupt(identity, str(payload.request_id), attempt)
        raise
