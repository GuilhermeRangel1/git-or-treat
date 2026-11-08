"""Contexto F1 obtido do catálogo instalado, sem consultar dados ou chamar modelo.

Preparação: deve ser chamado com escopo/publicação resolvidos pelo Backend.
Não certifica prontidão nem autoriza candidato SQL.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

from app.models.gold_v2 import TABLES
from app.schemas.genai_internal import QuestionPlanRequest
from app.services.gold_catalog import load_gold_catalog

F1_DIMENSIONS = {
    "geography.municipality": "municipio",
    "geography.neighborhood": "bairro",
    "customer.consumption_class": "classe_consumo",
    "network.feeder": "id_alimentador",
    "generation.distributed": "possui_gd",
}
F1_METRIC_SOURCE_CAPABILITY = {
    "billing.revenue": "faturamento.receita",
    # O fluxo legado validava a medida kWh junto da receita em diagnostico_receita.
    "energy.consumption": "faturamento.receita",
    "service.attendance": "atendimento.mensal",
    "service.satisfaction": "atendimento.mensal",
    "service.accumulated_attendance": "atendimento.uc_acumulado",
    "service.accumulated_satisfaction": "atendimento.uc_acumulado",
    "energy.gd_units": "consumo.variacao_uc",
    "energy.gd_consumption_drop": "consumo.variacao_uc",
    "network.equivalent_interruption_duration": "interrupcoes.dec_fec",
    "network.equivalent_interruption_frequency": "interrupcoes.dec_fec",
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


def requested_sql_metric_id(question: str, context=()) -> str:
    normalized = question.casefold()
    if is_gd_consumption_drop_question(question):
        return "energy.gd_consumption_drop"
    if _is_gd_units_question(question):
        return "energy.gd_units"
    if _is_accumulated_satisfaction_question(question):
        return "service.accumulated_satisfaction"
    if any(token in normalized for token in ("satisf", "nota média", "nota media")):
        return "service.satisfaction"
    if "histórico acumulado" in normalized and any(
        token in normalized
        for token in ("atendiment", "protocol", "chamad", "call center")
    ):
        return "service.accumulated_attendance"

    def continuity_metric(value: str) -> str | None:
        if re.search(r"\bfec\b|frequência equivalente", value):
            return "network.equivalent_interruption_frequency"
        if re.search(r"\bdec\b|duração equivalente", value):
            return "network.equivalent_interruption_duration"
        return None

    continuity = continuity_metric(normalized)
    if continuity:
        return continuity
    if is_explicit_multi_metric_question(question):
        return "energy.consumption"
    if any(
        token in normalized
        for token in ("atendiment", "protocolo", "chamado", "reclamação")
    ):
        return "service.attendance"
    if any(token in normalized for token in ("kwh", "quilowatt")):
        return "energy.consumption"
    if any(token in normalized for token in ("receit", "fatur", "r$", "reais")):
        return "billing.revenue"
    if "consum" in normalized:
        return "energy.consumption"
    for turn in reversed(context):
        if turn.role != "user":
            continue
        previous = turn.content.casefold()
        if is_gd_consumption_drop_question(turn.content):
            return "energy.gd_consumption_drop"
        if _is_gd_units_question(turn.content):
            return "energy.gd_units"
        if _is_accumulated_satisfaction_question(turn.content):
            return "service.accumulated_satisfaction"
        continuity = continuity_metric(previous)
        if continuity:
            return continuity
        if "histórico acumulado" in previous and any(
            token in previous
            for token in ("atendiment", "protocol", "chamad", "call center")
        ):
            return "service.accumulated_attendance"
        if any(
            token in previous
            for token in ("atendiment", "protocolo", "chamado", "reclamação")
        ):
            return "service.attendance"
        if any(token in previous for token in ("satisf", "nota média", "nota media")):
            return "service.satisfaction"
        if any(token in previous for token in ("kwh", "quilowatt")):
            return "energy.consumption"
        if any(token in previous for token in ("receit", "fatur", "r$", "reais")):
            return "billing.revenue"
        if "consum" in previous:
            return "energy.consumption"
    return "billing.revenue"


def _is_gd_units_question(question: str) -> bool:
    normalized = _normalize_question(question)
    if re.search(
        r"\b(?:queda|reducao|reduziram|diminuiram|cairam)\b|\b30\s*%", normalized
    ):
        return False
    asks_count = re.search(
        r"\b(?:quantas?|contagem|quantidade de|numero de|total de)\b",
        normalized,
    )
    names_uc = re.search(r"\b(?:uc|ucs|unidade|unidades)\b", normalized)
    mentions_gd = re.search(r"\b(?:gd|geracao distribuida)\b", normalized)
    return bool(asks_count and names_uc and mentions_gd)


def _is_accumulated_satisfaction_question(question: str) -> bool:
    normalized = _normalize_question(question)
    asks_satisfaction = re.search(
        r"\b(?:satisfacao|nota media|nota de satisfacao)\b", normalized
    )
    names_history = re.search(r"\b(?:historico|acumulad[oa]s?)\b", normalized)
    return bool(asks_satisfaction and names_history)


def is_gd_consumption_drop_question(question: str) -> bool:
    """Detecta a métrica legada de queda GD, ainda fora da SQL F1 executável."""
    normalized = _normalize_question(question)
    return bool(
        re.search(r"\b(?:gd|geracao distribuida)\b", normalized)
        and re.search(r"\b(?:queda|reducao|reduziram|diminuiram|cairam)\b", normalized)
    )


def is_explicit_multi_metric_question(question: str) -> bool:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    # “Classe de consumo” names a billing dimension, not the kWh measure.
    normalized_without_class = re.sub(
        r"\bclasses?\s+de\s+consumo\b",
        "",
        normalized,
    )
    asks_consumption = any(
        token in normalized_without_class
        for token in (
            "consum",
            "kwh",
            "quilowatt",
        )
    )
    asks_revenue = any(
        token in normalized for token in ("receit", "fatur", "r$", "reais")
    )
    return asks_consumption and asks_revenue


def is_periodized_accumulated_attendance_question(question: str) -> bool:
    """The accumulated source has no certified time window; never imply one."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return bool(
        re.search(
            r"\b(?:20\d{2}|jan(?:eiro)?|fev(?:ereiro)?|mar(?:co)?|abr(?:il)?|"
            r"mai(?:o)?|jun(?:ho)?|jul(?:ho)?|ago(?:sto)?|set(?:embro)?|"
            r"out(?:ubro)?|nov(?:embro)?|dez(?:embro)?|ultimos?|desde|entre|"
            r"competencia|periodo|mensal(?:mente)?|anos?|mes(?:es)?|trimestres?|"
            r"semestres?)\b|\b20\d{2}-(?:0[1-9]|1[0-2])\b",
            normalized,
        )
    )


