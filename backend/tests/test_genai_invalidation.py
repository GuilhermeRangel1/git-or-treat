"""GENAI-13 servidor: publicação esperada, catálogo físico, troca de lote e rollback.

Contrato: docs/contracts/genai-invalidation.md (itens I1, I2, I5, I6 e R2).
Rota, coordenador, planejamento, contexto de publicação e catálogo são reais; planejador
GenAI, gate de prontidão, executor e auditoria são controlados. Schema renomeado e tipo
alterado no PostgreSQL estão em ``test_genai_invalidation_postgres.py``.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert

from app.api.v1.endpoints import ai
from app.core.genai_gold_database import get_question_gold_resources
from app.main import app
from app.models.gold_load import BATCH
from app.repositories.gold_publication import GoldPublicationChanged, GoldPublicationInvalid
from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.schemas.genai_plan import LogicalReadPlan
from app.schemas.gold_readiness import GoldReadinessReport
from app.services import genai_coordination
from app.services.genai_coordination import answer_gold_question
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_planning import GoldPlanningResult, plan_gold_question
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_catalog import (
    GoldCatalogIncompatible,
    gold_physical_catalog,
    load_gold_catalog,
)
from tests.support.database import test_engine

LOTE = "GOLD_20000101T000000Z_aaaaaaaa"
OTHER_LOTE = "GOLD_20000201T000000Z_bbbbbbbb"
FINGERPRINT = "a" * 64
CORRELATION = "c" * 32
QUESTION = "Qual foi a receita em Recife em março de 2025?"
SCOPE = AccessScope(
    caller_ref="user.invalidacao", profile_id="v-energy-grid-360-gold",
    source_id="gold.local", allowed_operations={"read"},
    allowed_metric_ids={"billing.revenue"},
    allowed_dimension_ids={"geography.municipality"},
)


def _publish(*, lote=LOTE, fingerprint=FINGERPRINT, schema_version="gold-csv-v2") -> str:
    publication_id = str(uuid4())
    with test_engine.begin() as connection:
        connection.execute(delete(BATCH))
        connection.execute(insert(BATCH).values(
            id=1, lote=lote, fingerprint=fingerprint, importado_em=datetime.now(UTC),
            manifesto={}, schema_version=schema_version, publication_id=publication_id,
            origem={"run_id_silver": "silver-run", "lote_bronze_silver": "bronze-run"},
        ))
    return f"{schema_version}:{lote}:{publication_id}"


@pytest.fixture
def publication_rows():
    yield
    with test_engine.begin() as connection:
        connection.execute(delete(BATCH))


@pytest.fixture
def gold_route(client, monkeypatch):
    """Rota pública em modo Gold; o coordenador é substituído por um espião."""
    calls = []

    async def spy(engine, genai, request, **kwargs):
        calls.append((request, kwargs))
        return AIQuestionResponse(
            correlation_id=kwargs["correlation_id"], status="needs_clarification",
            message="Informe o recorte.",
        )

    monkeypatch.setattr(ai, "answer_gold_question", spy)
    previous = app.dependency_overrides.get(get_question_gold_resources)
    app.dependency_overrides[get_question_gold_resources] = lambda: (test_engine, lambda: SCOPE)
    try:
        yield client, calls
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_question_gold_resources, None)
        else:
            app.dependency_overrides[get_question_gold_resources] = previous


def _error(response, status, code, retryable):
    assert response.status_code == status
    body = response.json()
    assert body["error"] == {"code": code, "retryable": retryable}
    assert "answer" not in body
    assert LOTE not in response.text and FINGERPRINT not in response.text
    return body


def test_matching_publication_pins_planning_to_the_captured_batch(gold_route):
    client, calls = gold_route
    batch_ref = _publish()
    response = client.post("/api/v1/ai/questions", json={
        "question": QUESTION,
        "expected_publication": {"lote": LOTE, "fingerprint": FINGERPRINT},
    })
    assert response.status_code == 200
    request, kwargs = calls[0]
    assert kwargs["expected_batch_ref"] == batch_ref
    # O núcleo recebe o mesmo envelope anterior, sem o campo novo.
    assert type(request) is AIQuestionRequest
    assert "expected_publication" not in request.model_dump()


def test_absent_publication_keeps_the_previous_contract(gold_route):
    client, calls = gold_route
    _publish()
    assert client.post("/api/v1/ai/questions", json={"question": QUESTION}).status_code == 200
    assert calls[0][1]["expected_batch_ref"] is None


@pytest.mark.parametrize("expected", [
    {"lote": OTHER_LOTE, "fingerprint": FINGERPRINT},
    {"lote": LOTE, "fingerprint": "b" * 64},
], ids=["lote", "fingerprint"])
def test_divergent_publication_is_a_non_retryable_conflict(gold_route, expected):
    client, calls = gold_route
    _publish()
    response = client.post(
        "/api/v1/ai/questions", json={"question": QUESTION, "expected_publication": expected},
    )
    _error(response, 409, "invalid_context", False)
    assert "Recarregue a tela" in response.json()["message"]
    assert calls == []


@pytest.mark.parametrize("expected", [
    {"lote": LOTE, "fingerprint": "ABC"},
    {"lote": "", "fingerprint": FINGERPRINT},
    {"lote": LOTE, "fingerprint": FINGERPRINT, "publication_id": "x"},
], ids=["fingerprint-malformado", "lote-vazio", "campo-extra"])
def test_malformed_publication_is_rejected_before_planning(gold_route, expected):
    client, calls = gold_route
    _publish()
    response = client.post(
        "/api/v1/ai/questions", json={"question": QUESTION, "expected_publication": expected},
    )
    _error(response, 422, "invalid_request", False)
    assert calls == []


@pytest.mark.parametrize("schema_version", [None, "gold-csv-v1"], ids=["ausente", "v1"])
def test_missing_or_v1_publication_is_unavailable_without_fallback(gold_route, schema_version):
    client, calls = gold_route
    if schema_version is not None:
        _publish(schema_version=schema_version)
    response = client.post("/api/v1/ai/questions", json={
        "question": QUESTION,
        "expected_publication": {"lote": LOTE, "fingerprint": FINGERPRINT},
    })
    _error(response, 503, "service_unavailable", False)
    assert calls == []


def test_synthetic_mode_rejects_publication_and_forwards_the_unchanged_contract(
    client, monkeypatch,
):
    from tests.test_ai_chat import FakeQuestionGateway

    gateway = FakeQuestionGateway()
    monkeypatch.setattr(app.state, "genai_question_client", gateway, raising=False)
    previous = app.dependency_overrides.get(get_question_gold_resources)
    app.dependency_overrides[get_question_gold_resources] = lambda: None
    try:
        rejected = client.post("/api/v1/ai/questions", json={
            "question": QUESTION,
            "expected_publication": {"lote": LOTE, "fingerprint": FINGERPRINT},
        })
        accepted = client.post("/api/v1/ai/questions", json={"question": QUESTION})
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_question_gold_resources, None)
        else:
            app.dependency_overrides[get_question_gold_resources] = previous
    _error(rejected, 422, "invalid_request", False)
    assert accepted.status_code == 200
    assert len(gateway.calls) == 1
    assert type(gateway.calls[0][0]) is AIQuestionRequest


@pytest.mark.parametrize("failure,status,code,retryable", [
    (GoldPublicationChanged("detalhe privado"), 409, "invalid_context", True),
    (GoldCatalogIncompatible(), 503, "service_unavailable", False),
], ids=["lote-mudou-durante", "catalogo-incompativel"])
def test_route_maps_change_and_incompatibility_to_recoverable_errors(
    gold_route, monkeypatch, failure, status, code, retryable,
):
    client, _ = gold_route

    async def failing(*args, **kwargs):
        raise failure

    monkeypatch.setattr(ai, "answer_gold_question", failing)
    response = client.post("/api/v1/ai/questions", json={"question": QUESTION})
    _error(response, status, code, retryable)
    assert "privado" not in response.text


def _plan(metric_id="billing.revenue", unit="R$") -> LogicalReadPlan:
    return LogicalReadPlan.model_validate({
        "catalog_version": "v1", "operation": "read",
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "domain_id": "revenue", "metric_id": metric_id, "unit": unit,
        "dimension_ids": ["geography.municipality"],
        "window": {"kind": "bounded", "start": "2025-03-01", "end": "2025-03-31",
                   "granularity": "month"},
        "filters": [{"dimension_id": "geography.municipality", "operator": "eq",
                     "values": ["Recife"]}],
        "limit": 100,
    })


def _plan_response(plan, catalog="current") -> QuestionPlanResponse:
    payload = {
        "correlation_id": CORRELATION, "status": "planned",
        "plan": plan.model_dump(mode="json"), "plan_fingerprint": plan.fingerprint(),
    }
    if catalog == "current":
        payload["physical_catalog"] = gold_physical_catalog().model_dump(mode="json")
    elif catalog is not None:
        payload["physical_catalog"] = catalog
    return QuestionPlanResponse.model_validate(payload)


class PlanningClient:
    def __init__(self, response):
        self.response = response
        self.plans = 0

    async def plan(self, payload, *, correlation_id):
        self.plans += 1
        return self.response


@pytest.fixture
def planning(monkeypatch, publication_rows):
    """Planejamento real com metadados e cobertura controlados (SQLite sem tabelas v2)."""
    from app.services import genai_planning

    def planning_fields(self, engine, scope):
        return {
            "batch_ref": self.batch_ref,
            "temporal_coverage": [
                {"metric_id": metric_id, "kind": "monthly", "competencies": ["2025-03"]}
                for metric_id in sorted(scope.allowed_metric_ids)
            ],
        }

    monkeypatch.setattr(GoldPublicationContext, "planning_fields", planning_fields)
    monkeypatch.setattr(genai_planning, "_has_selected_coverage", lambda *args: True)

    def run(response, *, expected_batch_ref=None):
        client = PlanningClient(response)
        result = asyncio.run(plan_gold_question(
            test_engine, client, AIQuestionRequest(question=QUESTION),
            resolve_scope=lambda: SCOPE, correlation_id=CORRELATION,
            expected_batch_ref=expected_batch_ref,
        ))
        return result, client

    return run


@pytest.mark.parametrize("catalog", ["current", None], ids=["mesmo-catalogo", "sem-catalogo"])
def test_plan_from_the_same_catalog_or_legacy_planner_is_admitted(planning, catalog):
    _publish()
    result, _ = planning(_plan_response(_plan(), catalog=catalog))
    assert result.source is not None
    assert result.source.table == "diagnostico_receita"


def test_plan_from_another_physical_catalog_is_rejected_before_admission(planning):
    _publish()
    other = {**gold_physical_catalog().model_dump(mode="json"), "digest": "f" * 64}
    with pytest.raises(GoldCatalogIncompatible):
        planning(_plan_response(_plan(), catalog=other))


def test_metric_missing_from_backend_catalog_is_incompatible_not_invalid(planning):
    _publish()
    with pytest.raises(GoldCatalogIncompatible):
        planning(_plan_response(_plan(metric_id="metrica.retirada"), catalog=None))


def test_publication_replaced_before_capture_is_a_retryable_change(planning):
    previous = _publish()
    _publish()
    with pytest.raises(GoldPublicationChanged) as raised:
        planning(_plan_response(_plan()), expected_batch_ref=previous)
    assert raised.value.retryable is True


def test_rollback_to_v1_publication_is_rejected_before_planning(planning):
    _publish(schema_version="gold-csv-v1")
    response = _plan_response(_plan())
    with pytest.raises(GoldPublicationInvalid):
        planning(response)


class SynthesisClient:
    def __init__(self):
        self.syntheses = 0

    async def synthesize(self, payload, *, correlation_id):
        self.syntheses += 1
        raise AssertionError("síntese não pode ocorrer")


class AuditSpy:
    def __init__(self):
        self.events = []

    def record(self, event, *, service):
        self.events.append(event.stage)
        return uuid4().hex


def _coordinate(monkeypatch, plan, *, during_execution=None):
    batch_ref = _publish()
    publication = GoldPublicationContext.capture(test_engine)
    metric = next((m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id), None)
    source = (metric or load_gold_catalog().metrics[0]).sources[0]
    planned = GoldPlanningResult(
        _plan_response(plan, catalog=None), publication, source, SCOPE,
        GenAIRequestDeadline.start(35),
    )
    executions = []

    async def fake_plan(*args, **kwargs):
        return planned

    async def gate(result):
        return GoldReadinessReport(
            readiness_version="gold-readiness-v2", batch_ref=batch_ref, lot_state="ready",
            capabilities={"faturamento.receita": {"status": "available"}},
        )

    def execute(engine, current, **kwargs):
        executions.append(current)
        if during_execution is not None:
            during_execution()
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE, message="Sem registros no recorte.",
        )

    monkeypatch.setattr(genai_coordination, "plan_gold_question", fake_plan)
    monkeypatch.setattr(genai_coordination, "execute_gold_plan", execute)
    client = SynthesisClient()
    audit = AuditSpy()
    coroutine = answer_gold_question(
        test_engine, client, AIQuestionRequest(question=QUESTION),
        resolve_scope=lambda: SCOPE, correlation_id=CORRELATION,
        readiness_gate=gate, audit_store=audit,
    )
    return coroutine, client, audit, executions


def test_batch_change_between_sql_and_synthesis_never_synthesizes(
    monkeypatch, publication_rows,
):
    coroutine, client, audit, executions = _coordinate(
        monkeypatch, _plan(), during_execution=_publish,
    )
    with pytest.raises(GoldPublicationChanged):
        asyncio.run(coroutine)
    assert len(executions) == 1
    assert client.syntheses == 0
    assert "response" not in audit.events


def test_metric_missing_in_coordinator_is_incompatible_before_sql(
    monkeypatch, publication_rows,
):
    coroutine, client, _, executions = _coordinate(monkeypatch, _plan(metric_id="metrica.retirada"))
    with pytest.raises(GoldCatalogIncompatible):
        asyncio.run(coroutine)
    assert executions == []
    assert client.syntheses == 0
