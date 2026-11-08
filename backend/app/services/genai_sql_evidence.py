"""Converte execução interna em evidência exata, sem SQL nem plano fictício."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

from sqlglot import parse_one

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_evidence import SqlEvidence, sql_evidence_digest
from app.schemas.sql_generation import SqlGenerationCandidate, SqlResultColumn
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_admission import SqlAdmission, SqlAdmissionDenied
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_executor import SqlExecutionResult
from app.services.genai_sql_result import (
    MAX_SQL_RESULT_BYTES,
    SqlMaterializedResult,
    SqlResultLimitExceeded,
    sql_result_digest,
)
from app.services.genai_sql_semantics import GROWTH_PERCENT_COLUMN, review_sql_semantics

_DIMENSIONS = {"competencia": "competency", "municipio": "municipality",
               "bairro": "neighborhood",
               "classe_consumo": "consumption_class"}
def _with_growth_percentage(result: SqlMaterializedResult) -> SqlMaterializedResult:
    """Derive percent change against a positive previous-period baseline.

    A zero/negative/missing baseline has no conventional growth percentage and
    remains null; this avoids division by zero and misleading negative-base rates.
    """
    if GROWTH_PERCENT_COLUMN in result.columns:
        raise SqlAdmissionDenied("Alias reservado para medida percentual derivada.")
    by_meaning = {meaning: result.columns.index(name)
                  for name, meaning in result.measure_semantics}
    current_index = by_meaning["period_0_total"]
    baseline_index = by_meaning["period_1_total"]
    rows = []
    for row in result.rows:
        current, baseline = row[current_index], row[baseline_index]
        growth = None
        if current is not None and baseline is not None and baseline > 0:
            try:
                with localcontext() as context:
                    context.prec = 256
                    growth = ((current - baseline) / baseline * Decimal(100)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_EVEN,
                    )
            except InvalidOperation:
                raise SqlAdmissionDenied("Variação percentual fora da precisão admitida.") from None
            if (not growth.is_finite() or abs(growth.adjusted()) > 100
                    or abs(growth.as_tuple().exponent) > 100):
                raise SqlAdmissionDenied("Variação percentual fora do limite de evidência.")
        rows.append((*row, growth))
    columns = (*result.columns, GROWTH_PERCENT_COLUMN)
    measure_semantics = (*result.measure_semantics, (
        GROWTH_PERCENT_COLUMN, "period_0_growth_percent",
    ))
    material = {
        "columns": columns,
        "measure_semantics": measure_semantics,
        "rows": tuple(rows),
        "status": result.status,
    }
    serialized_bytes = len(json.dumps(
        material, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        default=lambda item: format(item, "f"),
    ).encode("utf-8"))
    if serialized_bytes > MAX_SQL_RESULT_BYTES:
        raise SqlResultLimitExceeded("Resultado SQL excede o limite de bytes.")
    return replace(result, columns=columns, rows=tuple(rows),
                   measure_semantics=measure_semantics, serialized_bytes=serialized_bytes)


def build_sql_evidence(
    executed: SqlExecutionResult, admitted: SqlAdmission, candidate: SqlGenerationCandidate,
    request: QuestionPlanRequest, *, resolve_scope: Callable[[], AccessScope],
    deadline: GenAIRequestDeadline,
) -> SqlEvidence:
    def active():
        deadline.remaining_seconds(60)
        if deadline.clock() >= admitted.expires_at or resolve_scope() != request.access_scope:
            raise SqlAdmissionDenied("Contexto expirado ou alterado antes da evidência SQL.")

    active()
    review = review_sql_semantics(candidate, request)
    context = build_sql_generation_context(request)
    candidate_digest = hashlib.sha256(json.dumps(candidate.model_dump(mode="json"),
        ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
    raw_result_digest = sql_result_digest(executed.result)
    expected_execution = hashlib.sha256((admitted.digest + "\n" + review.canonical_sql
                                         + "\n" + raw_result_digest).encode()).hexdigest()
    if (candidate_digest != admitted.candidate_digest or review != admitted.review
            or context.context_version != admitted.context_version
            or executed.batch_ref != admitted.batch_ref
            or executed.admission_digest != admitted.digest
            or executed.execution_digest != expected_execution
            or executed.result_digest != raw_result_digest
            or executed.result.columns != review.output_names
            or executed.result.measure_semantics != review.measure_semantics):
        raise SqlAdmissionDenied("Execução e admissão SQL divergem antes da evidência.")
    result = (_with_growth_percentage(executed.result)
              if candidate.interpretation.operation == "comparison" else executed.result)
    result_digest = sql_result_digest(result)
    body = json.loads(context.contents)
    tree = parse_one(review.canonical_sql, read="postgres", max_nodes=512, error_message_context=0)
    dimensions = {item.alias: _DIMENSIONS[item.this.name] for item in tree.expressions
                  if item.alias not in dict(review.measure_semantics)}

    def cell(value):
        if value is None or type(value) is str:
            return value
        if (type(value) is Decimal and value.is_finite() and abs(value.adjusted()) <= 100
                and abs(value.as_tuple().exponent) <= 100):
            return format(value, "f")
        raise SqlAdmissionDenied("Valor da execução incompatível com evidência SQL.")

    payload = {
        "evidence_contract_version": (
            "text-to-sql-f1-evidence-v6"
            if candidate.interpretation.metric_id == "service.accumulated_attendance"
            else "text-to-sql-f1-evidence-v5"
            if candidate.interpretation.metric_id in {
                "network.equivalent_interruption_duration",
                "network.equivalent_interruption_frequency",
            }
            else "text-to-sql-f1-evidence-v4"
            if candidate.interpretation.metric_id == "service.attendance"
            else "text-to-sql-f1-evidence-v3"
            if candidate.interpretation.metric_id == "energy.consumption"
            else "text-to-sql-f1-evidence-v2"
            if candidate.interpretation.operation == "comparison"
            else "text-to-sql-f1-evidence-v1"
        ), "source_id": "gold.local",
        "source_table": f"{body['source']['schema']}.{body['source']['table']}",
        "metric_id": candidate.interpretation.metric_id,
        "coverage_quality": admitted.quality_mode,
        "batch_ref": executed.batch_ref, "context_version": context.context_version,
        "admission_digest": admitted.digest, "execution_digest": executed.execution_digest,
        "result_digest": result_digest,
        **body["catalog"], "interpretation": candidate.interpretation.model_dump(mode="json"),
        "columns": [column.model_dump(mode="json") for column in candidate.result_columns]
        + ([SqlResultColumn(
            name=GROWTH_PERCENT_COLUMN, role="measure", value_type="decimal", unit="%",
        ).model_dump(mode="json")] if candidate.interpretation.operation == "comparison" else []),
        "measure_semantics": dict(result.measure_semantics), "dimension_semantics": dimensions,
        "rows": [[cell(value) for value in row] for row in result.rows],
        "status": result.status,
    }
    digest_payload = dict(payload)
    if payload["evidence_contract_version"] not in {
        "text-to-sql-f1-evidence-v5", "text-to-sql-f1-evidence-v6",
    }:
        digest_payload.pop("coverage_quality", None)
    evidence = SqlEvidence.model_validate({
        **payload, "evidence_digest": sql_evidence_digest(digest_payload),
    })
    active()
    return evidence