_GD_TERM = r"(?:\bgd\b|geracao distribuida)"
_GD_CLEAR = re.compile(
    r"\b(?:sem esse filtro|remova o filtro|remover o filtro|sem filtro)\b"
)
_METRIC_REQUEST = re.compile(
    r"\b(?:consumo|consumir|kwh|quilowatt|receita|faturamento|atendimento|"
    r"protocolo|chamado|dec|fec)\b"
)


def _normalize_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _gd_value_in_message(message: str) -> tuple[bool, str | None]:
    normalized = _normalize_question(message)
    if not re.search(_GD_TERM, normalized):
        return False, None
    negative = re.search(rf"\bsem\b[^.!?]{{0,40}}{_GD_TERM}", normalized)
    positive = re.search(
        rf"\b(?:com|possui|possuem|tem)\b[^.!?]{{0,40}}{_GD_TERM}", normalized
    )
    if negative and not positive:
        return True, "Não"
    if positive and not negative:
        return True, "Sim"
    return True, None


def requested_gd_filter_value(question: str, context=()) -> str | None:
    """Resolve filtro GD explícito ou herdado só em acompanhamento elíptico."""
    mentioned, value = _gd_value_in_message(question)
    if mentioned:
        return value
    current = _normalize_question(question)
    if _GD_CLEAR.search(current) or _METRIC_REQUEST.search(current):
        return None
    for turn in reversed(context):
        if turn.role != "user":
            continue
        mentioned, value = _gd_value_in_message(turn.content)
        if mentioned:
            return value
        previous = _normalize_question(turn.content)
        if _GD_CLEAR.search(previous) or _METRIC_REQUEST.search(previous):
            return None
    return None


