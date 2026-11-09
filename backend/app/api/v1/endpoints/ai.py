import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.progressive import progressive_handler
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_database import (
    get_question_gold_readiness_gate,
    get_question_gold_resources,
)
from app.core.genai_limits import GOLD_REQUEST_TIMEOUT_SECONDS
from app.core.platform_identity import require_permission
from app.repositories.gold_publication import (
    GoldPublicationChanged,
    GoldPublicationUnavailable,
)
from app.repositories.panorama import PanoramaRepository, get_panorama_repository
from app.schemas.ai import (
    AIConversationTurn,
    AIQueryRequest,
    AIQuestionError,
    AIQuestionErrorResponse,
    AIQuestionResponse,
)
from app.schemas.ai_insight import (
    AIInsightResponse,
    PanoramaInsightEnvelope,
    PanoramaInsightRequest,
)
from app.schemas.ai_question_publication import AIQuestionPublicRequest
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_analysis import (
    SqlAnalysisRequest,
    SqlAnalysisResponse,
    SqlCompoundAnalysis,
    SqlContinuityPairAnalysis,
)
from app.services.analytics import AnalyticsAPIError
from app.services.genai_audit import AuditStore
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_continuation import (
    InvalidContinuation,
    issue_context_continuation,
    issue_continuation,
    restore_continuation,
)
from app.services.genai_coordination import (
    GoldCoverageUnavailable,
    answer_gold_question,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_domain_policy import (
    OUT_OF_DOMAIN_MESSAGE,
    is_explicitly_outside_energy_domain,
)
from app.services.genai_executor import GoldExecutionDenied
from app.services.genai_expected_publication import (
    ExpectedPublicationMismatch,
    resolve_expected_batch_ref,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_compound import CompoundEvidenceUnavailable
from app.services.genai_sql_compound_route import (
    CompoundStagingUnavailable,
    is_price_volume_question,
    query_compound_from_sources,
)
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    continuity_metric_question,
    is_explicit_dec_fec_question,
    requested_sql_metric_id,
)
from app.services.genai_sql_continuation import (
    InvalidSqlContinuation,
    issue_sql_continuation,
    restore_sql_continuation,
)
from app.services.genai_sql_pipeline import run_sql_question
from app.services.genai_sql_telemetry import record_sql_runtime, sql_stage
from app.services.gold_catalog import GoldCatalogIncompatible
from app.services.gold_panorama_coordination import generate_gold_panorama_insight
from app.services.panorama_insights import (
    StalePanoramaInsight,
    UnsupportedPanoramaInsight,
    build_panorama_insight,
)

router = APIRouter(dependencies=[Depends(require_permission("ai:ask"))])


def get_sql_genai_question_client(request: Request) -> GenAIQuestionClient:
    return request.app.state.genai_question_client


def require_sql_analysis_enabled() -> None:
    """Fail before resolving Gold resources when the opt-in route is disabled."""
    if not settings.GENAI_SQL_EXECUTION_ENABLED or settings.ANALYTICS_SOURCE != "gold":
        raise HTTPException(503, "Análise SQL indisponível.")


@router.post(
    "/sql-analyses",
    response_model=SqlAnalysisResponse,
    dependencies=[Depends(require_sql_analysis_enabled)],
)
async def run_f1_sql_analysis(
    payload: SqlAnalysisRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_sql_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Entrada HTTP pública; argumentos internos nunca alteram o body v1."""
    request.state.genai_strategy = "text_to_sql_f1"
    return await _run_f1_sql_analysis_impl(
        payload,
        request,
        genai,
        gold_resources,
        db,
    )


async def _run_f1_sql_analysis_impl(
    payload: SqlAnalysisRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_sql_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    db: Annotated[Session, Depends(get_db)],
    *,
    trusted_context: list[AIConversationTurn] | None = None,
    trusted_batch_ref: str | None = None,
):
    """Rota autenticada opt-in; entrega evidência sem expor SQL interno."""
    if not settings.GENAI_SQL_EXECUTION_ENABLED or settings.ANALYTICS_SOURCE != "gold":
        raise HTTPException(503, "Análise SQL indisponível.")
    if gold_resources is None or gold_resources[0] is None:
        raise HTTPException(503, "Leitura dos dados indisponível.")
    engine, resolve_scope = gold_resources

    def resolve_f1_scope():
        current = resolve_scope()
        return current.model_copy(
            update={
                "allowed_metric_ids": current.allowed_metric_ids
                & {
                    "billing.revenue",
                    "energy.consumption",
                    "energy.average_consumption_per_uc",
                    "billing.average_ticket",
                    "billing.effective_tariff",
                    "service.attendance",
                    "service.satisfaction",
                    "service.accumulated_attendance",
                    "service.accumulated_satisfaction",
                    "energy.gd_units",
                    "energy.gd_consumption_drop",
                    "customer.units_by_class",
                    "inspection.units_by_priority",
                    "network.equivalent_interruption_duration",
                    "network.equivalent_interruption_frequency",
                },
                "allowed_dimension_ids": current.allowed_dimension_ids
                & {
                    "geography.municipality",
                    "customer.consumption_class",
                    "geography.neighborhood",
                    "network.feeder",
                    "generation.distributed",
                    "inspection.priority",
                },
            }
        )

    scope = resolve_f1_scope()
    try:
        with sql_stage(request.state.correlation_id, "publication"):
            publication = GoldPublicationContext.capture(engine)
            if (
                trusted_batch_ref is not None
                and publication.batch_ref != trusted_batch_ref
            ):
                return _question_error(
                    request,
                    status_code=409,
                    code="invalid_context",
                    retryable=False,
                    message="Os dados disponíveis mudaram. Atualize a página antes de perguntar.",
                )
            fields = publication.planning_fields(engine, scope)
    except GoldPublicationChanged:
        raise HTTPException(
            409, "A publicação dos dados mudou. Refaça a pergunta."
        ) from None
    except (GoldPublicationUnavailable, GoldCoverageUnavailable, SQLAlchemyError):
        raise HTTPException(
            503, "A análise dos dados está temporariamente indisponível."
        ) from None
    sql_context = list(trusted_context or [])
    secret = (
        settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()
        if settings.AI_AGENT_SERVICE_API_TOKEN is not None
        else None
    )
    session = request.cookies.get("grid360_session", "")
    if trusted_context is not None and (
        payload.continuation_token is not None or payload.context
    ):
        return _question_error(
            request,
            status_code=409,
            code="invalid_continuation",
            retryable=False,
            message="O contexto anterior não é mais válido. Inicie uma nova conversa.",
        )
    if trusted_context is None and (
        payload.continuation_token is not None or payload.context
    ):
        if (
            payload.continuation_token is None
            or payload.conversation_id is None
            or not secret
            or not session
        ):
            return _question_error(
                request,
                status_code=409,
                code="invalid_continuation",
                retryable=False,
                message="O contexto anterior não é mais válido. Inicie uma nova conversa.",
            )
        try:
            sql_context = restore_sql_continuation(
                payload.continuation_token,
                scope=scope,
                batch_ref=publication.batch_ref,
                session=session,
                conversation_id=payload.conversation_id,
                secret=secret,
            )
        except InvalidSqlContinuation:
            return _question_error(
                request,
                status_code=409,
                code="invalid_continuation",
                retryable=False,
                message="O contexto anterior não é mais válido. Inicie uma nova conversa.",
            )
    continuity_pair_requested = is_explicit_dec_fec_question(payload.question)
    requested_metric_id = requested_sql_metric_id(payload.question, sql_context)
    required_metrics = (
        {
            "network.equivalent_interruption_duration",
            "network.equivalent_interruption_frequency",
        }
        if continuity_pair_requested
        else {requested_metric_id}
    )
    if not required_metrics <= scope.allowed_metric_ids:
        raise HTTPException(403, "Métrica fora do acesso atual.")
    remaining_ms = min(
        int(GOLD_REQUEST_TIMEOUT_SECONDS * 1000),
        int(settings.AI_AGENT_TIMEOUT_SECONDS * 1000),
    )
    plan_request = QuestionPlanRequest.model_validate(
        {
            **payload.model_dump(
                mode="json", exclude={"conversation_id", "continuation_token"}
            ),
            "context": [turn.model_dump(mode="json") for turn in sql_context],
            "access_scope": scope.model_dump(mode="json"),
            "remaining_timeout_ms": remaining_ms,
            **fields,
        }
    )
    deadline = GenAIRequestDeadline.start(remaining_ms / 1000)
    audit_store = AuditStore(db.get_bind())
    started = monotonic()

    async def record_audit(
        stage,
        code,
        outcome,
        *,
        row_count=0,
        evidence_ref=None,
        model_calls=0,
        source_calls=0,
        sql_f1_artifact=None,
        metric_id_override=None,
    ):
        event = BackendAuditEvent(
            correlation_id=request.state.correlation_id,
            stage=stage,
            code=code,
            outcome=outcome,
            duration_ms=max(0, int((monotonic() - started) * 1000)),
            row_count=row_count,
            model_calls=model_calls,
            source_calls=source_calls,
            batch_ref=publication.batch_ref,
            caller_ref=scope.caller_ref,
            metric_id=metric_id_override or requested_metric_id,
            source_id=scope.source_id,
            evidence_ref=evidence_ref,
            sql_f1_artifact=sql_f1_artifact,
        )
        try:
            return await deadline.run(
                GOLD_REQUEST_TIMEOUT_SECONDS,
                lambda: asyncio.to_thread(audit_store.record, event, service="backend"),
            )
        except (SQLAlchemyError, ValueError, GenAITimeout):
            raise GenAIServiceUnavailable(retryable=False) from None

    try:
        await record_audit("request", "started", "started")
        record_sql_runtime(request.state.correlation_id)
    except GenAIServiceUnavailable:
        raise HTTPException(503, "A trilha de auditoria está indisponível.") from None

    async def record_failure(stage, code, outcome, *, model_calls=0):
        try:
            await record_audit(stage, code, outcome, model_calls=model_calls)
        except (GenAIServiceUnavailable, GenAITimeout):
            # O erro primário continua sem resposta quantitativa se a própria
            # trilha de auditoria também estiver indisponível.
            return

    try:
        if is_price_volume_question(payload.question):
            required_metrics = {"billing.revenue", "energy.consumption"}
            required_dimensions = {"geography.municipality", "customer.consumption_class"}
            if (
                not required_metrics <= scope.allowed_metric_ids
                or not required_dimensions <= scope.allowed_dimension_ids
            ):
                raise GoldExecutionDenied
            staging_dir = settings.GENAI_PRICE_VOLUME_STAGING_DIR
            if staging_dir is None:
                raise CompoundStagingUnavailable("Staging local não configurado.")
            periods = tuple(
                f"{year:04d}-{month:02d}"
                for year in (2024, 2025, 2026)
                for month in range(1, 13)
                if "2024-07" <= f"{year:04d}-{month:02d}" <= "2026-06"
            )
            report = await deadline.run(
                60,
                lambda: genai.evaluate_readiness(
                    engine,
                    requested_periods=periods,
                    approved_controls=frozenset(settings.GENAI_GOLD_APPROVED_CONTROLS),
                    correlation_id=request.state.correlation_id,
                    expected_batch_ref=publication.batch_ref,
                ),
            )
            if (
                report.batch_ref != publication.batch_ref
                or report.lot_state not in {"ready", "partial"}
                or any(
                    report.capabilities.get(capability) is None
                    or report.capabilities[capability].status != "available"
                    for capability in ("faturamento.receita",)
                )
            ):
                raise CompoundEvidenceUnavailable("Prontidão Gold insuficiente para a composição.")
            publication.assert_sql_source_coverage(
                engine,
                table_name="diagnostico_receita",
                periods=periods,
                dimension_ids=frozenset(required_dimensions),
                metric_ids=frozenset(required_metrics),
                source_capability_id="faturamento.receita",
            )
            current_scope = resolve_f1_scope()
            if current_scope != scope:
                raise GoldExecutionDenied
            result, manifest, manifest_digest = await deadline.run(
                10,
                lambda: asyncio.to_thread(
                    query_compound_from_sources,
                    engine,
                    staging_dir,
                    batch_ref=publication.batch_ref,
                    publication=publication,
                ),
            )
            publication.assert_current(engine)
            if resolve_f1_scope() != scope:
                raise GoldExecutionDenied
            analysis = SqlCompoundAnalysis.from_sources(result, manifest, manifest_digest)
            row_count = sum(len(row.revenue_by_class) for row in analysis.municipalities)
            await record_audit(
                "source", "completed", "success", row_count=row_count,
                evidence_ref=analysis.evidence_digest, source_calls=2,
            )
            audit_reference = await record_audit(
                "response", "available", "success", row_count=row_count,
                evidence_ref=analysis.evidence_digest, source_calls=2, model_calls=0,
            )
            response = SqlAnalysisResponse.from_compound(
                request.state.correlation_id, analysis, audit_reference=audit_reference
            )
            if payload.conversation_id is not None and secret and session:
                token = issue_sql_continuation(
                    question=payload.question,
                    response=analysis.answer,
                    previous_context=sql_context,
                    scope=scope,
                    batch_ref=publication.batch_ref,
                    session=session,
                    conversation_id=payload.conversation_id,
                    secret=secret,
                )
                if token is not None:
                    response = response.model_copy(update={"continuation_token": token})
            return response
        if continuity_pair_requested:
            pair_runs = {}
            for indicator, expected_metric in (
                ("DEC", "network.equivalent_interruption_duration"),
                ("FEC", "network.equivalent_interruption_frequency"),
            ):
                single_question = continuity_metric_question(payload.question, indicator)
                single_request = plan_request.model_copy(
                    update={"question": single_question}
                )
                if requested_sql_metric_id(single_question, sql_context) != expected_metric:
                    raise GenAIResponseInvalid
                current_scope = resolve_f1_scope()
                if current_scope != scope:
                    raise GoldExecutionDenied
                publication.assert_current(engine)
                pair_runs[indicator] = await run_sql_question(
                    single_request,
                    engine=engine,
                    readiness_engine=engine,
                    publication=publication,
                    client=genai,
                    resolve_scope=resolve_f1_scope,
                    approved_controls=frozenset(settings.GENAI_GOLD_APPROVED_CONTROLS),
                    deadline=deadline,
                    correlation_id=request.state.correlation_id,
                )
                current_scope = resolve_f1_scope()
                if current_scope != scope:
                    raise GoldExecutionDenied
                publication.assert_current(engine)
                if pair_runs[indicator].evidence is None:
                    failed = pair_runs[indicator]
                    audit_reference = await record_audit(
                        "response",
                        "clarification" if failed.candidate.status == "needs_clarification" else "refused",
                        "success" if failed.candidate.status == "needs_clarification" else "refused",
                        model_calls=failed.model_calls,
                        sql_f1_artifact=failed.audit_artifact,
                        metric_id_override=expected_metric,
                    )
                    response = SqlAnalysisResponse.from_run(
                        request.state.correlation_id,
                        failed,
                        audit_reference=audit_reference,
                    )
                    break
            else:
                dec_evidence = pair_runs["DEC"].evidence
                fec_evidence = pair_runs["FEC"].evidence
                if dec_evidence is None or fec_evidence is None:
                    raise GenAIResponseInvalid
                continuity_pair = SqlContinuityPairAnalysis.from_evidence(
                    dec_evidence, fec_evidence
                )
                for indicator, metric_id in (
                    ("DEC", "network.equivalent_interruption_duration"),
                    ("FEC", "network.equivalent_interruption_frequency"),
                ):
                    evidence = pair_runs[indicator].evidence
                    await record_audit(
                        "source",
                        "completed",
                        "success",
                        row_count=len(evidence.rows),
                        evidence_ref=evidence.evidence_digest,
                        source_calls=1,
                        sql_f1_artifact=pair_runs[indicator].audit_artifact,
                        metric_id_override=metric_id,
                    )
                audit_reference = await record_audit(
                    "response",
                    "available",
                    "success",
                    row_count=2,
                    evidence_ref=continuity_pair.evidence_digest,
                    model_calls=sum(run.model_calls for run in pair_runs.values()),
                    source_calls=2,
                )
                response = SqlAnalysisResponse.from_continuity_pair(
                    request.state.correlation_id,
                    continuity_pair,
                    audit_reference=audit_reference,
                )
            publication.assert_current(engine)
            if resolve_f1_scope() != scope:
                raise GoldExecutionDenied
        else:
            run = await run_sql_question(
                plan_request,
                engine=engine,
                readiness_engine=engine,
                publication=publication,
                client=genai,
                resolve_scope=resolve_f1_scope,
                approved_controls=frozenset(settings.GENAI_GOLD_APPROVED_CONTROLS),
                deadline=deadline,
                correlation_id=request.state.correlation_id,
            )
            publication.assert_current(engine)
            if resolve_f1_scope() != scope:
                raise GoldExecutionDenied
            if run.evidence is not None:
                await record_audit(
                    "source", "completed", "success",
                    row_count=len(run.evidence.rows),
                    evidence_ref=run.evidence.evidence_digest,
                    source_calls=1,
                )
                outcome, code = "success", "available"
            elif run.candidate.status == "needs_clarification":
                outcome, code = "success", "clarification"
            else:
                outcome, code = "refused", "refused"
            audit_reference = await record_audit(
                "response", code, outcome,
                row_count=len(run.evidence.rows) if run.evidence is not None else 0,
                evidence_ref=run.evidence.evidence_digest
                if run.evidence is not None else None,
                model_calls=run.model_calls,
                sql_f1_artifact=run.audit_artifact,
            )
            with sql_stage(
                request.state.correlation_id,
                "presentation",
                context_version=(
                    run.evidence.context_version if run.evidence is not None else None
                ),
                contract_version=(
                    "text-to-sql-f1-presentation-v12"
                    if run.evidence is not None
                    and run.evidence.metric_id in {"billing.average_ticket", "billing.effective_tariff"}
                    else "text-to-sql-f1-presentation-v11"
                    if run.evidence is not None
                    and run.evidence.interpretation.operation == "weighted_continuity"
                    else "text-to-sql-f1-presentation-v10"
                    if run.evidence is not None
                    and run.evidence.metric_id == "energy.average_consumption_per_uc"
                    else
                    "text-to-sql-f1-presentation-v6"
                    if run.evidence is not None
                    and run.evidence.metric_id == "service.satisfaction"
                    else "text-to-sql-f1-presentation-v3"
                    if run.evidence is not None
                    and run.evidence.metric_id == "service.attendance"
                    else "text-to-sql-f1-presentation-v5"
                    if run.evidence is not None
                    and run.evidence.metric_id == "service.accumulated_attendance"
                    else "text-to-sql-f1-presentation-v4"
                    if run.evidence is not None
                    and run.evidence.metric_id
                    in {
                        "network.equivalent_interruption_duration",
                        "network.equivalent_interruption_frequency",
                    }
                    else "text-to-sql-f1-presentation-v1"
                ),
            ):
                response = SqlAnalysisResponse.from_run(
                    request.state.correlation_id,
                    run,
                    audit_reference=audit_reference,
                )
        publication.assert_current(engine)
        if resolve_f1_scope() != scope:
            raise GoldExecutionDenied
        if payload.conversation_id is not None and secret and session:
            if response.status == "answered":
                response_text = (
                    response.continuity_pair_analysis.answer
                    if response.continuity_pair_analysis is not None
                    else response.presentation.answer
                )
            elif response.status == "needs_clarification":
                response_text = response.clarification.question
            else:
                response_text = response.unsupported_reason.message
            token = issue_sql_continuation(
                question=payload.question,
                response=response_text,
                previous_context=sql_context,
                scope=scope,
                batch_ref=publication.batch_ref,
                session=session,
                conversation_id=payload.conversation_id,
                secret=secret,
            )
            if token is not None:
                response = response.model_copy(update={"continuation_token": token})
        return response
    except SqlAdmissionDenied:
        await record_failure("source", "unavailable", "error", model_calls=1)
        raise HTTPException(
            503, "A análise dos dados está temporariamente indisponível."
        ) from None
    except (CompoundStagingUnavailable, CompoundEvidenceUnavailable):
        await record_failure("source", "unavailable", "error")
        raise HTTPException(
            503, "A composição entre consumo e faturamento está indisponível para este recorte."
        ) from None
    except (SqlContextUnavailable, GoldCatalogIncompatible):
        await record_failure("source", "unavailable", "error", model_calls=0)
        raise HTTPException(
            503, "Essa análise não está disponível para este recorte."
        ) from None
    except GoldExecutionDenied:
        await record_failure("policy", "denied", "refused")
        raise HTTPException(
            403, "A consulta não está autorizada com o acesso atual."
        ) from None
    except GoldPublicationChanged:
        await record_failure("source", "invalid", "error")
        raise HTTPException(
            409, "A publicação dos dados mudou. Refaça a pergunta."
        ) from None
    except (GoldPublicationUnavailable, GoldCoverageUnavailable, SQLAlchemyError):
        await record_failure("source", "unavailable", "error")
        raise HTTPException(
            503, "A análise dos dados está temporariamente indisponível."
        ) from None
    except GenAIServiceUnavailable:
        await record_failure("response", "unavailable", "error")
        raise HTTPException(
            503, "O serviço de resposta está temporariamente indisponível."
        ) from None
    except GenAITimeout:
        await record_failure("response", "limit", "error")
        raise HTTPException(
            504, "O serviço de resposta excedeu o tempo limite."
        ) from None
    except GenAIResponseInvalid:
        await record_failure("response", "invalid", "error")
        raise HTTPException(
            502, "O serviço de resposta não retornou um resultado válido."
        ) from None


class AIQuestionRoute(APIRoute):
    """Retorna erro de validação estável sem ecoar valores da pergunta."""

    def __init__(self, *args, **kwargs):
        kwargs["responses"] = {
            401: {
                "model": AIQuestionErrorResponse,
                "description": "Sessão individual ausente ou inválida.",
            },
            403: {
                "model": AIQuestionErrorResponse,
                "description": "Consulta não autorizada pelo acesso atual.",
            },
            422: {
                "model": AIQuestionErrorResponse,
                "description": "Solicitação fora do contrato v1.",
            },
            409: {
                "model": AIQuestionErrorResponse,
                "description": "O lote dos indicadores mudou.",
            },
            502: {
                "model": AIQuestionErrorResponse,
                "description": "Resposta inválida do serviço GenAI.",
            },
            503: {
                "model": AIQuestionErrorResponse,
                "description": "Serviço GenAI indisponível.",
            },
            504: {
                "model": AIQuestionErrorResponse,
                "description": "Tempo limite do serviço GenAI.",
            },
            **(kwargs.get("responses") or {}),
        }
        super().__init__(*args, **kwargs)

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def ai_question_handler(request: Request):
            try:
                return await original_handler(request)
            except ExplicitOutOfDomainQuestion as refusal:
                response = AIQuestionResponse(
                    correlation_id=request.state.correlation_id,
                    audit_reference=refusal.audit_reference,
                    status="refused",
                    message=OUT_OF_DOMAIN_MESSAGE,
                    error=AIQuestionError(code="out_of_scope", retryable=False),
                )
                return JSONResponse(
                    status_code=200,
                    content=response.model_dump(mode="json"),
                    headers={"X-Correlation-ID": request.state.correlation_id},
                )
            except RequestValidationError:
                return _question_error(
                    request,
                    status_code=422,
                    code="invalid_request",
                    retryable=False,
                    message="A solicitação não segue o contrato v1.",
                )

            except SQLAlchemyError:
                return _question_error(
                    request,
                    status_code=503,
                    code="service_unavailable",
                    retryable=True,
                    message="O serviço está temporariamente indisponível.",
                )

            except HTTPException as exc:
                if exc.status_code in {401, 403}:
                    return _question_error(
                        request,
                        status_code=exc.status_code,
                        code="access_denied",
                        retryable=False,
                        message="A consulta não está autorizada com o acesso atual.",
                    )
                if exc.status_code != 503:
                    raise
                return _question_error(
                    request,
                    status_code=503,
                    code="service_unavailable",
                    retryable=False,
                    message="O serviço de resposta está temporariamente indisponível.",
                )

        return progressive_handler(ai_question_handler)


def _question_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    retryable: bool,
    message: str,
) -> JSONResponse:
    body = AIQuestionErrorResponse(
        correlation_id=request.state.correlation_id,
        message=message,
        error=AIQuestionError(code=code, retryable=retryable),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


def get_genai_question_client(request: Request) -> GenAIQuestionClient:
    return request.app.state.genai_question_client


def get_genai_insight_client(request: Request) -> GenAIInsightClient:
    return request.app.state.genai_insight_client


class ExplicitOutOfDomainQuestion(Exception):
    def __init__(self, audit_reference: str | None):
        self.audit_reference = audit_reference


async def enforce_explicit_question_domain(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Reject an external subject before Gold dependencies or model calls."""
    try:
        body = await request.json()
    except ValueError:
        return  # Let request validation return the standard 422 envelope.
    question = body.get("question") if isinstance(body, dict) else None
    if not isinstance(question, str) or not is_explicitly_outside_energy_domain(
        question
    ):
        return
    audit_reference = AuditStore(db.get_bind()).record(
        BackendAuditEvent(
            correlation_id=request.state.correlation_id,
            stage="policy",
            code="refused",
            outcome="refused",
            duration_ms=0,
            model_calls=0,
            source_calls=0,
        ),
        service="backend",
    )
    raise ExplicitOutOfDomainQuestion(audit_reference)


questions_router = APIRouter(
    route_class=AIQuestionRoute,
    dependencies=[
        Depends(require_permission("ai:ask")),
        Depends(enforce_explicit_question_domain),
    ],
)
insights_router = APIRouter(
    route_class=AIQuestionRoute,
    dependencies=[
        Depends(require_permission("ai:ask")),
        Depends(require_permission("panorama:read")),
    ],
)


@router.post(
    "/query",
    response_model=AIQuestionErrorResponse,
    status_code=503,
    summary="Consulta analítica legada ainda indisponível",
)
def query_analytical_data(
    payload: AIQueryRequest, request: Request
) -> AIQuestionErrorResponse:
    """O contrato legado não executa Gold e nunca deve simular sucesso."""

    return AIQuestionErrorResponse(
        correlation_id=request.state.correlation_id,
        message="A consulta analítica ainda não está disponível.",
        error=AIQuestionError(code="service_unavailable", retryable=False),
    )


@questions_router.post(
    "/questions",
    response_model=AIQuestionResponse,
    summary="Envia uma pergunta conversacional ao serviço GenAI",
)
async def ask_genai_question(
    payload: AIQuestionPublicRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine | None, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    readiness_gate: Annotated[
        Callable | None, Depends(get_question_gold_readiness_gate)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AIQuestionResponse | JSONResponse:
    """Coordena consulta e contexto curto autenticado, sem persistir histórico."""

    question = payload.without_publication()
    if is_explicitly_outside_energy_domain(question.question):
        audit_reference = AuditStore(db.get_bind()).record(
            BackendAuditEvent(
                correlation_id=request.state.correlation_id,
                stage="policy",
                code="refused",
                outcome="refused",
                duration_ms=0,
                model_calls=0,
                source_calls=0,
            ),
            service="backend",
        )
        return AIQuestionResponse(
            correlation_id=request.state.correlation_id,
            audit_reference=audit_reference,
            status="refused",
            message=OUT_OF_DOMAIN_MESSAGE,
            error=AIQuestionError(code="out_of_scope", retryable=False),
        )
    deadline = GenAIRequestDeadline.start(GOLD_REQUEST_TIMEOUT_SECONDS)
    try:
        if gold_resources is not None:
            engine, resolve_scope = gold_resources
            expected_batch_ref = None
            secret = (
                settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()
                if settings.AI_AGENT_SERVICE_API_TOKEN is not None
                else None
            )
            session = request.cookies.get("grid360_session", "")
            if payload.continuation_token is not None:
                if not secret or not session or not payload.conversation_id:
                    raise InvalidContinuation
                scope = await deadline.run(
                    GOLD_REQUEST_TIMEOUT_SECONDS,
                    lambda: asyncio.to_thread(resolve_scope),
                )
                expected_batch_ref, restored = restore_continuation(
                    payload.continuation_token,
                    scope,
                    session=session,
                    conversation=payload.conversation_id,
                    secret=secret,
                    context=question.context,
                )
                question = question.model_copy(update={"context": restored})
            if payload.expected_publication is not None:
                displayed_batch = await deadline.run(
                    GOLD_REQUEST_TIMEOUT_SECONDS,
                    lambda: asyncio.to_thread(
                        resolve_expected_batch_ref,
                        db.get_bind(),
                        payload.expected_publication,
                    ),
                )
                if (
                    expected_batch_ref is not None
                    and expected_batch_ref != displayed_batch
                ):
                    raise InvalidContinuation
                expected_batch_ref = displayed_batch

            def continuation(planned, response):
                if not secret or not session or not payload.conversation_id:
                    return None
                if planned.response.pending_question is not None:
                    return issue_context_continuation(
                        planned.response.pending_question,
                        planned.access_scope,
                        planned.publication.batch_ref,
                        session=session,
                        conversation=payload.conversation_id,
                        secret=secret,
                        kind="pending",
                        response_text=response.message or "",
                    )
                return issue_continuation(
                    planned.response.plan,
                    planned.access_scope,
                    planned.publication.batch_ref,
                    session=session,
                    conversation=payload.conversation_id,
                    secret=secret,
                    response_text=response.answer or response.message or "",
                )

            result = await answer_gold_question(
                engine,
                genai,
                question,
                resolve_scope=resolve_scope,
                correlation_id=request.state.correlation_id,
                readiness_gate=readiness_gate,
                audit_store=AuditStore(db.get_bind()),
                expected_batch_ref=expected_batch_ref,
                continuation=continuation,
                request_deadline=deadline,
                on_visual=getattr(request.state, "publish_visual", None),
            )
        else:
            if payload.continuation_token is not None:
                raise InvalidContinuation
            if payload.expected_publication is not None:
                return _question_error(
                    request,
                    status_code=422,
                    code="invalid_request",
                    retryable=False,
                    message="A publicação esperada só se aplica à fonte Gold.",
                )
            result = await genai.ask(
                question,
                correlation_id=request.state.correlation_id,
            )
    except InvalidContinuation:
        return _question_error(
            request,
            status_code=409,
            code="invalid_continuation",
            retryable=False,
            message="O contexto anterior não é mais válido. Inicie uma nova conversa.",
        )
    except ExpectedPublicationMismatch:
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=False,
            message="Os dados da tela foram atualizados. Recarregue a tela antes de perguntar.",
        )
    except GoldCatalogIncompatible:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="O catálogo Gold dos serviços não é compatível; a consulta não foi executada.",
        )
    except GoldExecutionDenied:
        return _question_error(
            request,
            status_code=403,
            code="access_denied",
            retryable=False,
            message="A consulta não está autorizada com o acesso atual.",
        )
    except GoldPublicationChanged:
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=True,
            message="A publicação dos dados mudou. Refaça a pergunta.",
        )
    except GoldPublicationUnavailable:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="A publicação Gold não está disponível para esta consulta.",
        )
    except SQLAlchemyError:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=True,
            message="Não foi possível consultar os dados agora. Tente novamente em instantes.",
        )
    except GoldCoverageUnavailable:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="Os dados disponíveis não têm cobertura suficiente para responder "
            "a esse indicador no recorte solicitado. Tente outro período ou indicador.",
        )
    except GenAIServiceUnavailable as exc:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=exc.retryable,
            message="O serviço de resposta está temporariamente indisponível.",
        )
    except GenAITimeout:
        return _question_error(
            request,
            status_code=504,
            code="service_unavailable",
            retryable=True,
            message="O serviço de resposta excedeu o tempo limite.",
        )
    except GenAIResponseInvalid:
        return _question_error(
            request,
            status_code=502,
            code="invalid_upstream_response",
            retryable=False,
            message="O serviço de resposta não retornou um resultado válido.",
        )

    return result


