"""Prontidão por domínio pela operação pública do Backend, com banco controlado."""

import pytest

from app.services.gold_attendance_readiness import observe_domain_readiness
from tests.test_gold_attendance_readiness import published  # noqa: F401


def test_domain_observation_does_not_promote_missing_measures_to_zero(published):  # noqa: F811
    facts = observe_domain_readiness(
        published,
        requested_periods=("2001-01",),
        approved_controls=frozenset({"C01", "C02", "C04", "C11"}),
    )
    for key in ("C01", "C02", "C04", "C11"):
        assert facts["control_results"][key]["status"] == "failed"
    assert facts["control_results"]["C14"]["status"] == "passed"
    assert "UC_PRIVATE" not in str(facts)


def test_gd_controls_reject_missing_uc_from_the_reference_population(published):  # noqa: F811
    from sqlalchemy import select
    from app.models.gold_v2_load import TABLES

    with published.begin() as connection:
        reference = connection.execute(select(TABLES["visao_360_uc"])).mappings().first()
        connection.execute(TABLES["variacao_consumo_uc"].delete())
        connection.execute(TABLES["variacao_consumo_uc"].insert(), {
            "id_uc": reference["id_uc"], "municipio": reference["municipio"],
            "possui_gd": reference["possui_gd"], "meses_com_leitura_p1": 0,
            "meses_com_leitura_p2": 0, "queda_consumo_superior_30_pct": False,
        })
    facts = observe_domain_readiness(published, requested_periods=(),
                                    approved_controls=frozenset({"C08", "C09"}))
    assert all(facts["control_results"][key]["status"] == "passed" for key in ("C08", "C09"))
    with published.begin() as connection:
        connection.execute(TABLES["visao_360_uc"].insert(), {"id_uc": "MISSING_PRIVATE"})
    facts = observe_domain_readiness(published, requested_periods=(),
                                    approved_controls=frozenset({"C08", "C09"}))
    assert all(facts["control_results"][key]["status"] == "failed" for key in ("C08", "C09"))
    assert "MISSING_PRIVATE" not in str(facts)


def test_gd_control_does_not_accept_non_finite_values_as_missing_measurements():
    from sqlalchemy import Table
    from app.services.gold_variation_controls import observe_variation_controls

    population = {"SYNTHETIC": {"municipio": "Cidade", "possui_gd": "Sim"}}
    def read_rows(statement):
        if isinstance(statement, Table):
            return [{"id_uc": "SYNTHETIC", "municipio": "Cidade", "possui_gd": "Sim",
                     "consumo_medio_inicial": float("nan"), "consumo_medio_final": float("nan"),
                     "meses_com_leitura_p1": 12, "meses_com_leitura_p2": 12,
                     "queda_consumo_superior_30_pct": False, "variacao_pct": None}]
        return [{"id_uc": "SYNTHETIC", "mean0": float("nan"), "mean1": float("nan"),
                 "months0": 12, "months1": 12}]
    assert observe_variation_controls(read_rows, population=population) == {
        "C08": False, "C09": False,
    }


def seed_measures(engine):
    from app.models.gold_v2_load import TABLES

    with engine.begin() as c:
        c.execute(
            TABLES["visao_360_uc"]
            .update()
            .values(
                municipio="Municipio",
                bairro="Bairro",
                classe="Classe",
                alimentador="ALIM",
                media_consumo_historico=10,
            )
        )
        c.execute(
            TABLES["consumo_mensal_uc"].insert(),
            {
                "id_uc": "UC_PRIVATE",
                "competencia": "2001-01",
                "consumo_kwh": 10,
                "receita_reais": 20,
                "tem_fatura": True,
                "tem_leitura": True,
                "qtd_faturas": 1,
                "qtd_leituras_observadas": 1,
            },
        )
        c.execute(
            TABLES["diagnostico_receita"].insert(),
            {
                "competencia": "2001-01",
                "municipio": "Municipio",
                "classe_consumo": "Classe",
                "subgrupo_tarifario": "B",
                "bandeira_tarifaria": "Verde",
                "possui_gd": "Não",
                "consumo_total_kwh": 10,
                "receita_total_reais": 20,
                "qtd_ucs_distintas_faturadas_no_mes": 1,
            },
        )
        c.execute(
            TABLES["consumo_receita_bairro"].insert(),
            {
                "competencia": "2001-01",
                "municipio": "Municipio",
                "bairro": "Bairro",
                "classe_consumo": "Classe",
                "consumo_total_kwh": 10,
                "receita_total_reais": 20,
                "qtd_ucs_distintas_faturadas_no_mes": 1,
            },
        )


