import pytest
from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_semantics import review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected

from tests.test_genai_sql_structure import TOTAL, candidate
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


def query(sql_request, condition="competencia = :month AND municipio = :city", **values):
    params = {"month": {"type": "string", "value": "2026-06"},
              "city": {"type": "string", "value": "Recife"}}
    for key, value in values.items():
        params[key] = {"type": "string", "value": value}
    return candidate(sql_request, TOTAL + " WHERE " + condition, parameters=params)


def consumption_request(sql_request):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Qual foi o consumo de energia em junho de 2026?"
    payload["access_scope"]["allowed_metric_ids"] = [
        "billing.revenue", "energy.consumption",
    ]
    payload["temporal_coverage"] = [{
        "metric_id": "energy.consumption", "kind": "monthly", "competencies": ["2026-06"],
    }]
    return type(sql_request).model_validate(payload)


def consumption_query(sql_request, *, unit="kWh", metric_id="energy.consumption"):
    request = consumption_request(sql_request)
    value = candidate(request, "SELECT SUM(consumo_total_kwh) AS consumption "
                      "FROM gold_v2.diagnostico_receita WHERE competencia = :month",
                      parameters={"month": {"type": "string", "value": "2026-06"}})
    payload = value.model_dump(mode="json")
    payload["generation_contract_version"] = "text-to-sql-f1-v2"
    payload["interpretation"]["metric_id"] = metric_id
    payload["interpretation"]["filters"] = []
    payload["result_columns"][0].update(name="consumption", unit=unit)
    return type(value).model_validate(payload), request


def neighborhood_revenue_query(sql_request, *, group=False):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Qual foi a receita por bairro em Recife em junho de 2026?"
    payload["access_scope"]["allowed_dimension_ids"].append("geography.neighborhood")
    payload["temporal_coverage"] = [{
        "metric_id": "billing.revenue", "kind": "monthly", "competencies": ["2026-06"],
    }]
    payload["dimension_value_coverage"].append({
        "dimension_id": "geography.neighborhood", "values": ["Boa Vista"],
    })
    request = type(sql_request).model_validate(payload)
    sql = ("SELECT bairro AS neighborhood, SUM(receita_total_reais) AS revenue "
           "FROM gold_v2.consumo_receita_bairro WHERE competencia = :month "
           "AND municipio = :city GROUP BY bairro" if group else
           "SELECT SUM(receita_total_reais) AS revenue FROM gold_v2.consumo_receita_bairro "
           "WHERE competencia = :month AND municipio = :city AND bairro = :neighborhood")
    params = {"month": {"type": "string", "value": "2026-06"},
              "city": {"type": "string", "value": "Recife"}}
    if not group:
        params["neighborhood"] = {"type": "string", "value": "Boa Vista"}
    value = candidate(request, sql, parameters=params,
                      dimensions=("neighborhood",) if group else ())
    body = value.model_dump(mode="json")
    body["interpretation"].update(
        metric_id="billing.revenue", periods=[{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=([{"dimension_id": "geography.municipality", "operator": "eq",
                   "values": ["Recife"]}] if group else [
            {"dimension_id": "geography.municipality", "operator": "eq",
             "values": ["Recife"]},
            {"dimension_id": "geography.neighborhood", "operator": "eq",
             "values": ["Boa Vista"]},
        ]),
        operation="grouped_total" if group else "total",
        group_by=["neighborhood"] if group else [],
    )
    if group:
        body["result_columns"][0]["name"] = "neighborhood"
    return type(value).model_validate(body), request


def accumulated_attendance_query(sql_request, *, sql=None):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Quantos chamados no histórico acumulado?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.accumulated_attendance"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [{
        "metric_id": "service.accumulated_attendance", "kind": "none",
    }]
    request = type(sql_request).model_validate(payload)
    value = candidate(request, sql or
        "SELECT SUM(total_chamados_callcenter) AS attendance "
        "FROM gold_v2.visao_360_uc")
    body = value.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v5"
    body["interpretation"].update(
        metric_id="service.accumulated_attendance", operation="accumulated_total",
        aggregation="sum", periods=[], filters=[], group_by=[],
        ranking_direction=None, ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": "attendance", "role": "measure", "value_type": "integer", "unit": "protocolos",
    }]
    return type(value).model_validate(body), request


