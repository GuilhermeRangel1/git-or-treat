"""Gold API smoke against an isolated disposable PostgreSQL database."""
import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from pydantic import SecretStr
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.main import app
import app.repositories.gold_context as gold_context_module
from app.models.gold_v2_load import BATCH, SCHEMA_VERSION, TABLES
from app.repositories.gold_context import get_gold_context, load_gold_context
from app.services.analytics import AnalyticsAPIError


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_GOLD_ANALYTICS_POSTGRES_URL"),
    reason="Set TEST_GOLD_ANALYTICS_POSTGRES_URL to an isolated disposable PostgreSQL database.",
)


@pytest.fixture(scope="module")
def gold_engine() -> Engine:
    url = os.environ["TEST_GOLD_ANALYTICS_POSTGRES_URL"]
    parsed = make_url(url)
    assert parsed.drivername == "postgresql+psycopg", "Gold tests require the isolated psycopg test database."
    assert parsed.database is not None and parsed.database.endswith("_test"), "Refusing database without a _test suffix."
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    created = False
    try:
        with engine.connect() as connection:
            identity = connection.exec_driver_sql(
                "SELECT current_database(), current_user, role.rolsuper "
                "FROM pg_roles AS role WHERE role.rolname = current_user"
            ).one()
            assert identity[0] == parsed.database and identity[2] is False, "Gold test role/database is not isolated or is privileged."
            tables = connection.exec_driver_sql(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
            ).scalars().all()
            assert not tables, "Gold test database must have an empty public schema before setup."
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA gold_v2")
            connection.exec_driver_sql("CREATE SCHEMA gold")
            BATCH.create(connection, checkfirst=True)
            TABLES["diagnostico_receita"].create(connection, checkfirst=True)
            TABLES["indicadores_dec_fec"].create(connection, checkfirst=True)
            TABLES["consumo_mensal_uc"].create(connection, checkfirst=True)
            TABLES["visao_360_uc"].create(connection, checkfirst=True)
            connection.exec_driver_sql("CREATE VIEW gold.publicacao_contexto AS "
                "SELECT schema_version,lote,publication_id,fingerprint,importado_em "
                "FROM public.gold_carga_atual WHERE id=1")
        created = True
        yield engine
    finally:
        try:
            if created:
                with engine.begin() as connection:
                    connection.exec_driver_sql("DROP VIEW gold.publicacao_contexto")
                    connection.exec_driver_sql("DROP SCHEMA gold")
                    for table in (TABLES["diagnostico_receita"], TABLES["indicadores_dec_fec"], TABLES["consumo_mensal_uc"], TABLES["visao_360_uc"], BATCH):
                        table.drop(connection, checkfirst=True)
                    connection.exec_driver_sql("DROP SCHEMA gold_v2")
        finally:
            engine.dispose()