def test_revenue_and_consumption_reconcile_without_releasing_unclosed_months(published):  # noqa: F811
    seed_measures(published)
    facts = observe_domain_readiness(
        published,
        requested_periods=("2001-01",),
        approved_controls=frozenset({"C01", "C02", "C03", "C04", "C10", "C12", "C13"}),
    )
    for key in ("C01", "C02", "C03", "C04", "C10", "C12", "C13"):
        assert facts["control_results"][key]["status"] == "passed"
    assert facts["coverage"]["faturamento.receita"]["closed_periods"] == []
    assert facts["coverage"]["consumo.mensal_uc"]["closed_periods"] == []


def test_continuity_uses_events_and_population_instead_of_summing_ratios(published):  # noqa: F811
    from datetime import datetime

    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(
            TABLES["ocorrencias_uc"].insert(),
            {
                "id_ocorrencia": "EVENT_PRIVATE",
                "id_uc": "UC_PRIVATE",
                "alimentador": "ALIM",
                "data_abertura": datetime(2001, 1, 1),
                "duracao_min": 120,
                "flag_duracao_incompativel": False,
                "flag_abertura_futura": False,
                "flag_encerramento_futuro": False,
            },
        )
        c.execute(
            TABLES["indicadores_dec_fec"].insert(),
            {
                "id_alimentador": "ALIM",
                "competencia": "2001-01",
                "total_ucs_alimentador": 1,
                "ucs_interrompidas": 1,
                "frequencia_total_interrupcoes": 1,
                "duracao_total_interrupcoes_horas": 2,
                "DEC": 2,
                "FEC": 1,
            },
        )
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset({"C11"})
    )
    assert facts["control_results"]["C11"]["status"] == "passed"
    assert facts["coverage"]["interrupcoes.dec_fec"]["closed_periods"] == []
    assert "EVENT_PRIVATE" not in str(facts)




@pytest.mark.parametrize(
    "table,field,value,control",
    [
        ("diagnostico_receita", "receita_total_reais", 21, "C01"),
        ("diagnostico_receita", "classe_consumo", "Outra", "C02"),
        ("diagnostico_receita", "municipio", "Outro", "C04"),
        ("consumo_mensal_uc", "qtd_faturas", None, "C01"),
        ("consumo_mensal_uc", "tem_leitura", None, "C03"),
        ("visao_360_uc", "media_consumo_historico", float("inf"), "C10"),
        ("consumo_receita_bairro", "consumo_total_kwh", 11, "C12"),
        ("diagnostico_receita", "receita_total_reais", None, "C01"),
    ],
)
def test_bad_measures_block_only_dependent_controls(
    published,  # noqa: F811 - fixture compartilhada
    table,
    field,
    value,
    control,
):
    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(TABLES[table].update().values({field: value}))
    facts = observe_domain_readiness(
        published,
        requested_periods=("2001-01",),
        approved_controls=frozenset({control}),
    )
    assert facts["control_results"][control]["status"] == "failed"
    assert facts["control_results"]["C14"]["status"] == "passed"