def mentions_gd(question: str, context=()) -> bool:
    """Detecta GD atual/herdada sem reaplicar filtro a uma nova pergunta completa."""
    mentioned, _ = _gd_value_in_message(question)
    if mentioned:
        return True
    current = _normalize_question(question)
    if _GD_CLEAR.search(current) or _METRIC_REQUEST.search(current):
        return False
    for turn in reversed(context):
        if turn.role != "user":
            continue
        mentioned, _ = _gd_value_in_message(turn.content)
        if mentioned:
            return True
        previous = _normalize_question(turn.content)
        if _GD_CLEAR.search(previous) or _METRIC_REQUEST.search(previous):
            return False
    return False


def requested_sql_source_capability(question: str, metric_id: str, context=()) -> str:
    """Seleciona a fonte de bairro apenas quando o pedido explicita esse recorte."""
    latest_user_turn = next(
        (turn.content for turn in reversed(context) if turn.role == "user"), ""
    )
    normalized = f"{question} {latest_user_turn}".casefold()
    if metric_id == "billing.revenue" and re.search(r"\bbairro\b", normalized):
        return "faturamento.receita_bairro"
    return F1_METRIC_SOURCE_CAPABILITY[metric_id]


def build_sql_generation_context(request: QuestionPlanRequest) -> SqlGenerationContext:
    scope = request.access_scope
    metric_id = requested_sql_metric_id(request.question, request.context)
    generation_version = (
        "text-to-sql-f1-v4"
        if metric_id.startswith("network.equivalent_interruption_")
        else "text-to-sql-f1-v7"
        if metric_id == "service.satisfaction"
        else "text-to-sql-f1-v10"
        if metric_id == "energy.gd_consumption_drop"
        else "text-to-sql-f1-v8"
        if metric_id == "energy.gd_units"
        else "text-to-sql-f1-v9"
        if metric_id == "service.accumulated_satisfaction"
        else "text-to-sql-f1-v5"
        if metric_id == "service.accumulated_attendance"
        else "text-to-sql-f1-v3"
        if metric_id == "service.attendance"
        else "text-to-sql-f1-v2"
        if metric_id == "energy.consumption"
        else "text-to-sql-f1-v1"
    )
    if (
        scope.profile_id != "v-energy-grid-360-gold"
        or scope.source_id != "gold.local"
        or scope.allowed_operations != frozenset({"read"})
        or re.fullmatch(r"session:[a-f0-9]{64}", scope.caller_ref) is None
        or metric_id not in scope.allowed_metric_ids
        or request.batch_ref is None
    ):
        raise SqlContextUnavailable(
            "Escopo F1 indisponível.", reason="scope_unavailable"
        )
    if metric_id in {
        "service.accumulated_attendance",
        "service.accumulated_satisfaction",
        "energy.gd_units",
        "energy.gd_consumption_drop",
    }:
        coverage = next(
            (item for item in request.temporal_coverage if item.metric_id == metric_id),
            None,
        )
        if coverage is None or coverage.kind != "none" or coverage.competencies:
            raise SqlContextUnavailable(
                "Cobertura da fonte de retrato indisponível.",
                reason="coverage_unavailable",
            )
    else:
        coverage = next(
            (item for item in request.temporal_coverage if item.metric_id == metric_id),
            None,
        )
        if coverage is None or coverage.kind != "monthly" or not coverage.competencies:
            raise SqlContextUnavailable(
                "Cobertura mensal F1 indisponível.", reason="coverage_unavailable"
            )
    catalog = load_gold_catalog()
    metric = next(item for item in catalog.metrics if item.metric_id == metric_id)
    source_capability = requested_sql_source_capability(
        request.question, metric_id, request.context
    )
    if (
        source_capability == "faturamento.receita_bairro"
        and "geography.neighborhood" not in scope.allowed_dimension_ids
    ):
        raise SqlContextUnavailable(
            "Recorte por bairro não autorizado.", reason="scope_unavailable"
        )
    source = next(
        item for item in metric.sources if item.capability_id == source_capability
    )
    measure_column = (
        "queda_consumo_superior_30_pct"
        if metric_id == "energy.gd_consumption_drop"
        else source.measure_column
    )
    gd_filter_value = requested_gd_filter_value(request.question, request.context)
    if gd_filter_value is not None and metric_id == "energy.consumption":
        if "generation.distributed" not in scope.allowed_dimension_ids:
            raise SqlContextUnavailable(
                "Filtro GD não autorizado.", reason="scope_unavailable"
            )
        gd_values = next(
            (
                item.values
                for item in request.dimension_value_coverage
                if item.dimension_id == "generation.distributed"
            ),
            (),
        )
        normalize = lambda value: "".join(
            char
            for char in unicodedata.normalize("NFD", value.casefold())
            if not unicodedata.combining(char)
        )
        if normalize(gd_filter_value) not in {normalize(value) for value in gd_values}:
            raise SqlContextUnavailable(
                "Vocabulário GD indisponível na publicação.",
                reason="dimension_values_unavailable",
            )
    dimensions = {
        key: value
        for key, value in source.dimension_columns.items()
        if key in scope.allowed_dimension_ids
        and (
            key != "generation.distributed"
            or gd_filter_value is not None
            and metric_id == "energy.consumption"
            or metric_id in {"energy.gd_units", "energy.gd_consumption_drop"}
        )
    }
    columns = [
        column
        for column in (source.temporal_column, measure_column, *dimensions.values())
        if column is not None
    ]
    if metric_id == "energy.gd_consumption_drop":
        columns.extend(("meses_com_leitura_p1", "meses_com_leitura_p2"))
    table = TABLES[source.table]
    payload = {
        "generation_contract_version": generation_version,
        "dialect": "postgres",
        "question": request.question,
        "context": [turn.model_dump(mode="json") for turn in request.context],
        "publication": request.batch_ref,
        "catalog": {
            "mapping_version": catalog.mapping_version,
            "dictionary_version": catalog.dictionary_version,
        },
        "semantic_registry": {
            "purpose": "recognition_only_not_authorization",
            "metrics": [
                {
                    "metric_id": item.metric_id,
                    "label": item.label,
                    "definition": item.definition,
                    "unit": item.unit,
                }
                for item in catalog.metrics
            ],
        },
        "schema_basis": "installed_models_and_versioned_catalog_not_live_database",
        "source": {
            "capability_id": source.capability_id,
            "schema": catalog.physical_schema,
            "table": source.table,
            "temporal_column": source.temporal_column,
            "columns": {name: str(table.c[name].type) for name in columns},
        },
        "metric": {
            "id": metric.metric_id,
            "definition": metric.definition,
            "unit": metric.unit,
            "measure_column": measure_column,
            "measure_type": "integer"
            if metric_id
            in {
                "service.attendance",
                "service.accumulated_attendance",
                "energy.gd_units",
                "energy.gd_consumption_drop",
            }
            else metric.measure_type,
            "aggregation": metric.aggregation,
            "null_rule": metric.null_rule,
            "rounding": metric.rounding.model_dump(mode="json"),
        },
        "dimensions": dimensions,
        "dimension_values": [
            item.model_dump(mode="json")
            for item in request.dimension_value_coverage
            if item.dimension_id in dimensions
        ],
        "temporal_coverage": coverage.model_dump(mode="json"),
        "rules": {
            "time_anchor": "latest_competency_in_authorized_coverage",
            "coverage_is_not_readiness": True,
            "annual_requires_all_months": True,
            "partial_year_requires_explicit_request": True,
            "joins_allowed": False,
            "metric_is_billed_not_paid": metric_id == "billing.revenue",
            "metric_definition_must_be_preserved": True,
            "dimensions_use_current_registry": True,
            "gd_filter_requires_explicit_question": metric_id == "energy.consumption",
            "aggregate_all_published_rows_before_ranking": True,
            "scope_is_not_authorized_by_model": True,
            "attendance_uses_utc_month_boundaries": metric_id
            in {
                "service.attendance",
                "service.satisfaction",
            },
            "attendance_operations": ["total"]
            if metric_id == "service.attendance"
            else [],
            "satisfaction_operations": ["average"]
            if metric_id == "service.satisfaction"
            else [],
            "satisfaction_definition": (
                "AVG(nota_satisfacao) por data_abertura no mês UTC; NULL é ignorado, zero é válido"
                if metric_id == "service.satisfaction"
                else None
            ),
            "accumulated_attendance_operations": ["accumulated_total"]
            if metric_id == "service.accumulated_attendance"
            else [],
            "accumulated_period_is_unknown": metric_id
            == "service.accumulated_attendance",
            "accumulated_satisfaction_operations": ["accumulated_average"]
            if metric_id == "service.accumulated_satisfaction"
            else [],
            "accumulated_satisfaction_period_is_unknown": metric_id
            == "service.accumulated_satisfaction",
            "accumulated_satisfaction_definition": (
                "AVG das notas individuais não nulas; zero é válido; sem período histórico conhecido"
                if metric_id == "service.accumulated_satisfaction"
                else None
            ),
            "snapshot_operations": ["snapshot_total"]
            if metric_id == "energy.gd_units"
            else [],
            "snapshot_period_phrase": "cadastro de GD no lote"
            if metric_id == "energy.gd_units"
            else None,
            "fixed_filter_values": metric.fixed_filter_values,
            "snapshot_definition": metric.definition
            if metric_id == "energy.gd_units"
            else None,
            "gd_drop_operations": ["snapshot_total"]
            if metric_id == "energy.gd_consumption_drop"
            else [],
            "gd_drop_windows": [
                {"start": "2022-07", "end": "2023-06"},
                {"start": "2025-07", "end": "2026-06"},
            ]
            if metric_id == "energy.gd_consumption_drop"
            else [],
            "gd_drop_minimum_months_per_window": 6
            if metric_id == "energy.gd_consumption_drop"
            else None,
            "gd_drop_threshold_exclusive": -30
            if metric_id == "energy.gd_consumption_drop"
            else None,
            "gd_drop_count_definition": (
                "COUNT(queda_consumo_superior_30_pct) filtrando valor TRUE e possui_gd='Sim'; "
                "a prontidão deve aprovar C08/C09, que reconciliam a flag com médias e meses "
                "de leitura das duas janelas fixas"
            )
            if metric_id == "energy.gd_consumption_drop"
            else None,
            "continuity_operations": ["grain_read"]
            if metric_id.startswith("network.equivalent_interruption_")
            else [],
            "continuity_no_aggregation": metric_id.startswith(
                "network.equivalent_interruption_"
            ),
        },
    }
    # Inclui escopo completo no digest sem enviar identidade/objetos não liberados ao modelo.
    scope_material = {
        "caller_ref": scope.caller_ref,
        "profile_id": scope.profile_id,
        "source_id": scope.source_id,
        "operations": sorted(scope.allowed_operations),
        "metrics": sorted(scope.allowed_metric_ids),
        "dimensions": sorted(scope.allowed_dimension_ids),
    }
    digest = hashlib.sha256(
        (_canonical(scope_material) + "\n" + _canonical(payload)).encode()
    ).hexdigest()
    contents = _canonical({"context_version": digest, **payload})
    context_bytes = len(contents.encode("utf-8"))
    if context_bytes > 65536:
        raise SqlContextUnavailable(
            "Contexto F1 excede o limite.",
            reason="context_too_large",
            context_bytes=context_bytes,
        )
    return SqlGenerationContext(
        context_version=digest,
        contents=contents,
        mapping_version=catalog.mapping_version,
        dictionary_version=catalog.dictionary_version,
        metric_ids=(metric.metric_id,),
        dimension_ids=tuple(sorted(dimensions)),
        column_names=tuple(columns),
        coverage_months=len(coverage.competencies),
        dimension_value_count=sum(
            len(item.values)
            for item in request.dimension_value_coverage
            if item.dimension_id in dimensions
        ),
        context_bytes=context_bytes,
    )
