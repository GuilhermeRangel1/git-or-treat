"""Executor F1 interno: admissão revalidada, snapshot e materialização limitada.

Sem chamador público. Somente SQL canônico da admissão fresca alcança o driver.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.genai_gold_database import GOLD_READER_ROLE
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_client import GenAIQuestionClient, GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import (
    SqlAdmission,
    SqlAdmissionDenied,
    revalidate_sql_admission,
)
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_result import (
    SqlMaterializedResult,
    materialize_sql_result,
    sql_result_digest,
)
from app.services.genai_sql_telemetry import sql_stage


@dataclass(frozen=True)
class SqlExecutionResult:
    result: SqlMaterializedResult
    batch_ref: str
    admission_digest: str
    execution_digest: str
    result_digest: str


def _read_snapshot(
    admitted: SqlAdmission,
    *,
    engine: Engine,
    publication: GoldPublicationContext,
    resolve_scope: Callable[[], AccessScope],
    expected_scope: AccessScope,
    request: QuestionPlanRequest,
    deadline: GenAIRequestDeadline,
    stopped: Event,
    correlation_id: str,
) -> SqlExecutionResult:
    def active():
        if stopped.is_set():
            raise GenAITimeout
        deadline.remaining_seconds(60)

    def scope_current():
        active()
        if resolve_scope() != expected_scope:
            raise SqlAdmissionDenied("Escopo SQL alterado durante execução.")

    scope_current()
    context = json.loads(build_sql_generation_context(request).contents)
    selected_metric_id = context["metric"]["id"]
    with publication.execution_snapshot(
        engine,
        validate_f1_catalog=True,
        dimension_ids=expected_scope.allowed_dimension_ids,
        metric_ids=expected_scope.allowed_metric_ids
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
        source_capability_ids={selected_metric_id: context["source"]["capability_id"]},
    ) as connection:
        milliseconds = deadline.sql_timeout_ms(5)
        connection.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": f"{milliseconds}ms"},
        ).close()
        identity = connection.exec_driver_sql(
            "SELECT current_user, current_setting('transaction_read_only'), rolsuper, rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname = current_user"
        )
        try:
            row = identity.one()
            if tuple(row) != (GOLD_READER_ROLE, "on", False, False):
                raise SqlAdmissionDenied(
                    "Conexão SQL exige papel restrito e snapshot somente leitura."
                )
        finally:
            identity.close()
        scope_current()
        connection.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": f"{deadline.sql_timeout_ms(5)}ms"},
        ).close()
        with sql_stage(
            correlation_id, "sql_execution", context_version=admitted.context_version
        ):
            cursor = connection.execution_options(
                stream_results=True, max_row_buffer=1
            ).exec_driver_sql(
                admitted.review.canonical_sql, dict(admitted.review.parameter_items)
            )
        with sql_stage(
            correlation_id, "materialization", context_version=admitted.context_version
        ):
            result = materialize_sql_result(
                cursor, admitted.review, check_active=active
            )
        scope_current()
    # A saída do snapshot já conferiu a publicação em conexão nova.
    scope_current()
    result_digest = sql_result_digest(result)
    digest = hashlib.sha256(
        (
            admitted.digest
            + "\n"
            + admitted.review.canonical_sql
            + "\n"
            + result_digest
        ).encode()
    ).hexdigest()
    return SqlExecutionResult(
        result, admitted.batch_ref, admitted.digest, digest, result_digest
    )


async def execute_sql_admission(
    admitted: SqlAdmission,
    candidate: SqlGenerationCandidate,
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
) -> SqlExecutionResult:
    if (
        engine.dialect.name != "postgresql"
        or engine.dialect.driver != "psycopg"
        or engine.url.username != GOLD_READER_ROLE
        or not engine.hide_parameters
        or engine.echo
    ):
        raise SqlAdmissionDenied("Engine SQL incompatível com a leitura Gold restrita.")
    deadline = GenAIRequestDeadline(
        min(deadline.expires_at, admitted.expires_at), deadline.clock
    )
    with sql_stage(
        correlation_id,
        "admission_revalidation",
        context_version=admitted.context_version,
    ):
        fresh = await revalidate_sql_admission(
            admitted,
            candidate,
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
    stopped = Event()
    task = asyncio.create_task(
        asyncio.to_thread(
            _read_snapshot,
            fresh,
            engine=engine,
            publication=publication,
            resolve_scope=resolve_scope,
            expected_scope=request.access_scope,
            request=request,
            deadline=deadline,
            stopped=stopped,
            correlation_id=correlation_id,
        )
    )
    try:
        result = await deadline.run(60, lambda: asyncio.shield(task))
        if resolve_scope() != request.access_scope:
            raise SqlAdmissionDenied("Escopo SQL alterado após execução.")
        return result
    except (asyncio.CancelledError, GenAITimeout):
        stopped.set()
        # Não devolve o pool ao chamador enquanto a thread ainda usa a conexão.
        # SQL em andamento depende do statement_timeout; cancelamento não é imediato.
        cleanup = asyncio.gather(task, return_exceptions=True)
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                stopped.set()
        raise
