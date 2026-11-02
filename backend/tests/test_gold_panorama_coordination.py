"""Revogação, publicação e confirmação durável na fronteira do insight."""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.gold_publication import GoldPublicationChanged
from app.schemas.ai_insight import (
    AIInsightRequest,
    AIInsightResponse,
    PanoramaInsightAnalysis,
    PanoramaInsightMetric,
    PanoramaInsightRequest,
    PanoramaInsightSource,
)
from app.schemas.genai_internal import AccessScope
from app.schemas.gold_readiness import GoldReadinessReport
from app.services import gold_panorama_coordination as flow
from app.services.genai_client import GenAIResponseInvalid, GenAIServiceUnavailable
from app.services.genai_executor import GoldExecutionDenied
from tests.test_ai_insights import _upstream_response


@pytest.mark.parametrize("case", ["answered", "revoked_before", "revoked_after", "batch", "audit", "mismatch", "gate", "missing_previous", "old_lot"])
def test_gold_insight_revalidates_scope_publication_and_audit(monkeypatch, case):
    state = {"revoked": False, "changed": False, "calls": 0}
    scope = AccessScope(caller_ref="session:" + "a" * 64,
        profile_id="v-energy-grid-360-gold", source_id="gold.local",
        allowed_operations={"read"}, allowed_metric_ids={"billing.revenue"},
        allowed_dimension_ids={"geography.municipality", "customer.consumption_class"})
    def resolve():
        if state["revoked"]:
            raise GoldExecutionDenied
        return scope
    def current(engine):
        if state["changed"]:
            raise GoldPublicationChanged
    publication = SimpleNamespace(
        batch_ref="gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        reference=SimpleNamespace(schema_version="gold-csv-v2", run_id="test"), assert_current=current)
    monkeypatch.setattr(flow.GoldPublicationContext, "capture", lambda engine: publication)
    payload = PanoramaInsightRequest(filters={"periodo": "2025-03", "comparacao": "nenhuma",
        "municipio": "Cidade Teste", "classe": "RESIDENCIAL"}, loteVersao="test")
    if case == "missing_previous":
        payload = payload.model_copy(update={"filters": payload.filters.model_copy(update={"comparacao": "anterior"})})
        monkeypatch.setattr(flow, "published_revenue_periods", lambda *args: {"2025-03"})
    if case == "old_lot":
        payload = payload.model_copy(update={"loteVersao": "old"})
    prepared = AIInsightRequest(screen={"metric": "Receita comparável", "unit": "R$",
        "period": {"start": "2025-03-01", "end": "2025-03-31", "granularity": "month"},
        "filters": payload.filters.model_dump(), "observations": [{"label": "Período atual", "value": 12}],
        "reference": {"source": "gold.local", "description": "Lote autorizado.", "is_demo": False},
        "limitations": ["Fechamento mensal não certificado."]})
    metadata = (prepared, PanoramaInsightMetric(id="rec_fat", definicao="Receita comparável", formula="soma"),
        PanoramaInsightSource(kind="gold", loteVersao="test", dataAtualizacao="2026-11-01T12:00:00Z",
            isDemo=False, limitacoes=prepared.screen.limitations), PanoramaInsightAnalysis(direcao="indisponivel"))
    monkeypatch.setattr(flow, "read_gold_panorama_insight", lambda *args: metadata)

    class Readiness:
        async def evaluate_readiness(self, *args, **kwargs):
            if case == "missing_previous":
                assert kwargs["requested_periods"] == ("2025-03",)
            return GoldReadinessReport(readiness_version="gold-readiness-v2", batch_ref=publication.batch_ref,
                lot_state="ready", capabilities={"faturamento.receita": {
                    "status": "unavailable" if case == "gate" else "available",
                    "reasons": ["control_pending"] if case == "gate" else []}})

    class Audit:
        def record(self, event, **kwargs):
            if case == "audit":
                raise SQLAlchemyError("private audit detail")
            if case == "revoked_before" and event.stage == "source":
                state["revoked"] = True
            return "d" * 32

    class Client:
        async def synthesize_gold(self, body, **kwargs):
            state["calls"] += 1
            result = _upstream_response("b" * 32, body["screen"])
            result["evidence"] = [body["screen"]["reference"]]
            result["limitations"] = body["screen"]["limitations"]
            if case == "mismatch":
                result["observation"]["values"] = [{"label": "Período atual", "value": 999}]
            state["revoked"] = case == "revoked_after"
            state["changed"] = case == "batch"
            return AIInsightResponse.model_validate(result)

    async def run():
        return await flow.generate_gold_panorama_insight(None, None, Client(), Readiness(), payload,
            resolve_scope=resolve, correlation_id="b" * 32, audit_store=Audit(), approved_controls=[])
    expected = {"revoked_before": GoldExecutionDenied, "revoked_after": GoldExecutionDenied,
        "batch": GoldPublicationChanged, "audit": GenAIServiceUnavailable,
        "mismatch": GenAIResponseInvalid, "gate": GenAIServiceUnavailable,
        "old_lot": flow.StalePanoramaInsight}
    if case in {"answered", "missing_previous"}:
        result = asyncio.run(run())
        assert result.insight.audit_reference == "d" * 32
        assert result.insight.observation.values[0].value == 12
    else:
        with pytest.raises(expected[case]):
            asyncio.run(run())
    if case in {"revoked_before", "audit", "gate", "old_lot"}:
        assert state["calls"] == 0


def test_stale_gold_insight_metadata_uses_conflict(monkeypatch):
    from contextlib import contextmanager

    from app.services.analytics import AnalyticsAPIError
    from app.services.panorama_insights import StalePanoramaInsight
    @contextmanager
    def connect():
        yield None
    monkeypatch.setattr(flow, "load_gold_context", lambda *args: (_ for _ in ()).throw(
        AnalyticsAPIError(409, "stale_batch", "Publicação alterada")))
    with pytest.raises(StalePanoramaInsight):
        flow.read_gold_panorama_insight(None, SimpleNamespace(connect=connect), None,
            SimpleNamespace(loteVersao="old", fingerprint=None))


@pytest.mark.parametrize("matched", [True, False])
def test_fingerprint_preflight_prevents_model_and_quantitative_read(monkeypatch, matched):
    scope = AccessScope(caller_ref="test.reader", profile_id="v-energy-grid-360-gold",
        source_id="gold.local", allowed_operations={"read"},
        allowed_metric_ids={"billing.revenue"},
        allowed_dimension_ids={"geography.municipality", "customer.consumption_class"})
    publication = SimpleNamespace(batch_ref="current", reference=SimpleNamespace(
        schema_version="gold-csv-v2", run_id="local-test"))
    monkeypatch.setattr(flow.GoldPublicationContext, "capture", lambda engine: publication)
    def resolve(engine, expected):
        assert expected.fingerprint == "a" * 64
        if not matched:
            raise flow.ExpectedPublicationMismatch
        return "replaced-during-preflight"
    monkeypatch.setattr(flow, "resolve_expected_batch_ref", resolve)
    payload = PanoramaInsightRequest(filters={"periodo": "2025-03", "comparacao": "nenhuma",
        "municipio": "todos", "classe": "todas"}, loteVersao="local-test", fingerprint="a" * 64)
    with pytest.raises(flow.StalePanoramaInsight):
        asyncio.run(flow.generate_gold_panorama_insight(None, None, None, None, payload,
            resolve_scope=lambda: scope, correlation_id="b" * 32, audit_store=None,
            approved_controls=[]))
