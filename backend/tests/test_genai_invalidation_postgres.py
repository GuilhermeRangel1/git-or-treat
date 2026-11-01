"""GENAI-13 no PostgreSQL: schema alterado, catálogo físico e escopo de cache na evidência.

Contrato: docs/contracts/genai-invalidation.md (itens I1, I2, R1 e R3). Executor, snapshot,
migrações e catálogo são reais; linhas e publicação são artificiais. Exige o banco
descartável ``v_energy_test`` preparado por ``scripts/prepare_test_postgres.sql``.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, text
from sqlalchemy.engine import make_url

from app.models.gold_v2_load import BATCH, TABLES
from app.schemas.genai_evidence import EvidenceLookupStatus, GoldEvidenceQuality
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.schemas.genai_physical_catalog import PhysicalCatalogRef
from app.schemas.genai_plan import LogicalReadPlan
from app.services import genai_executor
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import execute_gold_plan
from app.services.genai_planning import GoldPlanningResult, _admit_plan
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_catalog import GoldCatalogIncompatible, gold_physical_catalog
from tests.support.migrations import migrated_database

SCOPE = AccessScope(
    caller_ref="user.invalidacao", profile_id="v-energy-grid-360-gold",
    source_id="gold.local", allowed_operations={"read"},
    allowed_metric_ids={"billing.revenue"},
    allowed_dimension_ids={"geography.municipality", "customer.consumption_class"},
)
MUNICIPALITY = {"dimension_id": "geography.municipality", "operator": "eq", "values": ["Recife"]}
CLASS = {"dimension_id": "customer.consumption_class", "operator": "eq",
         "values": ["RESIDENCIAL"]}


@pytest.fixture
def gold_v2_postgres():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Configure PostgreSQL descartável v_energy_test.")
    assert make_url(url).database == "v_energy_test"
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection, migrated_database(connection):
            connection.execute(insert(BATCH).values(
                id=1, lote="GOLD_20250301T000000Z_deadbeef", fingerprint="a" * 64,
                importado_em=datetime.now(UTC), manifesto={}, schema_version="gold-csv-v2",
                publication_id=str(uuid4()),
                origem={"run_id_silver": "silver-run", "lote_bronze_silver": "bronze-run"},
            ))
            for classe, receita in (("RESIDENCIAL", 100), ("COMERCIAL", 40)):
                connection.execute(insert(TABLES["diagnostico_receita"]).values(
                    competencia="2025-03", municipio="Recife", classe_consumo=classe,
                    subgrupo_tarifario="B1", bandeira_tarifaria="Verde", possui_gd="Não",
                    receita_total_reais=receita, consumo_total_kwh=10,
                ))
            connection.commit()
            yield engine
    finally:
        engine.dispose()


def _plan(filters) -> LogicalReadPlan:
    return LogicalReadPlan.model_validate({
        "catalog_version": "v1", "operation": "read",
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "domain_id": "revenue", "metric_id": "billing.revenue", "unit": "R$",
        "dimension_ids": sorted({item["dimension_id"] for item in filters}),
        "window": {"kind": "bounded", "start": "2025-03-01", "end": "2025-03-31",
                   "granularity": "month"},
        "filters": filters, "limit": 100,
    })


def _execute(engine, filters=(MUNICIPALITY, CLASS)):
    plan = _plan(list(filters))
    publication = GoldPublicationContext.capture(engine)
    response = QuestionPlanResponse(
        correlation_id="c" * 32, status="planned", plan=plan, plan_fingerprint=plan.fingerprint(),
    )
    planned = GoldPlanningResult(
        response, publication, _admit_plan(plan, SCOPE), SCOPE, GenAIRequestDeadline.start(35),
    )
    quality = GoldEvidenceQuality(
        readiness_version="gold-readiness-v2", batch_ref=publication.batch_ref,
        lot_state="ready", available_capability_ids=("faturamento.receita",),
    )
    return execute_gold_plan(engine, planned, resolve_scope=lambda: SCOPE, quality=quality), plan


def test_executor_declares_catalog_and_scopes_cache_by_catalog_not_filter_order(
    gold_v2_postgres, monkeypatch,
):
    result, plan = _execute(gold_v2_postgres)
    assert result.status is EvidenceLookupStatus.AVAILABLE
    assert result.evidence.records[0]["value"] == 100
    assert result.evidence.provenance.physical_catalog == gold_physical_catalog()
    wire = result.model_dump(mode="json")["evidence"]
    assert wire["provenance"]["physical_catalog"]["mapping_version"] == "gold-catalog-v2"
    assert "cache_scope" not in wire

    reordered, reordered_plan = _execute(gold_v2_postgres, filters=(CLASS, MUNICIPALITY))
    assert reordered_plan.fingerprint() != plan.fingerprint()
    assert reordered.evidence.cache_scope == result.evidence.cache_scope

    other = PhysicalCatalogRef(**{**gold_physical_catalog().model_dump(), "digest": "f" * 64})
    monkeypatch.setattr(genai_executor, "gold_physical_catalog", lambda: other)
    changed, _ = _execute(gold_v2_postgres)
    assert changed.evidence.provenance.physical_catalog == other
    assert changed.evidence.cache_scope != result.evidence.cache_scope


def _column_type(connection) -> str:
    return connection.execute(text(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = 'gold_v2.diagnostico_receita'::regclass "
        "AND attname = 'receita_total_reais'"
    )).scalar_one()


@pytest.mark.parametrize("change,restore", [
    (
        "ALTER TABLE gold_v2.diagnostico_receita RENAME COLUMN receita_total_reais "
        "TO receita_renomeada",
        "ALTER TABLE gold_v2.diagnostico_receita RENAME COLUMN receita_renomeada "
        "TO receita_total_reais",
    ),
    (
        "ALTER TABLE gold_v2.diagnostico_receita ALTER COLUMN receita_total_reais "
        "TYPE text USING receita_total_reais::text",
        "ALTER TABLE gold_v2.diagnostico_receita ALTER COLUMN receita_total_reais "
        "TYPE {original} USING receita_total_reais::{original}",
    ),
    (
        "ALTER TABLE gold_v2.diagnostico_receita RENAME TO diagnostico_receita_antiga",
        "ALTER TABLE gold_v2.diagnostico_receita_antiga RENAME TO diagnostico_receita",
    ),
], ids=["coluna-renomeada", "tipo-alterado", "tabela-renomeada"])
def test_schema_drift_fails_closed_as_incompatible_and_recovers(
    gold_v2_postgres, change, restore,
):
    with gold_v2_postgres.begin() as connection:
        original = _column_type(connection)
        connection.execute(text(change))
    try:
        with pytest.raises(GoldCatalogIncompatible):
            _execute(gold_v2_postgres)
    finally:
        with gold_v2_postgres.begin() as connection:
            connection.execute(text(restore.format(original=original)))
    recovered, _ = _execute(gold_v2_postgres)
    assert recovered.status is EvidenceLookupStatus.AVAILABLE
