"""Opt-in HTTP integration against the currently configured Gold v2 reader.

Set TSQL11_LIVE_GOLD_URL explicitly to run. The candidate is fixed; no model call
is made. The public route, admission, restricted SQL executor, evidence and audit
run normally. The only source query is an aggregate over GD drop eligibility.
"""

import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.api.v1.endpoints import ai as endpoint
from app.core.config import settings
from app.core.genai_gold_database import get_question_gold_resources
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.gold_readiness import GoldReadinessReport
from app.schemas.sql_generation import SqlGenerationResponse
from app.services.genai_publication import GoldPublicationContext
from tests.support.platform_auth import login_as_profile
from tests.test_genai_sql_structure import candidate as candidate_envelope


@pytest.fixture(scope="module")
def live_gold_engine():
    address = os.getenv("TSQL11_LIVE_GOLD_URL")
    if not address:
        pytest.skip("Configure TSQL11_LIVE_GOLD_URL para a conferência local da Gold.")
    url = make_url(address)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "venergy_genai_reader"
    engine = create_engine(url, hide_parameters=True, echo=False, pool_size=1, max_overflow=0)
    try:
        yield engine
    finally:
        engine.dispose()


def test_public_http_route_executes_gd_drop_against_active_gold(
    client, monkeypatch, live_gold_engine,
):
    batch_ref = GoldPublicationContext.capture(live_gold_engine).batch_ref
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold",
        "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["energy.gd_consumption_drop"],
        "allowed_dimension_ids": ["generation.distributed", "geography.municipality"],
    })
    assert {"C08", "C09"} <= set(settings.GENAI_GOLD_APPROVED_CONTROLS)

    class FixedCandidateClient:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            context = json.loads(payload.contents)
            request = QuestionPlanRequest.model_validate({
                "question": context["question"],
                "context": context["context"],
                "remaining_timeout_ms": payload.remaining_timeout_ms,
                "batch_ref": context["publication"],
                "access_scope": scope.model_dump(mode="json"),
                "temporal_coverage": [context["temporal_coverage"]],
                "dimension_value_coverage": context["dimension_values"],
            })
            value = candidate_envelope(
                request,
                "SELECT COUNT(queda_consumo_superior_30_pct) AS gd_drop_units "
                "FROM gold_v2.variacao_consumo_uc WHERE possui_gd = :gd "
                "AND queda_consumo_superior_30_pct = :eligible "
                "AND meses_com_leitura_p1 >= :minimum_months "
                "AND meses_com_leitura_p2 >= :minimum_months",
                parameters={
                    "gd": {"type": "string", "value": "Sim"},
                    "eligible": {"type": "boolean", "value": True},
                    "minimum_months": {"type": "integer", "value": 6},
                },
            )
            body = value.model_dump(mode="json")
            body["generation_contract_version"] = "text-to-sql-f1-v10"
            body["interpretation"].update(
                metric_id="energy.gd_consumption_drop",
                operation="snapshot_total",
                aggregation="count_gd_drop",
                periods=[],
                filters=[{
                    "dimension_id": "generation.distributed",
                    "operator": "eq",
                    "values": ["Sim"],
                }],
                group_by=[],
                ranking_direction=None,
                ranking_limit=None,
            )
            body["result_columns"] = [{
                "name": "gd_drop_units",
                "role": "measure",
                "value_type": "integer",
                "unit": "UCs",
            }]
            candidate = type(value).model_validate(body)
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version="text-to-sql-f1-v10",
                candidate=candidate,
            )

        async def evaluate_readiness(self, _engine, **kwargs):
            assert kwargs["expected_batch_ref"] == batch_ref
            assert {"C08", "C09"} <= kwargs["approved_controls"]
            return GoldReadinessReport.model_validate({
                "readiness_version": "gold-readiness-v2",
                "batch_ref": batch_ref,
                "lot_state": "partial",
                "capabilities": {
                    "consumo.variacao_uc": {"status": "available"},
                },
            })

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (live_gold_engine, lambda: scope),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        endpoint.get_sql_genai_question_client,
        FixedCandidateClient,
    )
    login_as_profile(
        client,
        monkeypatch,
        "commercial",
        username=f"sql-live-gd-{uuid4().hex[:10]}",
    )

    response = client.post("/api/v1/ai/sql-analyses", json={
        "question": "Quantas UCs com GD tiveram queda de consumo superior a 30%?",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["evidence"]["metric_id"] == "energy.gd_consumption_drop"
    assert body["evidence"]["evidence_contract_version"] == "text-to-sql-f1-evidence-v10"
    assert body["evidence"]["source_table"] == "gold_v2.variacao_consumo_uc"
    assert len(body["evidence"]["rows"]) == 1
    with live_gold_engine.connect() as connection:
        expected = connection.execute(text(
            "SELECT COUNT(queda_consumo_superior_30_pct) "
            "FROM gold_v2.variacao_consumo_uc WHERE possui_gd='Sim' "
            "AND queda_consumo_superior_30_pct IS TRUE "
            "AND meses_com_leitura_p1>=6 AND meses_com_leitura_p2>=6"
        )).scalar_one()
    assert body["evidence"]["rows"] == [[str(expected)]]
    assert body["evidence"]["rows"] == [["3111"]]


def test_public_http_route_executes_gd_registry_against_active_gold(
    client, monkeypatch, live_gold_engine,
):
    batch_ref = GoldPublicationContext.capture(live_gold_engine).batch_ref
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "b" * 64,
        "profile_id": "v-energy-grid-360-gold",
        "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["energy.gd_units"],
        "allowed_dimension_ids": ["generation.distributed", "geography.municipality"],
    })
    assert {"C08", "C09"} <= set(settings.GENAI_GOLD_APPROVED_CONTROLS)

    class FixedCandidateClient:
        async def generate_sql_candidate(self, payload, *, correlation_id):
            context = json.loads(payload.contents)
            request = QuestionPlanRequest.model_validate({
                "question": context["question"],
                "context": context["context"],
                "remaining_timeout_ms": payload.remaining_timeout_ms,
                "batch_ref": context["publication"],
                "access_scope": scope.model_dump(mode="json"),
                "temporal_coverage": [context["temporal_coverage"]],
                "dimension_value_coverage": context["dimension_values"],
            })
            value = candidate_envelope(
                request,
                "SELECT COUNT(possui_gd) AS gd_units "
                "FROM gold_v2.variacao_consumo_uc WHERE possui_gd = :gd",
                parameters={"gd": {"type": "string", "value": "Sim"}},
            )
            body = value.model_dump(mode="json")
            body["generation_contract_version"] = "text-to-sql-f1-v8"
            body["interpretation"].update(
                metric_id="energy.gd_units",
                operation="snapshot_total",
                aggregation="count_non_null",
                periods=[],
                filters=[{
                    "dimension_id": "generation.distributed",
                    "operator": "eq",
                    "values": ["Sim"],
                }],
                group_by=[],
                ranking_direction=None,
                ranking_limit=None,
            )
            body["result_columns"] = [{
                "name": "gd_units",
                "role": "measure",
                "value_type": "integer",
                "unit": "UCs",
            }]
            candidate = type(value).model_validate(body)
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version="text-to-sql-f1-v8",
                candidate=candidate,
            )

        async def evaluate_readiness(self, _engine, **kwargs):
            assert kwargs["expected_batch_ref"] == batch_ref
            assert {"C08", "C09"} <= kwargs["approved_controls"]
            return GoldReadinessReport.model_validate({
                "readiness_version": "gold-readiness-v2",
                "batch_ref": batch_ref,
                "lot_state": "partial",
                "capabilities": {
                    "consumo.variacao_uc": {"status": "available"},
                },
            })

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (live_gold_engine, lambda: scope),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        endpoint.get_sql_genai_question_client,
        FixedCandidateClient,
    )
    login_as_profile(
        client,
        monkeypatch,
        "commercial",
        username=f"sql-live-gd-units-{uuid4().hex[:10]}",
    )

    response = client.post("/api/v1/ai/sql-analyses", json={
        "question": "Quantas UCs têm GD?",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["evidence"]["metric_id"] == "energy.gd_units"
    assert body["evidence"]["evidence_contract_version"] == "text-to-sql-f1-evidence-v8"
    assert body["evidence"]["source_table"] == "gold_v2.variacao_consumo_uc"
    assert len(body["evidence"]["rows"]) == 1
    with live_gold_engine.connect() as connection:
        expected = connection.execute(text(
            "SELECT COUNT(possui_gd) FROM gold_v2.variacao_consumo_uc "
            "WHERE possui_gd='Sim'"
        )).scalar_one()
    assert body["evidence"]["rows"] == [[str(expected)]]
    assert body["evidence"]["rows"] == [["3510"]]
