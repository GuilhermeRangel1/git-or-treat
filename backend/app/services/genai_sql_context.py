"""Contexto F1 obtido do catálogo instalado, sem consultar dados ou chamar modelo.

Preparação: deve ser chamado com escopo/publicação resolvidos pelo Backend.
Não certifica prontidão nem autoriza candidato SQL.
"""

import hashlib
import json
import re
from dataclasses import dataclass

from app.models.gold_v2 import TABLES
from app.schemas.genai_internal import QuestionPlanRequest
from app.services.gold_catalog import load_gold_catalog

F1_DIMENSIONS = {
    "geography.municipality": "municipio",
    "customer.consumption_class": "classe_consumo",
}


class SqlContextUnavailable(ValueError):
    """Contexto insuficiente ou escopo incompatível com a primeira fatia."""

    def __init__(self, message: str, *, reason: str, context_bytes: int | None = None):
        super().__init__(message)
        self.reason = reason
        self.context_bytes = context_bytes


@dataclass(frozen=True)
class SqlGenerationContext:
    context_version: str
    contents: str
    mapping_version: str
    dictionary_version: str
    metric_ids: tuple[str, ...]
    dimension_ids: tuple[str, ...]
    column_names: tuple[str, ...]
    coverage_months: int
    dimension_value_count: int
    context_bytes: int


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_sql_generation_context(request: QuestionPlanRequest) -> SqlGenerationContext:
    scope = request.access_scope
    if (scope.profile_id != "v-energy-grid-360-gold" or scope.source_id != "gold.local"
            or scope.allowed_operations != frozenset({"read"})
            or re.fullmatch(r"session:[a-f0-9]{64}", scope.caller_ref) is None
            or "billing.revenue" not in scope.allowed_metric_ids or request.batch_ref is None):
        raise SqlContextUnavailable("Escopo F1 indisponível.", reason="scope_unavailable")
    coverage = next((item for item in request.temporal_coverage
                     if item.metric_id == "billing.revenue"), None)
    if coverage is None or coverage.kind != "monthly" or not coverage.competencies:
        raise SqlContextUnavailable("Cobertura mensal F1 indisponível.",
                                    reason="coverage_unavailable")
    catalog = load_gold_catalog()
    metric = next(item for item in catalog.metrics if item.metric_id == "billing.revenue")
    source = next(item for item in metric.sources
                  if item.capability_id == "faturamento.receita")
    dimensions = {key: value for key, value in F1_DIMENSIONS.items()
                  if key in scope.allowed_dimension_ids}
    columns = [source.temporal_column, source.measure_column, *dimensions.values()]
    table = TABLES[source.table]
    payload = {
        "generation_contract_version": "text-to-sql-f1-v1",
        "dialect": "postgres",
        "question": request.question,
        "context": [turn.model_dump(mode="json") for turn in request.context],
        "publication": request.batch_ref,
        "catalog": {"mapping_version": catalog.mapping_version,
                    "dictionary_version": catalog.dictionary_version},
        "semantic_registry": {
            "purpose": "recognition_only_not_authorization",
            "metrics": [
                {"metric_id": item.metric_id, "label": item.label,
                 "definition": item.definition, "unit": item.unit}
                for item in catalog.metrics
            ],
        },
        "schema_basis": "installed_models_and_versioned_catalog_not_live_database",
        "source": {"schema": catalog.physical_schema, "table": source.table,
                   "columns": {name: str(table.c[name].type) for name in columns}},
        "metric": {"id": metric.metric_id, "definition": metric.definition,
                   "unit": metric.unit, "measure_column": source.measure_column,
                   "aggregation": metric.aggregation, "null_rule": metric.null_rule,
                   "rounding": metric.rounding.model_dump(mode="json")},
        "dimensions": dimensions,
        "dimension_values": [item.model_dump(mode="json")
                             for item in request.dimension_value_coverage
                             if item.dimension_id in dimensions],
        "temporal_coverage": coverage.model_dump(mode="json"),
        "rules": {
            "time_anchor": "latest_competency_in_authorized_coverage",
            "coverage_is_not_readiness": True,
            "annual_requires_all_months": True,
            "partial_year_requires_explicit_request": True,
            "joins_allowed": False,
            "metric_is_billed_not_paid": True,
            "dimensions_use_current_registry": True,
            "aggregate_all_published_rows_before_ranking": True,
            "scope_is_not_authorized_by_model": True,
        },
    }
    # Inclui escopo completo no digest sem enviar identidade/objetos não liberados ao modelo.
    scope_material = {
        "caller_ref": scope.caller_ref, "profile_id": scope.profile_id,
        "source_id": scope.source_id, "operations": sorted(scope.allowed_operations),
        "metrics": sorted(scope.allowed_metric_ids),
        "dimensions": sorted(scope.allowed_dimension_ids),
    }
    digest = hashlib.sha256((_canonical(scope_material) + "\n" + _canonical(payload)).encode()).hexdigest()
    contents = _canonical({"context_version": digest, **payload})
    context_bytes = len(contents.encode("utf-8"))
    if context_bytes > 65536:
        raise SqlContextUnavailable("Contexto F1 excede o limite.",
                                    reason="context_too_large", context_bytes=context_bytes)
    return SqlGenerationContext(
        context_version=digest,
        contents=contents,
        mapping_version=catalog.mapping_version,
        dictionary_version=catalog.dictionary_version,
        metric_ids=(metric.metric_id,),
        dimension_ids=tuple(sorted(dimensions)),
        column_names=tuple(columns),
        coverage_months=len(coverage.competencies),
        dimension_value_count=sum(len(item.values) for item in request.dimension_value_coverage
                                  if item.dimension_id in dimensions),
        context_bytes=context_bytes,
    )
