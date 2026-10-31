"""Metadados v2 de planejamento limitados à publicação e ao escopo."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, insert, update

from app.models.gold_v2_load import BATCH, TABLES
from app.repositories.gold_publication import GoldPublicationChanged
from app.schemas.ai import AIQuestionRequest
from app.schemas.genai_internal import (
    AccessScope,
    QuestionPlanRequest,
    QuestionSynthesisRequest,
)
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_planning import plan_gold_question
from app.services.genai_publication import GoldPublicationContext
from tests.support.migrations import migrated_database


@pytest.fixture
def gold_v2_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'gold-v2.db').as_posix()}"
    ).execution_options(schema_translate_map={"gold": None, "gold_v2": None})
    try:
        with engine.connect() as connection, migrated_database(connection):
            run_id = "GOLD_20250301T000000Z_deadbeef"
            connection.execute(
                insert(BATCH).values(
                    id=1,
                    lote=run_id,
                    fingerprint="a" * 64,
                    importado_em=datetime.now(UTC),
                    manifesto={},
                    schema_version="gold-csv-v2",
                    publication_id=str(uuid4()),
                    origem={
                        "run_id_silver": "silver-run",
                        "lote_bronze_silver": "bronze-run",
                    },
                )
            )
            connection.execute(
                insert(TABLES["diagnostico_receita"]).values(
                    competencia="2025-03",
                    municipio="Recife",
                    classe_consumo="Residencial",
                    subgrupo_tarifario="B1",
                    bandeira_tarifaria="Verde",
                    possui_gd="Não",
                    receita_total_reais=100,
                    consumo_total_kwh=50,
                )
            )
            connection.execute(
                insert(TABLES["consumo_receita_bairro"]).values(
                    competencia="2025-04",
                    municipio="Olinda",
                    bairro="Centro",
                    classe_consumo="Residencial",
                    receita_total_reais=200,
                    consumo_total_kwh=70,
                )
            )
            connection.execute(
                insert(TABLES["consumo_mensal_uc"]).values(
                    id_uc="UC-ARTIFICIAL-01",
                    competencia="2025-05",
                    receita_reais=300,
                    consumo_kwh=80,
                )
            )
            connection.commit()
            yield engine
    finally:
        engine.dispose()


def test_planning_fields_use_gold_v2_and_only_authorized_public_vocabulary(
    gold_v2_database,
):
    scope = AccessScope(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_operations=frozenset({"read"}),
        allowed_metric_ids=frozenset({"billing.revenue", "energy.consumption"}),
        allowed_dimension_ids=frozenset(
            {
                "geography.municipality",
                "geography.neighborhood",
                "customer.consumer_unit",
            }
        ),
    )
    context = GoldPublicationContext.capture(gold_v2_database)

    fields = context.planning_fields(gold_v2_database, scope)

    assert fields["batch_ref"].startswith("gold-csv-v2:GOLD_20250301T000000Z_deadbeef:")
    coverage = {item["metric_id"]: item for item in fields["temporal_coverage"]}
    assert coverage["billing.revenue"]["competencies"] == [
        "2025-03",
        "2025-04",
        "2025-05",
    ]
    assert coverage["energy.consumption"]["competencies"] == [
        "2025-03",
        "2025-04",
        "2025-05",
    ]
    dimensions = {
        item["dimension_id"]: item["values"]
        for item in fields["dimension_value_coverage"]
    }
    assert dimensions["geography.municipality"] == ["Olinda", "Recife"]
    assert dimensions["geography.neighborhood"] == ["Centro"]
    assert "customer.consumer_unit" not in dimensions

    request = QuestionPlanRequest.model_validate(
        {
            "question": "Qual foi a receita em Recife?",
            "context": [],
            "remaining_timeout_ms": 35000,
            "access_scope": scope.model_dump(mode="json"),
            **fields,
        }
    )
    assert request.batch_ref == fields["batch_ref"]


def test_planning_fields_reject_a_non_gold_profile(gold_v2_database):
    context = GoldPublicationContext.capture(gold_v2_database)
    scope = AccessScope(
        caller_ref="user.test",
        profile_id="other-profile",
        source_id="gold.local",
        allowed_operations=frozenset({"read"}),
    )

    with pytest.raises(ValueError, match="perfil fora do catálogo"):
        context.planning_fields(gold_v2_database, scope)


def test_planning_fields_require_read_permission(gold_v2_database):
    context = GoldPublicationContext.capture(gold_v2_database)
    scope = AccessScope(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_metric_ids=frozenset({"billing.revenue"}),
    )

    with pytest.raises(ValueError, match="operação de leitura"):
        context.planning_fields(gold_v2_database, scope)


def test_planning_fields_reject_metadata_from_a_replaced_publication(gold_v2_database):
    context = GoldPublicationContext.capture(gold_v2_database)
    scope = AccessScope(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_operations=frozenset({"read"}),
        allowed_metric_ids=frozenset({"billing.revenue"}),
    )
    with gold_v2_database.begin() as connection:
        connection.execute(
            update(BATCH)
            .where(BATCH.c.id == 1)
            .values(
                lote="GOLD_20250302T000000Z_deadbeef",
                publication_id=str(uuid4()),
            )
        )

    with pytest.raises(GoldPublicationChanged):
        context.planning_fields(gold_v2_database, scope)


@pytest.mark.parametrize(
    "month,status,revoke",
    [("abril de 2025", "planned", False),
     ("junho de 2025", "needs_clarification", False),
     ("março de 2025", "needs_clarification", False),
     ("abril de 2025", "refused", True)],
)
def test_database_metadata_drives_the_composed_genai_plan(
    gold_v2_database, month, status, revoke
):
    """Banco → produtor → cliente Backend → HTTP ASGI GenAI → núcleo, sem imports cruzados."""
    genai_root = Path(__file__).resolve().parents[2] / "ai-agent"
    if not (genai_root / "app/agent/composition.py").is_file():
        pytest.skip("A imagem Backend isolada não contém GenAI; execute no checkout completo.")
    scope = AccessScope(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={"billing.revenue"},
        allowed_dimension_ids={
            "geography.municipality",
            "geography.neighborhood",
            "customer.consumption_class",
        },
    )
    publication = GoldPublicationContext.capture(gold_v2_database)
    request = QuestionPlanRequest.model_validate(
        {
            "question": f"Receita residencial em Olinda no bairro Centro em {month}?",
            "remaining_timeout_ms": 35000,
            "access_scope": scope,
            **publication.planning_fields(gold_v2_database, scope),
        }
    )
    code = """
