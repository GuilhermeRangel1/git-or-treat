"""Coordena insight Gold com sessão, snapshot restrito e auditoria confirmada."""

import asyncio
import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from time import monotonic

from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.models.gold_v2_load import TABLES
from app.repositories.gold_context import load_gold_context
from app.repositories.panorama import GoldPanoramaRepository
from app.schemas.ai_insight import (
    AIInsightRequest,
    AIInsightResponse,
    PanoramaInsightEnvelope,
    PanoramaInsightRequest,
)
from app.schemas.ai_question_publication import AIExpectedPublication
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_internal import AccessScope
from app.schemas.gold_readiness import GoldReadinessReport
from app.services.analytics import AnalyticsAPIError
from app.services.genai_audit import AuditStore
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import GoldExecutionDenied
from app.services.genai_expected_publication import (
    ExpectedPublicationMismatch,
    resolve_expected_batch_ref,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_panorama_insights import (
    GoldPanoramaInsightPreparation,
    build_gold_panorama_insight,
)
from app.services.panorama import comparison_period
from app.services.panorama_insights import StalePanoramaInsight


def _authorize_panorama_scope(scope: AccessScope) -> None:
    if (
        scope.source_id != "gold.local"
        or scope.profile_id != "v-energy-grid-360-gold"
        or "read" not in scope.allowed_operations
        or "billing.revenue" not in scope.allowed_metric_ids
        or not {"geography.municipality", "customer.consumption_class"}
        <= scope.allowed_dimension_ids
    ):
        raise GoldExecutionDenied


async def generate_gold_panorama_insight(
    engine: Engine,
    operational_engine: Engine,
    client: GenAIInsightClient,
    readiness_client: GenAIQuestionClient,
    payload: PanoramaInsightRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    correlation_id: str,
    audit_store: AuditStore,
    approved_controls: Iterable[str],
) -> PanoramaInsightEnvelope:
    """Recalcula o mesmo KPI do portal; descarta resultado após revogação/troca."""
    started = monotonic()
    deadline = GenAIRequestDeadline.start(35)

    async def work(function):
        return await deadline.run(35, lambda: asyncio.to_thread(function))

    scope = await work(resolve_scope)
    _authorize_panorama_scope(scope)
    publication = await work(lambda: GoldPublicationContext.capture(engine))
    if publication.reference.schema_version != "gold-csv-v2":
        raise GenAIServiceUnavailable(retryable=False)

    async def revalidate():
        if await work(resolve_scope) != scope:
            raise GoldExecutionDenied
        await work(lambda: publication.assert_current(engine))

    if payload.loteVersao != publication.reference.run_id:
        raise StalePanoramaInsight
    if payload.fingerprint is not None:
        try:
            expected_batch = await work(
                lambda: resolve_expected_batch_ref(
                    operational_engine,
                    AIExpectedPublication(
                        lote=payload.loteVersao, fingerprint=payload.fingerprint
                    ),
                )
            )
        except ExpectedPublicationMismatch:
            raise StalePanoramaInsight from None
        if expected_batch != publication.batch_ref:
            raise StalePanoramaInsight
    periods = [payload.filters.periodo]

    previous = comparison_period(payload.filters.periodo, payload.filters.comparacao)
    if previous and previous in await work(
        lambda: published_revenue_periods(engine, publication)
    ):
        periods.append(previous)
    report = await deadline.run(
        35,
        lambda: readiness_client.evaluate_readiness(
            operational_engine,
            requested_periods=tuple(sorted(set(periods))),
            approved_controls=frozenset(approved_controls),
            correlation_id=correlation_id,
            expected_batch_ref=publication.batch_ref,
        ),
    )
    report = GoldReadinessReport.model_validate(report.model_dump(mode="json"))
    if (
        report.batch_ref != publication.batch_ref
        or report.lot_state not in {"ready", "partial"}
        or any(
            key not in report.capabilities
            or report.capabilities[key].status != "available"
            for key in ("faturamento.receita",)
        )
    ):
        raise GenAIServiceUnavailable(retryable=False)
    await revalidate()
    prepared, metric, source, analysis = await work(
        lambda: read_gold_panorama_insight(
            engine, operational_engine, publication, payload
        )
    )
    await revalidate()
    serialized = prepared.model_dump(mode="json")
    digest = panorama_insight_digest(prepared)

    async def audit(stage, code, outcome):
        try:
            return await work(
                lambda: audit_store.record(
                    BackendAuditEvent(
                        correlation_id=correlation_id,
                        flow="insight",
                        stage=stage,
                        code=code,
                        outcome=outcome,
                        duration_ms=max(0, int((monotonic() - started) * 1000)),
                        batch_ref=publication.batch_ref,
                        caller_ref=scope.caller_ref,
                        metric_id="billing.revenue",
                        source_id="gold.local",
                        evidence_ref=digest,
                    ),
                    service="backend",
                )
            )
        except (SQLAlchemyError, ValueError):
            raise GenAIServiceUnavailable(retryable=False) from None

    await audit("source", "available", "success")
    await revalidate()
    if isinstance(prepared, AIInsightResponse):
        result = prepared.model_copy(update={"correlation_id": correlation_id})
    else:
        result = await deadline.run(
            35,
            lambda: client.synthesize_gold(
                {
                    **serialized,
                    "access_scope": scope.model_dump(mode="json"),
                    "batch_ref": publication.batch_ref,
                    "remaining_timeout_ms": deadline.remaining_timeout_ms(35),
                },
                correlation_id=correlation_id,
            ),
        )
        if result.status == "answered" and (
            result.context.model_dump(mode="json")
            != prepared.screen.model_dump(
                mode="json", exclude={"observations", "reference", "limitations"}
            )
            or result.observation.values != prepared.screen.observations
            or not result.evidence
            or any(
                item.is_demo or item.source != "gold.local" for item in result.evidence
            )
            or not set(prepared.screen.limitations) <= set(result.limitations)
        ):
            raise GenAIResponseInvalid
    await revalidate()
    reference = await audit(
        "response", "completed", "success" if result.status == "answered" else "error"
    )
    await revalidate()
    return PanoramaInsightEnvelope(
        insight=result.model_copy(update={"audit_reference": reference}),
        metric=metric,
        source=source,
        analysis=analysis,
    )


def read_gold_panorama_insight(
    engine: Engine,
    operational_engine: Engine,
    publication: GoldPublicationContext,
    payload: PanoramaInsightRequest,
) -> GoldPanoramaInsightPreparation:
    # Metadados operacionais não concedem acesso quantitativo ao executor.
    with operational_engine.connect() as connection:
        try:
            metadata = load_gold_context(
                connection, payload.loteVersao, payload.fingerprint
            )
        except AnalyticsAPIError as exc:
            if exc.status_code == 409:
                raise StalePanoramaInsight from None
            raise
    if metadata.lote != publication.reference.run_id:
        raise GenAIServiceUnavailable(retryable=False)
    with publication.execution_snapshot(engine) as connection:
        expires = monotonic() + 5

        def limit_sql(conn, cursor, statement, parameters, context, executemany):
            milliseconds = int((expires - monotonic()) * 1000)
            if milliseconds < 1:
                raise GenAITimeout
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{milliseconds}ms",),
            )

        event.listen(connection, "before_cursor_execute", limit_sql)
        context = replace(metadata, connection=connection)
        return build_gold_panorama_insight(GoldPanoramaRepository(context), payload)


