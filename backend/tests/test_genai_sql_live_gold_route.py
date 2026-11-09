"""Opt-in HTTP integration against the currently configured Gold v2 reader.

Set TSQL11_LIVE_GOLD_URL explicitly to run. Candidates are fixed by default;
TSQL11_LIVE_GEMINI_ROUTE=1 exercises real generation for the released-control
cases. The authenticated route, admission, restricted SQL executor, evidence,
audit and Gold readiness run normally.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
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
from app.services.gold_readiness import evaluate_domain_readiness
from tests.support.platform_auth import login_as_profile
from tests.test_genai_sql_semantics import (
    accumulated_attendance_query,
    accumulated_satisfaction_candidate,
    satisfaction_candidate,
    weighted_continuity_candidate,
)
from tests.test_genai_sql_structure import candidate as candidate_envelope

_CONTROL_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "genai_gold_released_controls_c05_c09.json")
    .read_text(encoding="utf-8")
)["cases"]
_CONTROL_CASES_BY_ID = {case["id"]: case for case in _CONTROL_CASES}
_CADASTRAL_CONTROL_CASES = [
    case for case in _CONTROL_CASES if case["control"] in {"C05", "C06", "C07"}
]


def _gd_consumption_total_candidate(request):
    payload = request.model_dump(mode="json")
    payload["question"] = (
        "Qual foi o consumo das unidades com geração distribuída em Recife "
        "em junho de 2026?"
    )
    payload["access_scope"]["allowed_metric_ids"] = [
        "billing.revenue", "energy.consumption",
    ]
    payload["temporal_coverage"] = [{
        "metric_id": "energy.consumption",
        "kind": "monthly",
        "competencies": ["2026-06"],
    }]
    request = type(request).model_validate(payload)
    candidate = candidate_envelope(
        request,
        "SELECT SUM(consumo_total_kwh) AS consumption "
        "FROM gold_v2.diagnostico_receita "
        "WHERE competencia = :month AND municipio = :city AND possui_gd = :gd",
        parameters={
            "month": {"type": "string", "value": "2026-06"},
            "city": {"type": "string", "value": "RECIFE"},
            "gd": {"type": "string", "value": "Sim"},
        },
    )
    body = candidate.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v2"
    body["interpretation"].update(
        metric_id="energy.consumption",
        operation="total",
        aggregation="sum",
        periods=[{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=[
            {
                "dimension_id": "geography.municipality",
                "operator": "eq",
                "values": ["RECIFE"],
            },
            {
                "dimension_id": "generation.distributed",
                "operator": "eq",
                "values": ["Sim"],
            },
        ],
        group_by=[],
        ranking_direction=None,
        ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": "consumption", "role": "measure", "value_type": "decimal", "unit": "kWh",
    }]
    return type(candidate).model_validate(body), request


def _grouped_neighborhood_revenue_candidate(request):
    payload = request.model_dump(mode="json")
    payload["question"] = "Qual foi a receita por bairro em Recife em junho de 2026?"
    payload["temporal_coverage"] = [{
        "metric_id": "billing.revenue",
        "kind": "monthly",
        "competencies": ["2026-06"],
    }]
    request = type(request).model_validate(payload)
    candidate = candidate_envelope(
        request,
        "SELECT bairro AS neighborhood, SUM(receita_total_reais) AS revenue "
        "FROM gold_v2.consumo_receita_bairro "
        "WHERE competencia = :month AND municipio = :city GROUP BY bairro",
        parameters={
            "month": {"type": "string", "value": "2026-06"},
            "city": {"type": "string", "value": "RECIFE"},
        },
        dimensions=("neighborhood",),
    )
    body = candidate.model_dump(mode="json")
    body["interpretation"].update(
        metric_id="billing.revenue",
        operation="grouped_total",
        aggregation="sum",
        periods=[{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=[{
            "dimension_id": "geography.municipality",
            "operator": "eq",
            "values": ["RECIFE"],
        }],
        group_by=["neighborhood"],
        ranking_direction=None,
        ranking_limit=None,
    )
    body["result_columns"] = [
        {"name": "neighborhood", "role": "dimension", "value_type": "string"},
        {"name": "revenue", "role": "measure", "value_type": "decimal", "unit": "R$"},
    ]
    return type(candidate).model_validate(body), request


def _average_billing_ratio_candidate(request, *, metric_id: str):
    specs = {
        "billing.average_ticket": (
            "Qual foi o ticket médio em Recife em junho de 2026?",
            "ROUND(SUM(receita_total_reais) / NULLIF(SUM(qtd_ucs_distintas_faturadas_no_mes), 0), 2)",
            "average_ticket",
            "R$ por UC faturada no mês",
        ),
        "billing.effective_tariff": (
            "Qual foi o preço médio observado por kWh em Recife em junho de 2026?",
            "ROUND(SUM(receita_base_comparavel_reais) / NULLIF(SUM(consumo_base_comparavel_kwh)::numeric, 0), 4)",
            "effective_tariff",
            "R$/kWh",
        ),
    }
    question, expression, alias, unit = specs[metric_id]
    payload = request.model_dump(mode="json")
    payload["question"] = question
    payload["temporal_coverage"] = [{
        "metric_id": metric_id,
        "kind": "monthly",
        "competencies": ["2026-06"],
    }]
    request = type(request).model_validate(payload)
    candidate = candidate_envelope(
        request,
        f"SELECT {expression} AS {alias} FROM gold_v2.diagnostico_receita "
        "WHERE competencia = :month AND municipio = :city",
        parameters={
            "month": {"type": "string", "value": "2026-06"},
            "city": {"type": "string", "value": "RECIFE"},
        },
    )
    body = candidate.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v13"
    body["interpretation"].update(
        metric_id=metric_id,
        operation="ratio_of_sums",
        aggregation="ratio_of_sums",
        periods=[{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=[{
            "dimension_id": "geography.municipality",
            "operator": "eq",
            "values": ["RECIFE"],
        }],
        group_by=[],
        ranking_direction=None,
        ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": alias,
        "role": "measure",
        "value_type": "decimal",
        "unit": unit,
    }]
    return type(candidate).model_validate(body), request


def _average_ticket_candidate(request):
    return _average_billing_ratio_candidate(request, metric_id="billing.average_ticket")


def _effective_tariff_candidate(request):
    return _average_billing_ratio_candidate(request, metric_id="billing.effective_tariff")


def _average_consumption_candidate(request):
    payload = request.model_dump(mode="json")
    payload["question"] = (
        "Qual foi o consumo médio por UC com leitura em junho de 2026?"
    )
    payload["temporal_coverage"] = [{
        "metric_id": "energy.average_consumption_per_uc",
        "kind": "monthly",
        "competencies": ["2026-06"],
    }]
    request = type(request).model_validate(payload)
    candidate = candidate_envelope(
        request,
        "SELECT SUM(consumo_total_kwh) / NULLIF(SUM(qtd_ucs_com_leitura), 0) "
        "AS average_consumption_per_uc FROM gold_v2.diagnostico_receita "
        "WHERE competencia = :month",
        parameters={"month": {"type": "string", "value": "2026-06"}},
    )
    body = candidate.model_dump(mode="json")
    body["generation_contract_version"] = "text-to-sql-f1-v11"
    body["interpretation"].update(
        metric_id="energy.average_consumption_per_uc",
        operation="ratio_of_sums",
        aggregation="ratio_of_sums",
        periods=[{"start": "2026-06-01", "end": "2026-06-30"}],
        filters=[],
        group_by=[],
        ranking_direction=None,
        ranking_limit=None,
    )
    body["result_columns"] = [{
        "name": "average_consumption_per_uc",
        "role": "measure",
        "value_type": "decimal",
        "unit": "kWh por UC com leitura no mês",
    }]
    return type(candidate).model_validate(body), request


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
    if os.getenv("TSQL11_LIVE_GEMINI_ROUTE") != "1":
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
        "question": _CONTROL_CASES_BY_ID["CTL-006"]["question"],
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
            _CONTROL_CASES_BY_ID["CTL-006"]["reference_sql"]
        )).scalar_one()
    assert body["evidence"]["rows"] == [[str(expected)]]


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
    if os.getenv("TSQL11_LIVE_GEMINI_ROUTE") != "1":
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
        "question": _CONTROL_CASES_BY_ID["CTL-005"]["question"],
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
            _CONTROL_CASES_BY_ID["CTL-005"]["reference_sql"]
        )).scalar_one()
    assert body["evidence"]["rows"] == [[str(expected)]]


@pytest.mark.parametrize(
    ("question", "profile", "scope_data", "build_candidate", "metric_id", "source_table", "oracle_sql"),
    [
        (
            "Qual foi o consumo das unidades com geração distribuída em Recife em junho de 2026?",
            "commercial",
            {
                "allowed_metric_ids": ["billing.revenue", "energy.consumption"],
                "allowed_dimension_ids": [
                    "geography.municipality", "customer.consumption_class",
                    "generation.distributed",
                ],
            },
            _gd_consumption_total_candidate,
            "energy.consumption",
            "gold_v2.diagnostico_receita",
            (
                "SELECT SUM(consumo_total_kwh) FROM gold_v2.diagnostico_receita "
                "WHERE competencia='2026-06' AND municipio='RECIFE' AND possui_gd='Sim'"
            ),
        ),
        (
            "Qual foi a nota média de satisfação em junho de 2026?",
            "customer_service",
            {
                "allowed_metric_ids": ["service.attendance", "service.satisfaction"],
                "allowed_dimension_ids": [],
            },
            satisfaction_candidate,
            "service.satisfaction",
            "gold_v2.atendimentos_uc",
            (
                "SELECT AVG(nota_satisfacao) FROM gold_v2.atendimentos_uc "
                "WHERE data_abertura >= TIMESTAMPTZ '2026-06-01 00:00:00+00' "
                "AND data_abertura < TIMESTAMPTZ '2026-07-01 00:00:00+00'"
            ),
        ),
        (
            "Qual foi a nota média de satisfação no histórico acumulado?",
            "customer_service",
            {
                "allowed_metric_ids": ["service.accumulated_satisfaction"],
                "allowed_dimension_ids": [],
            },
            accumulated_satisfaction_candidate,
            "service.accumulated_satisfaction",
            "gold_v2.atendimentos_uc",
            "SELECT AVG(nota_satisfacao) FROM gold_v2.atendimentos_uc",
        ),
        (
            "Quantos chamados no histórico acumulado?",
            "customer_service",
            {
                "allowed_metric_ids": ["service.accumulated_attendance"],
                "allowed_dimension_ids": [],
            },
            accumulated_attendance_query,
            "service.accumulated_attendance",
            "gold_v2.visao_360_uc",
            "SELECT SUM(total_chamados_callcenter) FROM gold_v2.visao_360_uc",
        ),
        (
            "Qual foi a receita por bairro em Recife em junho de 2026?",
            "commercial",
            {
                "allowed_metric_ids": ["billing.revenue"],
                "allowed_dimension_ids": [
                    "geography.municipality", "geography.neighborhood",
                ],
            },
            _grouped_neighborhood_revenue_candidate,
            "billing.revenue",
            "gold_v2.consumo_receita_bairro",
            (
                "SELECT SUM(receita_total_reais) FROM gold_v2.consumo_receita_bairro "
                "WHERE competencia='2026-06' AND municipio='RECIFE'"
            ),
        ),
        (
            "Qual foi o consumo médio por UC com leitura em junho de 2026?",
            "commercial",
            {
                "allowed_metric_ids": [
                    "billing.revenue", "energy.consumption",
                    "energy.average_consumption_per_uc",
                ],
                "allowed_dimension_ids": [
                    "geography.municipality", "customer.consumption_class",
                ],
            },
            _average_consumption_candidate,
            "energy.average_consumption_per_uc",
            "gold_v2.diagnostico_receita",
            (
                "SELECT SUM(consumo_total_kwh) / NULLIF(SUM(qtd_ucs_com_leitura), 0) "
                "FROM gold_v2.diagnostico_receita WHERE competencia='2026-06'"
            ),
        ),
        (
            "Qual foi o ticket médio em Recife em junho de 2026?",
            "commercial",
            {
                "allowed_metric_ids": ["billing.revenue", "billing.average_ticket"],
                "allowed_dimension_ids": ["geography.municipality"],
            },
            _average_ticket_candidate,
            "billing.average_ticket",
            "gold_v2.diagnostico_receita",
            (
                "SELECT ROUND(SUM(receita_total_reais) / "
                "NULLIF(SUM(qtd_ucs_distintas_faturadas_no_mes), 0), 2) "
                "FROM gold_v2.diagnostico_receita "
                "WHERE competencia='2026-06' AND municipio='RECIFE'"
            ),
        ),
        (
            "Qual foi o preço médio observado por kWh em Recife em junho de 2026?",
            "commercial",
            {
                "allowed_metric_ids": ["billing.revenue", "energy.consumption", "billing.effective_tariff"],
                "allowed_dimension_ids": ["geography.municipality"],
            },
            _effective_tariff_candidate,
            "billing.effective_tariff",
            "gold_v2.diagnostico_receita",
            (
                "SELECT ROUND(SUM(receita_base_comparavel_reais) / "
                "NULLIF(SUM(consumo_base_comparavel_kwh)::numeric, 0), 4) "
                "FROM gold_v2.diagnostico_receita "
                "WHERE competencia='2026-06' AND municipio='RECIFE'"
            ),
        ),
        (
            "Qual foi o DEC de todos os alimentadores entre janeiro e março de 2026?",
            "commercial",
            {
                "allowed_metric_ids": ["network.equivalent_interruption_duration"],
                "allowed_dimension_ids": ["network.feeder"],
            },
            weighted_continuity_candidate,
            "network.equivalent_interruption_duration",
            "gold_v2.indicadores_dec_fec",
            (
                "WITH feeders AS (SELECT DISTINCT id_alimentador FROM gold_v2.indicadores_dec_fec), "
                "windows AS (SELECT id_alimentador, COUNT(DISTINCT competencia) AS months_seen, "
                "COUNT(*) AS rows_seen, COUNT(duracao_total_interrupcoes_horas) AS numerator_values, "
                "COUNT(total_ucs_alimentador) AS denominator_values, "
                "MIN(total_ucs_alimentador) AS min_denominator, MAX(total_ucs_alimentador) AS max_denominator, "
                "SUM(duracao_total_interrupcoes_horas) AS numerator "
                "FROM gold_v2.indicadores_dec_fec WHERE competencia BETWEEN '2026-01' AND '2026-03' "
                "GROUP BY id_alimentador), evaluated AS (SELECT feeders.id_alimentador, "
                "windows.numerator, windows.min_denominator AS denominator, "
                "COALESCE(windows.months_seen = 3 AND windows.rows_seen = 3 "
                "AND windows.numerator_values = 3 AND windows.denominator_values = 3 "
                "AND windows.min_denominator > 0 AND windows.min_denominator = windows.max_denominator, FALSE) AS eligible "
                "FROM feeders LEFT JOIN windows USING (id_alimentador)) "
                "SELECT SUM(CASE WHEN eligible THEN numerator END)::numeric / "
                "NULLIF(SUM(CASE WHEN eligible THEN denominator END), 0), "
                "COUNT(*) FILTER (WHERE eligible), COUNT(*) FILTER (WHERE NOT eligible) FROM evaluated"
            ),
        ),
    ],
    ids=["con04", "satisfaction-monthly", "satisfaction-accumulated", "attendance-accumulated", "revenue-by-neighborhood", "average-consumption-per-uc", "average-ticket", "effective-tariff", "continuity-weighted"],
)
def test_public_http_route_executes_tsql11_capabilities_against_active_gold(
    client, monkeypatch, live_gold_engine, question, profile, scope_data,
    build_candidate, metric_id, source_table, oracle_sql,
):
    """Real readiness and Gold execution; optional real Gemini via an explicit env flag."""
    from app.api.v1.endpoints import ai as endpoint

    batch_ref = GoldPublicationContext.capture(live_gold_engine).batch_ref
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "c" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"], **scope_data,
    })
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
            assert request.question == question
            candidate, _ = build_candidate(request)
            body = candidate.model_dump(mode="json")
            body["context_version"] = payload.context_version
            candidate = type(candidate).model_validate(body)
            return SqlGenerationResponse(
                correlation_id=correlation_id,
                generation_contract_version=candidate.generation_contract_version,
                candidate=candidate,
            )

        async def evaluate_readiness(self, engine, **kwargs):
            assert kwargs["expected_batch_ref"] == batch_ref
            assert engine is live_gold_engine
            # Keep the public route's audit DB isolated while consulting the
            # actual readiness service against the active Gold reader.
            async with httpx.AsyncClient(timeout=45, trust_env=False) as transport:
                return await evaluate_domain_readiness(
                    live_gold_engine,
                    http_client=transport,
                    base_url=str(settings.AI_AGENT_BASE_URL),
                    service_token=settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value(),
                    **kwargs,
                )

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (live_gold_engine, lambda: scope),
    )
    if os.getenv("TSQL11_LIVE_GEMINI_ROUTE") != "1":
        monkeypatch.setitem(
            client.app.dependency_overrides,
            endpoint.get_sql_genai_question_client,
            lambda: FixedCandidateClient(),
        )
    login_as_profile(
        client, monkeypatch, profile,
        username=f"sql-live-tsql11-{uuid4().hex[:10]}",
    )

    client._transport.raise_server_exceptions = True
    response = client.post("/api/v1/ai/sql-analyses", json={"question": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["evidence"]["metric_id"] == metric_id
    assert body["evidence"]["source_table"] == source_table
    assert body["evidence"]["rows"]

    with live_gold_engine.connect() as connection:
        oracle_row = connection.execute(text(oracle_sql)).one()
        expected = oracle_row[0]
    if metric_id == "billing.revenue" and body["evidence"]["rows"][0][0] != expected:
        actual = sum(float(row[1]) for row in body["evidence"]["rows"])
    elif metric_id == "billing.revenue":
        actual = float(body["evidence"]["rows"][0][0])
    else:
        actual = float(body["evidence"]["rows"][0][0])
    rounded_decimals = (
        4 if metric_id == "billing.effective_tariff"
        else 2 if metric_id in {
            "service.satisfaction", "service.accumulated_satisfaction",
            "energy.average_consumption_per_uc", "billing.average_ticket",
        }
        else None
    )
    expected_value = float(round(expected, rounded_decimals)) if rounded_decimals is not None else float(expected)
    assert actual == pytest.approx(expected_value, rel=1e-12, abs=1e-9)
    if body["evidence"]["interpretation"]["operation"] == "weighted_continuity":
        assert body["evidence"]["coverage_quality"] == "observed_uncertified"
        assert int(body["evidence"]["rows"][0][1]) == oracle_row[1]
        assert int(body["evidence"]["rows"][0][2]) == oracle_row[2]
        assert "Valores observados; cobertura do alimentador não certificada." in body["presentation"]["limitations"]


@pytest.mark.parametrize(
    ("case_id", "question", "metric_id", "source_table", "oracle_sql", "expected_groups"),
    [
        (
            case["id"], case["question"], case["metric_id"],
            case["source_table"], case["reference_sql"], bool(case["group_by"]),
        )
            for case in _CADASTRAL_CONTROL_CASES
    ],
    ids=[case["id"] for case in _CADASTRAL_CONTROL_CASES],
)
def test_public_http_route_executes_c05_c06_c07_against_active_gold(
    client, monkeypatch, live_gold_engine, case_id, question, metric_id,
    source_table, oracle_sql, expected_groups,
):
    """The authenticated route must match independent SQL on the actual Gold lot.

    With TSQL11_LIVE_GEMINI_ROUTE=1 this bypasses the local count compiler so the
    same request traverses the real Gemini candidate path as well.
    """
    from app.api.v1.endpoints import ai as endpoint
    from app.services import genai_sql_observation as observation

    batch_ref = GoldPublicationContext.capture(live_gold_engine).batch_ref
    scope = AccessScope.model_validate({
        "caller_ref": "session:" + "d" * 64,
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": [metric_id],
        "allowed_dimension_ids": [
            "customer.consumption_class"
            if metric_id == "customer.units_by_class"
            else "inspection.priority"
        ],
    })

    class ReadinessOnlyClient:
        async def generate_sql_candidate(self, *args, **kwargs):
            pytest.fail("C05-C07 devem usar a interpretação/consulta determinística")

        async def evaluate_readiness(self, engine, **kwargs):
            assert kwargs["expected_batch_ref"] == batch_ref
            assert engine is live_gold_engine
            async with httpx.AsyncClient(timeout=45, trust_env=False) as transport:
                return await evaluate_domain_readiness(
                    live_gold_engine,
                    http_client=transport,
                    base_url=str(settings.AI_AGENT_BASE_URL),
                    service_token=settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value(),
                    **kwargs,
                )

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "GENAI_GOLD_APPROVED_CONTROLS",
        sorted(set(settings.GENAI_GOLD_APPROVED_CONTROLS) | {"C05", "C06", "C07"}),
    )
    monkeypatch.setitem(
        client.app.dependency_overrides,
        get_question_gold_resources,
        lambda: (live_gold_engine, lambda: scope),
    )
    if os.getenv("TSQL11_LIVE_GEMINI_ROUTE") == "1":
        monkeypatch.setattr(
            observation, "_explicit_control_count_candidate", lambda *_args: None
        )
    else:
        monkeypatch.setitem(
            client.app.dependency_overrides,
            endpoint.get_sql_genai_question_client,
            lambda: ReadinessOnlyClient(),
        )
    case = _CONTROL_CASES_BY_ID[case_id]
    login_as_profile(
        client, monkeypatch, case.get("profile", "admin"),
        username=f"sql-live-controls-{uuid4().hex[:10]}",
    )

    client._transport.raise_server_exceptions = True
    response = client.post("/api/v1/ai/sql-analyses", json={"question": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    evidence = body["evidence"]
    assert evidence["metric_id"] == metric_id
    assert evidence["source_table"] == source_table
    assert evidence["batch_ref"] == batch_ref

    with live_gold_engine.connect() as connection:
        oracle_rows = connection.execute(text(oracle_sql)).all()
    actual_rows = evidence["rows"]
    if expected_groups:
        expected = {str(row[0]): int(row[1]) for row in oracle_rows}
        actual = {str(row[0]): int(row[1]) for row in actual_rows}
        assert actual == expected
    else:
        assert len(oracle_rows) == len(actual_rows) == 1
        assert int(actual_rows[0][-1]) == int(oracle_rows[0][0])
    if case_id == "CTL-004":
        assert int(actual_rows[0][-1]) == 0
        answer = body["presentation"]["answer"].casefold()
        assert "não há ucs" in answer
        assert "sem histórico" not in answer
