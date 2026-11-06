"""Geração e revisão F1 em observação; não chama executor nem concede prontidão."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate, SqlGenerationRequest
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import (
    SqlAdmission,
    SqlAdmissionDenied,
    admit_sql_candidate,
)
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
)
from app.services.genai_sql_semantics import SqlSemanticReview, review_sql_semantics

logger = logging.getLogger(__name__)


def log_sql_context_ready(context, correlation_id: str) -> None:
    """Registra composição e versões do contexto, nunca conteúdo ou valores."""
    logger.info(
        "genai_sql_context outcome=ready correlation_id=%s context_version=%s "
        "context_bytes=%d mapping_version=%s dictionary_version=%s metric_ids=%s "
        "dimension_ids=%s column_names=%s coverage_months=%d dimension_value_count=%d "
        "truncation=none",
        correlation_id,
        context.context_version,
        context.context_bytes,
        context.mapping_version,
        context.dictionary_version,
        context.metric_ids,
        context.dimension_ids,
        context.column_names,
        context.coverage_months,
        context.dimension_value_count,
    )


def log_sql_context_unavailable(error: SqlContextUnavailable, correlation_id: str) -> None:
    """Registra apenas motivo tipado e tamanho, sem serializar a entrada."""
    logger.warning(
        "genai_sql_context outcome=unavailable correlation_id=%s reason=%s context_bytes=%s",
        correlation_id,
        error.reason,
        error.context_bytes,
    )


@dataclass(frozen=True)
class SqlGenerationObservation:
    candidate: SqlGenerationCandidate
    review: SqlSemanticReview | None


@dataclass(frozen=True)
class SqlPreparation:
    candidate: SqlGenerationCandidate
    admission: SqlAdmission | None


def assert_current_sql_request_context(
    request: QuestionPlanRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    publication: GoldPublicationContext,
) -> None:
    """Binds generation to a freshly resolved session scope and publication."""
    if resolve_scope() != request.access_scope or publication.batch_ref != request.batch_ref:
        raise SqlAdmissionDenied("Contexto SQL indisponível antes da geração.")


async def observe_sql_generation(
    request: QuestionPlanRequest, *, client: GenAIQuestionClient,
    deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlGenerationObservation:
    """Recebe contexto resolvido e o prazo já iniciado pelo coordenador Backend.

    Uso interno opt-in; não substitui a estratégia pública. Falhas de provedor ou
    revisão são propagadas sem retry/fallback e sem converter erro em resposta.
    """
    stage_seconds = min(request.remaining_timeout_ms / 1000, 60)
    # Reduz o prazo absoluto recebido, sem renovar o saldo entre etapas.
    deadline = GenAIRequestDeadline(
        expires_at=min(deadline.expires_at, deadline.clock() + stage_seconds),
        clock=deadline.clock,
    )
    deadline.remaining_seconds(stage_seconds)
    try:
        context = build_sql_generation_context(request)
    except SqlContextUnavailable as exc:
        log_sql_context_unavailable(exc, correlation_id)
        raise
    log_sql_context_ready(context, correlation_id)
    payload = SqlGenerationRequest(
        context_version=context.context_version, contents=context.contents,
        remaining_timeout_ms=deadline.remaining_timeout_ms(stage_seconds),
    )
    response = await deadline.run(stage_seconds, lambda: client.generate_sql_candidate(
        payload, correlation_id=correlation_id))
    candidate = response.candidate
    if candidate.status != "sql_candidate":
        deadline.remaining_seconds(stage_seconds)
        return SqlGenerationObservation(candidate, None)
    reviewed = review_sql_semantics(candidate, request)
    deadline.remaining_seconds(stage_seconds)
    return SqlGenerationObservation(candidate, reviewed)


async def prepare_sql_candidate(
    request: QuestionPlanRequest, *, engine: Engine, readiness_engine: Engine, publication: GoldPublicationContext,
    client: GenAIQuestionClient, resolve_scope: Callable[[], AccessScope],
    approved_controls: frozenset[str], deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlPreparation:
    """Compõe geração e admissão com uma única validade; sem execução ou rota pública."""
    deadline = GenAIRequestDeadline(
        min(deadline.expires_at, deadline.clock() + request.remaining_timeout_ms / 1000),
        deadline.clock,
    )
    deadline.remaining_seconds(60)
    assert_current_sql_request_context(
        request, resolve_scope=resolve_scope, publication=publication,
    )
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    observed = await observe_sql_generation(
        request, client=client, deadline=deadline, correlation_id=correlation_id)
    if observed.review is None:
        return SqlPreparation(observed.candidate, None)
    admitted = await admit_sql_candidate(
        observed.candidate, request, engine=engine, readiness_engine=readiness_engine, publication=publication, client=client,
        resolve_scope=resolve_scope, approved_controls=approved_controls,
        deadline=deadline, correlation_id=correlation_id)
    return SqlPreparation(observed.candidate, admitted)
