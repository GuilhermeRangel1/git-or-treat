"""GENAI-13: catálogo físico, chave de cache e invalidação pela composição Gold oficial.

Contrato: docs/contracts/genai-invalidation.md (itens I1, I2, I3, I6, R1 e R3).
Modelo e auditoria são controlados; rotas, fábrica, perfil, guard e cache são reais.
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.agent.execution import authorized_cache_scope
from app.config import Settings
from app.gold_runtime import create_gold_app
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_catalog import (
    GOLD_PHYSICAL_CATALOG,
    GRID360_GOLD_RUNTIME_PROFILE,
)
from app.providers.caching import CachingModelAdapter, cache_key
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceResult
from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.physical_catalog import PhysicalCatalogRef, physical_catalog_digest
from app.schemas.read_plan import LogicalReadPlan, ReadFilter

from .conftest import FakeModelAdapter, InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_question_filters import _setup

BACKEND_CATALOG = Path(__file__).resolve().parents[2] / "backend/app/catalogs/gold_v2.json"
TOKEN = "test-gold-cache-service-token-0000000000"
AUDIT_TOKEN = "test-gold-cache-audit-token-00000000000"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Correlation-ID": "b" * 32}
QUESTION = "Receita residencial em Olinda em março de 2025?"
OTHER_BATCH = (
    "gold-csv-v2:GOLD_20000201T000000Z_bbbbbbbb:22345678-1234-4123-8123-123456789abc"
)
OTHER_CATALOG = GOLD_PHYSICAL_CATALOG.model_copy(update={"digest": "f" * 64})


class CountingModel(FakeModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def generate(self, question, context, evidence):
        self.calls += 1
        return await super().generate(question, context, evidence)


@pytest.fixture
def gold_runtime(monkeypatch):
    """create_gold_app com cache de modelo real em volta de um modelo contador."""
    from app import main
    from app.audit import BackendEventSink

    model = CountingModel()
    cached = CachingModelAdapter(model, ttl_seconds=600, max_entries=16, namespace="teste")
    monkeypatch.setattr(main, "build_model_adapter", lambda settings: cached)
    monkeypatch.setattr(BackendEventSink, "record", lambda self, event: None)
    application = create_gold_app(Settings(
        _env_file=None, service_api_token=TOKEN,
        audit_url="http://backend/api/v1/internal/genai-audit-events",
        audit_write_token=AUDIT_TOKEN,
    ))
    with InProcessClient(application) as client:
        yield client, model


def _plan(client):
    _, request = _setup(QUESTION)
    planned = client.post(
        "/api/v1/internal/question-plans", json=request.model_dump(mode="json"), headers=HEADERS,
    )
    assert planned.status_code == 200
    return request, planned.json()


def _synthesize(client, request, planned, *, batch_ref=None, catalog=GOLD_PHYSICAL_CATALOG):
    plan = LogicalReadPlan.model_validate(planned["plan"])
    lookup = _lookup(plan, batch_ref=batch_ref or request.batch_ref)
    lookup.evidence.records[0].update(
        period="2025-03", municipality="Olinda", consumption_class="RESIDENCIAL",
    )
    provenance = lookup.evidence.provenance.model_copy(update={"physical_catalog": catalog})
    lookup = lookup.model_copy(update={
        "evidence": lookup.evidence.model_copy(update={"provenance": provenance}),
    })
    payload = QuestionSynthesisRequest(
        question=request.question, access_scope=request.access_scope,
        remaining_timeout_ms=35000, plan=plan, plan_fingerprint=planned["plan_fingerprint"],
        lookup=lookup, expected_batch_ref=request.batch_ref,
    )
    response = client.post(
        "/api/v1/internal/question-syntheses", json=payload.model_dump(mode="json"),
        headers=HEADERS,
    )
    assert response.status_code == 200
    return response.json()


def _assert_failure_without_demo(body):
    assert body["status"] == "recoverable_error"
    assert body.get("answer") is None
    assert body["evidence"] == []
    assert "privad" not in json.dumps(body)


def test_catalog_identity_matches_backend_artifact_without_importing_it():
    payload = json.loads(BACKEND_CATALOG.read_text(encoding="utf-8"))
    expected = PhysicalCatalogRef(
        mapping_version=payload["mapping_version"],
        physical_schema=payload["physical_schema"],
        dictionary_version=payload["dictionary_version"],
        digest=physical_catalog_digest(payload),
    )
    assert expected == GOLD_PHYSICAL_CATALOG
    assert (GOLD_PHYSICAL_CATALOG.mapping_version, GOLD_PHYSICAL_CATALOG.physical_schema,
            GOLD_PHYSICAL_CATALOG.dictionary_version) == ("gold-catalog-v2", "gold_v2",
                                                          "gold-csv-v2")


def test_formula_change_changes_catalog_digest():
    payload = json.loads(BACKEND_CATALOG.read_text(encoding="utf-8"))
    changed = json.loads(json.dumps(payload))
    changed["metrics"][0]["aggregation"] = "ratio_of_sums"
    assert physical_catalog_digest(changed) != physical_catalog_digest(payload)


def test_official_runtime_declares_physical_catalog_only_on_ready_plans(gold_runtime):
    client, _ = gold_runtime
    _, planned = _plan(client)
    assert planned["status"] == "planned"
    assert planned["physical_catalog"] == GOLD_PHYSICAL_CATALOG.model_dump(mode="json")

    _, request = _setup("Qual foi a receita?")
    clarification = client.post(
        "/api/v1/internal/question-plans", json=request.model_dump(mode="json"), headers=HEADERS,
    ).json()
    assert clarification["status"] != "planned"
    assert "physical_catalog" not in clarification


def test_runtime_profile_differs_from_logical_profile_only_by_catalog():
    assert GRID360_GOLD_PROFILE.physical_catalog is None
    assert GRID360_GOLD_RUNTIME_PROFILE.model_copy(
        update={"physical_catalog": None}
    ) == GRID360_GOLD_PROFILE


def test_evidence_from_other_physical_catalog_is_rejected_before_model(gold_runtime):
    client, model = gold_runtime
    request, planned = _plan(client)
    body = _synthesize(client, request, planned, catalog=OTHER_CATALOG)
    _assert_failure_without_demo(body)
    assert model.calls == 0


def test_evidence_without_catalog_keeps_compatibility(gold_runtime):
    client, model = gold_runtime
    request, planned = _plan(client)
    body = _synthesize(client, request, planned, catalog=None)
    assert body["status"] == "answered"
    assert all(not item["is_demo"] for item in body["evidence"])
    assert model.calls == 1


def test_error_after_valid_cache_prevails_over_cached_answer(gold_runtime):
    client, model = gold_runtime
    request, planned = _plan(client)
    first = _synthesize(client, request, planned)
    second = _synthesize(client, request, planned)
    assert first["status"] == second["status"] == "answered"
    assert model.calls == 1, "segunda síntese idêntica deveria vir do cache"

    changed_batch = _synthesize(client, request, planned, batch_ref=OTHER_BATCH)
    _assert_failure_without_demo(changed_batch)
    changed_catalog = _synthesize(client, request, planned, catalog=OTHER_CATALOG)
    _assert_failure_without_demo(changed_catalog)
    assert model.calls == 1


def _evidence(**provenance_update) -> EvidenceResult:
    plan = _gold_plan()
    lookup = _lookup(plan, batch_ref=OTHER_BATCH)
    provenance = lookup.evidence.provenance.model_copy(
        update={"physical_catalog": GOLD_PHYSICAL_CATALOG, **provenance_update}
    )
    return lookup.evidence.model_copy(
        update={"provenance": provenance, "cache_scope": "c" * 64}
    )


def _gold_plan(filters=None) -> LogicalReadPlan:
    filters = filters or (
        ReadFilter(dimension_id="geography.municipality", operator="in",
                   values=("Olinda", "Recife")),
        ReadFilter(dimension_id="customer.consumption_class", operator="eq",
                   values=("RESIDENCIAL",)),
    )
    return LogicalReadPlan(
        catalog_version="v1", operation="read", profile_id="v-energy-grid-360-gold",
        source_id="gold.local", domain_id="revenue", metric_id="billing.revenue",
        dimension_ids=tuple(sorted({item.dimension_id for item in filters})),
        unit="R$",
        window={"kind": "bounded", "start": "2025-03-01", "end": "2025-03-31",
                "granularity": "month"},
        filters=filters, limit=100,
    )


def test_cache_key_changes_with_catalog_batch_and_readiness():
    base = cache_key(QUESTION, [], _evidence(), "ns")
    assert cache_key(QUESTION, [], _evidence(physical_catalog=OTHER_CATALOG), "ns") != base
    assert cache_key(QUESTION, [], _evidence(physical_catalog=None), "ns") != base
    quality = _evidence().provenance.quality.model_copy(update={"lot_state": "ready"})
    assert cache_key(QUESTION, [], _evidence(quality=quality), "ns") != base
    other = _lookup(_gold_plan(), batch_ref=OTHER_BATCH.replace("bbbbbbbb", "cccccccc"))
    moved = _evidence(batch_ref=other.evidence.provenance.batch_ref)
    assert cache_key(QUESTION, [], moved, "ns") != base


def test_cache_key_separates_prompt_and_model_through_namespace(monkeypatch):
    from app.providers import factory

    chain = [("gemini", "modelo-a")]
    base = factory._cache_namespace(["gemini"], chain)
    assert factory._cache_namespace(["gemini"], [("gemini", "modelo-b")]) != base
    monkeypatch.setattr(factory, "SYSTEM_INSTRUCTION", "instrucoes alteradas")
    assert factory._cache_namespace(["gemini"], chain) != base
    evidence = _evidence()
    assert cache_key(QUESTION, [], evidence, base) != cache_key(QUESTION, [], evidence, "outro")


def test_cache_key_normalizes_filter_order_without_changing_plan_fingerprint():
    ordered = _gold_plan()
    reordered = _gold_plan(filters=(
        ReadFilter(dimension_id="customer.consumption_class", operator="eq",
                   values=("RESIDENCIAL",)),
        ReadFilter(dimension_id="geography.municipality", operator="in",
                   values=("Recife", "Olinda")),
    ))
    assert ordered.fingerprint() != reordered.fingerprint()

    def evidence_for(plan):
        return _evidence(filters=plan.filters, plan_fingerprint=plan.fingerprint())

    first = evidence_for(ordered)
    second = evidence_for(reordered).model_copy(
        update={"provenance": evidence_for(reordered).provenance.model_copy(
            update={"plan_fingerprint": ordered.fingerprint()}
        )}
    )
    assert cache_key(QUESTION, [], first, "ns") == cache_key(QUESTION, [], second, "ns")
    narrowed = _gold_plan(filters=(
        ReadFilter(dimension_id="geography.municipality", operator="eq", values=("Recife",)),
    ))
    assert cache_key(QUESTION, [], evidence_for(narrowed), "ns") != cache_key(
        QUESTION, [], first, "ns"
    )


def _context(caller: str, metrics=("billing.revenue",), correlation="d" * 32) -> AccessContext:
    return AccessContext(
        correlation_id=correlation, caller_ref=caller,
        profile_id="v-energy-grid-360-gold", source_id="gold.local",
        allowed_operations={"read"}, allowed_metric_ids=set(metrics),
        allowed_dimension_ids={"geography.municipality", "customer.consumption_class"},
    )


def test_authorized_scope_isolates_access_and_ignores_filter_order():
    plan = _gold_plan()
    reordered = _gold_plan(filters=tuple(reversed(plan.filters)))
    owner = _context("user.a")
    assert authorized_cache_scope(owner, plan) == authorized_cache_scope(owner, reordered)
    # Correlação é transitória e não separa entradas.
    assert authorized_cache_scope(owner, plan) == authorized_cache_scope(
        _context("user.a", correlation="e" * 32), plan
    )
    assert authorized_cache_scope(owner, plan) != authorized_cache_scope(_context("user.b"), plan)
    widened = _context("user.a", metrics=("billing.revenue", "energy.consumption"))
    assert authorized_cache_scope(owner, plan) != authorized_cache_scope(widened, plan)


def test_catalog_change_invalidates_cache_before_ttl_expires():
    model = CountingModel()
    now = [0.0]
    cached = CachingModelAdapter(
        model, ttl_seconds=3600, max_entries=8, namespace="ns", clock=lambda: now[0],
    )
    evidence = _evidence()
    record = {**evidence.records[0], "observation_id": "row_1"}
    current = evidence.model_copy(update={"records": [record]})
    asyncio.run(cached.generate(QUESTION, [], current))
    asyncio.run(cached.generate(QUESTION, [], current))
    assert model.calls == 1
    now[0] = 1.0
    changed = current.model_copy(update={"provenance": current.provenance.model_copy(
        update={"physical_catalog": OTHER_CATALOG}
    )})
    asyncio.run(cached.generate(QUESTION, [], changed))
    assert model.calls == 2, "TTL vigente não pode reaproveitar resposta de outro catálogo"
