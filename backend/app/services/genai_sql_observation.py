"""Geração e revisão F1 em observação; não chama executor nem concede prontidão."""

import asyncio
import json
import logging
import re
import unicodedata
from calendar import monthrange
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
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
    is_periodized_accumulated_attendance_question,
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
                "alta historico irregular", "alta por historico irregular",
            ),
            "ALTA - CONSUMO ZERO": (
                "alta consumo zero", "alta por consumo zero", "consumo zero",
            ),
            "BAIXA": ("baixa", "baixa prioridade"),
            "MEDIA - NUNCA INSPECIONADO": (
                "media nunca inspecionado", "media por nunca inspecionado",
            ),
            "REVISAR - SEM HISTORICO DE CONSUMO": (
                "revisar sem historico de consumo",
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
        bool(re.search(r"\b(?:por|cada|distribuicao|distribuidos|distribuidas)\b", question))
        or "classe de consumo" in question
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


def _is_periodized_cadastral_snapshot_question(question: str) -> bool:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return bool(re.search(
        r"\b(?:20\d{2}|jan(?:eiro)?|fev(?:ereiro)?|mar(?:co)?|abr(?:il)?|"
        r"mai(?:o)?|jun(?:ho)?|jul(?:ho)?|ago(?:sto)?|set(?:embro)?|"
        r"out(?:ubro)?|nov(?:embro)?|dez(?:embro)?|periodo|mensal(?:mente)?|"
        r"competencia|ultimos?|desde|entre)\b",
        normalized,
    ))


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
                    "code": "period_not_supported",
                    "message": (
                        "As contagens por classe e prioridade descrevem o cadastro atual "
                        "do lote Gold e não têm série histórica por competência."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
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
                        "Esta pergunta combina consumo medido e faturamento; "
                        "a análise conjunta ainda não está disponível."
                    ),
                },
            ),
            None,
            model_calls=0,
        )
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
