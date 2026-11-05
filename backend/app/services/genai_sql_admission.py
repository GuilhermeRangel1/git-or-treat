"""Admissão interna F1 com publicação/prontidão atuais; não executa consulta.

O artefato é interno ao processo, não um token de autorização do navegador.
Um futuro executor deve revalidá-lo e usar snapshot/papel de leitura próprios.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_semantics import SqlSemanticReview, review_sql_semantics

SQL_ADMISSION_POLICY_VERSION = "text-to-sql-f1-admission-1"


class SqlAdmissionDenied(ValueError):
    """Admissão inválida/expirada, sem conteúdo de SQL, sessão ou provedor."""


@dataclass(frozen=True)
class SqlAdmission:
    review: SqlSemanticReview
    context_version: str
    candidate_digest: str
    readiness_digest: str
    batch_ref: str
    policy_version: str
    requested_periods: tuple[str, ...]
    expires_at: float
    digest: str


def _digest(value) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False,
                            allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _require(value) -> None:
    if not value:
        raise SqlAdmissionDenied("Admissão SQL F1 indisponível ou divergente.")


def _periods(candidate: SqlGenerationCandidate) -> tuple[str, ...]:
    periods = set()
    for window in candidate.interpretation.periods:
        year, month = window.start.year, window.start.month
        while (year, month) <= (window.end.year, window.end.month):
            periods.add(f"{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(sorted(periods))


async def admit_sql_candidate(
    candidate: SqlGenerationCandidate, request: QuestionPlanRequest, *,
    engine: Engine, publication: GoldPublicationContext, client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope], approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlAdmission:
    original_candidate, original_request = candidate, request
    candidate = SqlGenerationCandidate.model_validate_json(candidate.model_dump_json())
    request = QuestionPlanRequest.model_validate_json(request.model_dump_json())
    candidate_digest = _digest(candidate.model_dump(mode="json"))
    request_digest = _digest(request.model_dump(mode="json"))
    deadline = GenAIRequestDeadline(
        min(deadline.expires_at, deadline.clock() + request.remaining_timeout_ms / 1000),
        deadline.clock,
    )
    deadline.remaining_seconds(60)
    _require(publication.batch_ref == request.batch_ref and resolve_scope() == request.access_scope)
    # Falha de semântica é rejeitada antes de ler metadados da publicação.
    review_sql_semantics(candidate, request)
    fields = await deadline.run(5, lambda: asyncio.to_thread(
        publication.planning_fields, engine, request.access_scope))
    _require(resolve_scope() == request.access_scope)
    payload = request.model_dump(mode="json")
    payload.update(fields)
    fresh_request = QuestionPlanRequest.model_validate(payload)
    review = review_sql_semantics(candidate, fresh_request)
    context = build_sql_generation_context(fresh_request)
    periods = _periods(candidate)
    report = await deadline.run(60, lambda: client.evaluate_readiness(
        engine, requested_periods=periods, approved_controls=approved_controls,
        correlation_id=correlation_id, expected_batch_ref=publication.batch_ref))
    _require(report.batch_ref == publication.batch_ref
             and report.lot_state in ("ready", "partial"))
    capability = report.capabilities.get("faturamento.receita")
    _require(capability is not None and capability.status == "available" and not capability.reasons)
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    _require(resolve_scope() == request.access_scope)
    deadline.remaining_seconds(60)
    _require(_digest(original_candidate.model_dump(mode="json")) == candidate_digest
             and _digest(original_request.model_dump(mode="json")) == request_digest)
    readiness_digest = _digest(report.model_dump(mode="json"))
    material = {
        "context": context.context_version, "candidate": candidate_digest,
        "readiness": readiness_digest, "batch": publication.batch_ref,
        "policy": SQL_ADMISSION_POLICY_VERSION, "periods": periods,
        "approved_controls": sorted(approved_controls),
        "expires_at": deadline.expires_at,
        "sql": review.canonical_sql, "parameters": review.parameter_items,
        "columns": sorted(review.source_columns), "outputs": review.output_names,
        "measure_semantics": review.measure_semantics,
    }
    return SqlAdmission(review, context.context_version, candidate_digest, readiness_digest,
                        publication.batch_ref, SQL_ADMISSION_POLICY_VERSION, periods,
                        deadline.expires_at, _digest(material))


async def revalidate_sql_admission(
    admitted: SqlAdmission, candidate: SqlGenerationCandidate, request: QuestionPlanRequest, *,
    engine: Engine, publication: GoldPublicationContext, client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope], approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlAdmission:
    _require(admitted.policy_version == SQL_ADMISSION_POLICY_VERSION
             and deadline.clock() < admitted.expires_at)
    # Mantém a validade original, mesmo que o chamador apresente um prazo novo.
    bounded = GenAIRequestDeadline(min(deadline.expires_at, admitted.expires_at), deadline.clock)
    fresh = await admit_sql_candidate(
        candidate, request, engine=engine, publication=publication, client=client,
        resolve_scope=resolve_scope, approved_controls=approved_controls,
        deadline=bounded, correlation_id=correlation_id)
    _require(fresh == admitted)
    return fresh
