"""Coordenação Gold do Backend sobre plano, executor e síntese existentes."""

import asyncio
import json
import logging
from calendar import monthrange
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date
from time import monotonic

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.genai_limits import GOLD_REQUEST_TIMEOUT_SECONDS
from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_evidence import GoldEvidenceQuality
from app.schemas.genai_internal import AccessScope, QuestionSynthesisRequest
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus, WindowKind
from app.schemas.gold_readiness import GoldReadinessReport
from app.services.chat_visualization import (
    build_chat_visualization,
    build_visual_preview,
)
from app.services.genai_audit import AuditStore
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_continuation import ranked_result_anchor
from app.services.genai_continuity_coverage import (
    GoldCoverageUnavailable,
    observed_coverage_valid,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import GoldExecutionDenied, execute_gold_plan
from app.services.genai_flow import should_synthesize
from app.services.genai_planning import GoldPlanningResult, plan_gold_question
from app.services.genai_replay import execution_artifact
from app.services.gold_catalog import GoldCatalogIncompatible, load_gold_catalog

OBSERVED_CONTINUITY_WARNING = "Valores observados; cobertura do alimentador não certificada."
_OBSERVED_CONTINUITY_METRICS = frozenset({
    "network.equivalent_interruption_duration",
    "network.equivalent_interruption_frequency",
})


def _requested_months(plan: LogicalReadPlan) -> tuple[str, ...]:
    window = getattr(plan, "window", None)
    if window is None:
        return ()
    if window.kind is not WindowKind.BOUNDED or window.granularity != "month":
        return ()
    if (
        window.start.day != 1
        or window.end.day != monthrange(window.end.year, window.end.month)[1]
    ):
        return ()
    if plan.comparison_periods is not None:
        return plan.comparison_periods
    current = date(window.start.year, window.start.month, 1)
    end = date(window.end.year, window.end.month, 1)
    periods = []
    while current <= end:
        periods.append(current.strftime("%Y-%m"))
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return tuple(periods)


def _observed_continuity_quality(
    report: GoldReadinessReport, plan: LogicalReadPlan, batch_ref: str
) -> GoldEvidenceQuality | None:
    """Autoriza somente a falha de certificação após os controles C11 passarem."""
    if report.batch_ref != batch_ref or plan.metric_id not in _OBSERVED_CONTINUITY_METRICS:
        return None
    periods = _requested_months(plan)
    feeder_filters = [
        item for item in getattr(plan, "filters", ())
        if item.dimension_id == "network.feeder"
    ]
    if (
        not periods
        or len(feeder_filters) != 1
        or feeder_filters[0].operator.value != "eq"
        or len(feeder_filters[0].values) != 1
        or getattr(plan, "group_by_dimension_ids", ())
    ):
        return None
    readiness = report.capabilities.get("interrupcoes.dec_fec")
    if (
        readiness is None
        or readiness.status != "unavailable"
        or readiness.reasons != ("coverage_incomplete",)
    ):
        return None
    return GoldEvidenceQuality(
        readiness_version=report.readiness_version,
        batch_ref=batch_ref,
        lot_state=report.lot_state,
        quality_mode="observed_uncertified",
        available_capability_ids=(),
        observed_capability_ids=("interrupcoes.dec_fec",),
        observed_periods=periods,
    )


def _apply_observed_continuity_warning(
    response: AIQuestionResponse, quality: GoldEvidenceQuality
) -> AIQuestionResponse:
    if quality.quality_mode != "observed_uncertified" or response.status != "answered":
        return response
    answer = response.answer or ""
    if OBSERVED_CONTINUITY_WARNING not in answer:
        suffix = f" {OBSERVED_CONTINUITY_WARNING}"
        answer = answer.rstrip()
        answer = answer[:4000 - len(suffix)].rstrip() + suffix
    limitations = list(response.limitations)
    if OBSERVED_CONTINUITY_WARNING not in limitations:
        limitations = limitations[:19]
        limitations.append(OBSERVED_CONTINUITY_WARNING)
    return response.model_copy(update={"answer": answer, "limitations": limitations})


async def answer_gold_question(
    engine: Engine | None,
    client: GenAIQuestionClient,
    request: AIQuestionRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    correlation_id: str,
    readiness_gate: Callable[[GoldPlanningResult], Awaitable[GoldReadinessReport]] | None = None,
    audit_store: AuditStore | None = None,
    expected_batch_ref: str | None = None,
    previous_approved_plan: LogicalReadPlan | None = None,
    continuation: Callable[[GoldPlanningResult, AIQuestionResponse], str | None] | None = None,
    request_deadline: GenAIRequestDeadline | None = None,
    on_visual: Callable[[AIQuestionResponse], Awaitable[None]] | None = None,
) -> AIQuestionResponse:
    """Mantém plano, identidade, publicação e prazo entre as duas operações HTTP.

    A execução síncrona usa timeout no servidor PostgreSQL; cancelar a coroutine
    não constitui prova de cancelamento do trabalho na thread.
    """
    if audit_store is None:
        raise GenAIServiceUnavailable(retryable=False)
    started = monotonic()
    deadline = request_deadline or GenAIRequestDeadline.start(GOLD_REQUEST_TIMEOUT_SECONDS)

    async def audit(stage, code, outcome, **metadata):
        event = BackendAuditEvent(
            correlation_id=correlation_id, stage=stage, code=code, outcome=outcome,
            duration_ms=max(0, int((monotonic() - started) * 1000)), **metadata,
        )
        try:
            return await asyncio.to_thread(audit_store.record, event, service="backend")
        except (SQLAlchemyError, ValueError):
            raise GenAIServiceUnavailable(retryable=False) from None

    await deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: audit("request", "started", "started"))
    # Publicação já conferida contra a tela; troca até a captura é mudança em curso.
    planned = await plan_gold_question(
        engine, client, request, resolve_scope=resolve_scope,
        correlation_id=correlation_id, expected_batch_ref=expected_batch_ref,
        previous_approved_plan=previous_approved_plan,
        deadline=deadline,
    )
    if planned.response.status is not QuestionPlanStatus.PLANNED:
        if planned.response.response is None:
            raise GenAIResponseInvalid
        response = planned.response.response
        outcome = "error" if response.status == "recoverable_error" else (
            "refused" if response.status == "refused" else "success"
        )
        reference = await deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: audit("response", "completed", outcome))
        token = (continuation(planned, response) if continuation is not None
                 and response.status == "needs_clarification"
                 and planned.response.pending_question is not None else None)
        return response.model_copy(update={"audit_reference": reference, "continuation_token": token})
    if engine is None:
        # Identidade promovida entre a admissão HTTP e o planejamento: este
        # pedido não reabre recursos sob a nova concessão.
        raise GenAIServiceUnavailable(retryable=False)
    if planned.deadline is None or planned.access_scope is None or planned.source is None:
        raise GenAIResponseInvalid
    if readiness_gate is None:
        raise GenAIServiceUnavailable(retryable=False)
    report = await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: readiness_gate(planned))
    report = GoldReadinessReport.model_validate(report.model_dump(mode="json"))
    metric = next((m for m in load_gold_catalog().metrics
                   if m.metric_id == planned.response.plan.metric_id), None)
    if metric is None:
        raise GoldCatalogIncompatible
    required = {*metric.required_capability_ids, planned.source.capability_id}
    if (report.batch_ref != planned.publication.batch_ref
        or report.lot_state not in {"ready", "partial"}
        or any(key not in report.capabilities for key in required)):
        raise GenAIServiceUnavailable(retryable=False)
    unavailable = [report.capabilities[key] for key in required
                   if report.capabilities[key].status != "available"]
    if unavailable:
        quality = _observed_continuity_quality(
            report, planned.response.plan, planned.publication.batch_ref
        )
        if quality is None:
            coverage_reasons = {
                "period_missing",
                "period_insufficient",
                "coverage_missing",
                "coverage_incomplete",
                "table_empty",
                "source_not_in_gold",
            }
            if all(
                capability.reasons
                and set(capability.reasons) <= coverage_reasons
                for capability in unavailable
            ):
                raise GoldCoverageUnavailable
            raise GenAIServiceUnavailable(retryable=False)
    else:
        quality = GoldEvidenceQuality(
            readiness_version=report.readiness_version,
            batch_ref=report.batch_ref,
            lot_state=report.lot_state,
            available_capability_ids=tuple(sorted(required)),
        )
    metadata = {
        "plan_id": planned.response.plan_fingerprint,
        "catalog_version": planned.response.plan.catalog_version,
        "batch_ref": planned.publication.batch_ref,
        "caller_ref": planned.access_scope.caller_ref,
        "metric_id": planned.response.plan.metric_id,
        "source_id": planned.response.plan.source_id,
    }
    quality_audit = {
        "quality_mode": quality.quality_mode,
        "observed_capability_ids": quality.observed_capability_ids,
        "observed_periods": quality.observed_periods,
        "quality_limitation": (
            OBSERVED_CONTINUITY_WARNING
            if quality.quality_mode == "observed_uncertified" else None
        ),
    }
    await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: audit("plan", "ready", "success", artifact=execution_artifact(planned), **metadata))
    query_started = monotonic()
    lookup = await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(
            execute_gold_plan, engine, planned, resolve_scope=resolve_scope,
            quality=quality,
        ),
    )
    if not should_synthesize(
        planning_status=planned.response.status, lookup=lookup.model_dump(mode="json"),
        policy="completed_lookup",
    ):
        raise GenAIResponseInvalid
    row_count = len(lookup.evidence.records) if lookup.evidence else 0
    logging.getLogger("uvicorn.error").info("genai_execution %s", json.dumps({
        "correlation_id": correlation_id, "stage": "query",
        "work_ms": int((monotonic() - query_started) * 1000), "row_count": row_count,
        "evidence_bytes": len(lookup.model_dump_json().encode("utf-8")),
    }, separators=(",", ":")))
    await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: audit(
        "source", "completed", "success", row_count=row_count,
        artifact=execution_artifact(planned, lookup=lookup), **metadata, **quality_audit,
    ))
    current_scope = await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope),
    )
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(planned.publication.assert_current, engine),
    )
    if on_visual is not None:
        preview = await planned.deadline.run(
            GOLD_REQUEST_TIMEOUT_SECONDS,
            lambda: asyncio.to_thread(build_visual_preview, planned.response.plan, lookup),
        )
        if preview is not None:
            # A montagem também consome prazo: conferir novamente antes de publicar.
            if await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope)) != planned.access_scope:
                raise GoldExecutionDenied
            await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(planned.publication.assert_current, engine))
            await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: on_visual(preview))
    payload = QuestionSynthesisRequest(
        **request.model_dump(), access_scope=planned.access_scope,
        dimension_value_coverage=planned.dimension_value_coverage,
        remaining_timeout_ms=planned.deadline.remaining_timeout_ms(GOLD_REQUEST_TIMEOUT_SECONDS),
        plan=planned.response.plan,
        plan_fingerprint=planned.response.plan_fingerprint,
        lookup=lookup, expected_batch_ref=planned.publication.batch_ref,
    )
    try:
        result = await planned.deadline.run(
            GOLD_REQUEST_TIMEOUT_SECONDS, lambda: client.synthesize(payload, correlation_id=correlation_id),
        )
    except (GenAIServiceUnavailable, GenAIResponseInvalid, GenAITimeout):
        # Uma falha do modelo não pode ocultar revogação/troca após a prévia.
        if on_visual is not None:
            if await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope)) != planned.access_scope:
                raise GoldExecutionDenied from None
            await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(planned.publication.assert_current, engine))
        raise
    result = _apply_observed_continuity_warning(result, quality)
    current_scope = await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope),
    )
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(planned.publication.assert_current, engine),
    )
    planned.deadline.remaining_seconds(GOLD_REQUEST_TIMEOUT_SECONDS)
    visual = await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS,
        lambda: asyncio.to_thread(build_chat_visualization, planned.response.plan, lookup, result),
    )
    outcome = "error" if result.status == "recoverable_error" else (
        "refused" if result.status == "refused" else "success"
    )
    reference = await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: audit(
        "response", "completed", outcome, row_count=row_count, **metadata, **quality_audit,
    ))
    # A confirmação durável também consome tempo; não publicar com escopo/lote
    # revogados enquanto a transação de auditoria era confirmada.
    current_scope = await planned.deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope))
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    await planned.deadline.run(
        GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(planned.publication.assert_current, engine),
    )
    planned.deadline.remaining_seconds(GOLD_REQUEST_TIMEOUT_SECONDS)
    continuation_plan = planned
    if result.status == "answered" and visual is not None and lookup.evidence is not None:
        anchor = ranked_result_anchor(planned.response.plan, lookup.evidence.records)
        continuation_plan = replace(
            planned, response=planned.response.model_copy(update={"plan": anchor}),
        )
    token = continuation(continuation_plan, result) if continuation is not None and result.status in {"answered", "no_evidence"} else None
    planned.deadline.remaining_seconds(GOLD_REQUEST_TIMEOUT_SECONDS)
    return result.model_copy(update={"audit_reference": reference, "continuation_token": token, "visualization": visual})


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
        if plan.comparison_periods is not None:
            periods = list(plan.comparison_periods)
        if plan.metric_id == "billing.price_volume":
            from app.services.gold_price_volume import configured_windows, window_months
            def read_windows():
                with planned.publication.execution_snapshot(engine) as connection:
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
                    return configured_windows(connection, plan)
            windows = await planned.deadline.run(5, lambda: asyncio.to_thread(read_windows))
            periods = list(window_months(windows)) if windows is not None else []
        report = await client.evaluate_readiness(
            engine, requested_periods=tuple(periods),
            approved_controls=frozenset(approved_controls),
            correlation_id=planned.response.correlation_id,
            expected_batch_ref=planned.publication.batch_ref,
        )
        quality = _observed_continuity_quality(report, plan, planned.publication.batch_ref)
        if quality is not None:
            def check_coverage() -> bool:
                with planned.publication.execution_snapshot(engine) as connection:
                    timeout = planned.deadline.sql_timeout_ms(5)
                    connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout}")
                    return observed_coverage_valid(connection, plan, quality)

            if not await planned.deadline.run(5, lambda: asyncio.to_thread(check_coverage)):
                raise GoldCoverageUnavailable
        return report
    return evaluate
