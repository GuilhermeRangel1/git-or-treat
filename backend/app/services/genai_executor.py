"""Execução controlada de planos Gold v1 no Backend (GENAI-06)."""

import calendar
import json
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from hashlib import sha256
from math import isfinite

from sqlalchemy import func, literal, select, text
from sqlalchemy.engine import Engine

from app.models.gold_v2 import TABLES
from app.schemas.genai_evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceResult,
    GoldEvidenceQuality,
)
from app.schemas.genai_internal import AccessScope
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus, WindowKind
from app.services.genai_client import GenAIResponseInvalid
from app.services.genai_plan import validate_gold_genai_plan
from app.services.genai_planning import GoldPlanningResult, _admit_plan
from app.services.gold_catalog import load_gold_catalog

MAX_EVIDENCE_ROWS = 100
MAX_EVIDENCE_BYTES = 16_384
SQL_STATEMENT_TIMEOUT = "5000ms"

_DIMENSION_FIELDS = {
    "geography.municipality": "municipality",
    "geography.neighborhood": "neighborhood",
    "customer.consumption_class": "consumption_class",
    "tariff.subgroup": "tariff_subgroup",
    "tariff.flag": "tariff_flag",
    "generation.distributed": "distributed_generation",
    "network.feeder": "feeder",
}


class GoldExecutionDenied(Exception):
    """Plano sem autorização atual ou fora do subconjunto compilável."""


