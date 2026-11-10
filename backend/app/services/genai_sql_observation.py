"""Geração e revisão F1 em observação; não chama executor nem concede prontidão."""

import asyncio
import json
import logging
import re
import unicodedata
from calendar import monthrange
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from time import perf_counter

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_generation import (
    SqlAnalysisFilter,
    SqlGenerationCandidate,
    SqlGenerationRequest,
)
from app.services.genai_client import GenAIQuestionClient, GenAIResponseInvalid
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_domain_policy import (
    OUT_OF_DOMAIN_MESSAGE,
    is_explicitly_outside_energy_domain,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_question_feedback import (
    ScopeDecisionRejected,
    enforce_scope_decision,
)
from app.services.genai_sql_admission import (
    SqlAdmission,
    SqlAdmissionDenied,
    admit_sql_candidate,
)
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
    is_explicit_multi_metric_question,
    is_gd_consumption_drop_followup,
    is_gd_consumption_drop_question,
    is_periodized_accumulated_attendance_question,
    requested_gd_filter_value,
)
from app.services.genai_sql_semantics import SqlSemanticReview, review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected
from app.services.genai_sql_telemetry import record_sql_stage, sql_stage

logger = logging.getLogger(__name__)

_MONTH_NUMBERS = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2,
    "marco": 3, "mar": 3, "abril": 4, "abr": 4,
    "maio": 5, "mai": 5, "junho": 6, "jun": 6,
    "julho": 7, "jul": 7, "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9, "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}


def _explicit_weighted_continuity_candidate(request, context):
    """Build a typed plan only for an explicit, covered month range and feeder."""
    if context.generation_contract_version != "text-to-sql-f1-v12":
        return None
    metric = context.metric_ids[0]
    if metric not in {
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        return None
    text = unicodedata.normalize("NFKD", request.question.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    month_pattern = "|".join(sorted(_MONTH_NUMBERS, key=len, reverse=True))
    indicator = "dec" if metric.endswith("duration") else "fec"
    match = re.fullmatch(
        rf"(?:calcule o {indicator} ponderado para a janela inteira, sem retornar "
        rf"serie mensal, preservando o alimentador e o periodo pedidos:\s*)?"
        rf"(?:como ficaram o {indicator} do|qual foi o {indicator} do|"
        rf"como ficou o {indicator} do|quanto deu o {indicator} do|"
        rf"quanto deu de {indicator} no) alimentador (?P<feeder>[\w.-]+) "
        rf"de (?P<start_month>{month_pattern}) a (?P<end_month>{month_pattern}) "
        rf"de (?P<year>20\d{{2}})\??",
        text.strip(),
    )
    if match is None:
        return None
    start_month = match.group("start_month")
    end_month = match.group("end_month")
    year = match.group("year")
    start_month, end_month, year = (
        _MONTH_NUMBERS[start_month], _MONTH_NUMBERS[end_month], int(year)
    )
    if start_month > end_month:
        return None
    start = date(year, start_month, 1)
    end = date(year, end_month, monthrange(year, end_month)[1])
    covered = {
        item.metric_id: set(item.competencies)
        for item in request.temporal_coverage
    }.get(metric, set())
    expected = {
        f"{year:04d}-{month:02d}" for month in range(start_month, end_month + 1)
    }
    if not expected <= covered:
        return None

    dimensions = {
        item.dimension_id: item.values for item in request.dimension_value_coverage
    }
    authorized_feeders = dimensions.get("network.feeder", ())
    normalize = lambda value: "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    feeder_name = match.group("feeder")
    matched_feeders = tuple(
        value for value in authorized_feeders if normalize(value) == normalize(feeder_name)
    )
    if not matched_feeders:
        return None
    if len(matched_feeders) > 1:
        return None
    filters = (
        (SqlAnalysisFilter(
            dimension_id="network.feeder", operator="eq", values=matched_feeders
        ),)
        if matched_feeders
        else ()
    )
    alias = (
        "dec_value" if metric.endswith("duration") else "fec_value"
    )
    unit = "horas por UC" if alias == "dec_value" else "interrupções por UC"
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "interpretation": {
            "metric_id": metric,
            "operation": "weighted_continuity",
            "aggregation": "weighted_ratio",
            "periods": [{"start": start.isoformat(), "end": end.isoformat()}],
            "filters": [item.model_dump(mode="json") for item in filters],
            "group_by": [],
        },
        "result_columns": [
            {"name": alias, "role": "measure", "value_type": "decimal", "unit": unit},
            {"name": "feeders_included", "role": "measure", "value_type": "integer", "unit": "alimentadores"},
            {"name": "feeders_excluded", "role": "measure", "value_type": "integer", "unit": "alimentadores"},
        ],
    })


