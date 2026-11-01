"""Coordenação Gold do Backend sobre plano, executor e síntese existentes."""

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.engine import Engine

from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_evidence import GoldEvidenceQuality
from app.schemas.genai_internal import AccessScope, QuestionSynthesisRequest
from app.schemas.genai_plan import QuestionPlanStatus
from app.schemas.gold_readiness import GoldReadinessReport
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
)
from app.services.genai_executor import GoldExecutionDenied, execute_gold_plan
from app.services.genai_flow import should_synthesize
from app.services.genai_planning import GoldPlanningResult, plan_gold_question
from app.services.gold_catalog import load_gold_catalog


async def answer_gold_question(
    engine: Engine,
    client: GenAIQuestionClient,
    request: AIQuestionRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    correlation_id: str,
    readiness_gate: Callable[[GoldPlanningResult], Awaitable[GoldReadinessReport]] | None = None,
) -> AIQuestionResponse:
    """Mantém plano, identidade, publicação e prazo entre as duas operações HTTP.

    A execução síncrona usa timeout no servidor PostgreSQL; cancelar a coroutine
    não constitui prova de cancelamento do trabalho na thread.
    """
    planned = await plan_gold_question(
        engine, client, request, resolve_scope=resolve_scope,
        correlation_id=correlation_id,
    )
    if planned.response.status is not QuestionPlanStatus.PLANNED:
        if planned.response.response is None:
            raise GenAIResponseInvalid
        return planned.response.response
    if planned.deadline is None or planned.access_scope is None or planned.source is None:
        raise GenAIResponseInvalid
    if readiness_gate is None:
        raise GenAIServiceUnavailable(retryable=False)
    report = await planned.deadline.run(35, lambda: readiness_gate(planned))
    report = GoldReadinessReport.model_validate(report.model_dump(mode="json"))
    metric = next(m for m in load_gold_catalog().metrics
                  if m.metric_id == planned.response.plan.metric_id)
    required = {*metric.required_capability_ids, planned.source.capability_id}
    if (report.batch_ref != planned.publication.batch_ref
        or report.lot_state not in {"ready", "partial"}
        or any(key not in report.capabilities or report.capabilities[key].status != "available"
               for key in required)):
        raise GenAIServiceUnavailable(retryable=False)
    quality = GoldEvidenceQuality(
        readiness_version=report.readiness_version,
        batch_ref=report.batch_ref,
        lot_state=report.lot_state,
        available_capability_ids=tuple(sorted(required)),
    )
    lookup = await planned.deadline.run(
        35, lambda: asyncio.to_thread(
            execute_gold_plan, engine, planned, resolve_scope=resolve_scope,
            quality=quality,
        ),
    )
    if not should_synthesize(
        planning_status=planned.response.status, lookup=lookup.model_dump(mode="json"),
        policy="completed_lookup",
    ):
        raise GenAIResponseInvalid
    current_scope = await planned.deadline.run(
        35, lambda: asyncio.to_thread(resolve_scope),
    )
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    await planned.deadline.run(
        35, lambda: asyncio.to_thread(planned.publication.assert_current, engine),
    )
    payload = QuestionSynthesisRequest(
        **request.model_dump(), access_scope=planned.access_scope,
        dimension_value_coverage=planned.dimension_value_coverage,
        remaining_timeout_ms=planned.deadline.remaining_timeout_ms(35),
        plan=planned.response.plan,
        plan_fingerprint=planned.response.plan_fingerprint,
        lookup=lookup, expected_batch_ref=planned.publication.batch_ref,
    )
    result = await planned.deadline.run(
        35, lambda: client.synthesize(payload, correlation_id=correlation_id),
    )
    current_scope = await planned.deadline.run(
        35, lambda: asyncio.to_thread(resolve_scope),
    )
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    await planned.deadline.run(
        35, lambda: asyncio.to_thread(planned.publication.assert_current, engine),
    )
    planned.deadline.remaining_seconds(35)
    return result


def build_readiness_gate(engine: Engine, client: GenAIQuestionClient, approved_controls):
    """Adapta o observador existente; aprovação vem da configuração do servidor."""
    async def evaluate(planned: GoldPlanningResult) -> GoldReadinessReport:
        plan = planned.response.plan
        periods = []
        if plan.window.start is not None:
            year, month = plan.window.start.year, plan.window.start.month
            while (year, month) <= (plan.window.end.year, plan.window.end.month):
                periods.append(f"{year:04d}-{month:02d}")
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return await client.evaluate_readiness(
            engine, requested_periods=tuple(periods),
            approved_controls=frozenset(approved_controls),
            correlation_id=planned.response.correlation_id,
            expected_batch_ref=planned.publication.batch_ref,
        )
    return evaluate
