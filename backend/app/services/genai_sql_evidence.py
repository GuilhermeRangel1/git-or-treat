"""Converte execução interna em evidência exata, sem SQL nem plano fictício."""

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal

from sqlglot import parse_one

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_evidence import SqlEvidence, sql_evidence_digest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_admission import SqlAdmission, SqlAdmissionDenied
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_executor import SqlExecutionResult
from app.services.genai_sql_result import sql_result_digest
from app.services.genai_sql_semantics import review_sql_semantics

_DIMENSIONS = {"competencia": "competency", "municipio": "municipality",
               "classe_consumo": "consumption_class"}


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
    result_digest = sql_result_digest(executed.result)
    expected_execution = hashlib.sha256((admitted.digest + "\n" + review.canonical_sql
                                         + "\n" + result_digest).encode()).hexdigest()
    if (candidate_digest != admitted.candidate_digest or review != admitted.review
            or context.context_version != admitted.context_version
            or executed.batch_ref != admitted.batch_ref
            or executed.admission_digest != admitted.digest
            or executed.execution_digest != expected_execution
            or executed.result_digest != result_digest
            or executed.result.columns != review.output_names
            or executed.result.measure_semantics != review.measure_semantics):
        raise SqlAdmissionDenied("Execução e admissão SQL divergem antes da evidência.")
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
        "evidence_contract_version": "text-to-sql-f1-evidence-v1", "source_id": "gold.local",
        "source_table": "gold_v2.diagnostico_receita", "metric_id": "billing.revenue",
        "batch_ref": executed.batch_ref, "context_version": context.context_version,
        "admission_digest": admitted.digest, "execution_digest": executed.execution_digest,
        "result_digest": result_digest,
        **body["catalog"], "interpretation": candidate.interpretation.model_dump(mode="json"),
        "columns": [column.model_dump(mode="json") for column in candidate.result_columns],
        "measure_semantics": dict(review.measure_semantics), "dimension_semantics": dimensions,
        "rows": [[cell(value) for value in row] for row in executed.result.rows],
        "status": executed.result.status,
    }
    evidence = SqlEvidence.model_validate({**payload, "evidence_digest": sql_evidence_digest(payload)})
    active()
    return evidence