@pytest.mark.parametrize(
    "case",
    ["closed", "partial", "lineage", "count", "undated", "future_cut", "no_evidence"],
)
def test_monthly_coverage_requires_evidence_and_reconciliation(published, case):  # noqa: F811
    from datetime import UTC, datetime

    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    row = {
        "dominio": "faturamento",
        "recorte": "DOMINIO",
        "competencia": "2001-01",
        "qtd_registros": 1,
        "qtd_sem_competencia": 0,
        "zero_registros_confirmado": False,
        "estado_cobertura": "FECHADO",
        "run_id_silver": "silver_test",
        "lote_bronze_silver": "bronze_test",
        "referencia_evidencia": "controlled-evidence",
        "natureza_certificacao": "FECHAMENTO_CONTABIL",
        "data_corte_evidencia": datetime(2001, 2, 1, tzinfo=UTC),
    }
    if case == "partial":
        row["estado_cobertura"] = "PARCIAL"
    if case == "lineage":
        row["run_id_silver"] = "other"
    if case == "count":
        row["qtd_registros"] = 2
    if case == "undated":
        row["qtd_sem_competencia"] = 1
    if case == "future_cut":
        row["data_corte_evidencia"] = datetime(2999, 2, 1, tzinfo=UTC)
    if case == "no_evidence":
        row["referencia_evidencia"] = None
    with published.begin() as c:
        c.execute(TABLES["cobertura_dominios"].insert(), row)
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset()
    )
    assert facts["coverage"]["faturamento.receita"]["closed_periods"] == (
        ["2001-01"] if case == "closed" else []
    )
    assert not facts["control_results"]["C01"]["approved"]


@pytest.mark.parametrize("case", ["same", "different", "changed"])
def test_domain_transport_keeps_controls_and_revalidates_publication(published, case):  # noqa: F811
    import asyncio
    import json
    from uuid import uuid4

    import httpx

    from app.models.gold_v2_load import BATCH
    from app.repositories.gold_publication import GoldPublicationChanged
    from app.services.genai_client import GenAIResponseInvalid
    from app.services.gold_readiness import evaluate_domain_readiness

    seed_measures(published)

    def transport(request):
        facts = json.loads(request.content)
        assert facts["control_results"]["C01"]["status"] == "passed"
        assert facts["coverage"]["faturamento.receita"]["closed_periods"] == []
        assert request.headers["authorization"] == "Bearer controlled-token"
        keys = (
            "faturamento.receita",
            "faturamento.receita_bairro",
            "faturamento.preco_volume",
            "faturamento.faturas_em_aberto",
            "consumo.mensal_uc",
            "consumo.variacao_uc",
            "interrupcoes.dec_fec",
            "interrupcoes.uc_acumulado",
            "atendimento.uc_acumulado",
            "atendimento.mensal",
            "apoio.fila_inspecao",
            "apoio.medidor_uc",
            "apoio.energia_recuperavel",
        )
        ref = facts["batch_ref"]
        if case == "different":
            ref = ref.rsplit(":", 1)[0] + ":" + str(uuid4())
        if case == "changed":
            with published.begin() as c:
                c.execute(BATCH.update().values(publication_id=str(uuid4())))
        return httpx.Response(
            200,
            json={
                "readiness_version": "gold-readiness-v2",
                "batch_ref": ref,
                "lot_state": "partial",
                "capabilities": {
                    k: {"status": "unavailable", "reasons": ["coverage_incomplete"]}
                    for k in keys
                },
            },
            headers={"X-Correlation-ID": "a" * 32},
        )

    expected = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset()
    )["batch_ref"]

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            return await evaluate_domain_readiness(
                published,
                http_client=client,
                base_url="http://genai",
                service_token="controlled-token",
                requested_periods=("2001-01",),
                approved_controls=frozenset({"C01", "C02", "C04"}),
                correlation_id="a" * 32,
                expected_batch_ref=expected,
            )

    if case == "same":
        assert asyncio.run(run()).lot_state == "partial"
    else:
        with pytest.raises(
            GenAIResponseInvalid if case == "different" else GoldPublicationChanged
        ):
            asyncio.run(run())