@pytest.fixture
def published_artificial_gold(gold_engine):
    fingerprint = "a" * 64
    imported_at = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    diagnosis = TABLES["diagnostico_receita"]
    continuity = TABLES["indicadores_dec_fec"]
    with gold_engine.begin() as connection:
        connection.execute(diagnosis.delete())
        connection.execute(continuity.delete())
        connection.execute(TABLES["consumo_mensal_uc"].delete())
        connection.execute(TABLES["visao_360_uc"].delete())
        connection.execute(BATCH.delete())
        connection.execute(BATCH.insert().values(
            id=1, lote="dev131-test", schema_version=SCHEMA_VERSION,
            fingerprint=fingerprint, importado_em=imported_at, manifesto={},
        ))
        connection.execute(diagnosis.insert(), [
            {
                "competencia": "2025-01", "municipio": "Cidade Teste",
                "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "B1",
                "bandeira_tarifaria": "VERDE", "possui_gd": "NÃ£o",
                "qtd_ucs_distintas_faturadas_no_mes": 2, "soma_faturamentos_mensais": 2,
                "consumo_total_kwh": 50.0, "receita_total_reais": Decimal("100.00"),
                "consumo_base_comparavel_kwh": 40.0, "receita_base_comparavel_reais": Decimal("80.00"),
                "ticket_medio_reais_por_uc": 50.0, "consumo_medio_kwh_por_uc": 25.0,
                "tarifa_media_efetiva": 2.0,
            },
            {
                "competencia": "2025-02", "municipio": "Cidade Teste",
                "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "B1",
                "bandeira_tarifaria": "VERDE", "possui_gd": "NÃ£o",
                "qtd_ucs_distintas_faturadas_no_mes": 3, "soma_faturamentos_mensais": 2,
                "consumo_total_kwh": 60.0, "receita_total_reais": Decimal("120.00"),
                "consumo_base_comparavel_kwh": 50.0, "receita_base_comparavel_reais": Decimal("110.00"),
                "ticket_medio_reais_por_uc": 60.0, "consumo_medio_kwh_por_uc": 30.0,
                "tarifa_media_efetiva": 2.0,
            },
            {
                "competencia": "2025-03", "municipio": "Outra Cidade",
                "classe_consumo": "COMERCIAL", "subgrupo_tarifario": "B3",
                "bandeira_tarifaria": "AMARELA", "possui_gd": "NÃ£o",
                "qtd_ucs_distintas_faturadas_no_mes": 1, "soma_faturamentos_mensais": 1,
                "consumo_total_kwh": 10.0, "receita_total_reais": Decimal("25.00"),
                "consumo_base_comparavel_kwh": None, "receita_base_comparavel_reais": None,
                "ticket_medio_reais_por_uc": 25.0, "consumo_medio_kwh_por_uc": 10.0,
                "tarifa_media_efetiva": 2.5,
            },
            {
                "competencia": "2025-04", "municipio": "Cidade Teste",
                "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "B1",
                "bandeira_tarifaria": "VERDE", "possui_gd": "Não",
                "qtd_ucs_distintas_faturadas_no_mes": 1, "soma_faturamentos_mensais": 1,
                "consumo_total_kwh": 300.0, "receita_total_reais": Decimal("100.00"),
                "consumo_base_comparavel_kwh": 300.0, "receita_base_comparavel_reais": Decimal("100.00"),
                "ticket_medio_reais_por_uc": 100.0, "consumo_medio_kwh_por_uc": 300.0,
                "tarifa_media_efetiva": 0.3333333333333333,
            },
            {
                "competencia": "2025-05", "municipio": "Cidade Teste",
                "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "B1",
                "bandeira_tarifaria": "VERDE", "possui_gd": "Não",
                "qtd_ucs_distintas_faturadas_no_mes": 1, "soma_faturamentos_mensais": 1,
                "consumo_total_kwh": 300.0, "receita_total_reais": Decimal("101.00"),
                "consumo_base_comparavel_kwh": 300.0, "receita_base_comparavel_reais": Decimal("101.00"),
                "ticket_medio_reais_por_uc": 101.0, "consumo_medio_kwh_por_uc": 300.0,
                "tarifa_media_efetiva": 0.3366666666666667,
            },
            {
                "competencia": "2025-06", "municipio": "Cidade Teste",
                "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "B1",
                "bandeira_tarifaria": "VERDE", "possui_gd": "Não",
                "qtd_ucs_distintas_faturadas_no_mes": 1, "soma_faturamentos_mensais": 1,
                "consumo_total_kwh": 300.0,
                "receita_total_reais": Decimal("1000000000000000000000000000000000.00"),
                "consumo_base_comparavel_kwh": 300.0,
                "receita_base_comparavel_reais": Decimal("1000000000000000000000000000000000.00"),
                "ticket_medio_reais_por_uc": None,
                "consumo_medio_kwh_por_uc": 300.0,
                "tarifa_media_efetiva": 3333333333333333333333333333333.33,
            },
        ])
        connection.execute(continuity.insert(), [
            {
                "id_alimentador": "AL-TESTE", "municipio": "Cidade Teste", "competencia": "2025-01",
                "total_ucs_alimentador": 10, "ucs_interrompidas": 2,
                "frequencia_total_interrupcoes": 3, "duracao_total_interrupcoes_horas": 6.0,
                "DEC": 0.6, "FEC": 0.3,
            },
            {
                "id_alimentador": "AL-TESTE", "municipio": "Cidade Teste", "competencia": "2025-02",
                "total_ucs_alimentador": 10, "ucs_interrompidas": 1,
                "frequencia_total_interrupcoes": 1, "duracao_total_interrupcoes_horas": 9.0,
                "DEC": 0.9, "FEC": 0.1,
            },
        ])
    return fingerprint, imported_at


