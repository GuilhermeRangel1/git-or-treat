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


@pytest.mark.parametrize("condition", [
    "competencia = :month AND municipio = :city",
    "municipio = :city AND competencia BETWEEN :month AND :month",
    "competencia IN (:month) AND municipio IN (:city)",
    "(competencia >= :month AND competencia <= :month) AND municipio = :city",
])
def test_equivalent_filters_match_intent(sql_request, condition):
    assert review_sql_semantics(query(sql_request, condition), sql_request)


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