def published_revenue_periods(
    engine: Engine, publication: GoldPublicationContext
) -> set[str]:
    with publication.execution_snapshot(engine) as connection:
        return set(
            connection.execute(
                select(TABLES["diagnostico_receita"].c.competencia).distinct()
            ).scalars()
        )


def panorama_insight_digest(prepared: AIInsightRequest | AIInsightResponse) -> str:
    """Compromisso reproduzível sem guardar filtros nem números na trilha."""
    return hashlib.sha256(
        json.dumps(
            prepared.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def verify_audited_panorama_insight(
    audit_store: AuditStore,
    reference: str,
    engine: Engine,
    operational_engine: Engine,
    payload: PanoramaInsightRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
) -> bool:
    scope = resolve_scope()
    events = audit_store.read_reference(reference)
    response = next(
        (
            row["event"]
            for row in events
            if row["id"] == reference
            and row["service"] == "backend"
            and row["event"].get("flow") == "insight"
            and row["event"].get("stage") == "response"
        ),
        None,
    )
    if response is None or response.get("caller_ref") != scope.caller_ref:
        raise GoldExecutionDenied
    _authorize_panorama_scope(scope)
    publication = GoldPublicationContext.capture(engine)
    if response.get("batch_ref") != publication.batch_ref:
        return False
    prepared, _, _, _ = read_gold_panorama_insight(
        engine, operational_engine, publication, payload
    )
    if resolve_scope() != scope:
        raise GoldExecutionDenied
    publication.assert_current(engine)
    return panorama_insight_digest(prepared) == response.get("evidence_ref")