def attendance_candidate(sql_request, *, periods=None, aggregation="count_non_null",
                         sql=None, values=None, unit="protocolos", metric_id="service.attendance"):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Quantos protocolos de atendimento foram abertos em junho de 2026?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.attendance"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["temporal_coverage"] = [{
        "metric_id": "service.attendance", "kind": "monthly", "competencies": ["2026-06"],
    }]
    request = type(sql_request).model_validate(payload)
    value = candidate(request,
        sql or "SELECT COUNT(protocolo) AS attendance FROM gold_v2.atendimentos_uc "
        "WHERE data_abertura >= :period_start AND data_abertura < :period_end",
        parameters=values or {
            "period_start": {"type": "timestamp", "value": "2026-06-01T00:00:00Z"},
            "period_end": {"type": "timestamp", "value": "2026-07-01T00:00:00Z"},
        })
    body = value.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v3"
    body["interpretation"].update(
        metric_id=metric_id, aggregation=aggregation, operation="total",
        periods=periods or [{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=[], group_by=[], ranking_direction=None, ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": "attendance", "role": "measure", "value_type": "integer", "unit": unit,
    }]
    return type(value).model_validate(body), request


def continuity_candidate(sql_request, metric_id="network.equivalent_interruption_duration", *,
                        sql=None, feeder="ALIM-01", period="2026-06", filters=None,
                        operation="grain_read", aggregation="key_grain_read", unit=None):
    payload = sql_request.model_dump(mode="json")
    label = "DEC" if metric_id.endswith("duration") else "FEC"
    payload["question"] = f"Qual foi o {label} do alimentador {feeder} em {period}?"
    payload["access_scope"]["allowed_metric_ids"] = [metric_id]
    payload["access_scope"]["allowed_dimension_ids"] = ["network.feeder"]
    payload["temporal_coverage"] = [{
        "metric_id": metric_id, "kind": "monthly", "competencies": [period],
    }]
    payload["dimension_value_coverage"] = [{
        "dimension_id": "network.feeder", "values": [feeder],
    }]
    request = type(sql_request).model_validate(payload)
    measure = "DEC" if metric_id.endswith("duration") else "FEC"
    value = candidate(request, sql or
        f'SELECT "{measure}" AS value FROM gold_v2.indicadores_dec_fec '
        "WHERE competencia = :month AND id_alimentador = :feeder",
        parameters={
            "month": {"type": "string", "value": period},
            "feeder": {"type": "string", "value": feeder},
        })
    body = value.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v4"
    body["interpretation"].update(
        metric_id=metric_id, operation=operation, aggregation=aggregation,
        periods=[{"start": f"{period}-01", "end": f"{period}-30"}],
        filters=filters if filters is not None else [{
            "dimension_id": "network.feeder", "operator": "eq", "values": [feeder],
        }],
        group_by=[], ranking_direction=None, ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": "value", "role": "measure", "value_type": "decimal",
        "unit": unit or ("horas por UC" if measure == "DEC" else "interrupções por UC"),
    }]
    return type(value).model_validate(body), request


def test_attendance_counts_protocols_for_one_closed_utc_month(sql_request):
    value, request = attendance_candidate(sql_request)
    review = review_sql_semantics(value, request)
    assert review.source_columns == frozenset({"data_abertura", "protocolo"})
    assert review.measure_semantics == (("attendance", "attendance_total"),)
    assert review.measure_value_type == "integer"


@pytest.mark.parametrize("group", [False, True])
def test_revenue_neighborhood_uses_approved_bairro_source_and_grain(sql_request, group):
    value, request = neighborhood_revenue_query(sql_request, group=group)
    review = review_sql_semantics(value, request)
    assert review.source_columns == frozenset({
        "competencia", "municipio", "bairro", "receita_total_reais",
    })
    assert review.measure_semantics == (("revenue", "revenue_total"),)


def test_accumulated_attendance_sums_only_the_unperiodized_published_history(sql_request):
    value, request = accumulated_attendance_query(sql_request)
    review = review_sql_semantics(value, request)
    assert review.source_columns == frozenset({"total_chamados_callcenter"})
    assert review.measure_semantics == (("attendance", "attendance_accumulated_total"),)
    assert review.measure_value_type == "integer_sum"