def _query(plan: LogicalReadPlan, source, metric):
    if plan.window.kind is WindowKind.BOUNDED and (
        source.temporal_column is None
        or plan.window.granularity not in ("month", "year")
    ):
        raise GoldExecutionDenied

    table = TABLES[source.table]
    filters = []
    period_column = table.c[source.temporal_column] if source.temporal_column else None
    if plan.window.kind is WindowKind.BOUNDED:
        assert period_column is not None
        if plan.window.granularity == "month":
            if (
                plan.window.start.day != 1
                or plan.window.end.day != calendar.monthrange(
                    plan.window.end.year, plan.window.end.month
                )[1]
            ):
                raise GoldExecutionDenied
        elif (
            plan.window.start.month != 1
            or plan.window.start.day != 1
            or plan.window.end.month != 12
            or plan.window.end.day != 31
        ):
            raise GoldExecutionDenied

        if source.temporal_transform == "identity":
            period = (
                func.substr(period_column, 1, 4)
                if plan.window.granularity == "year"
                else period_column
            )
            filters.extend((
                period_column >= plan.window.start.strftime("%Y-%m"),
                period_column <= plan.window.end.strftime("%Y-%m"),
            ))
        else:
            period = func.to_char(
                func.timezone("UTC", period_column),
                "YYYY" if plan.window.granularity == "year" else "YYYY-MM",
            )
            start = datetime.combine(plan.window.start, time.min, tzinfo=UTC)
            end = datetime.combine(
                plan.window.end + timedelta(days=1), time.min, tzinfo=UTC
            )
            filters.extend((period_column >= start, period_column < end))
    else:
        if (
            plan.window.phrase not in metric.accumulated_period_phrases
        ):
            raise GoldExecutionDenied
        # Uma expressão acumulada é mapeada pelo catálogo e não ganha um filtro
        # temporal físico que a fonte não oferece.
        period = literal(plan.window.phrase)

    for item in plan.filters:
        column_name = source.dimension_columns.get(item.dimension_id)
        if column_name is None:
            raise GoldExecutionDenied
        column = table.c[column_name]
        if item.operator.value == "eq":
            filters.append(column == item.values[0])
        elif item.operator.value == "in":
            filters.append(column.in_(item.values))
        else:
            raise GoldExecutionDenied

    selected = [period.label("period")]
    dimensions = {}
    for dimension_id in plan.group_by_dimension_ids:
        field_name = _DIMENSION_FIELDS.get(dimension_id)
        column_name = source.dimension_columns.get(dimension_id)
        if field_name is None or column_name is None:
            raise GoldExecutionDenied
        dimensions[dimension_id] = table.c[column_name]
        selected.append(table.c[column_name].label(field_name))

    aggregation = metric.aggregation
    if aggregation in ("sum", "count_non_null", "average_non_null"):
        if source.measure_column is None:
            raise GoldExecutionDenied
        measure = table.c[source.measure_column]
        if aggregation == "sum":
            value = func.sum(measure)
        elif aggregation == "count_non_null":
            value = func.count(measure)
        else:
            value = func.avg(measure)
        selected.append(value.label("value"))
        grouped_columns = [] if plan.window.kind is WindowKind.CATALOG_PHRASE else [period]
        grouped_columns.extend(dimensions.values())
        statement = select(*selected).where(*filters)
        if grouped_columns:
            statement = statement.group_by(*grouped_columns)
    elif aggregation == "ratio_of_sums":
        if source.numerator_column is None or source.denominator_column is None:
            raise GoldExecutionDenied
        numerator = func.sum(table.c[source.numerator_column])
        denominator = func.sum(table.c[source.denominator_column])
        value = numerator / func.nullif(denominator, 0)
        selected.append(value.label("value"))
        grouped_columns = [] if plan.window.kind is WindowKind.CATALOG_PHRASE else [period]
        grouped_columns.extend(dimensions.values())
        statement = select(*selected).where(*filters)
        if grouped_columns:
            statement = statement.group_by(*grouped_columns)
    elif aggregation == "key_grain_read":
        if (
            plan.window.kind is not WindowKind.BOUNDED
            or source.measure_column is None
            or plan.group_by_dimension_ids
        ):
            raise GoldExecutionDenied
        # DEC/FEC são leituras já agregadas por alimentador e mês; não se somam
        # entre competências nem alimentadores. Só selecionamos a chave aprovada.
        key_columns = [column for column in source.grain if column != source.temporal_column]
        for column_name in key_columns:
            dimension_id = next(
                (key for key, value in source.dimension_columns.items() if value == column_name),
                None,
            )
            field_name = _DIMENSION_FIELDS.get(dimension_id or "")
            if dimension_id not in plan.dimension_ids or field_name is None:
                raise GoldExecutionDenied
            if dimension_id not in dimensions:
                dimensions[dimension_id] = table.c[column_name]
                selected.append(table.c[column_name].label(field_name))
        value = table.c[source.measure_column]
        selected.append(value.label("value"))
        statement = select(*selected).where(*filters)
    else:
        raise GoldExecutionDenied

    order_by = []
    if plan.order is not None:
        if plan.order.field_id == plan.metric_id:
            order_expression = value
        else:
            order_expression = dimensions.get(plan.order.field_id)
        if order_expression is None:
            raise GoldExecutionDenied
        order = order_expression.desc() if plan.order.direction == "desc" else order_expression.asc()
        order_by.append(order.nulls_last())
    # Desempate estável antes do LIMIT, inclusive quando o plano ordena pela métrica.
    if plan.window.kind is WindowKind.BOUNDED:
        order_by.append(period.asc())
    order_by.extend(column.asc() for column in dimensions.values())
    statement = statement.order_by(*order_by).limit(min(plan.limit, MAX_EVIDENCE_ROWS) + 1)
    return statement


def _rounded_number(value: object, decimals: int) -> float | None:
    if value is None:
        return None
    try:
        rounded = Decimal(str(value)).quantize(
            Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_EVEN
        )
        result = float(rounded)
    except (InvalidOperation, ValueError, OverflowError):
        raise GoldExecutionDenied from None
    if not isfinite(result):
        raise GoldExecutionDenied
    return result


def _clarification(message: str) -> EvidenceLookupResult:
    return EvidenceLookupResult(
        status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
        message=message,
    )


def _exceeds_evidence_byte_limit(result: EvidenceLookupResult) -> bool:
    serialized = json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, allow_nan=False
    )
    return len(serialized.encode("utf-8")) > MAX_EVIDENCE_BYTES