def _explicit_control_count_candidate(request, context):
    """Compile the two snapshot counts from the closed catalog; Gemini is not needed."""
    metric_id = context.metric_ids[0]
    if metric_id not in {"customer.units_by_class", "inspection.units_by_priority"}:
        return None
    body = json.loads(context.contents)
    source = body["source"]
    measure = body["metric"]["measure_column"]
    question = unicodedata.normalize("NFKD", request.question.casefold())
    question = " ".join(
        "".join(ch for ch in question if not unicodedata.combining(ch)).split()
    )
    dimension_id = (
        "customer.consumption_class"
        if metric_id == "customer.units_by_class"
        else "inspection.priority"
    )
    dimension = body["dimensions"].get(dimension_id)
    vocabulary = next(
        (item["values"] for item in body["dimension_values"]
         if item["dimension_id"] == dimension_id),
        [],
    )
    aliases = {
        "customer.consumption_class": {
            "COMERCIAL": ("comercial", "comerciais"),
            "INDUSTRIAL": ("industrial", "industriais"),
            "PODER PUBLICO": ("poder publico",),
            "RESIDENCIAL": ("residencial", "residenciais"),
            "RURAL": ("rural", "rurais"),
        },
        "inspection.priority": {
            "ALTA - HISTORICO IRREGULAR": (
                "historico irregular", "alta historico irregular",
                "alta por historico irregular",
            ),
            "ALTA - CONSUMO ZERO": (
                "alta consumo zero", "alta por consumo zero", "consumo zero",
            ),
            "BAIXA": ("baixa", "baixa prioridade"),
            "MEDIA - NUNCA INSPECIONADO": (
                "nunca foram inspecionadas", "nunca inspecionada",
                "media nunca inspecionado", "media por nunca inspecionado",
            ),
            "REVISAR - SEM HISTORICO DE CONSUMO": (
                "revisar sem historico de consumo",
                "revisao por falta de historico",
                "marcada para revisao por falta de historico",
            ),
        },
    }[dimension_id]
    # C07's zero-consumption class may be absent from the data because its true
    # count is zero. It is still a versioned Gold category and safe to query.
    matchable_values = list(vocabulary)
    if dimension_id == "inspection.priority":
        matchable_values.extend(
            value for value in aliases if value not in matchable_values
        )
    filters = []
    if dimension:
        for value in matchable_values:
            normalized_aliases = [
                " ".join(
                    "".join(
                        ch for ch in unicodedata.normalize("NFKD", alias.casefold())
                        if not unicodedata.combining(ch)
                    ).replace("-", " ").split()
                )
                for alias in aliases[value]
            ]
            if any(
                re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", question)
                for alias in normalized_aliases
            ):
                filters.append(value)
    if len(filters) > 1:
        return None
    is_grouped = (
        bool(re.search(
            r"\b(?:cada|distribuicao|distribuidos|distribuidas|"
            r"por municipio|por classe|por prioridade|por faixa)\b",
            question,
        ))
        or bool(re.search(r"\bclasses? de consumo\b", question))
        or "prioridade de inspecao" in question
        or "faixa de prioridade" in question
    )
    group_name = (
        "consumption_class"
        if dimension_id == "customer.consumption_class"
        else "inspection_priority"
    )
    columns = [
        {
            "name": group_name,
            "role": "dimension",
            "value_type": "string",
            "unit": None,
        },
        {"name": "units_count", "role": "measure", "value_type": "integer", "unit": "UCs"},
    ] if is_grouped else [
        {"name": "units_count", "role": "measure", "value_type": "integer", "unit": "UCs"}
    ]
    projection = (
        f"{dimension} AS {group_name}, " if is_grouped else ""
    ) + f"COUNT(DISTINCT {measure}) AS units_count"
    sql = f"SELECT {projection} FROM {source['schema']}.{source['table']}"
    parameters = {}
    if filters:
        parameter = "control_value"
        sql += f" WHERE {dimension} = :{parameter}"
        parameters[parameter] = {"type": "string", "value": filters[0]}
    if is_grouped:
        sql += f" GROUP BY {dimension}"
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": sql,
        "parameters": parameters,
        "interpretation": {
            "metric_id": metric_id,
            "operation": "snapshot_total",
            "aggregation": "count_distinct",
            "periods": [],
            "filters": ([{
                "dimension_id": dimension_id, "operator": "eq", "values": filters,
            }] if filters else []),
            "group_by": [group_name] if is_grouped else [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": columns,
    })


def _explicit_grouped_gd_units_candidate(request, context):
    """Build the supported snapshot breakdown of GD UCs by municipality."""
    if context.metric_ids != ("energy.gd_units",):
        return None
    question = unicodedata.normalize("NFKD", request.question.casefold())
    question = "".join(char for char in question if not unicodedata.combining(char))
    if not re.search(r"\b(?:em cada municipio|por municipio|cada municipio)\b", question):
        return None
    if re.search(r"\b(?:20\d{2}|mensal|competencia|periodo|entre|desde)\b", question):
        return None

    body = json.loads(context.contents)
    source = body["source"]
    municipality = body["dimensions"].get("geography.municipality")
    if municipality is None or "municipio" not in source["columns"]:
        return None
    gd_values = next(
        (item["values"] for item in body["dimension_values"]
         if item["dimension_id"] == "generation.distributed"),
        [],
    )
    if "Sim" not in gd_values:
        return None
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": (
            f"SELECT {municipality} AS municipality, "
            f"COUNT({body['metric']['measure_column']}) AS gd_units "
            f"FROM {source['schema']}.{source['table']} "
            f"WHERE {body['metric']['measure_column']} = :distributed "
            f"GROUP BY {municipality}"
        ),
        "parameters": {"distributed": {"type": "string", "value": "Sim"}},
        "interpretation": {
            "metric_id": "energy.gd_units",
            "operation": "snapshot_total",
            "aggregation": "count_non_null",
            "periods": [],
            "filters": [{
                "dimension_id": "generation.distributed",
                "operator": "eq",
                "values": ["Sim"],
            }],
            "group_by": ["municipality"],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [
            {"name": "municipality", "role": "dimension", "value_type": "string"},
            {"name": "gd_units", "role": "measure", "value_type": "integer", "unit": "UCs"},
        ],
    })


