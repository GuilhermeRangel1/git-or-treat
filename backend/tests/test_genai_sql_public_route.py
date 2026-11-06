import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.genai_gold_database import get_question_gold_resources
from app.models.gold_v2 import TABLES
from app.schemas.genai_internal import AccessScope
from app.schemas.gold_readiness import GoldReadinessReport
from app.schemas.sql_generation import SqlGenerationResponse
from tests.support.platform_auth import login_as_profile
from tests.test_genai_sql_structure import candidate as make_candidate


def test_sql_analysis_route_requires_individual_ai_permission(client):
    response = client.post("/api/v1/ai/sql-analyses", json={"question": "faturamento"})
    assert response.status_code == 401


def test_sql_analysis_route_is_disabled_by_default_for_authenticated_user(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial", username="sql-route-disabled")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", False)
    response = client.post("/api/v1/ai/sql-analyses", json={"question": "faturamento"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Análise SQL indisponível."


def test_public_sql_analysis_response_schema_does_not_expose_candidate_sql():
    from app.schemas.sql_analysis import SqlAnalysisResponse

    schema = SqlAnalysisResponse.model_json_schema()
    assert "sql" not in schema["properties"]
    assert "parameters" not in schema["properties"]


class BenchmarkCandidateClient:
    """Candidatos fixos exercitam a rota; não simulam uma chamada Gemini."""

    def __init__(self, reference_cases):
        self.reference_cases = reference_cases

    async def generate_sql_candidate(self, payload, *, correlation_id):
        context = json.loads(payload.contents)
        question = context["question"]
        case = next(item for item in self.reference_cases if item["question"] == question)
        coverage = context["temporal_coverage"]["competencies"]
        request = _candidate_request(question, context, coverage)
        candidate = _benchmark_candidate(case["id"], request)
        candidate = candidate.model_copy(update={"context_version": payload.context_version})
        return SqlGenerationResponse(correlation_id=correlation_id, candidate=candidate)

    async def evaluate_readiness(self, engine, **kwargs):
        return GoldReadinessReport.model_validate({
            "readiness_version": "gold-readiness-v2", "batch_ref": kwargs["expected_batch_ref"],
            "lot_state": "ready", "capabilities": {
                "faturamento.receita": {"status": "available"}},
        })


def _candidate_request(question, context, coverage):
    from app.schemas.genai_internal import QuestionPlanRequest

    return QuestionPlanRequest.model_validate({
        "question": question, "context": context["context"], "remaining_timeout_ms": 60000,
        "batch_ref": context["publication"],
        "access_scope": {
            "caller_ref": "session:" + "a" * 64, "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local", "allowed_operations": ["read"],
            "allowed_metric_ids": ["billing.revenue"],
            "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class"],
        },
        "temporal_coverage": [{"metric_id": "billing.revenue", "kind": "monthly",
                               "competencies": coverage}],
        "dimension_value_coverage": context["dimension_values"],
    })


def _benchmark_candidate(case_id, request):
    """Um candidato conhecido por oráculo, para medir rota/SQL sem Gemini."""
    periods = {
        "F1-01": (("2026-06", "2026-06"),),
        "F1-03": (("2026-01", "2026-06"),),
        "F1-04": (("2026-01", "2026-06"), ("2025-01", "2025-06")),
        "F1-05": (("2026-01", "2026-06"),),
        "F1-06": (("2026-01", "2026-06"),),
        "F1-07": (("2026-06", "2026-06"),),
        "F1-08": (("2026-06", "2026-06"),),
    }
    if case_id == "F1-02":
        from app.schemas.sql_generation import SqlGenerationCandidate
        from app.services.genai_sql_context import build_sql_generation_context

        return SqlGenerationCandidate.model_validate({
            "generation_contract_version": "text-to-sql-f1-v1", "status": "needs_clarification",
            "context_version": build_sql_generation_context(request).context_version,
            "clarification": {"question": "Você quer apenas janeiro a junho de 2026?",
                              "missing_fields": ["period"]},
        })

    windows = periods[case_id]
    params = {}
    dimensions = ()
    if case_id in ("F1-01", "F1-03", "F1-04", "F1-05", "F1-07", "F1-08"):
        params["municipality"] = {"type": "string", "value": "Recife"}
    for index, (start, end) in enumerate(windows):
        params[f"start_{index}"] = {"type": "string", "value": start}
        params[f"end_{index}"] = {"type": "string", "value": end}
    select = "SELECT SUM(receita_total_reais) AS revenue"
    where = []
    operation = "total"
    group_by = []
    if case_id == "F1-04":
        operation = "comparison"
        select = ("SELECT SUM(receita_total_reais) FILTER (WHERE competencia BETWEEN :start_0 AND :end_0) AS current_total, "
                  "SUM(receita_total_reais) FILTER (WHERE competencia BETWEEN :start_1 AND :end_1) AS previous_total, "
                  "SUM(receita_total_reais) FILTER (WHERE competencia BETWEEN :start_0 AND :end_0) - "
                  "SUM(receita_total_reais) FILTER (WHERE competencia BETWEEN :start_1 AND :end_1) AS difference")
        # Use distinct placeholders for the two filtered sums and global predicate.
        params = {"current_start": {"type": "string", "value": "2026-01"},
                  "current_end": {"type": "string", "value": "2026-06"},
                  "previous_start": {"type": "string", "value": "2025-01"},
                  "previous_end": {"type": "string", "value": "2025-06"},
                  "municipality": {"type": "string", "value": "Recife"}}
        select = select.replace(":start_0", ":current_start").replace(":end_0", ":current_end")
        select = select.replace(":start_1", ":previous_start").replace(":end_1", ":previous_end")
        where = ["(competencia BETWEEN :previous_start AND :previous_end OR "
                 + "competencia BETWEEN :current_start AND :current_end)"]
        result_columns = ("current_total", "previous_total", "difference")
    else:
        where.append("competencia BETWEEN :start_0 AND :end_0")
        if case_id == "F1-05":
            operation, group_by = "monthly_series", ["competency"]
            select = "SELECT competencia AS competency, SUM(receita_total_reais) AS revenue"
            dimensions = ("competency",)
        elif case_id == "F1-06":
            operation, group_by = "ranking", ["municipality"]
            select = "SELECT municipio AS municipality, SUM(receita_total_reais) AS revenue"
            dimensions = ("municipality",)
        elif case_id == "F1-07":
            operation, group_by = "grouped_total", ["consumption_class"]
            select = "SELECT classe_consumo AS consumption_class, SUM(receita_total_reais) AS revenue"
            dimensions = ("consumption_class",)
    if "municipality" in params:
        where.append("municipio = :municipality")
    sql = select + " FROM gold_v2.diagnostico_receita WHERE " + " AND ".join(where)
    if group_by == ["competency"]:
        sql += " GROUP BY competencia ORDER BY competencia"
    elif group_by == ["municipality"]:
        sql += " GROUP BY municipio ORDER BY revenue DESC NULLS LAST LIMIT 5"
    elif group_by == ["consumption_class"]:
        sql += " GROUP BY classe_consumo ORDER BY classe_consumo"

    value = make_candidate(request, sql, parameters=params, dimensions=dimensions)
    data = value.model_dump(mode="json")
    column_names = result_columns if case_id == "F1-04" else (
        ("competency", "revenue") if case_id == "F1-05" else
        ("municipality", "revenue") if case_id == "F1-06" else
        ("consumption_class", "revenue") if case_id == "F1-07" else ("revenue",))
    data["result_columns"] = [
        {"name": name, "role": "dimension", "value_type": "string"}
        if name in dimensions else
        {"name": name, "role": "measure", "value_type": "decimal", "unit": "R$"}
        for name in column_names
    ]
    data["interpretation"].update(
        operation=operation,
        periods=[{"start": start + "-01", "end": start + "-01" if start == end else end + "-01"}
                 for start, end in windows],
        group_by=group_by,
        filters=([{"dimension_id": "geography.municipality", "operator": "eq",
                   "values": ["Recife"]}] if "municipality" in params else []),
        ranking_direction="desc" if operation == "ranking" else None,
        ranking_limit=5 if operation == "ranking" else None,
    )
    for period in data["interpretation"]["periods"]:
        from calendar import monthrange
        year, month = map(int, period["end"].split("-")[:2])
        period["end"] = f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"
    return type(value).model_validate(data)


def test_authenticated_route_executes_postgres_and_returns_reconciled_evidence(
    client, monkeypatch,
):
    address = os.getenv("TEST_TEXT_TO_SQL_URL")
    if not address:
        pytest.skip("Configure PostgreSQL descartável em TEST_TEXT_TO_SQL_URL.")
    owner_url = make_url(address)
    assert owner_url.database == "text_to_sql_f1_test"
    owner = create_engine(owner_url)
    with owner.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold_v2 CASCADE")
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold CASCADE")
        connection.exec_driver_sql("DROP ROLE IF EXISTS venergy_genai_reader")
        connection.exec_driver_sql("CREATE SCHEMA gold")
        connection.exec_driver_sql("CREATE SCHEMA gold_v2")
        connection.exec_driver_sql("CREATE TABLE gold.publicacao_atual (schema_version text, lote text, publication_id text)")
        connection.exec_driver_sql("INSERT INTO gold.publicacao_atual VALUES ('gold-csv-v2', 'GOLD_20000101T000000Z_aaaaaaaa', '12345678-1234-4123-8123-123456789abc')")
        TABLES["diagnostico_receita"].create(connection)
        TABLES["consumo_receita_bairro"].create(connection)
        TABLES["consumo_mensal_uc"].create(connection)
        fixture_path = Path(__file__).resolve().parents[2] / "ai-agent/tests/fixtures/text_to_sql_f1_reference.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        synthetic_rows = [{
            "competencia": row["competencia"], "municipio": row["municipio"],
            "classe_consumo": row["classe_consumo"], "subgrupo_tarifario": "FIXTURE",
            "bandeira_tarifaria": row["bandeira_tarifaria"], "possui_gd": "NAO",
            "receita_total_reais": row["receita_total_reais"],
        } for row in fixture["rows"]]
        connection.execute(TABLES["diagnostico_receita"].insert(), synthetic_rows)
        connection.exec_driver_sql("CREATE ROLE venergy_genai_reader LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'synthetic-test-only'")
        connection.exec_driver_sql("GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader")
        connection.exec_driver_sql("GRANT SELECT ON gold.publicacao_atual, gold_v2.diagnostico_receita, gold_v2.consumo_receita_bairro, gold_v2.consumo_mensal_uc TO venergy_genai_reader")
    reader = create_engine(owner_url.set(username="venergy_genai_reader", password="synthetic-test-only"),
                           hide_parameters=True, echo=False, pool_size=1, max_overflow=0)
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64, "profile_id": "v-energy-grid-360-gold",
        "source_id": "gold.local", "allowed_operations": ["read"],
        "allowed_metric_ids": ["billing.revenue"],
        "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class"],
    })
    app = client.app
    overrides = app.dependency_overrides
    app.dependency_overrides[get_question_gold_resources] = lambda: (reader, lambda: scope)
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    app.state.genai_question_client = BenchmarkCandidateClient(fixture["cases"])
    login_as_profile(client, monkeypatch, "commercial", username="sql-route-integration")
    try:
        strict_client = TestClient(app, raise_server_exceptions=True)
        strict_client.cookies.update(client.cookies)
        strict_client.headers.update(client.headers)
        for case in fixture["cases"]:
            context = ([{"role": "user", "content": "Qual foi o faturamento de Recife em junho de 2026?"}]
                       if case.get("context") else [])
            response = strict_client.post("/api/v1/ai/sql-analyses", json={
                "question": case["question"], "context": context})
            assert response.status_code == 200, f"{case['id']}: {response.text}"
            body = response.json()
            if case["expected_status"] == "needs_clarification":
                assert body["status"] == "needs_clarification", case["id"]
                assert body["evidence"] is None, case["id"]
                assert body["clarification"]["missing_fields"] == ["period"], case["id"]
                continue

            assert body["status"] == "answered", case["id"]
            assert "sql" not in body and "parameters" not in body["evidence"]
            with owner.connect() as control:
                oracle = control.execute(text(case["reference_sql"]), case["parameters"]).mappings().all()
            if case["id"] == "F1-04":
                by_year = {row["year"]: row["revenue"] for row in oracle}
                expected = [[format(by_year["2026"], ".2f"), format(by_year["2025"], ".2f"),
                             case["expected_difference_reais"]]]
            else:
                expected = [[format(value, ".2f") if value is not None and not isinstance(value, str)
                             else value for value in row.values()] for row in oracle]
            assert body["evidence"]["rows"] == expected, case["id"]
    finally:
        app.dependency_overrides = overrides
        reader.dispose()
        owner.dispose()
