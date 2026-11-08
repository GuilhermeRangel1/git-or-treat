"""Geração e revisão F1 em observação; não chama executor nem concede prontidão."""

import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate, SqlGenerationRequest
from app.services.genai_client import GenAIQuestionClient, GenAIResponseInvalid
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_domain_policy import (
    OUT_OF_DOMAIN_MESSAGE,
    is_explicitly_outside_energy_domain,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_question_feedback import (
    ScopeDecisionRejected,
    enforce_scope_decision,
    full_year_coverage_gap,
    incomplete_year_candidate,
)
from app.services.genai_sql_admission import (
    SqlAdmission,
    SqlAdmissionDenied,
    admit_sql_candidate,
)
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
    is_explicit_multi_metric_question,
    is_periodized_accumulated_attendance_question,
)
from app.services.genai_sql_parameters import SqlParameterMismatch
from app.services.genai_sql_semantics import SqlSemanticReview, review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected
from app.services.genai_sql_telemetry import record_sql_stage, sql_stage

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


def log_sql_context_unavailable(
    error: SqlContextUnavailable, correlation_id: str
) -> None:
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
    model_calls: int = 1


@dataclass(frozen=True)
class SqlPreparation:
    candidate: SqlGenerationCandidate
    admission: SqlAdmission | None
    model_calls: int = 1


def assert_current_sql_request_context(
    request: QuestionPlanRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    publication: GoldPublicationContext,
) -> None:
    """Binds generation to a freshly resolved session scope and publication."""
    if (
        resolve_scope() != request.access_scope
        or publication.batch_ref != request.batch_ref
    ):
        raise SqlAdmissionDenied("Contexto SQL indisponível antes da geração.")


