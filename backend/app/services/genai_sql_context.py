"""Contexto F1 obtido do catálogo instalado, sem consultar dados ou chamar modelo.

Preparação: deve ser chamado com escopo/publicação resolvidos pelo Backend.
Não certifica prontidão nem autoriza candidato SQL.
"""

import hashlib
import json
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


@dataclass(frozen=True)
class SqlGenerationContext:
    context_version: str
    contents: str


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_sql_generation_context(request: QuestionPlanRequest) -> SqlGenerationContext:
    scope = request.access_scope
    if (scope.profile_id != "v-energy-grid-360-gold" or scope.source_id != "gold.local"
            or scope.allowed_operations != frozenset({"read"})
            or "billing.revenue" not in scope.allowed_metric_ids or request.batch_ref is None):
        raise SqlContextUnavailable("Escopo F1 indisponível.")
    coverage = next((item for item in request.temporal_coverage
                     if item.metric_id == "billing.revenue"), None)
    if coverage is None or coverage.kind != "monthly" or not coverage.competencies:
        raise SqlContextUnavailable("Cobertura mensal F1 indisponível.")
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
    if len(contents.encode("utf-8")) > 65536:
        raise SqlContextUnavailable("Contexto F1 excede o limite.")
    return SqlGenerationContext(context_version=digest, contents=contents)