def execute_gold_plan(
    engine: Engine,
    planned: GoldPlanningResult,
    *,
    resolve_scope: Callable[[], AccessScope],
    quality: GoldEvidenceQuality | None = None,
) -> EvidenceLookupResult:
    """Revalida identidade, plano e lote; compila somente operações aprovadas.

    Recebe um engine analítico restrito e nunca recebe SQL do modelo. A consulta
    e a materialização ficam dentro do snapshot READ ONLY da publicação.
    """
    response = planned.response
    if (
        response.status is not QuestionPlanStatus.PLANNED
        or response.plan is None
        or response.plan_fingerprint is None
        or planned.access_scope is None
        or planned.deadline is None
        or (quality is not None and quality.batch_ref != planned.publication.batch_ref)
    ):
        raise GoldExecutionDenied

    try:
        plan = validate_gold_genai_plan(
            response.plan.model_dump(mode="json"), response.plan_fingerprint
        )
    except GenAIResponseInvalid:
        raise GoldExecutionDenied from None

    planned.deadline.remaining_seconds(35)
    current_scope = resolve_scope()
    if current_scope != planned.access_scope:
        raise GoldExecutionDenied
    try:
        source = _admit_plan(plan, current_scope)
    except (GenAIResponseInvalid, ValueError):
        raise GoldExecutionDenied from None
    catalog = load_gold_catalog()
    metric = next((item for item in catalog.metrics if item.metric_id == plan.metric_id), None)
    if metric is None:
        raise GoldExecutionDenied
    statement = _query(plan, source, metric)

    with planned.publication.execution_snapshot(engine) as connection:
        connection.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": str(min(
                int(SQL_STATEMENT_TIMEOUT.removesuffix("ms")),
                planned.deadline.sql_timeout_ms(5),
            )) + "ms"},
        )
        if resolve_scope() != current_scope:
            raise GoldExecutionDenied
        rows = connection.execute(statement).mappings().all()

    planned.deadline.remaining_seconds(35)
    if resolve_scope() != current_scope:
        raise GoldExecutionDenied
    if len(rows) > min(plan.limit, MAX_EVIDENCE_ROWS):
        return _clarification(
            "O recorte excede o limite de linhas; reduza o período ou aplique filtros."
        )

    records = []
    for row in rows:
        raw_value = row.get("value")
        value = _rounded_number(raw_value, metric.rounding.decimals)
        if value is None:
            return _clarification(
                "O recorte contém medida nula ou razão sem denominador válido; "
                "não é possível tratá-la como zero nem apresentar um resultado parcial."
            )
        record = {"value": value, "unit": plan.unit, "period": str(row["period"])}
        for field_name in _DIMENSION_FIELDS.values():
            if field_name in row:
                record[field_name] = row[field_name]
        records.append(record)

    if not records:
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Não há evidência disponível para o recorte solicitado.",
        )

    provenance = EvidenceProvenance(
        source_id=plan.source_id,
        reference_source=plan.source_id,
        plan_fingerprint=plan.fingerprint(),
        catalog_version=plan.catalog_version,
        metric_id=plan.metric_id,
        unit=plan.unit,
        window=plan.window,
        filters=plan.filters,
        dimension_ids=plan.dimension_ids,
        batch_ref=planned.publication.batch_ref,
        quality=quality,
    )
    cache_payload = json.dumps(
        {
            "caller": current_scope.caller_ref,
            "profile": current_scope.profile_id,
            "source": current_scope.source_id,
            "operations": sorted(current_scope.allowed_operations),
            "metrics": sorted(current_scope.allowed_metric_ids),
            "dimensions": sorted(current_scope.allowed_dimension_ids),
            "plan": plan.fingerprint(),
            "batch": planned.publication.batch_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence = EvidenceResult(
        reference={
            "source": plan.source_id,
            "description": "Evidência agregada da publicação Gold validada.",
            "is_demo": False,
        },
        records=records,
        provenance=provenance,
        cache_scope=sha256(cache_payload.encode("utf-8")).hexdigest(),
    )
    result = EvidenceLookupResult(status=EvidenceLookupStatus.AVAILABLE, evidence=evidence)
    if _exceeds_evidence_byte_limit(result):
        return _clarification(
            "O recorte excede o limite de tamanho da evidência; reduza o período ou filtros."
        )
    return result