def test_context_checks_batch_and_fingerprint_in_same_postgres_connection(gold_engine, published_artificial_gold):
    fingerprint, imported_at = published_artificial_gold
    with gold_engine.connect() as connection:
        with connection.begin():
            context = load_gold_context(connection, "dev131-test", fingerprint)
            assert context.connection is connection
            assert context.lote == "dev131-test"
            assert context.schema_version == "gold-csv-v2"
            assert context.imported_at == imported_at
            with pytest.raises(AnalyticsAPIError) as stale:
                load_gold_context(connection, "another-batch", fingerprint)
            assert stale.value.status_code == 409
            with pytest.raises(AnalyticsAPIError) as stale_fingerprint:
                load_gold_context(connection, "dev131-test", "b" * 64)
            assert stale_fingerprint.value.status_code == 409
            with pytest.raises(AnalyticsAPIError) as invalid_fingerprint:
                load_gold_context(connection, expected_fingerprint="not-a-hash")
            assert invalid_fingerprint.value.status_code == 422


def test_gold_dependency_holds_repeatable_read_only_snapshot_across_publication(gold_engine, published_artificial_gold, monkeypatch):
    fingerprint, _ = published_artificial_gold
    token = "local-read-token-for-isolated-test-0001"
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr(token))
    monkeypatch.setattr(settings, "ORDERS_WRITE_TOKEN", None)
    monkeypatch.setattr(gold_context_module, "engine", gold_engine)
    request = Request({"type": "http", "headers": []})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    context_generator = get_gold_context(request, "dev131-test", fingerprint, credentials)
    context = next(context_generator)
    try:
        assert context.connection.exec_driver_sql("SHOW transaction_isolation").scalar_one() == "repeatable read"
        assert context.connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
        before_batch = context.connection.execute(BATCH.select().where(BATCH.c.id == 1)).mappings().one()
        before_fact = context.connection.execute(
            TABLES["diagnostico_receita"].select().where(TABLES["diagnostico_receita"].c.competencia == "2025-02")
        ).mappings().first()
        with gold_engine.begin() as publisher:
            publisher.execute(BATCH.update().where(BATCH.c.id == 1).values(fingerprint="b" * 64))
            publisher.execute(TABLES["diagnostico_receita"].update().where(
                TABLES["diagnostico_receita"].c.competencia == "2025-02"
            ).values(receita_total_reais=Decimal("999.00")))
        after_batch = context.connection.execute(BATCH.select().where(BATCH.c.id == 1)).mappings().one()
        after_fact = context.connection.execute(
            TABLES["diagnostico_receita"].select().where(TABLES["diagnostico_receita"].c.competencia == "2025-02")
        ).mappings().first()
        assert after_batch["fingerprint"] == before_batch["fingerprint"] == fingerprint
        assert after_fact["receita_total_reais"] == before_fact["receita_total_reais"] == Decimal("120.00")
    finally:
        context_generator.close()

    stale_reader = get_gold_context(request, "dev131-test", fingerprint, credentials)
    with pytest.raises(AnalyticsAPIError) as stale:
        next(stale_reader)
    assert stale.value.status_code == 409
    with gold_engine.connect() as connection:
        assert connection.execute(
            TABLES["diagnostico_receita"].select().where(TABLES["diagnostico_receita"].c.competencia == "2025-02")
        ).mappings().first()["receita_total_reais"] == Decimal("999.00")


