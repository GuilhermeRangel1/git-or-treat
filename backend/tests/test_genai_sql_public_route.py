import json
import logging
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.genai_gold_database import get_question_gold_resources
from app.models.gold_v2 import TABLES
from app.schemas.genai_internal import AccessScope
from app.schemas.gold_readiness import GoldReadinessReport
from app.schemas.sql_generation import SqlGenerationResponse
from app.services.genai_audit import AuditStore
from tests.support.database import test_engine
from tests.support.platform_auth import login_as_profile
from tests.test_genai_sql_structure import candidate as make_candidate


def test_sql_analysis_route_requires_individual_ai_permission(client):
    response = client.post("/api/v1/ai/sql-analyses", json={"question": "faturamento"})
    assert response.status_code == 401


def test_sql_analysis_route_is_disabled_by_default_for_authenticated_user(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial", username="sql-route-disabled")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", False)
    response = client.post("/api/v1/ai/sql-analyses", json={"question": "faturamento"})
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Análise SQL indisponível."


def test_customer_service_public_route_recognizes_satisfaction_contract(client, monkeypatch):
    from app.api.v1.endpoints import ai as endpoint

    batch = (
        "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
        "12345678-1234-4123-8123-123456789abc"
    )
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["service.attendance", "service.satisfaction"],
        "allowed_dimension_ids": [],
    })

    class Publication:
        batch_ref = batch

        def planning_fields(self, _engine, _scope):
            return {
                "batch_ref": batch,
                "temporal_coverage": [{
                    "metric_id": "service.satisfaction", "kind": "monthly",
                    "competencies": ["2026-06"],
                }],
            }

        def assert_current(self, _engine):
            return None

    generated = []

    class Generator:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            body = json.loads(payload.contents)
            generated.append(body)
            assert body["metric"]["id"] == "service.satisfaction"
            assert payload.generation_contract_version == "text-to-sql-f1-v7"
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version="text-to-sql-f1-v7",
                candidate={
                    "generation_contract_version": "text-to-sql-f1-v7",
                    "context_version": payload.context_version,
                    "status": "unsupported",
                    "scope_assessment": {"status": "in_domain"},
                    "semantic_intent": {"metric_id": "service.satisfaction"},
                    "unsupported_reason": {
                        "code": "operation_outside_f1",
                        "message": "A solicitação não corresponde à consulta mensal disponível.",
                    },
                },
            )

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(endpoint.GoldPublicationContext, "capture",
                        classmethod(lambda _cls, _engine: Publication()))
    monkeypatch.setattr(endpoint.AuditStore, "record",
                        lambda _self, _event, **_kwargs: "a" * 32)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (test_engine, lambda: scope),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        endpoint.get_sql_genai_question_client,
        Generator,
    )
    login_as_profile(client, monkeypatch, "customer_service", username="sql-satisfaction-route")

    response = client.post("/api/v1/ai/sql-analyses", json={
        "question": "Qual foi a nota média de satisfação em junho de 2026?",
    })

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unsupported"
    assert generated and generated[0]["generation_contract_version"] == "text-to-sql-f1-v7"


def test_customer_service_public_route_recognizes_accumulated_satisfaction(client, monkeypatch):
    from app.api.v1.endpoints import ai as endpoint

    batch = (
        "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
        "12345678-1234-4123-8123-123456789abc"
    )
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["service.accumulated_satisfaction"],
        "allowed_dimension_ids": [],
    })

    class Publication:
        batch_ref = batch

        def planning_fields(self, _engine, _scope):
            return {
                "batch_ref": batch,
                "temporal_coverage": [{
                    "metric_id": "service.accumulated_satisfaction", "kind": "none",
                }],
            }

        def assert_current(self, _engine):
            return None

    generated = []

    class Generator:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            body = json.loads(payload.contents)
            generated.append(body)
            assert body["metric"]["id"] == "service.accumulated_satisfaction"
            assert body["generation_contract_version"] == "text-to-sql-f1-v9"
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version="text-to-sql-f1-v9",
                candidate={
                    "generation_contract_version": "text-to-sql-f1-v9",
                    "context_version": payload.context_version,
                    "status": "unsupported",
                    "scope_assessment": {"status": "in_domain"},
                    "semantic_intent": {
                        "metric_id": "service.accumulated_satisfaction",
                    },
                    "unsupported_reason": {
                        "code": "operation_outside_f1",
                        "message": "A solicitação não corresponde à média histórica disponível.",
                    },
                },
            )

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(endpoint.GoldPublicationContext, "capture",
                        classmethod(lambda _cls, _engine: Publication()))
    monkeypatch.setattr(endpoint.AuditStore, "record",
                        lambda _self, _event, **_kwargs: "a" * 32)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (test_engine, lambda: scope),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        endpoint.get_sql_genai_question_client,
        Generator,
    )
    login_as_profile(client, monkeypatch, "customer_service",
                     username="sql-accumulated-satisfaction-route")

    response = client.post("/api/v1/ai/sql-analyses", json={
        "question": "Qual foi a média acumulada das notas de satisfação?",
    })

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unsupported"
    assert generated and generated[0]["generation_contract_version"] == "text-to-sql-f1-v9"


