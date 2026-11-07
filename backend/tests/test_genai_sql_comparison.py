import pytest
from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_semantics import review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected

from tests.test_genai_sql_structure import candidate
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


def comparison(request):
    payload = request.model_dump(mode="json")
    payload["temporal_coverage"][0]["competencies"] = ["2025-06", "2026-06"]
    request = QuestionPlanRequest.model_validate(payload)
    first = "SUM(receita_total_reais) FILTER(WHERE competencia = :current)"
    second = "SUM(receita_total_reais) FILTER(WHERE competencia = :previous)"
    value = candidate(request,
        f"SELECT {first} AS a, {second} AS b, ({first}) - ({second}) AS delta "
        "FROM gold_v2.diagnostico_receita "
        "WHERE competencia IN (:current, :previous) AND municipio = :city",
        parameters={key: {"type": "string", "value": val} for key, val in {
            "current": "2026-06", "previous": "2025-06", "city": "Recife"}.items()})
    payload = value.model_dump(mode="json")
    payload["result_columns"] = [{"name": name, "role": "measure", "value_type": "decimal",
                                  "unit": "R$"} for name in ("a", "b", "delta")]
    payload["interpretation"].update(operation="comparison", periods=[
        {"start": "2026-06-01", "end": "2026-06-30"},
        {"start": "2025-06-01", "end": "2025-06-30"},
    ])
    return request, type(value).model_validate(payload)


def test_derives_meaning_from_expressions_without_relying_on_aliases(sql_request):
    request, value = comparison(sql_request)
    review = review_sql_semantics(value, request)
    assert dict(review.measure_semantics) == {
        "a": "period_0_total", "b": "period_1_total", "delta": "period_0_minus_period_1"}


def test_sql_candidate_cannot_label_backend_derived_measure_as_percent(sql_request):
    request, value = comparison(sql_request)
    result_columns = list(value.result_columns)
    result_columns[0] = result_columns[0].model_copy(update={"unit": "%"})

    with pytest.raises(SqlStructureRejected, match="percentuais são derivados no Backend"):
        review_sql_semantics(value.model_copy(update={"result_columns": result_columns}), request)


def test_sql_candidate_cannot_claim_reserved_backend_derived_alias(sql_request):
    request, value = comparison(sql_request)
    payload = value.model_dump(mode="json")
    payload["sql"] = payload["sql"].replace("AS a,", "AS period_0_growth_percent,", 1)
    payload["result_columns"][0]["name"] = "period_0_growth_percent"
    candidate_with_reserved_alias = type(value).model_validate(payload)

    with pytest.raises(SqlStructureRejected, match="Alias reservado"):
        review_sql_semantics(candidate_with_reserved_alias, request)


@pytest.mark.parametrize("old,new", [
    ("(:current, :previous)", "(:current)"),
    ("WHERE competencia = :previous", "WHERE competencia = :current"),
    ("WHERE competencia = :current", "WHERE competencia IN (:current, :previous)"),
    ("WHERE competencia = :current", "WHERE competencia = :current AND municipio != :city"),
])
def test_rejects_divergent_comparison_filters(sql_request, old, new):
    request, value = comparison(sql_request)
    sql = value.sql.replace(old, new)
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(value.model_copy(update={"sql": sql}), request)


def test_rejects_reversed_difference(sql_request):
    request, value = comparison(sql_request)
    sql = value.sql
    # Swap only the subtraction operands, preserving the two total columns.
    start = sql.index(", (")
    prefix, difference = sql[:start], sql[start:]
    difference = difference.replace(":current", ":swap").replace(
        ":previous", ":current").replace(":swap", ":previous")
    # Restore the global WHERE, which is outside the arithmetic expression.
    difference = difference.replace("IN (:previous, :current)", "IN (:current, :previous)")
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(value.model_copy(update={"sql": prefix + difference}), request)


def test_accepts_equivalent_temporal_predicates(sql_request):
    request, value = comparison(sql_request)
    sql = value.sql.replace("competencia = :current",
                            "competencia BETWEEN :current AND :current").replace(
        "competencia IN (:current, :previous)",
        "(competencia = :current OR competencia = :previous)")
    assert review_sql_semantics(value.model_copy(update={"sql": sql}), request)


@pytest.mark.parametrize("suffix", [" LIMIT 1", " ORDER BY delta DESC"])
def test_comparison_cannot_rank_or_truncate_totals(sql_request, suffix):
    request, value = comparison(sql_request)
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(value.model_copy(update={"sql": value.sql + suffix}), request)


def test_comparison_checks_coverage_of_both_periods(sql_request):
    request, value = comparison(sql_request)
    payload = request.model_dump(mode="json")
    payload["temporal_coverage"][0]["competencies"] = ["2026-06"]
    narrowed = QuestionPlanRequest.model_validate(payload)
    from app.services.genai_sql_context import build_sql_generation_context

    value = value.model_copy(update={
        "context_version": build_sql_generation_context(narrowed).context_version})
    with pytest.raises(SqlStructureRejected, match="cobertura"):
        review_sql_semantics(value, narrowed)


def test_missing_second_total_is_not_complete_comparison(sql_request):
    request, value = comparison(sql_request)
    start = value.sql.index(", SUM")
    end = value.sql.index(", (", start)
    payload = value.model_dump(mode="json")
    payload["sql"] = value.sql[:start] + value.sql[end:]
    payload["result_columns"] = [item for item in payload["result_columns"] if item["name"] != "b"]
    with pytest.raises(SqlStructureRejected, match="dois totais"):
        review_sql_semantics(type(value).model_validate(payload), request)