async def observe_sql_generation(
    request: QuestionPlanRequest,
    *,
    client: GenAIQuestionClient,
    deadline: GenAIRequestDeadline,
    correlation_id: str,
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
    context_started = perf_counter()
    try:
        context = build_sql_generation_context(request)
    except SqlContextUnavailable as exc:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="context",
            elapsed_ms=int((perf_counter() - context_started) * 1000),
            outcome="error",
            reason="context_unavailable",
        )
        log_sql_context_unavailable(exc, correlation_id)
        raise
    record_sql_stage(
        correlation_id=correlation_id,
        stage="context",
        elapsed_ms=int((perf_counter() - context_started) * 1000),
        outcome="success",
        context_version=context.context_version,
        mapping_version=context.mapping_version,
        dictionary_version=context.dictionary_version,
    )
    log_sql_context_ready(context, correlation_id)
    question = request.question.casefold()
    if context.metric_ids in {
        ("service.accumulated_attendance",),
        ("service.accumulated_satisfaction",),
    } and is_periodized_accumulated_attendance_question(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="accumulated_period_unavailable",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                scope_assessment={"status": "in_domain"},
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "reason_code": "unsupported_capability",
                    "message": (
                        "A Gold publica o total acumulado de protocolos sem informar "
                        "o intervalo histórico; não é possível responder por mês ou ano."
                        if context.metric_ids == ("service.accumulated_attendance",)
                        else "A Gold publica a média de satisfação do histórico sem "
                        "informar o intervalo; não é possível responder por mês ou ano."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if is_explicitly_outside_energy_domain(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="outside_domain",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                scope_assessment={"status": "out_of_domain"},
                unsupported_reason={
                    "code": "metric_outside_f1",
                    "reason_code": "out_of_domain",
                    "message": OUT_OF_DOMAIN_MESSAGE,
                },
            ),
            None,
            model_calls=0,
        )
    if is_explicit_multi_metric_question(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="multiple_metrics_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                scope_assessment={"status": "in_domain"},
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "reason_code": "unsupported_capability",
                    "message": (
                        "Esta pergunta combina consumo medido e faturamento; "
                        "a análise conjunta ainda não está disponível."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if not request.context and re.fullmatch(
        r"(?:qual\s+(?:foi\s+)?a\s+)?receita\s*[?!\.]*",
        question.strip(),
    ):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="clarification",
            reason="ambiguous_subject",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="needs_clarification",
                context_version=context.context_version,
                scope_assessment={"status": "uncertain"},
                clarification={
                    "question": "Você quer saber a receita de energia? Para qual período?",
                    "missing_fields": ["metric", "period"],
                    "reason_code": "ambiguous_subject",
                },
            ),
            None,
            model_calls=0,
        )
    coverage = next(
        (
            item
            for item in request.temporal_coverage
            if item.metric_id == context.metric_ids[0] and item.kind == "monthly"
        ),
        None,
    )
    year_gap = (
        full_year_coverage_gap(request.question, coverage.competencies)
        if coverage is not None
        else None
    )
    if year_gap is not None:
        # "Fechado" pede o ano completo: sem os doze meses publicados não há consulta.
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="clarification",
            reason="insufficient_coverage",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            incomplete_year_candidate(
                year_gap,
                generation_contract_version=context.generation_contract_version,
                context_version=context.context_version,
            ),
            None,
            model_calls=0,
        )
    payload = SqlGenerationRequest(
        generation_contract_version=context.generation_contract_version,
        context_version=context.context_version,
        contents=context.contents,
        remaining_timeout_ms=deadline.remaining_timeout_ms(stage_seconds),
    )
    with sql_stage(
        correlation_id, "generation", context_version=context.context_version
    ):
        response = await deadline.run(
            stage_seconds,
            lambda: client.generate_sql_candidate(
                payload, correlation_id=correlation_id
            ),
        )
    try:
        # Decisão de assunto ausente ou contraditória nunca chega à revisão nem à admissão.
        candidate = enforce_scope_decision(response.candidate)
    except ScopeDecisionRejected:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="error",
            reason="scope_decision_rejected",
            context_version=context.context_version,
        )
        raise GenAIResponseInvalid from None
    if candidate.status != "sql_candidate":
        deadline.remaining_seconds(stage_seconds)
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="clarification"
            if candidate.status == "needs_clarification"
            else "unsupported",
            reason=(
                candidate.clarification.reason_code
                if candidate.status == "needs_clarification"
                else candidate.unsupported_reason.reason_code
            ),
            context_version=context.context_version,
        )
        return SqlGenerationObservation(candidate, None)
    with sql_stage(
        correlation_id, "semantic_review", context_version=context.context_version
    ):
        try:
            reviewed = review_sql_semantics(candidate, request)
        except (SqlStructureRejected, SqlParameterMismatch):
            # An invalid model proposal is a controlled provider-response failure,
            # not an unhandled Backend exception. Keep the public error generic.
            raise GenAIResponseInvalid from None
    deadline.remaining_seconds(stage_seconds)
    return SqlGenerationObservation(candidate, reviewed)


async def prepare_sql_candidate(
    request: QuestionPlanRequest,
    *,
    engine: Engine,
    readiness_engine: Engine,
    publication: GoldPublicationContext,
    client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope],
    approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline,
    correlation_id: str,
) -> SqlPreparation:
    """Compõe geração e admissão com uma única validade; sem execução ou rota pública."""
    deadline = GenAIRequestDeadline(
        min(
            deadline.expires_at, deadline.clock() + request.remaining_timeout_ms / 1000
        ),
        deadline.clock,
    )
    deadline.remaining_seconds(60)
    assert_current_sql_request_context(
        request,
        resolve_scope=resolve_scope,
        publication=publication,
    )
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    observed = await observe_sql_generation(
        request, client=client, deadline=deadline, correlation_id=correlation_id
    )
    if observed.review is None:
        return SqlPreparation(
            observed.candidate, None, model_calls=observed.model_calls
        )
    with sql_stage(correlation_id, "readiness_admission"):
        admitted = await admit_sql_candidate(
            observed.candidate,
            request,
            engine=engine,
            readiness_engine=readiness_engine,
            publication=publication,
            client=client,
            resolve_scope=resolve_scope,
            approved_controls=approved_controls,
            deadline=deadline,
            correlation_id=correlation_id,
        )
    return SqlPreparation(observed.candidate, admitted)