@pytest.mark.parametrize("sql", [
    "SELECT SUM(total_chamados_callcenter) AS attendance FROM gold_v2.visao_360_uc "
    "WHERE id_uc = :uc",
    "SELECT SUM(total_chamados_callcenter) AS attendance FROM gold_v2.visao_360_uc "
    "GROUP BY id_uc",
    "SELECT COUNT(total_chamados_callcenter) AS attendance FROM gold_v2.visao_360_uc",
])
def test_accumulated_attendance_rejects_periods_dimensions_and_alternate_formulas(
    sql_request, sql,
):
    value, request = accumulated_attendance_query(sql_request, sql=sql)
    with pytest.raises((SqlStructureRejected, ValueError)):
        review_sql_semantics(value, request)


@pytest.mark.parametrize(("metric_id", "meaning"), [
    ("network.equivalent_interruption_duration", "dec_value"),
    ("network.equivalent_interruption_frequency", "fec_value"),
])
def test_continuity_reads_one_physical_value_at_feeder_month_grain(sql_request, metric_id, meaning):
    value, request = continuity_candidate(sql_request, metric_id)
    review = review_sql_semantics(value, request)
    assert review.source_columns == frozenset({"competencia", "id_alimentador", meaning.split("_")[0].upper()})
    assert review.measure_semantics == (("value", meaning),)
    assert review.measure_value_type == "double"


def test_backend_quotes_uppercase_physical_continuity_column(sql_request):
    value, request = continuity_candidate(
        sql_request,
        sql="SELECT DEC AS value FROM gold_v2.indicadores_dec_fec "
            "WHERE competencia = :month AND id_alimentador = :feeder",
    )
    review = review_sql_semantics(value, request)
    assert 'SELECT "DEC" AS value' in review.canonical_sql


@pytest.mark.parametrize("kwargs", [
    {"sql": 'SELECT SUM("DEC") AS value FROM gold_v2.indicadores_dec_fec '
            "WHERE competencia = :month AND id_alimentador = :feeder"},
    {"sql": 'SELECT "DEC" AS value FROM gold_v2.indicadores_dec_fec '
            "WHERE competencia = :month"},
    {"filters": [{"dimension_id": "network.feeder", "operator": "in",
                  "values": ["ALIM-01", "ALIM-02"]}]},
    {"unit": "R$"},
])
def test_continuity_rejects_aggregation_or_broader_recuts(sql_request, kwargs):
    with pytest.raises((SqlStructureRejected, ValueError)):
        value, request = continuity_candidate(sql_request, **kwargs)
        review_sql_semantics(value, request)


@pytest.mark.parametrize("kwargs", [
    {"sql": "SELECT COUNT(protocolo) AS attendance FROM gold_v2.atendimentos_uc "
            "WHERE data_abertura >= :period_start AND data_abertura < :period_end "
            "GROUP BY id_uc"},
    {"sql": "SELECT SUM(protocolo) AS attendance FROM gold_v2.atendimentos_uc "
            "WHERE data_abertura >= :period_start AND data_abertura < :period_end"},
    {"unit": "R$"},
    {"aggregation": "sum"},
    {"values": {
        "period_start": {"type": "timestamp", "value": "2026-06-01T00:00:00Z"},
        "period_end": {"type": "timestamp", "value": "2026-06-30T23:59:59Z"},
    }},
])
def test_attendance_rejects_other_operations_or_non_utc_month_windows(sql_request, kwargs):
    with pytest.raises((SqlStructureRejected, ValueError)):
        value, request = attendance_candidate(sql_request, **kwargs)
        review_sql_semantics(value, request)


@pytest.mark.parametrize("condition", [
    "competencia = :month AND municipio = :city",
    "municipio = :city AND competencia BETWEEN :month AND :month",
    "competencia IN (:month) AND municipio IN (:city)",
    "(competencia >= :month AND competencia <= :month) AND municipio = :city",
])
def test_equivalent_filters_match_intent(sql_request, condition):
    assert review_sql_semantics(query(sql_request, condition), sql_request)


def test_consumption_candidate_uses_measured_kwh_instead_of_revenue(sql_request):
    value, request = consumption_query(sql_request)
    review = review_sql_semantics(value, request)
    assert review.source_columns == frozenset({"competencia", "consumo_total_kwh"})
    assert review.measure_semantics == (("consumption", "energy_total"),)
    assert review.measure_value_type == "double"


@pytest.mark.parametrize("unit,metric_id", [
    ("R$", "energy.consumption"),
    ("kWh", "billing.revenue"),
])
def test_consumption_rejects_mismatched_measure_unit_or_metric(sql_request, unit, metric_id):
    value, request = consumption_query(sql_request, unit=unit, metric_id=metric_id)
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(value, request)