@pytest.mark.parametrize("case", ["both", "global_only", "feeder_partial"])
def test_continuity_requires_coverage_for_feeders_and_global_domain(published, case):  # noqa: F811
    from datetime import datetime

    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(
            TABLES["ocorrencias_uc"].insert(),
            {
                "id_ocorrencia": "EVENT",
                "id_uc": "UC_PRIVATE",
                "alimentador": "ALIM",
                "data_abertura": datetime(2001, 1, 1),
                "duracao_min": 60,
                "flag_duracao_incompativel": False,
                "flag_abertura_futura": False,
                "flag_encerramento_futuro": False,
            },
        )
        c.execute(
            TABLES["indicadores_dec_fec"].insert(),
            {
                "id_alimentador": "ALIM",
                "competencia": "2001-01",
                "total_ucs_alimentador": 1,
                "ucs_interrompidas": 1,
                "frequencia_total_interrupcoes": 1,
                "duracao_total_interrupcoes_horas": 1,
                "DEC": 1,
                "FEC": 1,
            },
        )
        for recorte in (
            ["DOMINIO"] if case == "global_only" else ["DOMINIO", "ALIMENTADOR:ALIM"]
        ):
            c.execute(
                TABLES["cobertura_dominios"].insert(),
                {
                    "dominio": "ocorrencias",
                    "competencia": "2001-01",
                    "recorte": recorte,
                    "estado_cobertura": "PARCIAL"
                    if case == "feeder_partial" and recorte != "DOMINIO"
                    else "FECHADO",
                    "qtd_registros": 1,
                    "qtd_sem_competencia": 0,
                    "zero_registros_confirmado": False,
                    "run_id_silver": "silver_test",
                    "lote_bronze_silver": "bronze_test",
                    "data_corte_evidencia": datetime(2001, 2, 1),
                    "referencia_evidencia": "controlled",
                    "natureza_certificacao": "FECHAMENTO_CONTABIL",
                },
            )
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset({"C11"})
    )
    assert facts["coverage"]["interrupcoes.dec_fec"]["closed_periods"] == (
        ["2001-01"] if case == "both" else []
    )


@pytest.mark.parametrize("case", ["valid", "missing", "excluded", "bad_hash"])
def test_extraction_evidence_must_preserve_its_control_counts(published, case):  # noqa: F811
    import json
    from datetime import datetime

    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    evidence = {
        "registros_origem": 1,
        "registros_aceitos": 1,
        "registros_excluidos": 0,
        "hash_inventario": "a" * 64,
    }
    if case == "excluded":
        evidence.update(registros_origem=2, registros_excluidos=1)
    if case == "bad_hash":
        evidence["hash_inventario"] = "invalid"
    with published.begin() as c:
        c.execute(
            TABLES["cobertura_dominios"].insert(),
            {
                "dominio": "faturamento",
                "competencia": "2001-01",
                "recorte": "DOMINIO",
                "estado_cobertura": "FECHADO",
                "qtd_registros": 1,
                "qtd_sem_competencia": 0,
                "zero_registros_confirmado": False,
                "run_id_silver": "silver_test",
                "lote_bronze_silver": "bronze_test",
                "data_corte_evidencia": datetime(2001, 2, 1),
                "referencia_evidencia": "controlled",
                "natureza_certificacao": "EXTRACAO",
                "reconciliacao_extracao_json": None
                if case == "missing"
                else json.dumps(evidence),
            },
        )
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset()
    )
    assert facts["coverage"]["faturamento.receita"]["closed_periods"] == (
        ["2001-01"] if case == "valid" else []
    )


def test_historical_mean_is_per_reading_not_per_month(published):  # noqa: F811
    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(
            TABLES["consumo_mensal_uc"]
            .update()
            .values(consumo_kwh=30, qtd_leituras_observadas=2)
        )
        c.execute(TABLES["visao_360_uc"].update().values(media_consumo_historico=15))
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset({"C10"})
    )
    assert facts["control_results"]["C10"]["status"] == "passed"


@pytest.mark.parametrize(
    "first,second", [("São José", "SÃ£o JosÃ©"), ("Boa Vista", "Boa  Vista")]
)
def test_bairro_control_handles_encoding_and_internal_spaces(published, first, second):  # noqa: F811
    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(TABLES["consumo_receita_bairro"].update().values(bairro=first))
        c.execute(
            TABLES["consumo_receita_bairro"].insert(),
            {
                "competencia": "2001-02",
                "municipio": "Municipio",
                "bairro": second,
                "classe_consumo": "Classe",
            },
        )
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset({"C13"})
    )
    assert facts["control_results"]["C13"]["status"] == "failed"