def test_commercial_public_route_recognizes_gd_registry_snapshot(client, monkeypatch):
    from app.api.v1.endpoints import ai as endpoint

    batch = (
        "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
        "12345678-1234-4123-8123-123456789abc"
    )
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"], "allowed_metric_ids": ["energy.gd_units"],
        "allowed_dimension_ids": ["geography.municipality", "generation.distributed"],
    })

    class Publication:
        batch_ref = batch

        def planning_fields(self, _engine, _scope):
            return {
                "batch_ref": batch,
                "temporal_coverage": [{"metric_id": "energy.gd_units", "kind": "none"}],
                "dimension_value_coverage": [{
                    "dimension_id": "generation.distributed", "values": ["Não", "Sim"],
                }],
            }

        def assert_current(self, _engine):
            return None

    generated = []

    class Generator:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            body = json.loads(payload.contents)
            generated.append(body)
            assert body["metric"]["id"] == "energy.gd_units"
            assert body["source"]["table"] == "variacao_consumo_uc"
            assert body["generation_contract_version"] == "text-to-sql-f1-v8"
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version="text-to-sql-f1-v8",
                candidate={
                    "generation_contract_version": "text-to-sql-f1-v8",
                    "context_version": payload.context_version,
                    "status": "unsupported",
                    "scope_assessment": {"status": "in_domain"},
                    "semantic_intent": {"metric_id": "energy.gd_units"},
                    "unsupported_reason": {
                        "code": "operation_outside_f1",
                        "message": "Esta execução de rota verifica apenas o contrato de contexto.",
                    },
                },
            )

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(endpoint.GoldPublicationContext, "capture",
                        classmethod(lambda _cls, _engine: Publication()))
    monkeypatch.setattr(endpoint.AuditStore, "record",
                        lambda _self, _event, **_kwargs: "a" * 32)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (test_engine, lambda: scope),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        endpoint.get_sql_genai_question_client,
        Generator,
    )
    login_as_profile(client, monkeypatch, "commercial", username="sql-gd-units-route")

    response = client.post("/api/v1/ai/sql-analyses", json={
        "question": "Quantas UCs têm GD?",
    })

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unsupported"
    assert generated and generated[0]["metric"]["id"] == "energy.gd_units"