import asyncio, json, sys, httpx
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
class NoExternalCalls:
    async def retrieve(self, *args, **kwargs):
        raise AssertionError("Planning must not execute an evidence lookup")
    async def generate(self, *args, **kwargs):
        raise AssertionError("Planning must not call a model")
class TestAudit:
    durable = True
    def record(self, event):
        pass
incoming = json.load(sys.stdin)
app = create_app(settings=Settings(_env_file=None, enable_demo_access=False,
        service_api_token="test-planning-service-token-0000000000"),
    domain_profile=GRID360_GOLD_PROFILE, source_id="gold.local", source_mode="external",
    evidence_source=NoExternalCalls(), model_adapter=NoExternalCalls(),
    access_context_resolver=lambda request: None, event_sink=TestAudit(),
    require_durable_audit=True)
async def send():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://genai") as client:
        result = await client.post(incoming["path"], json=incoming["payload"],
                                   headers=incoming["headers"])
        return {"status": result.status_code, "headers": dict(result.headers),
                "body": result.json()}
print(json.dumps(asyncio.run(send())))
"""
    def dispatch(outgoing):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            input=json.dumps({
                "path": outgoing.url.path,
                "payload": json.loads(outgoing.content),
                "headers": dict(outgoing.headers),
            }),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            encoding="utf-8",
            cwd=genai_root,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        result = json.loads(completed.stdout)
        return httpx.Response(result["status"], headers=result["headers"], json=result["body"])

    async def plan():
        async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch)) as transport:
            client = GenAIQuestionClient(
                http_client=transport, base_url="http://genai",
                service_token="test-planning-service-token-0000000000",
            )
            scope_reads = 0
            def resolve_scope():
                nonlocal scope_reads
                scope_reads += 1
                if revoke and scope_reads > 1:
                    return scope.model_copy(update={"allowed_metric_ids": frozenset()})
                return scope
            admitted = await plan_gold_question(
                gold_v2_database, client, AIQuestionRequest(question=request.question),
                resolve_scope=resolve_scope, correlation_id="a" * 32,
                expected_batch_ref=publication.batch_ref,
            )
            result = admitted.response
            if result.plan is not None:
                assert admitted.source.table == "consumo_receita_bairro"
                assert admitted.publication.batch_ref == publication.batch_ref
            if result.plan is not None:
                synthesis = QuestionSynthesisRequest(
                    question=request.question,
                    access_scope=scope,
                    remaining_timeout_ms=35000,
                    plan=result.plan,
                    plan_fingerprint=result.plan_fingerprint,
                    expected_batch_ref=publication.batch_ref,
                    lookup={"status": "no_evidence", "message": "Sem registros no recorte."},
                )
                answer = await client.synthesize(synthesis, correlation_id="a" * 32)
                assert answer.status == "no_evidence"
                assert answer.answer is None
                assert answer.correlation_id == "a" * 32
            return result

    response = asyncio.run(plan())
    publication.assert_current(gold_v2_database)
    assert response.status.value == status
    if status != "planned":
        assert response.plan is None
        return
    assert response.plan.metric_id == "billing.revenue"
    assert response.plan.window.start.isoformat() == "2025-04-01"
    assert response.plan.window.end.isoformat() == "2025-04-30"
    assert {item.dimension_id: item.values for item in response.plan.filters} == {
        "geography.municipality": ("Olinda",),
        "geography.neighborhood": ("Centro",),
        "customer.consumption_class": ("Residencial",),
    }
    assert response.plan_fingerprint == response.plan.fingerprint()