def _explicit_gd_consumption_drop_candidate(request, context):
    """Count the catalog-defined >30% GD drop flag over its fixed windows."""
    if context.metric_ids != ("energy.gd_consumption_drop",):
        return None
    if not (
        is_gd_consumption_drop_question(request.question)
        or is_gd_consumption_drop_followup(request.question, request.context)
    ):
        return None
    if requested_gd_filter_value(request.question, request.context) != "Sim":
        return None
    body = json.loads(context.contents)
    rules = body["rules"]
    source = body["source"]
    columns = set(source["columns"])
    required_columns = {
        "possui_gd", "queda_consumo_superior_30_pct",
        "meses_com_leitura_p1", "meses_com_leitura_p2", "municipio",
    }
    if (
        rules.get("gd_drop_minimum_months_per_window") != 6
        or rules.get("gd_drop_threshold_exclusive") != -30
        or not required_columns <= columns
    ):
        return None

    history = [request.question]
    if is_gd_consumption_drop_followup(request.question, request.context):
        history.extend(
            turn.content for turn in request.context if turn.role == "user"
        )
    text = " ".join(history)
    normalize = lambda value: "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    normalized_text = normalize(text)
    municipalities = next(
        (item["values"] for item in body["dimension_values"]
         if item["dimension_id"] == "geography.municipality"),
        [],
    )
    matched = tuple(
        value for value in municipalities
        if re.search(
            rf"(?<![\w]){re.escape(normalize(value))}(?![\w])",
            normalized_text,
        )
    )
    if len(matched) > 1:
        return None

    filters = [SqlAnalysisFilter(
        dimension_id="generation.distributed", operator="eq", values=("Sim",),
    )]
    predicates = [
        "possui_gd = :gd",
        "queda_consumo_superior_30_pct = :eligible",
        "meses_com_leitura_p1 >= :minimum_months",
        "meses_com_leitura_p2 >= :minimum_months",
    ]
    parameters = {
        "gd": {"type": "string", "value": "Sim"},
        "eligible": {"type": "boolean", "value": True},
        "minimum_months": {"type": "integer", "value": 6},
    }
    if matched:
        filters.append(SqlAnalysisFilter(
            dimension_id="geography.municipality", operator="eq", values=matched,
        ))
        predicates.append("municipio = :municipality")
        parameters["municipality"] = {"type": "string", "value": matched[0]}

    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": (
            "SELECT COUNT(queda_consumo_superior_30_pct) AS gd_drop_units "
            f"FROM {source['schema']}.{source['table']} WHERE "
            + " AND ".join(predicates)
        ),
        "parameters": parameters,
        "interpretation": {
            "metric_id": "energy.gd_consumption_drop",
            "operation": "snapshot_total",
            "aggregation": "count_gd_drop",
            "periods": [],
            "filters": [item.model_dump(mode="json") for item in filters],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [{
            "name": "gd_drop_units", "role": "measure",
            "value_type": "integer", "unit": "UCs",
        }],
    })


def _is_periodized_cadastral_snapshot_question(question: str) -> bool:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    month_pattern = "|".join(
        re.escape(month) for month in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    return bool(re.search(
        rf"\b(?:20\d{{2}}|{month_pattern}|periodo|mensal(?:mente)?|"
        rf"competencia|ultimos?|(?:desde|entre)\s+(?:20\d{{2}}|{month_pattern}))\b",
        normalized,
    ))


def _is_annual_monthly_attendance_question(question: str) -> bool:
    """An annual attendance total is outside F1's single-month operation."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    mentions_attendance = bool(
        re.search(r"\b(?:atendiment\w*|protocol\w*|chamad\w*)\b", normalized)
    )
    mentions_year = bool(re.search(r"\b20\d{2}\b", normalized))
    month_pattern = "|".join(sorted(_MONTH_NUMBERS, key=len, reverse=True))
    mentions_month = bool(re.search(rf"\b(?:{month_pattern})\b", normalized))
    return mentions_attendance and mentions_year and not mentions_month


def _is_unsupported_dec_fec_multi_feeder_question(question: str) -> bool:
    """A pooled DEC/FEC is not a per-feeder breakdown."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    asks_for_breakdown = bool(re.search(
        r"\b(?:por alimentador(?:es)?|em cada alimentador(?:es)?|"
        r"para cada alimentador(?:es)?)\b",
        normalized,
    ))
    names_feeder = bool(re.search(r"\bALM[-_][A-Z0-9]+(?:-[A-Z0-9]+)*\b", normalized))
    return asks_for_breakdown and not names_feeder


def _is_unsupported_percentage_ranking_question(question: str) -> bool:
    """Percentage ranking is not part of the admitted comparison contract."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    asks_for_percentage = bool(
        re.search(r"\b(?:percentual|percentuais|porcentual|porcentuais)\b", normalized)
    )
    asks_for_ranking = bool(
        re.search(r"\b(?:maior(?:es)?|menor(?:es)?|top|ranking)\b", normalized)
    )
    return asks_for_percentage and asks_for_ranking


def _is_sensitive_personal_data_question(question: str) -> bool:
    """Personal identifiers are outside the analytical F1 contract."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return bool(re.search(
        r"\b(?:dados pessoais|cpf|cnpj|telefone|endereco|"
        r"nome(?:s)? dos titulares?|titulares? das? ucs?)\b",
        normalized,
    ))


