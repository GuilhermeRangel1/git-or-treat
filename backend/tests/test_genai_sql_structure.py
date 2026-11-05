"""Candidatos artificiais: nenhuma conexão ou chamada de provedor."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_parameters import SqlParameterMismatch
from app.services.genai_sql_structure import SqlStructureRejected, review_sql_structure

SOURCE = "gold_v2.diagnostico_receita"
TOTAL = f"SELECT SUM(receita_total_reais) AS revenue FROM {SOURCE}"


@pytest.fixture
def sql_request():
    return QuestionPlanRequest.model_validate({
        "question": "Qual o faturamento em junho de 2026?", "context": [],
        "remaining_timeout_ms": 30000,
        "batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
            "allowed_operations": ["read"], "allowed_metric_ids": ["billing.revenue"],
            "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class"],
        },
        "temporal_coverage": [{"metric_id": "billing.revenue", "kind": "monthly",
                               "competencies": ["2026-06"]}],
    })


def candidate(sql_request, sql=TOTAL, *, parameters=None, dimensions=()):
    path = Path(__file__).resolve().parents[2] / "docs/contracts/examples/text-to-sql-f1-v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))["valid"][0]
    payload.update(sql=sql, parameters=parameters or {},
                   context_version=build_sql_generation_context(sql_request).context_version)
    payload["result_columns"] = [
        {"name": name, "role": "dimension", "value_type": "string"} for name in dimensions
    ] + [{"name": "revenue", "role": "measure", "value_type": "decimal", "unit": "R$"}]
    return SqlGenerationCandidate.model_validate(payload)


@pytest.mark.parametrize("condition", [
    "competencia = :month", "competencia BETWEEN :month AND :month",
    "(competencia >= :month AND competencia <= :month)",
    "municipio IN (:month, :month)",
    "municipio = :month OR classe_consumo = :month",
])
def test_accepts_combinations_with_native_named_parameters(sql_request, condition):
    value = "Recife'); DROP TABLE operational_users; --"
    query = candidate(sql_request, TOTAL + " WHERE " + condition,
                      parameters={"month": {"type": "string", "value": value}})
    reviewed = review_sql_structure(query, sql_request)
    assert reviewed.parameter_items == (("month", value),)
    assert value not in reviewed.canonical_sql
    assert "%(month)s" in reviewed.canonical_sql
    assert "receita_total_reais" in reviewed.source_columns
    with pytest.raises(FrozenInstanceError):
        reviewed.canonical_sql = "DELETE FROM anything"


@pytest.mark.parametrize("dimension", ["municipio", "classe_consumo", "competencia"])
def test_accepts_grouped_rankings_and_source_aliases(sql_request, dimension):
    sql = (f'SELECT r."{dimension}" AS bucket, SUM(r.receita_total_reais) AS revenue '
           f'FROM {SOURCE} AS r GROUP BY r."{dimension}" ORDER BY revenue DESC LIMIT 5')
    reviewed = review_sql_structure(candidate(sql_request, sql, dimensions=("bucket",)), sql_request)
    assert reviewed.output_names == ("bucket", "revenue")
    assert reviewed.source_columns == frozenset({dimension, "receita_total_reais"})


def test_accepts_two_filtered_sums_and_difference(sql_request):
    sql = (f"SELECT SUM(receita_total_reais) FILTER(WHERE competencia = :a) - "
           f"SUM(receita_total_reais) FILTER(WHERE competencia = :b) AS revenue FROM {SOURCE}")
    params = {name: {"type": "string", "value": value}
              for name, value in [("a", "2026-06"), ("b", "2025-06")]}
    assert review_sql_structure(candidate(sql_request, sql, parameters=params), sql_request)


@pytest.mark.parametrize("sql", [
    "DELETE FROM gold_v2.diagnostico_receita",
    TOTAL + "; DELETE FROM gold_v2.diagnostico_receita",
    f"WITH changed AS (DELETE FROM {SOURCE} RETURNING *) {TOTAL}",
    f"WITH t AS ({TOTAL}) SELECT * FROM t",
    TOTAL + " FOR UPDATE",
    f"SELECT SUM(receita_total_reais) AS revenue INTO stolen FROM {SOURCE}",
    TOTAL.replace(SOURCE, "public.diagnostico_receita"),
    TOTAL.replace(SOURCE, "other_database.gold_v2.diagnostico_receita"),
    TOTAL.replace(SOURCE, "pg_catalog.pg_authid"),
    TOTAL.replace(SOURCE, "gold_v2.faturas_uc"),
    TOTAL.replace(SOURCE, f"{SOURCE} JOIN {SOURCE} r ON true"),
    TOTAL.replace(SOURCE, f"(SELECT * FROM {SOURCE}) r"),
    TOTAL + " UNION ALL " + TOTAL,
    TOTAL.replace("SUM(receita_total_reais)", "pg_sleep(100)"),
    TOTAL.replace("SUM(receita_total_reais)", "nextval(:sequence)"),
    TOTAL.replace("SUM(receita_total_reais)", "evil.SUM(receita_total_reais)"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(consumo_total_kwh)"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(municipio)"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(SUM(receita_total_reais))"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(receita_total_reais) OVER ()"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(DISTINCT receita_total_reais)"),
    TOTAL.replace("SUM(receita_total_reais)", "r.receita_total_reais"),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(unknown.receita_total_reais)"),
    TOTAL.replace("SUM(receita_total_reais)", 'SUM("Receita_total_reais")'),
    TOTAL.replace("SUM(receita_total_reais)", "SUM(receita_total_reais)::text"),
    TOTAL.replace(" AS revenue", ""),
    TOTAL + " WHERE municipio = 'private-value'",
    TOTAL + " WHERE 1 = 1",
    TOTAL + " HAVING SUM(receita_total_reais) > 0",
    TOTAL + " GROUP BY municipio",
    TOTAL + " GROUP BY ALL",
    TOTAL + " GROUP BY ROLLUP (municipio)",
    TOTAL.replace("SELECT ", "SELECT DISTINCT "),
    TOTAL.replace(SOURCE, SOURCE + " TABLESAMPLE SYSTEM (1)"),
    TOTAL + " ORDER BY municipio",
    TOTAL + " LIMIT 0", TOTAL + " LIMIT 101", TOTAL + " LIMIT -1",
    TOTAL + " LIMIT :count", TOTAL + " OFFSET 1", TOTAL + " -- injected comment",
    f"SELECT * FROM {SOURCE}",
    f"SELECT SUM(receita_total_reais) AS revenue FROM {SOURCE} r(fake)",
    "SELECT (",
])
def test_rejects_sql_outside_structural_subset(sql_request, sql):
    with pytest.raises(SqlStructureRejected) as exc:
        review_sql_structure(candidate(sql_request, sql), sql_request)
    assert sql not in str(exc.value)
    assert "private-value" not in str(exc.value)


@pytest.mark.parametrize("parameters", [{}, {"wrong": {"type": "string", "value": "2026-06"}},
    {"month": {"type": "string", "value": "2026-06"},
     "unused": {"type": "string", "value": "unused"}}])
def test_checks_placeholder_names_extracted_from_ast(sql_request, parameters):
    with pytest.raises(SqlParameterMismatch):
        review_sql_structure(candidate(sql_request, TOTAL + " WHERE competencia = :month",
                                       parameters=parameters), sql_request)


def test_rejects_non_string_parameter_for_textual_gold_columns(sql_request):
    with pytest.raises(SqlStructureRejected, match="string"):
        review_sql_structure(candidate(sql_request, TOTAL + " WHERE competencia = :month",
                                       parameters={"month": {"type": "integer", "value": 1}}), sql_request)


@pytest.mark.parametrize("change", ["caller", "publication", "question", "dimension"])
def test_binds_candidate_to_backend_context(sql_request, change):
    query = candidate(sql_request)
    payload = sql_request.model_dump(mode="json")
    if change == "caller":
        payload["access_scope"]["caller_ref"] = "session:" + "b" * 64
    elif change == "publication":
        payload["batch_ref"] = payload["batch_ref"].replace("12345678", "22345678")
    elif change == "question":
        payload["question"] = "Qual o faturamento de Recife?"
    else:
        payload["access_scope"]["allowed_dimension_ids"] = []
    with pytest.raises(SqlStructureRejected, match="Contexto"):
        review_sql_structure(query, QuestionPlanRequest.model_validate(payload))


def test_rejects_revoked_dimension_even_with_fresh_context(sql_request):
    payload = sql_request.model_dump(mode="json")
    payload["access_scope"]["allowed_dimension_ids"] = []
    narrowed = QuestionPlanRequest.model_validate(payload)
    query = candidate(narrowed, TOTAL + " WHERE municipio = :city",
                      parameters={"city": {"type": "string", "value": "Recife"}})
    with pytest.raises(SqlStructureRejected, match="Coluna"):
        review_sql_structure(query, narrowed)


def test_rejects_oversized_ast(sql_request):
    query = candidate(sql_request, TOTAL + " WHERE " + " OR ".join(["competencia = :m"] * 120),
                      parameters={"m": {"type": "string", "value": "2026-06"}})
    with pytest.raises(SqlStructureRejected, match="Complexidade"):
        review_sql_structure(query, sql_request)


def test_review_does_not_retain_mutable_candidate_parameters(sql_request):
    query = candidate(sql_request, TOTAL + " WHERE competencia = :month",
                      parameters={"month": {"type": "string", "value": "2026-06"}})
    reviewed = review_sql_structure(query, sql_request)
    query.parameters.clear()
    assert reviewed.parameter_items == (("month", "2026-06"),)
    with pytest.raises(SqlParameterMismatch):
        review_sql_structure(query, sql_request)


def test_parser_fallback_does_not_log_untrusted_query_content(sql_request, caplog):
    with pytest.raises(SqlStructureRejected):
        review_sql_structure(candidate(sql_request, "VACUUM private_untrusted_marker"), sql_request)
    assert "private_untrusted_marker" not in caplog.text
