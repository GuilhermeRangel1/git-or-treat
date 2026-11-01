"""Planejamento operacional Gold: metadados, núcleo e admissão do plano no Backend.

Não executa a medida nem concede prontidão; o plano admitido é a entrada do executor.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from app.models.gold_v2 import TABLES
from app.repositories.gold_publication import GoldPublicationChanged
from app.schemas.ai import AIQuestionError, AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_internal import (
    AccessScope,
    DimensionValueCoverage,
    QuestionPlanRequest,
    QuestionPlanResponse,
)
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus, WindowKind
from app.schemas.gold_catalog import CatalogSource
from app.schemas.gold_publication import PublicationReference
from app.services.genai_client import GenAIQuestionClient, GenAIResponseInvalid
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_plan import validate_gold_genai_plan
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_catalog import load_gold_catalog, select_catalog_source

MAX_QUERY_MONTHS = 1200
MAX_QUERY_WINDOW_DAYS = 366 * 5


@dataclass(frozen=True)
class GoldPlanningResult:
    """Plano e referência capturada no servidor; o executor deve revalidar ambos."""

    response: QuestionPlanResponse
    publication: GoldPublicationContext | None
    source: CatalogSource | None = None
    access_scope: AccessScope | None = None
    deadline: GenAIRequestDeadline | None = None
    dimension_value_coverage: tuple[DimensionValueCoverage, ...] = ()


def _stop(status: QuestionPlanStatus, message: str, correlation_id: str):
    return QuestionPlanResponse(
        correlation_id=correlation_id,
        status=status,
        response=AIQuestionResponse(
            correlation_id=correlation_id, status=status.value, message=message,
            error=(AIQuestionError(code="access_denied", retryable=False)
                   if status == QuestionPlanStatus.REFUSED else None),
        ),
    )


def _scope_limitation(correlation_id: str) -> GoldPlanningResult:
    message = "Seu perfil tem acesso ao Assistente, mas as consultas da sua área ainda não estão disponíveis."
    response = QuestionPlanResponse(
        correlation_id=correlation_id,
        status=QuestionPlanStatus.NEEDS_CLARIFICATION,
        response=AIQuestionResponse(
            correlation_id=correlation_id,
            status=QuestionPlanStatus.NEEDS_CLARIFICATION.value,
            message=message,
            limitations=["Ainda não há consultas disponíveis para esta área."],
        ),
    )
    return GoldPlanningResult(response=response, publication=None)


def _admit_plan(plan: LogicalReadPlan, scope: AccessScope) -> CatalogSource:
    # Mesmo teto do resolvedor temporal, revalidado também pelo executor.
    if plan.window.kind is WindowKind.BOUNDED:
        start, end = plan.window.start, plan.window.end
        if (
            (end.year - start.year) * 12 + end.month - start.month >= MAX_QUERY_MONTHS
            or (end - start).days > MAX_QUERY_WINDOW_DAYS
        ):
            raise GenAIResponseInvalid
    catalog = load_gold_catalog()
    metric = next((m for m in catalog.metrics if m.metric_id == plan.metric_id), None)
    if (
        metric is None
        or plan.metric_id not in scope.allowed_metric_ids
        or "read" not in scope.allowed_operations
        or (scope.profile_id, scope.source_id) != (plan.profile_id, plan.source_id)
        or not set(plan.dimension_ids) <= scope.allowed_dimension_ids
        or plan.unit != metric.unit
    ):
        raise GenAIResponseInvalid
    for item in plan.filters:
        if item.operator.value not in metric.dimension_operators.get(item.dimension_id, ()):
            raise GenAIResponseInvalid
    # A seleção é compatibilidade de planejamento, nunca liberação de prontidão.
    filter_ids = {item.dimension_id for item in plan.filters}
    group_ids = set(plan.group_by_dimension_ids)
    source = select_catalog_source(
        catalog, plan.metric_id, filter_ids | group_ids,
        {s.capability_id for m in catalog.metrics for s in m.sources},
        plan.window.model_dump(mode="json"),
    )
    if (
        source is None
        or not set(plan.dimension_ids) <= source.dimension_columns.keys()
        or not group_ids <= set(plan.dimension_ids)
        or not group_ids <= source.dimension_columns.keys()
    ):
        raise GenAIResponseInvalid
    if plan.order is not None:
        ordered_field = plan.order.field_id
        if ordered_field != plan.metric_id and ordered_field not in group_ids:
            raise GenAIResponseInvalid
        if (
            metric.aggregation == "key_grain_read"
            and ordered_field != plan.metric_id
            and ordered_field not in plan.dimension_ids
        ):
            raise GenAIResponseInvalid
    return source


def _has_selected_coverage(
    engine: Engine, publication: GoldPublicationContext,
    plan: LogicalReadPlan, source: CatalogSource,
) -> bool:
    """A união de meses de outras fontes não prova cobertura da fonte escolhida."""
    if plan.window.kind != WindowKind.BOUNDED:
        return source.temporal_column is None
    if source.temporal_column is None:
        return False
    table = TABLES[source.table]
    column = table.c[source.temporal_column]

    def read(connection):
        period = column
        if source.temporal_transform == "utc_month":
            period = (
                func.to_char(func.timezone("UTC", column), "YYYY-MM")
                if connection.dialect.name == "postgresql"
                else func.strftime("%Y-%m", column)
            )
        query = select(period).where(column.is_not(None))
        for item in plan.filters:
            # Somente eq/in, já conferidos pelo catálogo. Valores são parâmetros SQL.
            query = query.where(table.c[source.dimension_columns[item.dimension_id]].in_(item.values))
        values = set(connection.execute(query.distinct().limit(1201)).scalars())
        cursor = plan.window.start.replace(day=1)
        while cursor <= plan.window.end:
            if cursor.strftime("%Y-%m") not in values:
                return False
            if (cursor.year, cursor.month) == (plan.window.end.year, plan.window.end.month):
                break
            cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        return True

    if engine.dialect.name == "postgresql":
        with publication.execution_snapshot(engine) as connection:
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
            return read(connection)
    publication.assert_current(engine)
    with engine.connect() as connection:
        result = read(connection)
    publication.assert_current(engine)
    return result


async def plan_gold_question(
    engine: Engine, client: GenAIQuestionClient, request: AIQuestionRequest, *,
    resolve_scope: Callable[[], AccessScope], correlation_id: str,
    expected_batch_ref: str | None = None,
    deadline: GenAIRequestDeadline | None = None,
) -> GoldPlanningResult:
    """Liga produtor e cliente em runtime, com prazo único e reautorização atual.

    O resolvedor é dependência confiável do Backend, nunca parte do corpo do portal.
    GENAI-06/07 consomem o plano admitido; o chamador não deve executar resposta recusada.
    """
    deadline = deadline or GenAIRequestDeadline.start(35)
    if expected_batch_ref is not None:
        PublicationReference.parse(expected_batch_ref)
    scope = await deadline.run(35, lambda: asyncio.to_thread(resolve_scope))
    # O escopo vazio é uma limitação de capacidade, não uma consulta recusada.
    # Retorne antes de abrir o leitor, carregar publicação ou chamar o modelo.
    if not scope.allowed_metric_ids:
        return _scope_limitation(correlation_id)
    publication = await deadline.run(
        35, lambda: asyncio.to_thread(GoldPublicationContext.capture, engine)
    )
    if expected_batch_ref is not None and publication.batch_ref != expected_batch_ref:
        raise GoldPublicationChanged("A publicação Gold mudou antes do planejamento.")
    fields = await deadline.run(
        35, lambda: asyncio.to_thread(publication.planning_fields, engine, scope)
    )
    payload = QuestionPlanRequest(
        **request.model_dump(), access_scope=scope,
        remaining_timeout_ms=deadline.remaining_timeout_ms(35), **fields,
    )
    response = await deadline.run(
        35, lambda: client.plan(payload, correlation_id=correlation_id)
    )
    # Mesmo os esclarecimentos só podem ser publicados sobre a referência original.
    await deadline.run(35, lambda: asyncio.to_thread(publication.assert_current, engine))
    current_scope = await deadline.run(35, lambda: asyncio.to_thread(resolve_scope))
    if current_scope != scope:
        return GoldPlanningResult(_stop(
            QuestionPlanStatus.REFUSED,
            "As permissões mudaram. Refaça a pergunta com o acesso atual.", correlation_id,
        ), publication, access_scope=scope)
    if response.status != QuestionPlanStatus.PLANNED:
        return GoldPlanningResult(response, publication, access_scope=scope)
    plan = validate_gold_genai_plan(
        response.plan.model_dump(mode="json"), response.plan_fingerprint
    )
    source = _admit_plan(plan, current_scope)
    if not await deadline.run(35, lambda: asyncio.to_thread(
        _has_selected_coverage, engine, publication, plan, source
    )):
        return GoldPlanningResult(_stop(
            QuestionPlanStatus.NEEDS_CLARIFICATION,
            "Não há cobertura de todas as competências na fonte e no recorte solicitados. "
            "Informe outro período ou recorte; ausência não equivale a zero.", correlation_id,
        ), publication, access_scope=scope)
    # A consulta de cobertura também pode consumir o prazo ou coincidir com uma revogação.
    current_scope = await deadline.run(35, lambda: asyncio.to_thread(resolve_scope))
    if current_scope != scope:
        return GoldPlanningResult(_stop(
            QuestionPlanStatus.REFUSED,
            "As permissões mudaram. Refaça a pergunta com o acesso atual.", correlation_id,
        ), publication, access_scope=scope)
    deadline.remaining_seconds(35)
    return GoldPlanningResult(
        response, publication, source, scope, deadline, payload.dimension_value_coverage,
    )