def get_panorama_insight_repository() -> PanoramaRepository | None:
    if settings.ANALYTICS_SOURCE == "gold":
        return None
    return get_panorama_repository()


@insights_router.post(
    "/insights",
    response_model=PanoramaInsightEnvelope,
    summary="Gera insight contextual do Panorama",
)
async def generate_panorama_insight(
    payload: PanoramaInsightRequest,
    request: Request,
    repository: Annotated[
        PanoramaRepository | None, Depends(get_panorama_insight_repository)
    ],
    genai: Annotated[GenAIInsightClient, Depends(get_genai_insight_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    readiness_client: Annotated[
        GenAIQuestionClient, Depends(get_genai_question_client)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> PanoramaInsightEnvelope | JSONResponse:
    """Monta os números no servidor e os envia pelo contrato de insight v1."""

    try:
        if gold_resources is not None:
            engine, resolve_scope = gold_resources
            return await generate_gold_panorama_insight(
                engine,
                db.get_bind(),
                genai,
                readiness_client,
                payload,
                resolve_scope=resolve_scope,
                correlation_id=request.state.correlation_id,
                audit_store=AuditStore(db.get_bind()),
                approved_controls=settings.GENAI_GOLD_APPROVED_CONTROLS,
            )
        insight_request, metric, source, analysis = build_panorama_insight(
            repository, payload
        )
    except GoldExecutionDenied:
        return _question_error(
            request,
            status_code=403,
            code="access_denied",
            retryable=False,
            message="A interpretação não está autorizada com o acesso atual.",
        )
    except GoldPublicationChanged:
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=False,
            message="O lote mudou. Atualize o Panorama antes de gerar o insight.",
        )
    except (GoldPublicationUnavailable, SQLAlchemyError, GenAIServiceUnavailable):
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="Não foi possível gerar a interpretação agora. Tente novamente em instantes.",
        )
    except GenAITimeout:
        return _question_error(
            request,
            status_code=504,
            code="service_unavailable",
            retryable=True,
            message="A interpretação excedeu o tempo limite.",
        )
    except GenAIResponseInvalid:
        return _question_error(
            request,
            status_code=502,
            code="invalid_upstream_response",
            retryable=False,
            message="A interpretação não corresponde ao recorte solicitado.",
        )
    except StalePanoramaInsight:
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=False,
            message="O lote dos indicadores mudou. Atualize o Panorama antes de gerar o insight.",
        )
    except UnsupportedPanoramaInsight:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="A fonte atual ainda não permite gerar este insight.",
        )
    except AnalyticsAPIError:
        return _question_error(
            request,
            status_code=422,
            code="invalid_request",
            retryable=False,
            message="Os filtros do insight não são válidos para o Panorama.",
        )

    if isinstance(insight_request, AIInsightResponse):
        return PanoramaInsightEnvelope(
            insight=insight_request.model_copy(
                update={"correlation_id": request.state.correlation_id}
            ),
            metric=metric,
            source=source,
            analysis=analysis,
        )

    try:
        result = await genai.generate(
            insight_request,
            correlation_id=request.state.correlation_id,
        )
    except GenAIServiceUnavailable as exc:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=exc.retryable,
            message="O serviço de insight está temporariamente indisponível.",
        )
    except GenAITimeout:
        return _question_error(
            request,
            status_code=504,
            code="service_unavailable",
            retryable=True,
            message="O serviço de insight excedeu o tempo limite.",
        )
    except GenAIResponseInvalid:
        return _question_error(
            request,
            status_code=502,
            code="invalid_upstream_response",
            retryable=False,
            message="O serviço de insight não retornou um resultado válido.",
        )

    if result.status == "answered":
        expected_screen = insight_request.screen
        if (
            result.context.model_dump(mode="json")
            != expected_screen.model_dump(
                mode="json", exclude={"observations", "reference", "limitations"}
            )
            or [item.model_dump(mode="json") for item in result.observation.values]
            != [item.model_dump(mode="json") for item in expected_screen.observations]
            or any(not item.is_demo for item in result.evidence)
        ):
            return _question_error(
                request,
                status_code=502,
                code="invalid_upstream_response",
                retryable=False,
                message="O serviço de insight retornou outro recorte de indicadores.",
            )

    return PanoramaInsightEnvelope(
        insight=result, metric=metric, source=source, analysis=analysis
    )