def test_gold_panorama_http_uses_artificial_publication(gold_engine, published_artificial_gold, monkeypatch):
    fingerprint, _ = published_artificial_gold
    token = "local-read-token-for-isolated-test-0001"
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr(token))
    monkeypatch.setattr(settings, "ORDERS_WRITE_TOKEN", None)
    monkeypatch.setattr(gold_context_module, "engine", gold_engine)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/panorama?competencia=2025-02&comparacao=nenhuma"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert response.status_code == 200, response.text
        panorama = response.json()
        assert panorama["metadata"]["source"]["version"] == "dev131-test"
        assert panorama["metadata"]["fingerprint"] == fingerprint
        assert panorama["data"]["metricas"]["receitaFaturada"]["valorAtual"] == 110.0
        assert panorama["data"]["metricas"]["energiaConsumida"]["valorAtual"] == 50.0
        assert panorama["data"]["metricas"]["precoMedioEfetivo"]["valorAtual"] == 2.2
        assert panorama["data"]["metricas"]["receitaFaturada"]["formula"] == "Σ(receita_base_comparavel_reais)"
        assert panorama["data"]["metricas"]["energiaConsumida"]["formula"] == "Σ(consumo_base_comparavel_kwh)"
        assert panorama["data"]["metricas"]["precoMedioEfetivo"]["formula"] == (
            "Σ(receita_base_comparavel_reais) / Σ(consumo_base_comparavel_kwh)"
        )
        february_point = next(
            point for point in panorama["data"]["serieMensal"] if point["competencia"] == "2025-02"
        )
        assert february_point["receitaFaturada"] == 110.0
        assert february_point["energiaConsumidaKwh"] == 50.0
        assert panorama["data"]["metricas"]["energiaFaturada"]["valorAtual"] is None
        assert panorama["data"]["metricas"]["receitaPaga"]["valorAtual"] is None
        assert panorama["data"]["metricas"]["ucsAtivas"]["valorAtual"] == 0
        assert panorama["data"]["metricas"]["energiaFaturada"]["statusComparacao"] == "unavailable"
        assert panorama["data"]["metricas"]["receitaPaga"]["statusComparacao"] == "unavailable"
        assert panorama["data"]["metricas"]["ucsAtivas"]["statusComparacao"] == "unavailable"
        billed_ucs = panorama["data"]["metricas"]["ucsFaturadasNoMes"]
        assert billed_ucs["valorAtual"] == 0
        assert billed_ucs["status"] == "available"
        assert "fechamento" in billed_ucs["limitacoesComparacao"][0].casefold()
        assert panorama["data"]["opcoesFiltros"]["competencias"] == [
            "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"
        ]
        assert panorama["data"]["metricas"]["receitaFaturada"]["variacaoPercentual"] is None
        assert panorama["data"]["metricas"]["receitaFaturada"]["statusComparacao"] == "empty"

        comparison = client.get(
            "/api/v1/panorama?competencia=2025-02&comparacao=anterior"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert comparison.status_code == 200, comparison.text
        compared_metric = comparison.json()["data"]["metricas"]["receitaFaturada"]
        assert compared_metric["valorAnterior"] == 80.0
        assert compared_metric["statusComparacao"] == "partial"
        assert compared_metric["variacaoAbsoluta"] == 30.0
        assert compared_metric["variacaoPercentual"] == 37.5
        assert any("não declara fechamento mensal" in item.lower() for item in compared_metric["limitacoesComparacao"])

        price_comparison = client.get(
            "/api/v1/panorama?competencia=2025-05&comparacao=anterior"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert price_comparison.status_code == 200, price_comparison.text
        price_metric = price_comparison.json()["data"]["metricas"]["precoMedioEfetivo"]
        assert price_metric["valorAtual"] == 0.34
        assert price_metric["valorAnterior"] == 0.33
        assert price_metric["variacaoAbsoluta"] == 0.0
        assert price_metric["variacaoPercentual"] == 1.0

        large_revenue = client.get(
            "/api/v1/panorama?competencia=2025-06&comparacao=nenhuma"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert large_revenue.status_code == 200, large_revenue.text
        large_price_metric = large_revenue.json()["data"]["metricas"]["precoMedioEfetivo"]
        assert large_price_metric["valorAtual"] is not None

        gap = client.get(
            "/api/v1/panorama?competencia=2025-03&comparacao=nenhuma&municipio=Cidade%20Teste"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert gap.status_code == 200, gap.text
        gap_data = gap.json()["data"]
        assert gap_data["metricas"]["receitaFaturada"]["valorAtual"] is None
        assert gap_data["serieMensal"][-1]["status"] == "empty"
        assert gap_data["serieMensal"][-1]["receitaFaturada"] is None

        financial_only = client.get(
            "/api/v1/panorama?competencia=2025-03&comparacao=nenhuma&municipio=Outra%20Cidade"
            "&expected_lote=dev131-test&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert financial_only.status_code == 200, financial_only.text
        financial_only_data = financial_only.json()["data"]
        assert financial_only_data["metricas"]["receitaFaturada"]["valorAtual"] is None
        assert financial_only_data["metricas"]["energiaConsumida"]["valorAtual"] is None
        assert financial_only_data["metricas"]["receitaFaturada"]["status"] == "unavailable"
        assert financial_only_data["metricas"]["energiaConsumida"]["status"] == "unavailable"
        assert financial_only_data["metricas"]["continuidadeDec"]["valorAtual"] is None
        assert financial_only_data["metricas"]["continuidadeFec"]["valorAtual"] is None
        assert any("não há município/alimentador" in text for text in financial_only_data["metricas"]["continuidadeDec"]["limitacoes"])

        for path in ("/api/v1/revenue", "/api/v1/ucs", "/api/v1/kpis"):
            unsupported = client.get(path, headers=headers)
            assert unsupported.status_code == 503

        stale = client.get(
            "/api/v1/panorama?expected_lote=old-batch&expected_fingerprint=" + fingerprint,
            headers=headers,
        )
        assert stale.status_code == 409
        unauthenticated = client.get("/api/v1/panorama")
        assert unauthenticated.status_code == 401


def test_gold_insight_matches_visible_kpi_and_independent_sql(gold_engine, published_artificial_gold):
    from sqlalchemy import select, func
    from app.repositories.panorama import GoldPanoramaRepository
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    from app.services.panorama import build_gold_panorama
    with gold_engine.connect() as connection:
        repository = GoldPanoramaRepository(load_gold_context(connection))
        request = PanoramaInsightRequest(filters={"periodo": "2025-02", "comparacao": "anterior",
            "municipio": "Cidade Teste", "classe": "RESIDENCIAL"}, loteVersao="dev131-test")
        prepared, metric, source, analysis = build_gold_panorama_insight(repository, request)
        visible = build_gold_panorama(repository, "2025-02", "anterior", "Cidade Teste", "RESIDENCIAL")
        table = TABLES["diagnostico_receita"]
        independent = connection.scalar(select(func.sum(table.c.receita_base_comparavel_reais)).where(
            table.c.competencia == "2025-02", table.c.municipio == "Cidade Teste",
            table.c.classe_consumo == "RESIDENCIAL"))
        assert prepared.screen.observations[0].value == float(independent) == 110
        assert prepared.screen.observations[0].value == visible.metricas["receitaFaturada"].valorAtual
        assert prepared.screen.observations[1].value == 80
        assert prepared.screen.observations[2].value == 30
        assert analysis.direcao == "alta" and analysis.variacaoPercentual == 37.5
        assert not source.isDemo and metric.id == "rec_fat"
        assert any("fechamento mensal" in item for item in prepared.screen.limitations)


@pytest.mark.parametrize("value,expected", [(Decimal("0"), "answered"), (None, "no_evidence")])
def test_gold_insight_preserves_zero_and_missing_values(gold_engine, published_artificial_gold, value, expected):
    from sqlalchemy import update
    from app.repositories.panorama import GoldPanoramaRepository
    from app.schemas.ai_insight import AIInsightRequest, PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    from app.services.panorama_insights import StalePanoramaInsight
    with gold_engine.begin() as connection:
        table = TABLES["diagnostico_receita"]
        connection.execute(update(table).where(table.c.competencia == "2025-02").values(
            receita_base_comparavel_reais=value))
        repository = GoldPanoramaRepository(load_gold_context(connection))
        request = PanoramaInsightRequest(filters={"periodo": "2025-02", "comparacao": "nenhuma",
            "municipio": "Cidade Teste", "classe": "RESIDENCIAL"}, loteVersao="dev131-test")
        prepared, _, _, _ = build_gold_panorama_insight(repository, request)
        if expected == "answered":
            assert isinstance(prepared, AIInsightRequest)
            assert prepared.screen.observations[0].value == 0
        else:
            assert prepared.status == "no_evidence" and prepared.observation.values == []
        with pytest.raises(StalePanoramaInsight):
            build_gold_panorama_insight(repository, request.model_copy(update={"loteVersao": "old"}))


def test_gold_contribution_uses_gross_same_sign_denominator(gold_engine, published_artificial_gold):
    from app.repositories.panorama import GoldPanoramaRepository
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    with gold_engine.begin() as connection:
        for city, current, previous in (("Compensação Teste", 30, 50), ("Alta Teste", 20, 10)):
            connection.execute(TABLES["diagnostico_receita"].insert(), [{
                "competencia": period, "municipio": city, "classe_consumo": "RESIDENCIAL",
                "subgrupo_tarifario": "B1", "bandeira_tarifaria": "VERDE", "possui_gd": "Não",
                "receita_base_comparavel_reais": value,
            } for period, value in (("2025-01", previous), ("2025-02", current))])
        repository = GoldPanoramaRepository(load_gold_context(connection))
        request = PanoramaInsightRequest(filters={"periodo": "2025-02", "comparacao": "anterior",
            "municipio": "todos", "classe": "RESIDENCIAL"}, loteVersao="dev131-test")
        prepared, _, _, analysis = build_gold_panorama_insight(repository, request)
        assert [v.value for v in prepared.screen.observations[:3]] == [160, 140, 20]
        assert analysis.principalContribuicao.segmento == "Cidade Teste"
        assert analysis.principalContribuicao.variacaoAbsoluta == 30
        assert analysis.principalContribuicao.participacaoPercentual == 75
        assert analysis.compensacao.variacaoAbsoluta == -20
        assert analysis.compensacao.participacaoPercentual == 100


def test_gold_insight_partial_and_empty_slices_are_explicit(gold_engine, published_artificial_gold):
    from app.repositories.panorama import GoldPanoramaRepository
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    with gold_engine.begin() as connection:
        connection.execute(TABLES["diagnostico_receita"].insert(), {
            "competencia": "2025-02", "municipio": "Cidade Teste", "classe_consumo": "RESIDENCIAL",
            "subgrupo_tarifario": "B2", "bandeira_tarifaria": "VERDE", "possui_gd": "Não",
            "receita_base_comparavel_reais": None})
        repo = GoldPanoramaRepository(load_gold_context(connection))
        request = PanoramaInsightRequest(filters={"periodo": "2025-02", "comparacao": "anterior",
            "municipio": "Cidade Teste", "classe": "RESIDENCIAL"}, loteVersao="dev131-test")
        prepared, _, _, analysis = build_gold_panorama_insight(repo, request)
        assert prepared.screen.observations[0].value == 110
        assert len(prepared.screen.observations) == 1
        assert any("ausentes" in text for text in prepared.screen.limitations)
        assert analysis.direcao == "indisponivel"
        empty = request.model_copy(update={"filters":request.filters.model_copy(update={
            "periodo":"2025-01", "municipio":"Outra Cidade", "classe":"COMERCIAL"})})
        response, _, _, _ = build_gold_panorama_insight(repo, empty)
        assert response.status == "no_evidence" and response.evidence == []