def _explicit_grouped_comparison_candidate(request, context):
    """Build a covered grouped comparison/ranking with an explicit month pair."""
    if context.metric_ids not in {("billing.revenue",), ("energy.consumption",)}:
        return None
    normalized = unicodedata.normalize("NFKD", request.question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    month_pattern = "|".join(
        re.escape(month) for month in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    match = re.search(
        rf"\bentre\s+(?P<first>{month_pattern})\s+e\s+"
        rf"(?P<second>{month_pattern})\s+(?:de\s+)?(?P<year>20\d{{2}})\b",
        normalized,
    )
    if match is None:
        return None

    group_dimension = (
        "customer.consumption_class"
        if re.search(r"\bclass(?:e|es)\b", normalized)
        else "geography.municipality"
        if re.search(r"\bmunicipios?\b", normalized)
        else None
    )
    if group_dimension is None or group_dimension not in request.access_scope.allowed_dimension_ids:
        return None
    group_name, group_column = {
        "customer.consumption_class": ("consumption_class", "classe_consumo"),
        "geography.municipality": ("municipality", "municipio"),
    }[group_dimension]

    year = int(match.group("year"))
    first_month = _MONTH_NUMBERS[match.group("first")]
    second_month = _MONTH_NUMBERS[match.group("second")]
    if first_month == second_month:
        return None
    metric_id = context.metric_ids[0]
    requested_months = (first_month, second_month)
    competencies = {
        item.metric_id: set(item.competencies) for item in request.temporal_coverage
    }
    if not all(
        f"{year:04d}-{month:02d}" in competencies.get(metric_id, set())
        for month in requested_months
    ):
        return None

    body = json.loads(context.contents)
    dimensions = {
        item["dimension_id"]: item["values"] for item in body["dimension_values"]
    }
    filters = []
    where_parameters = []
    if group_dimension != "geography.municipality":
        normalize = lambda value: "".join(
            char for char in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(char)
        )
        question_municipalities = [
            value for value in dimensions.get("geography.municipality", ())
            if re.search(
                rf"(?<!\w){re.escape(normalize(value))}(?!\w)", normalized
            )
        ]
        if len(question_municipalities) > 1:
            return None
        if question_municipalities:
            municipality = question_municipalities[0]
            filters.append({
                "dimension_id": "geography.municipality",
                "operator": "eq",
                "values": [municipality],
            })
            where_parameters.append("municipio = :municipality")

    ranking_direction = ranking_limit = None
    delta_alias = "period_1_minus_period_0"
    reduction = bool(re.search(r"\b(?:queda|reducao|diminuicao)\b", normalized))
    increase = bool(re.search(r"\b(?:aumento|aumentou|crescimento|subida)\b", normalized))
    rank_match = re.search(
        r"\b(?:maior|maiores|cinco|tres|dois|dez|1|2|3|5|10)\b", normalized
    )
    asks_ranking = bool(rank_match and re.search(r"\b(?:maior|maiores|top)\b", normalized))
    if asks_ranking:
        ranking_direction = "desc"
        if reduction:
            # Positive reduction = first window minus second window.
            delta_alias = "period_0_minus_period_1"
        else:
            # An increase is measured chronologically: second window minus first.
            delta_alias = "period_1_minus_period_0"
        limit_match = re.search(
            r"\b(?P<limit>cinco|tres|dois|dez|1|2|3|5|10)\b", normalized
        )
        limit_token = limit_match.group("limit") if limit_match else None
        ranking_limit = {
            "um": 1, "dois": 2, "tres": 3, "cinco": 5, "dez": 10,
        }.get(limit_token, int(limit_token)
              if limit_token and limit_token.isdigit() else 1)
        if increase and reduction:
            return None

    periods = [
        {
            "start": date(year, month, 1).isoformat(),
            "end": date(year, month, monthrange(year, month)[1]).isoformat(),
        }
        for month in requested_months
    ]
    source = body["source"]
    measure = body["metric"]["measure_column"]
    unit = body["metric"]["unit"]
    sql = (
        f"SELECT {group_column} AS {group_name}, "
        f"SUM({measure}) FILTER (WHERE competencia = :period_0) AS period_0_total, "
        f"SUM({measure}) FILTER (WHERE competencia = :period_1) AS period_1_total, "
        f"(SUM({measure}) FILTER (WHERE competencia = :{'period_0' if delta_alias == 'period_0_minus_period_1' else 'period_1'}) - "
        f"SUM({measure}) FILTER (WHERE competencia = :{'period_1' if delta_alias == 'period_0_minus_period_1' else 'period_0'})) "
        f"AS {delta_alias} FROM {source['schema']}.{source['table']} "
        "WHERE competencia IN (:period_0, :period_1)"
    )
    if where_parameters:
        sql += " AND " + " AND ".join(where_parameters)
    sql += f" GROUP BY {group_column}"
    if ranking_direction is not None:
        sql += (
            f" ORDER BY {delta_alias} DESC NULLS LAST, "
            f"{group_name} ASC NULLS LAST LIMIT {ranking_limit}"
        )

    parameters = {
        "period_0": {"type": "string", "value": f"{year:04d}-{first_month:02d}"},
        "period_1": {"type": "string", "value": f"{year:04d}-{second_month:02d}"},
    }
    if where_parameters:
        parameters["municipality"] = {"type": "string", "value": municipality}
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": sql,
        "parameters": parameters,
        "interpretation": {
            "metric_id": metric_id,
            "operation": "comparison",
            "aggregation": body["metric"]["aggregation"],
            "periods": periods,
            "filters": filters,
            "group_by": [group_name],
            "ranking_direction": ranking_direction,
            "ranking_limit": ranking_limit,
        },
        "result_columns": [
            {"name": group_name, "role": "dimension", "value_type": "string"},
            *[
                {"name": alias, "role": "measure", "value_type": "decimal", "unit": unit}
                for alias in ("period_0_total", "period_1_total", delta_alias)
            ],
        ],
    })