def test_sql_analysis_readiness_denial_returns_sanitized_http_error(
    client, monkeypatch, caplog,
):
    import logging
    from uuid import uuid4

    from app.api.v1.endpoints import ai as ai_endpoint
    from app.schemas.genai_internal import AccessScope
    from app.services.genai_sql_admission import SqlAdmissionDenied

    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold",
        "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["billing.revenue"],
        "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class"],
    })
    batch_ref = (
        "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
        "12345678-1234-4123-8123-123456789abc"
    )

    class Publication:
        def __init__(self):
            self.batch_ref = batch_ref

        def planning_fields(self, _engine, _scope):
            return {
                "batch_ref": self.batch_ref,
                "temporal_coverage": [{
                    "metric_id": "billing.revenue", "kind": "monthly",
                    "competencies": ["2026-06"],
                }],
            }

    async def reject_for_readiness(*_args, **_kwargs):
        raise SqlAdmissionDenied("private readiness detail")

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(
        ai_endpoint.GoldPublicationContext, "capture",
        classmethod(lambda _cls, _engine: Publication()),
    )
    monkeypatch.setattr(ai_endpoint, "run_sql_question", reject_for_readiness)
    monkeypatch.setattr(
        ai_endpoint.AuditStore, "record",
        lambda _self, _event, *, service="genai", now=None: "synthetic-audit-reference",
    )
    client.app.dependency_overrides[ai_endpoint.get_question_gold_resources] = (
        lambda: (test_engine, lambda: scope)
    )
    login_as_profile(client, monkeypatch, "commercial", username=f"sql-readiness-{uuid4().hex[:8]}")
    strict_client = TestClient(client.app, raise_server_exceptions=True)
    strict_client.cookies.update(client.cookies)
    strict_client.headers.update(client.headers)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={"question": "pergunta privada e faturamento"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "A análise dos dados está temporariamente indisponível."
    assert "private readiness detail" not in caplog.text
    assert "pergunta privada" not in caplog.text
    events = [
        json.loads(record.getMessage().removeprefix("genai_execution "))
        for record in caplog.records
        if record.getMessage().startswith("genai_execution {")
    ]
    assert any(event.get("stage") == "http" and event.get("http_status") == 503 for event in events)


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
            "scope_assessment": {"status": "in_domain"},
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


@pytest.mark.skipif(
    not os.getenv("TEST_TEXT_TO_SQL_URL"),
    reason="Configure PostgreSQL descartável em TEST_TEXT_TO_SQL_URL.",
)
def test_authenticated_route_executes_postgres_and_returns_reconciled_evidence(
    client, monkeypatch, caplog,
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
    pressure_reader = create_engine(
        owner_url.set(username="venergy_genai_reader", password="synthetic-test-only"),
        hide_parameters=True, echo=False, pool_size=1, max_overflow=0, pool_timeout=0.2,
    )
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
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    trace_correlation_id = None
    try:
        strict_client = TestClient(app, raise_server_exceptions=True)
        strict_client.cookies.update(client.cookies)
        strict_client.headers.update(client.headers)
        for case in fixture["cases"]:
            # Cada caso verifica a rota sem contexto de conversa. Follow-up real
            # exige token emitido pelo Backend e é coberto pelo teste de conversa.
            context = []
            response = strict_client.post("/api/v1/ai/sql-analyses", json={
                "question": case["question"], "context": context})
            assert response.status_code == 200, f"{case['id']}: {response.text}"
            body = response.json()
            if trace_correlation_id is None:
                trace_correlation_id = body["correlation_id"]
            assert re.fullmatch(r"[a-f0-9]{32}", body["audit_reference"])
            audit_events = AuditStore(test_engine).read_reference(body["audit_reference"])
            assert audit_events
            response_event = next(
                item for item in audit_events if item["event"]["stage"] == "response"
            )
            assert response_event["event"]["outcome"] in {"success", "refused"}
            assert not any(
                key in response_event["event"]
                for key in ("question", "sql", "parameters", "filters")
            )
            if case["expected_status"] == "needs_clarification":
                assert body["status"] == "needs_clarification", case["id"]
                assert audit_events[-1]["event"].get("sql_f1_artifact") is None
                assert body["evidence"] is None, case["id"]
                assert body["presentation"] is None, case["id"]
                assert body["unsupported_reason"] is None, case["id"]
                assert body["clarification"]["missing_fields"] == ["period"], case["id"]
                continue

            assert body["status"] == "answered", case["id"]
            sql_artifact = audit_events[-1]["event"]["sql_f1_artifact"]
            assert sql_artifact["artifact_version"] == "text-to-sql-f1-audit-v1"
            assert sql_artifact["contract_version"] == "text-to-sql-f1-v1"
            assert sql_artifact["canonical_sql_template"]
            assert re.fullmatch(r"[a-f0-9]{64}", sql_artifact["template_digest"])
            assert re.fullmatch(r"[a-f0-9]{64}", sql_artifact["candidate_digest"])
            assert re.fullmatch(r"[a-f0-9]{64}", sql_artifact["admission_digest"])
            assert re.fullmatch(r"[a-f0-9]{64}", sql_artifact["execution_digest"])
            assert re.fullmatch(r"[a-f0-9]{64}", sql_artifact["result_digest"])
            assert "Recife" not in json.dumps(sql_artifact)
            assert "sql" not in body and "parameters" not in body["evidence"]
            presentation = body["presentation"]
            assert presentation["evidence_digest"] == body["evidence"]["evidence_digest"]
            assert [row["cells"] for row in presentation["rows"]] == body["evidence"]["rows"]
            assert [column["key"] for column in presentation["columns"]] == [
                column["name"] for column in body["evidence"]["columns"]
            ]
            assert presentation["period"]
            assert presentation["answer"]
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


        if os.getenv("TEST_TEXT_TO_SQL_LOAD") == "1":
            from concurrent.futures import ThreadPoolExecutor
            from math import ceil
            from time import perf_counter

            question = fixture["cases"][0]["question"]
            payload = {"question": question, "context": []}
            baseline = strict_client.post("/api/v1/ai/sql-analyses", json=payload)
            assert baseline.status_code == 200
            expected_rows = baseline.json()["evidence"]["rows"]

            def request_under_load(_):
                started = perf_counter()
                result = strict_client.post("/api/v1/ai/sql-analyses", json=payload)
                elapsed_ms = (perf_counter() - started) * 1000
                assert result.status_code == 200
                assert result.json()["evidence"]["rows"] == expected_rows
                return elapsed_ms

            for concurrency in (1, 4, 8):
                started = perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency) as workers:
                    durations = sorted(workers.map(request_under_load, range(40)))
                elapsed = perf_counter() - started
                print(
                    f"F1_LOAD concurrency={concurrency} requests={len(durations)} "
                    f"p50_ms={durations[ceil(len(durations) * .50) - 1]:.1f} "
                    f"p95_ms={durations[ceil(len(durations) * .95) - 1]:.1f} "
                    f"requests_per_second={len(durations) / elapsed:.2f}"
                )

        app.dependency_overrides[get_question_gold_resources] = (
            lambda: (pressure_reader, lambda: scope)
        )
        with pressure_reader.connect():
            pool_failure = strict_client.post(
                "/api/v1/ai/sql-analyses",
                json={"question": fixture["cases"][0]["question"], "context": []},
            )
        assert pool_failure.status_code == 503
        assert "timeout" not in pool_failure.text.lower()
        pool_correlation = pool_failure.headers["X-Correlation-ID"]
        pool_events = [
            json.loads(record.getMessage().removeprefix("genai_execution "))
            for record in caplog.records
            if record.getMessage().startswith("genai_execution {")
        ]
        assert any(
            event.get("correlation_id") == pool_correlation
            and event.get("stage") == "publication"
            and event.get("reason") == "database_error"
            for event in pool_events
        )

        app.dependency_overrides[get_question_gold_resources] = lambda: (reader, lambda: scope)
        recovered = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={"question": fixture["cases"][0]["question"], "context": []},
        )
        assert recovered.status_code == 200

        trace_events = [
            json.loads(record.getMessage().removeprefix("genai_execution "))
            for record in caplog.records
            if record.getMessage().startswith("genai_execution {")
        ]
        correlated = [
            event for event in trace_events
            if event.get("correlation_id") == trace_correlation_id
        ]
        assert {
            "context", "generation", "semantic_review", "readiness_admission",
            "admission_revalidation", "sql_execution", "materialization", "evidence",
            "presentation", "http",
        } <= {event["stage"] for event in correlated}
        assert all(event["strategy"] == "text_to_sql_f1" for event in correlated)
        assert all(
            event["contract_version"] == (
                "text-to-sql-f1-presentation-v1"
                if event["stage"] in {"presentation", "http"}
                else "text-to-sql-f1-v1"
            )
            for event in correlated
        )
        assert not any(
            key in event for event in correlated
            for key in ("question", "sql", "parameters", "filters", "exception")
        )

        original_client = app.state.genai_question_client

        class EmptyResultClient(BenchmarkCandidateClient):
            async def generate_sql_candidate(self, payload, *, correlation_id):
                context = json.loads(payload.contents)
                request = _candidate_request(
                    context["question"],
                    context,
                    context["temporal_coverage"]["competencies"],
                )
                candidate = _benchmark_candidate("F1-07", request)
                data = candidate.model_dump(mode="json")
                data["parameters"]["municipality"]["value"] = "Cidade apenas janeiro"
                data["interpretation"]["filters"][0]["values"] = [
                    "Cidade apenas janeiro"
                ]
                result = type(candidate).model_validate(data)
                return SqlGenerationResponse(
                    correlation_id=correlation_id, candidate=result
                )

        with owner.begin() as connection:
            connection.execute(
                TABLES["diagnostico_receita"].insert(),
                {
                    "competencia": "2026-01",
                    "municipio": "Cidade apenas janeiro",
                    "classe_consumo": "RESIDENCIAL",
                    "subgrupo_tarifario": "FIXTURE",
                    "bandeira_tarifaria": "BASE",
                    "possui_gd": "NAO",
                    "receita_total_reais": 0.01,
                },
            )
        app.state.genai_question_client = EmptyResultClient(fixture["cases"])
        empty_response = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={
                "question": "Qual foi o faturamento de Cidade apenas janeiro em junho de 2026?",
                "context": [],
            },
        )
        assert empty_response.status_code == 200, empty_response.text
        empty_body = empty_response.json()
        assert empty_body["status"] == "answered"
        assert empty_body["evidence"]["status"] == "empty"
        assert empty_body["evidence"]["rows"] == []
        assert empty_body["presentation"]["state"] == "empty"
        assert "Não há linhas" in empty_body["presentation"]["answer"]
        app.state.genai_question_client = original_client

        from app.services.genai_client import GenAIServiceUnavailable

        class UnavailableClient:
            async def generate_sql_candidate(self, _payload, *, correlation_id):
                raise GenAIServiceUnavailable(retryable=True)

        app.state.genai_question_client = UnavailableClient()
        unavailable = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={"question": fixture["cases"][0]["question"], "context": []},
        )
        assert unavailable.status_code == 503
        assert "evidence" not in unavailable.json()
        assert "presentation" not in unavailable.json()
        app.state.genai_question_client = original_client

        class ChangingPublicationClient(BenchmarkCandidateClient):
            async def generate_sql_candidate(self, payload, *, correlation_id):
                response = await super().generate_sql_candidate(
                    payload, correlation_id=correlation_id
                )
                with owner.begin() as connection:
                    connection.exec_driver_sql(
                        "UPDATE gold.publicacao_atual "
                        "SET lote = 'GOLD_20261107T000000Z_bbbbbbbb'"
                    )
                return response

        app.state.genai_question_client = ChangingPublicationClient(fixture["cases"])
        changed = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={"question": fixture["cases"][0]["question"], "context": []},
        )
        assert changed.status_code == 409
        assert "evidence" not in changed.json()
        assert "presentation" not in changed.json()
        with owner.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE gold.publicacao_atual "
                "SET lote = 'GOLD_20261106T000000Z_aaaaaaaa'"
            )
        app.state.genai_question_client = original_client

        record_audit = AuditStore.record
        attempted_audit_stages = []

        def fail_response_audit(self, event, *, service="genai", now=None):
            attempted_audit_stages.append(event.stage)
            if event.stage == "response":
                raise SQLAlchemyError("synthetic audit failure")
            return record_audit(self, event, service=service, now=now)

        monkeypatch.setattr(AuditStore, "record", fail_response_audit)
        audit_failure = strict_client.post(
            "/api/v1/ai/sql-analyses",
            json={"question": fixture["cases"][0]["question"], "context": []},
        )
        assert audit_failure.status_code == 503
        assert "evidence" not in audit_failure.json()
        assert "presentation" not in audit_failure.json()
        assert attempted_audit_stages[:3] == ["request", "source", "response"]


    finally:
        app.dependency_overrides = overrides
        pressure_reader.dispose()
        reader.dispose()
        owner.dispose()



