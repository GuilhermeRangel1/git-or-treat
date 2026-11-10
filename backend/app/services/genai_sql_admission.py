"""Admissão interna F1 com publicação/prontidão atuais; não executa consulta.

O artefato é interno ao processo, não um token de autorização do navegador.
O executor deve revalidá-lo e usar snapshot/papel de leitura próprios.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_semantics import SqlSemanticReview, review_sql_semantics
from app.services.gold_catalog import GoldCatalogIncompatible, load_gold_catalog

SQL_ADMISSION_POLICY_VERSION = "text-to-sql-f1-admission-5"
OBSERVED_CONTINUITY_WARNING = "Valores observados; cobertura do alimentador não certificada."


class SqlAdmissionDenied(ValueError):
    """Admissão inválida/expirada, sem conteúdo de SQL, sessão ou provedor."""


@dataclass(frozen=True)
class SqlAdmission:
    review: SqlSemanticReview
    context_version: str
    candidate_digest: str
    request_digest: str
    readiness_digest: str
    batch_ref: str
    policy_version: str
    requested_periods: tuple[str, ...]
    approved_controls: tuple[str, ...]
    quality_mode: str
    expires_at: float
    digest: str


def _digest(value) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False,
                            allow_nan=False, separators=(",", ":"),
                            default=_canonical_scalar)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _request_digest(request: QuestionPlanRequest) -> str:
    """Canonicaliza os campos set-like do escopo antes de vincular o pedido."""
    material = request.model_dump(mode="json")
    scope = material["access_scope"]
    for field in ("allowed_operations", "allowed_metric_ids", "allowed_dimension_ids"):
        scope[field] = sorted(scope[field])
    return _digest(material)


def _canonical_scalar(value):
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise TypeError("timestamp do digest precisa de fuso explícito")
        return value.isoformat()
    if type(value) is date:
        return value.isoformat()
    if type(value) is Decimal and value.is_finite():
        return format(value, "f")
    raise TypeError(f"valor não canônico para digest: {type(value).__name__}")


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
    engine: Engine, readiness_engine: Engine, publication: GoldPublicationContext, client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope], approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlAdmission:
    original_candidate, original_request = candidate, request
    candidate_digest = _digest(candidate.model_dump(mode="json"))
    candidate = SqlGenerationCandidate.model_validate_json(candidate.model_dump_json())
    request = QuestionPlanRequest.model_validate_json(request.model_dump_json())
    request_digest = _request_digest(request)
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
    context_body = json.loads(context.contents)
    source_capability_id = context_body["source"]["capability_id"]
    if candidate.interpretation.metric_id in {
        "billing.revenue",
        "energy.consumption", "energy.average_consumption_per_uc",
                    "billing.average_ticket",
                    "billing.effective_tariff",
        "service.attendance", "service.satisfaction",
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        try:
            await deadline.run(5, lambda: asyncio.to_thread(
                publication.assert_sql_source_coverage, engine,
                table_name=context_body["source"]["table"], periods=periods,
                dimension_ids=request.access_scope.allowed_dimension_ids,
                metric_ids=frozenset(context.metric_ids),
                source_capability_id=source_capability_id,
            ))
        except GoldCatalogIncompatible:
            raise SqlAdmissionDenied(
                "Cobertura ou fonte SQL indisponível para o recorte."
            ) from None
    report = await deadline.run(60, lambda: client.evaluate_readiness(
        readiness_engine, requested_periods=periods, approved_controls=approved_controls,
        correlation_id=correlation_id, expected_batch_ref=publication.batch_ref))
    _require(report.batch_ref == publication.batch_ref
             and report.lot_state in ("ready", "partial"))
    metric = next((item for item in load_gold_catalog().metrics
                   if item.metric_id == candidate.interpretation.metric_id), None)
    source_capability_id = context_body["source"]["capability_id"]
    source = next((item for item in metric.sources
                   if item.capability_id == source_capability_id), None) if metric else None
    required_capabilities = (
        ({source.capability_id} if source.capability_id != metric.capability_id
         else {*metric.required_capability_ids, source.capability_id})
        if metric and source else set()
    )
    _require(bool(required_capabilities))
    observed_uncertified = False
    for capability_id in required_capabilities:
        capability = report.capabilities.get(capability_id)
        if capability is not None and capability.status == "available" and not capability.reasons:
            continue
        is_continuity = candidate.interpretation.metric_id in {
            "network.equivalent_interruption_duration",
            "network.equivalent_interruption_frequency",
        }
        feeder_filters = [item for item in candidate.interpretation.filters
                          if item.dimension_id == "network.feeder"]
        observed_operation = candidate.interpretation.operation
        weighted_period = candidate.interpretation.periods[0] if candidate.interpretation.periods else None
        weighted_month_count = len(periods)
        observed_filter_is_safe = (
            len(feeder_filters) <= 1
            if observed_operation == "weighted_continuity"
            else len(feeder_filters) == 1
            and feeder_filters[0].operator == "eq"
            and len(feeder_filters[0].values) == 1
        )
        exact_observed_recorte = (
            is_continuity
            and capability is not None
            and capability.status == "unavailable"
            and capability.reasons == ("coverage_incomplete",)
            and observed_operation in {"grain_read", "weighted_continuity"}
            and (
                observed_operation == "grain_read"
                and len(periods) == 1
                and len(candidate.interpretation.periods) == 1
                and observed_filter_is_safe
                or observed_operation == "weighted_continuity"
                and weighted_period is not None
                and 1 <= weighted_month_count <= 120
                and len(candidate.interpretation.periods) == 1
                and observed_filter_is_safe
            )
        )
        _require(exact_observed_recorte)
        observed_uncertified = True
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    _require(resolve_scope() == request.access_scope)
    deadline.remaining_seconds(60)
    _require(_digest(original_candidate.model_dump(mode="json")) == candidate_digest
             and _request_digest(original_request) == request_digest)
    readiness_digest = _digest(report.model_dump(mode="json"))
    material = {
        "context": context.context_version, "candidate": candidate_digest,
        "request": request_digest,
        "readiness": readiness_digest, "batch": publication.batch_ref,
        "policy": SQL_ADMISSION_POLICY_VERSION, "periods": periods,
        "approved_controls": sorted(approved_controls),
        "expires_at": deadline.expires_at,
        "sql": review.canonical_sql, "parameters": review.parameter_items,
        "columns": sorted(review.source_columns), "outputs": review.output_names,
        "measure_semantics": review.measure_semantics,
        "quality_mode": "observed_uncertified" if observed_uncertified else "certified",
    }
    return SqlAdmission(review, context.context_version, candidate_digest, request_digest,
                        readiness_digest, publication.batch_ref, SQL_ADMISSION_POLICY_VERSION, periods,
                        tuple(sorted(approved_controls)),
                        "observed_uncertified" if observed_uncertified else "certified",
                        deadline.expires_at, _digest(material))


async def revalidate_sql_admission(
    admitted: SqlAdmission, candidate: SqlGenerationCandidate, request: QuestionPlanRequest, *,
    engine: Engine, readiness_engine: Engine, publication: GoldPublicationContext, client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope], approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline, correlation_id: str,
) -> SqlAdmission:
    _require(admitted.policy_version == SQL_ADMISSION_POLICY_VERSION
             and deadline.clock() < admitted.expires_at)
    # A prontidão, cobertura da fonte e revisão semântica já foram verificadas
    # nesta mesma requisição. Repetir a leitura completa de centenas de milhares
    # de linhas aqui consumia o prazo. A publicação é imutável por batch_ref;
    # confira o vínculo leve agora e o catálogo/publicação novamente no snapshot
    # somente leitura do executor.
    candidate_digest = _digest(candidate.model_dump(mode="json"))
    candidate = SqlGenerationCandidate.model_validate_json(candidate.model_dump_json())
    request = QuestionPlanRequest.model_validate_json(request.model_dump_json())
    # Preserve o erro estrutural específico para parâmetros incompatíveis antes
    # de comparar o digest da admissão.
    review_sql_semantics(candidate, request)
    _require(admitted.policy_version == SQL_ADMISSION_POLICY_VERSION
             and deadline.clock() < admitted.expires_at
             and admitted.batch_ref == request.batch_ref == publication.batch_ref
             and admitted.approved_controls == tuple(sorted(approved_controls))
             and admitted.candidate_digest == candidate_digest
             and admitted.request_digest == _request_digest(request)
             and resolve_scope() == request.access_scope)
    fields = await deadline.run(5, lambda: asyncio.to_thread(
        publication.planning_fields, engine, request.access_scope))
    _require(resolve_scope() == request.access_scope)
    payload = request.model_dump(mode="json")
    payload.update(fields)
    fresh_request = QuestionPlanRequest.model_validate(payload)
    review = review_sql_semantics(candidate, fresh_request)
    context = build_sql_generation_context(fresh_request)
    periods = _periods(candidate)
    _require(context.context_version == admitted.context_version
             and periods == admitted.requested_periods
             and review == admitted.review)
    context_body = json.loads(context.contents)
    if candidate.interpretation.metric_id in {
        "billing.revenue", "energy.consumption", "energy.average_consumption_per_uc",
        "billing.average_ticket", "billing.effective_tariff", "service.attendance",
        "service.satisfaction", "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        try:
            await deadline.run(5, lambda: asyncio.to_thread(
                publication.assert_sql_source_coverage, engine,
                table_name=context_body["source"]["table"], periods=periods,
                dimension_ids=request.access_scope.allowed_dimension_ids,
                metric_ids=frozenset(context.metric_ids),
                source_capability_id=context_body["source"]["capability_id"],
            ))
        except GoldCatalogIncompatible:
            raise SqlAdmissionDenied(
                "Cobertura ou fonte SQL indisponível para o recorte."
            ) from None
    material = {
        "context": admitted.context_version,
        "candidate": admitted.candidate_digest,
        "request": admitted.request_digest,
        "readiness": admitted.readiness_digest,
        "batch": admitted.batch_ref,
        "policy": admitted.policy_version,
        "periods": admitted.requested_periods,
        "approved_controls": list(admitted.approved_controls),
        "expires_at": admitted.expires_at,
        "sql": admitted.review.canonical_sql,
        "parameters": admitted.review.parameter_items,
        "columns": sorted(admitted.review.source_columns),
        "outputs": admitted.review.output_names,
        "measure_semantics": admitted.review.measure_semantics,
        "quality_mode": admitted.quality_mode,
    }
    _require(_digest(material) == admitted.digest)
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    _require(resolve_scope() == request.access_scope)
    return admitted