def _explicit_monthly_comparison_candidate(request, context):
    """Build a constrained two-month consumption comparison from explicit wording."""
    if context.metric_ids != ("energy.consumption",):
        return None
    normalized = unicodedata.normalize("NFKD", request.question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    month_pattern = "|".join(
        re.escape(month) for month in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    match = re.fullmatch(
        rf"\s*compare o consumo medido de (?P<municipality>[\w -]+?) entre "
        rf"(?P<first>{month_pattern}) e (?P<second>{month_pattern}) de "
        rf"(?P<year>20\d{{2}})[?.!]?\s*",
        normalized,
    )
    if match is None:
        return None
    year = int(match.group("year"))
    first_month = _MONTH_NUMBERS[match.group("first")]
    second_month = _MONTH_NUMBERS[match.group("second")]
    if first_month == second_month:
        return None
    requested_months = (first_month, second_month)
    competencies = {item.metric_id: set(item.competencies) for item in request.temporal_coverage}
    if not all(
        f"{year:04d}-{month:02d}" in competencies.get("energy.consumption", set())
        for month in requested_months
    ):
        return None

    body = json.loads(context.contents)
    dimensions = {
        item["dimension_id"]: item["values"] for item in body["dimension_values"]
    }
    municipality = match.group("municipality").strip()
    normalize = lambda value: "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    matches = tuple(
        value for value in dimensions.get("geography.municipality", ())
        if normalize(value) == normalize(municipality)
    )
    if len(matches) != 1:
        return None

    periods = [
        {
            "start": date(year, month, 1).isoformat(),
            "end": date(year, month, monthrange(year, month)[1]).isoformat(),
        }
        for month in requested_months
    ]
    source = body["source"]
    measure = body["metric"]["measure_column"]
    unit = body["metric"]["unit"]
    sql = (
        f"SELECT SUM({measure}) FILTER (WHERE competencia = :period_0) AS period_0_total, "
        f"SUM({measure}) FILTER (WHERE competencia = :period_1) AS period_1_total, "
        f"(SUM({measure}) FILTER (WHERE competencia = :period_0) - "
        f"SUM({measure}) FILTER (WHERE competencia = :period_1)) "
        "AS period_0_minus_period_1 "
        f"FROM {source['schema']}.{source['table']} "
        "WHERE competencia IN (:period_0, :period_1) AND municipio = :municipality"
    )
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": sql,
        "parameters": {
            "period_0": {"type": "string", "value": f"{year:04d}-{first_month:02d}"},
            "period_1": {"type": "string", "value": f"{year:04d}-{second_month:02d}"},
            "municipality": {"type": "string", "value": matches[0]},
        },
        "interpretation": {
            "metric_id": "energy.consumption",
            "operation": "comparison",
            "aggregation": "sum",
            "periods": periods,
            "filters": [{
                "dimension_id": "geography.municipality",
                "operator": "eq",
                "values": [matches[0]],
            }],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [
            {"name": name, "role": "measure", "value_type": "decimal", "unit": unit}
            for name in (
                "period_0_total", "period_1_total", "period_0_minus_period_1"
            )
        ],
    })


def _explicit_accumulated_service_candidate(request, context):
    """Build the catalog-defined unperiodized aggregate for published service rows."""
    if context.metric_ids not in {
        ("service.accumulated_attendance",),
        ("service.accumulated_satisfaction",),
    }:
        return None
    body = json.loads(context.contents)
    metric = body["metric"]
    attendance = metric["id"] == "service.accumulated_attendance"
    operation = "accumulated_total" if attendance else "accumulated_average"
    aggregation = "sum" if attendance else "average_non_null"
    alias = "attendance" if attendance else "satisfaction"
    value_type = "integer" if attendance else "decimal"
    unit = "protocolos" if attendance else "pontos"
    expression = "SUM" if attendance else "AVG"
    candidate = SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": (
            f"SELECT {expression}({metric['measure_column']}) AS {alias} "
            f"FROM {body['source']['schema']}.{body['source']['table']}"
        ),
        "parameters": {},
        "interpretation": {
            "metric_id": metric["id"],
            "operation": operation,
            "aggregation": aggregation,
            "periods": [],
            "filters": [],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [{
            "name": alias,
            "role": "measure",
            "value_type": value_type,
            "unit": unit,
        }],
    })
    return candidate