@pytest.mark.parametrize(("question", "expected", "model_calls"), [
    ("Qual a receita de miojo de janeiro de 2026?", "unsupported", 0),
    ("Qual a receita de miojo?", "unsupported", 0),
    ("Como fazer uma receita de bolo?", "unsupported", 0),
    ("Qual a receita de lasanha em janeiro?", "unsupported", 0),
    ("Qual foi a receita?", "needs_clarification", 0),
    ("Qual a receita de energia e de miojo em janeiro?", "unsupported", 0),
    ("Qual o consumo de energia em junho?", "unsupported", 1),
    ("Quanto foi em junho?", "needs_clarification", 1),
])
def test_public_route_domain_policy_without_sql(
    client, monkeypatch, question, expected, model_calls,
):
    from app.api.v1.endpoints import ai as endpoint
    from app.services import genai_sql_pipeline as pipeline

    batch = (
        "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
        "12345678-1234-4123-8123-123456789abc"
    )
    scope = _candidate_request(question, {
        "context": [], "publication": batch, "dimension_values": [],
    }, ["2026-06"]).access_scope
    metric_id = "energy.consumption" if "consumo" in question.casefold() else "billing.revenue"
    if metric_id == "energy.consumption":
        scope = scope.model_copy(update={
            "allowed_metric_ids": frozenset({"billing.revenue", "energy.consumption"}),
        })

    class Publication:
        batch_ref = batch

        def planning_fields(self, engine, scope):
            return {
                "batch_ref": batch,
                "temporal_coverage": [{
                    "metric_id": metric_id, "kind": "monthly",
                    "competencies": ["2026-06"],
                }],
            }

        def assert_current(self, engine):
            pass

    calls = []

    class Generator:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            context = json.loads(payload.contents)
            calls.append(context["question"])
            assert model_calls == 1
            candidate = {
                "generation_contract_version": context["generation_contract_version"],
                "context_version": payload.context_version,
                "status": expected,
                "scope_assessment": {"status": "in_domain"},
            }
            if expected == "unsupported":
                candidate["semantic_intent"] = {"metric_id": "energy.consumption"}
                candidate["unsupported_reason"] = {
                    "code": "metric_outside_f1", "message": "Consumo fora da F1.",
                }
            else:
                candidate["clarification"] = {
                    "question": "Qual medida?", "missing_fields": ["metric"],
                }
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version=context["generation_contract_version"],
                candidate=candidate,
            )

    def record(_store, event, **_kwargs):
        audits.append(event)
        return "a" * 32

    audits = []
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(endpoint.GoldPublicationContext, "capture",
                        classmethod(lambda _cls, _engine: Publication()))
    monkeypatch.setattr(endpoint.AuditStore, "record", record)
    monkeypatch.setattr(pipeline, "execute_sql_admission",
                        lambda *args, **kwargs: pytest.fail("Pedido sem candidato executou SQL"))
    monkeypatch.setitem(client.app.dependency_overrides, get_question_gold_resources,
                        lambda: (test_engine, lambda: scope))
    monkeypatch.setitem(client.app.dependency_overrides, endpoint.get_sql_genai_question_client,
                        Generator)
    login_as_profile(client, monkeypatch, "commercial", username="sql-domain")

    response = client.post("/api/v1/ai/sql-analyses", json={"question": question})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == expected
    assert body["evidence"] is None and body["presentation"] is None
    assert "sql" not in body and "parameters" not in body
    assert calls == ([question] if model_calls else [])
    assert audits[-1].stage == "response" and audits[-1].model_calls == model_calls
    assert audits[-1].source_calls == 0


