"""Metadados v2 de planejamento limitados à publicação e ao escopo."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, update

from app.models.gold_v2_load import BATCH, TABLES
from app.repositories.gold_publication import GoldPublicationChanged
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
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