def _explicit_monthly_satisfaction_candidate(request, context):
    """Compile a covered monthly satisfaction average with UTC boundaries."""
    if context.metric_ids != ("service.satisfaction",):
        return None
    normalized = unicodedata.normalize("NFKD", request.question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    month_pattern = "|".join(
        re.escape(month) for month in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    match = re.search(
        rf"\b(?P<month>{month_pattern})\s+(?:de\s+)?(?P<year>20\d{{2}})\b",
        normalized,
    )
    if match is None:
        return None
    year = int(match.group("year"))
    month = _MONTH_NUMBERS[match.group("month")]
    period_start = date(year, month, 1)
    period_end = date(year, month, monthrange(year, month)[1])
    competency = f"{year:04d}-{month:02d}"
    covered = {
        item.metric_id: set(item.competencies) for item in request.temporal_coverage
    }
    if competency not in covered.get("service.satisfaction", set()):
        return None

    body = json.loads(context.contents)
    metric = body["metric"]
    source = body["source"]
    if not {"data_abertura", "nota_satisfacao"} <= set(source["columns"]):
        return None
    start_utc = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
    end_utc = datetime.combine(
        period_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": (
            f"SELECT AVG(nota_satisfacao) AS satisfaction "
            f"FROM {source['schema']}.{source['table']} "
            "WHERE data_abertura >= :period_start AND data_abertura < :period_end"
        ),
        "parameters": {
            "period_start": {
                "type": "timestamp", "value": start_utc.isoformat().replace("+00:00", "Z"),
            },
            "period_end": {
                "type": "timestamp", "value": end_utc.isoformat().replace("+00:00", "Z"),
            },
        },
        "interpretation": {
            "metric_id": "service.satisfaction",
            "operation": "average",
            "aggregation": "average_non_null",
            "periods": [{"start": period_start.isoformat(), "end": period_end.isoformat()}],
            "filters": [],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [{
            "name": "satisfaction",
            "role": "measure",
            "value_type": "decimal",
            "unit": metric["unit"],
        }],
    })


def _explicit_monthly_ratio_candidate(request, context):
    """Compile a covered single-month metric when explicit recuts map to Gold."""
    metric_id = context.metric_ids[0]
    if metric_id not in {
        "billing.revenue",
        "energy.consumption",
        "energy.average_consumption_per_uc",
        "billing.average_ticket",
        "billing.effective_tariff",
    }:
        return None
    body = json.loads(context.contents)
    normalized = unicodedata.normalize("NFKD", request.question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    month_pattern = "|".join(
        re.escape(month) for month in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    period_match = re.search(
        rf"\b(?P<month>{month_pattern})\s+(?:de\s+)?(?P<year>20\d{{2}})\b",
        normalized,
    )
    if period_match is None:
        return None
    year = int(period_match.group("year"))
    month = _MONTH_NUMBERS[period_match.group("month")]
    competency = f"{year:04d}-{month:02d}"
    covered = {
        item.metric_id: set(item.competencies) for item in request.temporal_coverage
    }
    if competency not in covered.get(metric_id, set()):
        return None

    normalize = lambda value: "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    source = body["source"]
    dimension_values = {
        item["dimension_id"]: item["values"] for item in body["dimension_values"]
    }
    filters: list[SqlAnalysisFilter] = []
    parameters = {"competency": {"type": "string", "value": competency}}
    predicates = ["competencia = :competency"]
    metric = body["metric"]
    normalized_question = normalize(request.question)
    explicit_values = {}
    gd_value = requested_gd_filter_value(request.question, request.context)
    for dimension_id, values in dimension_values.items():
        if dimension_id not in body["dimensions"]:
            continue
        matches = tuple(
            value for value in values
            if re.search(
                rf"(?<![\w]){re.escape(normalize(value))}(?![\w])",
                normalized_question,
            )
        )
        if dimension_id == "generation.distributed":
            if gd_value is None:
                continue
            matches = tuple(
                value for value in values if normalize(value) == normalize(gd_value)
            )
        if len(matches) > 1:
            return None
        if matches:
            explicit_values[dimension_id] = matches[0]
    if gd_value is not None and "generation.distributed" not in explicit_values:
        return None
    if any(
        cue in normalized_question and dimension_id not in explicit_values
        for dimension_id, cue in (
            ("tariff.subgroup", "subgrupo"),
            ("tariff.flag", "bandeira"),
        )
    ):
        return None
    if metric_id in {"billing.revenue", "energy.consumption"} and not (
        {"tariff.subgroup", "tariff.flag", "generation.distributed", "geography.neighborhood"}
        & explicit_values.keys()
    ):
        return None
    parameter_names = {
        "geography.municipality": "municipality",
        "geography.neighborhood": "neighborhood",
        "customer.consumption_class": "consumption_class",
        "tariff.subgroup": "tariff_subgroup",
        "tariff.flag": "tariff_flag",
        "generation.distributed": "distributed_generation",
    }
    for dimension_id, value in explicit_values.items():
        column = body["dimensions"][dimension_id]
        parameter_name = parameter_names.get(dimension_id)
        if parameter_name is None or len(filters) >= 3:
            return None
        filters.append(SqlAnalysisFilter(
            dimension_id=dimension_id, operator="eq", values=(value,),
        ))
        parameters[parameter_name] = {"type": "string", "value": value}
        predicates.append(f"{column} = :{parameter_name}")

    ratio_columns = {
        "energy.average_consumption_per_uc": (
            "consumo_total_kwh", "qtd_ucs_com_leitura",
        ),
        "billing.average_ticket": (
            "receita_total_reais", "qtd_ucs_distintas_faturadas_no_mes",
        ),
        "billing.effective_tariff": (
            "receita_base_comparavel_reais", "consumo_base_comparavel_kwh",
        ),
    }
    if metric_id in ratio_columns:
        numerator, denominator = ratio_columns[metric_id]
        if numerator not in body["source"]["columns"] or denominator not in body["source"]["columns"]:
            return None
    elif metric_id in {"billing.revenue", "energy.consumption"}:
        numerator, denominator = metric["measure_column"], None
        if numerator not in body["source"]["columns"]:
            return None
    else:
        return None
    if metric_id == "billing.revenue":
        alias, expression, operation, aggregation = (
            "revenue", f"SUM({numerator})", "total", "sum",
        )
    elif metric_id == "energy.consumption":
        alias, expression, operation, aggregation = (
            "consumption", f"SUM({numerator})", "total", "sum",
        )
    elif metric_id == "energy.average_consumption_per_uc":
        alias, expression = (
            "average_consumption_per_uc",
            f"SUM({numerator}) / NULLIF(SUM({denominator}), 0)",
        )
    elif metric_id == "billing.average_ticket":
        alias, expression = (
            "average_ticket",
            f"ROUND(SUM({numerator}) / NULLIF(SUM({denominator}), 0), 2)",
        )
    else:
        alias, expression = (
            "effective_tariff",
            f"ROUND(SUM({numerator}) / NULLIF(SUM({denominator})::numeric, 0), 4)",
        )
    if metric_id not in {"billing.revenue", "energy.consumption"}:
        operation, aggregation = "ratio_of_sums", "ratio_of_sums"
    sql = (
        f"SELECT {expression} AS {alias} FROM {source['schema']}.{source['table']} "
        f"WHERE {' AND '.join(predicates)}"
    )
    return SqlGenerationCandidate.model_validate({
        "generation_contract_version": context.generation_contract_version,
        "status": "sql_candidate",
        "context_version": context.context_version,
        "sql": sql,
        "parameters": parameters,
        "interpretation": {
            "metric_id": metric_id,
            "operation": operation,
            "aggregation": aggregation,
            "periods": [{
                "start": date(year, month, 1).isoformat(),
                "end": date(year, month, monthrange(year, month)[1]).isoformat(),
            }],
            "filters": [item.model_dump(mode="json") for item in filters],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        },
        "result_columns": [{
            "name": alias,
            "role": "measure",
                "value_type": "decimal",
            "unit": metric["unit"],
        }],
    })


def log_sql_context_ready(context, correlation_id: str) -> None:
    """Registra composição e versões do contexto, nunca conteúdo ou valores."""
    logger.info(
        "genai_sql_context outcome=ready correlation_id=%s context_version=%s "
        "context_bytes=%d mapping_version=%s dictionary_version=%s metric_ids=%s "
        "dimension_ids=%s column_names=%s coverage_months=%d dimension_value_count=%d "
        "truncation=none",
        correlation_id,
        context.context_version,
        context.context_bytes,
        context.mapping_version,
        context.dictionary_version,
        context.metric_ids,
        context.dimension_ids,
        context.column_names,
        context.coverage_months,
        context.dimension_value_count,
    )


def log_sql_context_unavailable(
    error: SqlContextUnavailable, correlation_id: str
) -> None:
    """Registra apenas motivo tipado e tamanho, sem serializar a entrada."""
    logger.warning(
        "genai_sql_context outcome=unavailable correlation_id=%s reason=%s context_bytes=%s",
        correlation_id,
        error.reason,
        error.context_bytes,
    )


@dataclass(frozen=True)
class SqlGenerationObservation:
    candidate: SqlGenerationCandidate
    review: SqlSemanticReview | None
    model_calls: int = 1


@dataclass(frozen=True)
class SqlPreparation:
    candidate: SqlGenerationCandidate
    admission: SqlAdmission | None
    model_calls: int = 1


def assert_current_sql_request_context(
    request: QuestionPlanRequest,
    *,
    resolve_scope: Callable[[], AccessScope],
    publication: GoldPublicationContext,
) -> None:
    """Binds generation to a freshly resolved session scope and publication."""
    if (
        resolve_scope() != request.access_scope
        or publication.batch_ref != request.batch_ref
    ):
        raise SqlAdmissionDenied("Contexto SQL indisponível antes da geração.")


async def observe_sql_generation(
    request: QuestionPlanRequest,
    *,
    client: GenAIQuestionClient,
    deadline: GenAIRequestDeadline,
    correlation_id: str,
) -> SqlGenerationObservation:
    """Recebe contexto resolvido e o prazo já iniciado pelo coordenador Backend.

    Uso interno opt-in; não substitui a estratégia pública. Falhas de provedor ou
    revisão são propagadas sem retry/fallback e sem converter erro em resposta.
    """
    stage_seconds = min(request.remaining_timeout_ms / 1000, 60)
    # Reduz o prazo absoluto recebido, sem renovar o saldo entre etapas.
    deadline = GenAIRequestDeadline(
        expires_at=min(deadline.expires_at, deadline.clock() + stage_seconds),
        clock=deadline.clock,
    )
    deadline.remaining_seconds(stage_seconds)
    context_started = perf_counter()
    try:
        context = build_sql_generation_context(request)
    except SqlContextUnavailable as exc:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="context",
            elapsed_ms=int((perf_counter() - context_started) * 1000),
            outcome="error",
            reason="context_unavailable",
        )
        log_sql_context_unavailable(exc, correlation_id)
        raise
    record_sql_stage(
        correlation_id=correlation_id,
        stage="context",
        elapsed_ms=int((perf_counter() - context_started) * 1000),
        outcome="success",
        context_version=context.context_version,
        mapping_version=context.mapping_version,
        dictionary_version=context.dictionary_version,
    )
    log_sql_context_ready(context, correlation_id)
    question = request.question.casefold()
    if context.metric_ids in {
        ("service.accumulated_attendance",),
        ("service.accumulated_satisfaction",),
    } and is_periodized_accumulated_attendance_question(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="accumulated_period_unavailable",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "A Gold publica o total acumulado de protocolos sem informar "
                        "o intervalo histórico; não é possível responder por mês ou ano."
                        if context.metric_ids == ("service.accumulated_attendance",)
                        else "A Gold publica a média de satisfação do histórico sem "
                        "informar o intervalo; não é possível responder por mês ou ano."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if (
        context.metric_ids == ("service.attendance",)
        and _is_annual_monthly_attendance_question(request.question)
    ):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="annual_attendance_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "Atendimento na rota F1 está disponível por competência mensal; "
                        "o total anual ainda não é suportado."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if is_explicitly_outside_energy_domain(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="outside_domain",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "metric_outside_f1",
                    "message": OUT_OF_DOMAIN_MESSAGE,
                    "reason_code": "out_of_domain",
                },
                scope_assessment={"status": "out_of_domain"},
            ),
            None,
            model_calls=0,
        )
    if _is_sensitive_personal_data_question(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="personal_data_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "A F1 não disponibiliza nomes nem dados pessoais de titulares. "
                        "Posso responder somente com métricas agregadas da Gold."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if (
        context.metric_ids in {("billing.revenue",), ("energy.consumption",)}
        and _is_unsupported_percentage_ranking_question(request.question)
    ):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="percentage_ranking_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "A F1 ainda não ordena municípios por variação percentual. "
                        "Ela pode comparar os totais e a diferença absoluta entre os períodos."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if is_explicit_multi_metric_question(request.question):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="multiple_metrics_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "Esta pergunta combina métricas independentes; a análise conjunta "
                        "ainda não está disponível nesta rota."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if (
        context.metric_ids in {
            ("customer.units_by_class",),
            ("inspection.units_by_priority",),
        }
        and _is_periodized_cadastral_snapshot_question(request.question)
    ):
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "As contagens por classe e prioridade descrevem o cadastro atual "
                        "do lote Gold e não têm série histórica por competência."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
    if (
        context.metric_ids[0] in {
            "network.equivalent_interruption_duration",
            "network.equivalent_interruption_frequency",
        }
        and _is_unsupported_dec_fec_multi_feeder_question(request.question)
    ):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="unsupported",
            reason="multi_feeder_breakdown_outside_f1",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                generation_contract_version=context.generation_contract_version,
                status="unsupported",
                context_version=context.context_version,
                unsupported_reason={
                    "code": "operation_outside_f1",
                    "message": (
                        "A F1 ainda não apresenta DEC/FEC discriminados por alimentador. "
                        "Informe um alimentador específico para consultar o indicador."
                    ),
                },
            ),
            None,
            model_calls=0,
        )

    gd_drop_candidate = _explicit_gd_consumption_drop_candidate(request, context)
    if gd_drop_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(gd_drop_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(gd_drop_candidate, reviewed, model_calls=0)

    grouped_gd_candidate = _explicit_grouped_gd_units_candidate(request, context)
    if grouped_gd_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(grouped_gd_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(grouped_gd_candidate, reviewed, model_calls=0)

    control_count_candidate = _explicit_control_count_candidate(request, context)
    if control_count_candidate is not None:
        record_sql_stage(
                correlation_id=correlation_id,
                stage="generation",
                elapsed_ms=0,
                outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(control_count_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
                correlation_id=correlation_id,
                stage="semantic_review",
                elapsed_ms=0,
                outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(control_count_candidate, reviewed, model_calls=0)
    accumulated_candidate = _explicit_accumulated_service_candidate(request, context)
    if accumulated_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(accumulated_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(accumulated_candidate, reviewed, model_calls=0)
    satisfaction_candidate = _explicit_monthly_satisfaction_candidate(request, context)
    if satisfaction_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(satisfaction_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(satisfaction_candidate, reviewed, model_calls=0)
    ratio_candidate = _explicit_monthly_ratio_candidate(request, context)
    if ratio_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(ratio_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(ratio_candidate, reviewed, model_calls=0)
    grouped_comparison_candidate = _explicit_grouped_comparison_candidate(
        request, context
    )
    if grouped_comparison_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(grouped_comparison_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            grouped_comparison_candidate, reviewed, model_calls=0
        )
    comparison_candidate = _explicit_monthly_comparison_candidate(request, context)
    if comparison_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(comparison_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(comparison_candidate, reviewed, model_calls=0)
    continuity_candidate = _explicit_weighted_continuity_candidate(request, context)
    if continuity_candidate is not None:
        record_sql_stage(
            correlation_id=correlation_id,
            stage="generation",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        try:
            reviewed = review_sql_semantics(continuity_candidate, request)
        except SqlStructureRejected:
            raise GenAIResponseInvalid from None
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="success",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            continuity_candidate, reviewed, model_calls=0
        )
    if not request.context and re.fullmatch(
        r"(?:qual\s+(?:foi\s+)?a\s+)?receita\s*[?!\.]*",
        question.strip(),
    ):
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="clarification",
            reason="ambiguous_subject",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(
            SqlGenerationCandidate(
                    generation_contract_version=context.generation_contract_version,
                status="needs_clarification",
                context_version=context.context_version,
                clarification={
                    "question": "Você quer saber a receita de energia? Para qual período?",
                    "missing_fields": ["metric", "period"],
                },
            ),
            None,
            model_calls=0,
        )
    payload = SqlGenerationRequest(
        generation_contract_version=context.generation_contract_version,
        context_version=context.context_version,
        contents=context.contents,
        remaining_timeout_ms=deadline.remaining_timeout_ms(stage_seconds),
    )
    with sql_stage(
        correlation_id, "generation", context_version=context.context_version
    ):
        response = await deadline.run(
            stage_seconds,
            lambda: client.generate_sql_candidate(
                payload, correlation_id=correlation_id
            ),
        )
    try:
        candidate = enforce_scope_decision(response.candidate)
    except ScopeDecisionRejected:
        # A decisão de escopo é entrada não confiável do modelo; falha fechada
        # antes de qualquer revisão semântica ou admissão de SQL.
        raise GenAIResponseInvalid from None
    if candidate.status != "sql_candidate":
        deadline.remaining_seconds(stage_seconds)
        record_sql_stage(
            correlation_id=correlation_id,
            stage="semantic_review",
            elapsed_ms=0,
            outcome="clarification"
            if candidate.status == "needs_clarification"
            else "unsupported",
            context_version=context.context_version,
        )
        return SqlGenerationObservation(candidate, None)
    with sql_stage(
        correlation_id, "semantic_review", context_version=context.context_version
    ):
        try:
            reviewed = review_sql_semantics(candidate, request)
        except SqlStructureRejected:
            # An invalid model proposal is a controlled provider-response failure,
            # not an unhandled Backend exception. Keep the public error generic.
            raise GenAIResponseInvalid from None
    deadline.remaining_seconds(stage_seconds)
    return SqlGenerationObservation(candidate, reviewed)


async def prepare_sql_candidate(
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
) -> SqlPreparation:
    """Compõe geração e admissão com uma única validade; sem execução ou rota pública."""
    deadline = GenAIRequestDeadline(
        min(
            deadline.expires_at, deadline.clock() + request.remaining_timeout_ms / 1000
        ),
        deadline.clock,
    )
    deadline.remaining_seconds(60)
    assert_current_sql_request_context(
        request,
        resolve_scope=resolve_scope,
        publication=publication,
    )
    await deadline.run(5, lambda: asyncio.to_thread(publication.assert_current, engine))
    observed = await observe_sql_generation(
        request, client=client, deadline=deadline, correlation_id=correlation_id
    )
    if observed.review is None:
        return SqlPreparation(
            observed.candidate, None, model_calls=observed.model_calls
        )
    with sql_stage(correlation_id, "readiness_admission"):
        admitted = await admit_sql_candidate(
            observed.candidate,
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
    return SqlPreparation(observed.candidate, admitted)