def test_consumption_rejects_revenue_column_even_if_output_claims_kwh(sql_request):
    value, request = consumption_query(sql_request)
    value = value.model_copy(update={
        "sql": value.sql.replace("consumo_total_kwh", "receita_total_reais"),
    })
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(value, request)


@pytest.mark.parametrize("condition,values", [
    ("competencia = :month AND municipio = :city", {"month": "2025-06"}),
    ("competencia = :month AND municipio = :city", {"city": "Olinda"}),
    ("competencia >= :month AND municipio = :city", {}),
    ("competencia = :month OR municipio = :city", {}),
    ("competencia != :month AND municipio = :city", {}),
])
def test_rejects_wrong_or_broadened_recuts(sql_request, condition, values):
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(query(sql_request, condition, **values), sql_request)


def test_rejects_missing_time_and_dimension_filters(sql_request):
    with pytest.raises(SqlStructureRejected, match="temporal"):
        review_sql_semantics(candidate(sql_request), sql_request)
    value = candidate(sql_request, TOTAL + " WHERE competencia = :month",
                      parameters={"month": {"type": "string", "value": "2026-06"}})
    with pytest.raises(SqlStructureRejected, match="Recortes"):
        review_sql_semantics(value, sql_request)


def test_rejects_partial_year_even_if_sql_matches_declared_period(sql_request):
    value = query(sql_request)
    payload = value.model_dump(mode="json")
    payload["interpretation"]["periods"] = [{"start": "2026-01-01", "end": "2026-12-31"}]
    with pytest.raises(SqlStructureRejected, match="cobertura"):
        review_sql_semantics(type(value).model_validate(payload), sql_request)


def test_context_change_still_rejects_candidate(sql_request):
    value = query(sql_request)
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Outra pergunta"
    changed = QuestionPlanRequest.model_validate(payload)
    assert build_sql_generation_context(changed).context_version != value.context_version
    with pytest.raises(SqlStructureRejected, match="Contexto"):
        review_sql_semantics(value, changed)


def test_total_cannot_silently_limit_result(sql_request):
    value = query(sql_request)
    value = value.model_copy(update={"sql": value.sql + " LIMIT 1"})
    with pytest.raises(SqlStructureRejected, match="truncar"):
        review_sql_semantics(value, sql_request)


def ranking(sql_request, *, direction="DESC", limit=5):
    value = candidate(sql_request,
        "SELECT municipio AS city, SUM(receita_total_reais) AS revenue "
        "FROM gold_v2.diagnostico_receita WHERE competencia = :month "
        f"GROUP BY municipio ORDER BY revenue {direction} NULLS LAST LIMIT {limit}",
        parameters={"month": {"type": "string", "value": "2026-06"}}, dimensions=("city",))
    payload = value.model_dump(mode="json")
    payload["interpretation"].update(operation="ranking", filters=[], group_by=["municipality"],
                                     ranking_direction="desc", ranking_limit=5)
    return type(value).model_validate(payload)


def test_ranking_matches_group_direction_and_limit(sql_request):
    assert review_sql_semantics(ranking(sql_request), sql_request)


@pytest.mark.parametrize("direction,limit", [("ASC", 5), ("DESC", 1)])
def test_rejects_incorrect_ranking_direction_or_limit(sql_request, direction, limit):
    with pytest.raises(SqlStructureRejected, match="ranking"):
        review_sql_semantics(ranking(sql_request, direction=direction, limit=limit), sql_request)


def test_rejects_grouping_different_from_interpretation(sql_request):
    value = ranking(sql_request)
    payload = value.model_dump(mode="json")
    payload["interpretation"]["group_by"] = ["consumption_class"]
    with pytest.raises(SqlStructureRejected, match="Agrupamento"):
        review_sql_semantics(type(value).model_validate(payload), sql_request)


def test_rejects_hidden_conditional_measure(sql_request):
    value = query(sql_request)
    value = value.model_copy(update={"sql": value.sql.replace(
        "SUM(receita_total_reais)",
        "SUM(receita_total_reais) FILTER(WHERE competencia = :month)")})
    with pytest.raises(SqlStructureRejected, match="condicional"):
        review_sql_semantics(value, sql_request)


def test_ranking_does_not_promote_missing_revenue(sql_request):
    value = ranking(sql_request)
    value = value.model_copy(update={"sql": value.sql.replace("NULLS LAST", "NULLS FIRST")})
    with pytest.raises(SqlStructureRejected, match="ranking"):
        review_sql_semantics(value, sql_request)