def test_closed_month_with_only_null_measure_is_not_usable(published):  # noqa: F811
    from datetime import datetime

    from app.models.gold_v2_load import TABLES

    seed_measures(published)
    with published.begin() as c:
        c.execute(TABLES["consumo_mensal_uc"].update().values(consumo_kwh=None))
        c.execute(
            TABLES["cobertura_dominios"].insert(),
            {
                "dominio": "consumo",
                "competencia": "2001-01",
                "recorte": "DOMINIO",
                "estado_cobertura": "FECHADO",
                "qtd_registros": 1,
                "qtd_sem_competencia": 0,
                "zero_registros_confirmado": False,
                "run_id_silver": "silver_test",
                "lote_bronze_silver": "bronze_test",
                "data_corte_evidencia": datetime(2001, 2, 1),
                "referencia_evidencia": "controlled",
                "natureza_certificacao": "FECHAMENTO_CONTABIL",
            },
        )
    facts = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset()
    )
    assert facts["coverage"]["consumo.mensal_uc"]["observed_periods"] == []


def test_domain_aggregates_execute_with_nonempty_postgres_publication(published):  # noqa: F811
    import os

    from sqlalchemy import create_engine, select
    from sqlalchemy.engine import make_url

    from app.models.gold_v2_load import BATCH, TABLES
    from tests.support.migrations import migrated_database

    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Configure PostgreSQL descartável v_energy_test para os agregados.")
    assert make_url(url).database == "v_energy_test"
    seed_measures(published)
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection, migrated_database(connection):
            with published.connect() as source, engine.begin() as destination:
                for table in (BATCH, *TABLES.values()):
                    rows = [dict(r) for r in source.execute(select(table)).mappings()]
                    if rows:
                        destination.execute(table.insert(), rows)
            facts = observe_domain_readiness(
                engine,
                requested_periods=("2001-01",),
                approved_controls=frozenset(
                    {"C01", "C02", "C03", "C04", "C10", "C12", "C13"}
                ),
            )
            assert all(
                facts["control_results"][key]["status"] == "passed"
                for key in ("C01", "C02", "C03", "C04", "C10", "C12", "C13")
            )
            assert facts["coverage"]["faturamento.receita"]["closed_periods"] == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("scope", ["attendance", "domains"])
@pytest.mark.parametrize("case", ["stale", "malformed"])
def test_consumer_reference_is_checked_before_genai_call(published, scope, case):  # noqa: F811
    import asyncio
    from uuid import uuid4

    import httpx

    from app.repositories.gold_publication import (
        GoldPublicationChanged,
        GoldPublicationInvalid,
    )
    from app.services.gold_readiness import (
        evaluate_attendance_readiness,
        evaluate_domain_readiness,
    )

    current = observe_domain_readiness(
        published, requested_periods=("2001-01",), approved_controls=frozenset()
    )["batch_ref"]
    expected = (
        current.rsplit(":", 1)[0] + ":" + str(uuid4())
        if case == "stale"
        else "invalid-private-reference"
    )

    def transport(request):
        pytest.fail("Não pode chamar GenAI para a publicação incorreta.")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            evaluate = (
                evaluate_domain_readiness
                if scope == "domains"
                else evaluate_attendance_readiness
            )
            return await evaluate(
                published,
                http_client=client,
                base_url="http://genai",
                service_token="controlled-token",
                requested_periods=("2001-01",),
                approved_controls=frozenset(),
                correlation_id="a" * 32,
                expected_batch_ref=expected,
            )

    with pytest.raises(
        GoldPublicationChanged if case == "stale" else GoldPublicationInvalid
    ):
        asyncio.run(run())


def test_accumulated_domain_observation_does_not_fabricate_monthly_coverage(published):  # noqa: F811
    facts = observe_domain_readiness(
        published, requested_periods=(), approved_controls=frozenset({"C14"}),
    )
    assert facts["coverage"] == {}
    assert facts["control_results"]["C14"]["status"] == "passed"
    assert facts["control_results"]["C14"]["approved"] is True
    assert facts["batch_ref"] == facts["expected_batch_ref"]