@pytest.mark.skipif(
    not os.getenv("TEST_TEXT_TO_SQL_URL"),
    reason="Configure PostgreSQL descartável em TEST_TEXT_TO_SQL_URL.",
)
def test_public_route_executes_legacy_gd_consumption_mapping(client, monkeypatch):
    from app.api.v1.endpoints import ai as endpoint
    from app.schemas.genai_internal import QuestionPlanRequest
    from tests.test_genai_sql_semantics import gd_consumption_query

    owner_url = make_url(os.environ["TEST_TEXT_TO_SQL_URL"])
    assert owner_url.database == "text_to_sql_f1_test"
    owner = create_engine(owner_url)
    with owner.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold_v2 CASCADE")
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold CASCADE")
        connection.exec_driver_sql("DROP ROLE IF EXISTS venergy_genai_reader")
        connection.exec_driver_sql("CREATE SCHEMA gold")
        connection.exec_driver_sql("CREATE SCHEMA gold_v2")
        connection.exec_driver_sql(
            "CREATE TABLE gold.publicacao_atual (schema_version text, lote text, publication_id text)"
        )
        connection.exec_driver_sql(
            "INSERT INTO gold.publicacao_atual VALUES "
            "('gold-csv-v2', 'GOLD_20000101T000000Z_aaaaaaaa', "
            "'12345678-1234-4123-8123-123456789abc')"
        )
        TABLES["diagnostico_receita"].create(connection)
        TABLES["consumo_receita_bairro"].create(connection)
        TABLES["consumo_mensal_uc"].create(connection)
        connection.execute(TABLES["diagnostico_receita"].insert(), [
            {"competencia": "2026-06", "municipio": "Recife",
             "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "FIXTURE",
             "bandeira_tarifaria": "BASE", "possui_gd": "Sim",
             "receita_total_reais": 100, "consumo_total_kwh": 12.5},
            {"competencia": "2026-06", "municipio": "Recife",
             "classe_consumo": "COMERCIAL", "subgrupo_tarifario": "FIXTURE",
             "bandeira_tarifaria": "BASE", "possui_gd": "Não",
             "receita_total_reais": 50, "consumo_total_kwh": 30},
        ])
        connection.exec_driver_sql(
            "CREATE ROLE venergy_genai_reader LOGIN NOSUPERUSER NOBYPASSRLS "
            "PASSWORD 'synthetic-test-only'"
        )
        connection.exec_driver_sql(
            "GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader"
        )
        connection.exec_driver_sql(
            "GRANT SELECT ON gold.publicacao_atual, gold_v2.diagnostico_receita, "
            "gold_v2.consumo_receita_bairro, gold_v2.consumo_mensal_uc "
            "TO venergy_genai_reader"
        )
    reader = create_engine(
        owner_url.set(username="venergy_genai_reader", password="synthetic-test-only"),
        hide_parameters=True, pool_size=1, max_overflow=0,
    )
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["billing.revenue", "energy.consumption"],
        "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class",
                                  "generation.distributed"],
    })

    class Generator:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            context = json.loads(payload.contents)
            request = QuestionPlanRequest.model_validate({
                "question": context["question"], "context": context["context"],
                "remaining_timeout_ms": payload.remaining_timeout_ms,
                "batch_ref": context["publication"], "access_scope": scope.model_dump(mode="json"),
                "temporal_coverage": [context["temporal_coverage"]],
                "dimension_value_coverage": [
                    item for item in context["dimension_values"]
                    if item["dimension_id"] != "generation.distributed"
                ],
            })
            candidate, _ = gd_consumption_query(request)
            candidate = candidate.model_copy(update={"context_version": payload.context_version})
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version=payload.generation_contract_version,
                candidate=candidate,
            )

        async def evaluate_readiness(self, _engine, **kwargs):
            return GoldReadinessReport.model_validate({
                "readiness_version": "gold-readiness-v2",
                "batch_ref": kwargs["expected_batch_ref"], "lot_state": "ready",
                "capabilities": {
                    "faturamento.receita": {"status": "available"},
                    "consumo.mensal_uc": {"status": "available"},
                },
            })

    app = client.app
    overrides = app.dependency_overrides
    original_overrides = overrides.copy()
    original_client = getattr(app.state, "genai_question_client", None)
    overrides[get_question_gold_resources] = lambda: (reader, lambda: scope)
    overrides[endpoint.get_sql_genai_question_client] = Generator
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "GENAI_GOLD_APPROVED_CONTROLS", frozenset({"C01", "C02", "C03", "C04", "C10"}))
    login_as_profile(client, monkeypatch, "commercial", username="sql-gd-route")
    strict_client = TestClient(app, raise_server_exceptions=True)
    strict_client.cookies.update(client.cookies)
    strict_client.headers.update(client.headers)
    try:
        response = strict_client.post("/api/v1/ai/sql-analyses", json={
            "question": "Qual foi o consumo das unidades com geração distribuída em Recife em junho de 2026?"
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "answered"
        assert body["evidence"]["rows"] == [["12.50"]]
        assert body["presentation"]["rows"][0]["cells"] == ["12.50"]
        assert body["presentation"]["filters"] == [
            "Município: Recife", "Geração distribuída (cadastro): Sim",
        ]
        assert "sql" not in body and "parameters" not in body
    finally:
        overrides.clear()
        overrides.update(original_overrides)
        if original_client is None:
            app.state.__dict__.pop("genai_question_client", None)
        else:
            app.state.genai_question_client = original_client
        reader.dispose()
        owner.dispose()


def test_saved_conversation_with_changed_data_returns_plain_language(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from starlette.requests import Request

    from app.api.v1.endpoints import ai as endpoint
    from app.schemas.sql_analysis import SqlAnalysisRequest

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(endpoint.GoldPublicationContext, "capture", classmethod(
        lambda _cls, _engine: SimpleNamespace(batch_ref="new-publication")
    ))
    scope = SimpleNamespace(allowed_metric_ids=set(), allowed_dimension_ids=set())
    scope.model_copy = lambda **_kwargs: scope
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.correlation_id = "a" * 32
    result = asyncio.run(endpoint._run_f1_sql_analysis_impl(
        SqlAnalysisRequest(question="Qual o faturamento?"), request, None,
        (object(), lambda: scope), None, trusted_batch_ref="old-publication",
    ))
    assert result.status_code == 409
    assert json.loads(result.body)["message"] == (
        "Os dados disponíveis mudaram. Atualize a página antes de perguntar."
    )
