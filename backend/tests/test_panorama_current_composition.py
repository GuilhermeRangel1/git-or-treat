from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.services.gold_panorama_insights import current_revenue_composition


def test_composition_uses_observed_current_sum_and_deterministic_tie():
    rows = [{"segment": "Olinda", "period": "2026-06", "revenue": Decimal("25")}, {"segment": "Recife", "period": "2026-06", "revenue": Decimal("75")}]
    repository = SimpleNamespace(revenue_groups=lambda *args: rows)
    filters = dict(periodo="2026-06", municipio="todos", classe="todas")
    value = current_revenue_composition(repository, filters, {"revenue": Decimal("100")})
    assert value.segmento == "Recife"
    assert value.valor == 75
    assert value.participacaoPercentual == 75


@pytest.mark.parametrize("total, values", [(Decimal("101"), [Decimal("25"), Decimal("75")]), (Decimal("100"), [Decimal("-1"), Decimal("101")]), (Decimal("0"), [])])
def test_composition_does_not_publish_unreconciled_or_negative_share(total, values):
    rows = [{"segment": str(i), "period": "2026-06", "revenue": v} for i, v in enumerate(values)]
    repository = SimpleNamespace(revenue_groups=lambda *args: rows)
    assert current_revenue_composition(repository, dict(periodo="2026-06", municipio="todos", classe="todas"), {"revenue": total}) is None


@pytest.fixture
def snapshot_repository():
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from app.repositories.panorama import GoldPanoramaRepository
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS gold_v2")
        connection.exec_driver_sql("CREATE TABLE gold_v2.diagnostico_receita (competencia TEXT, municipio TEXT, classe_consumo TEXT, receita_base_comparavel_reais NUMERIC, consumo_base_comparavel_kwh REAL)")
        connection.exec_driver_sql("CREATE TABLE gold_v2.consumo_receita_bairro (competencia TEXT, municipio TEXT, classe_consumo TEXT, bairro TEXT, receita_base_comparavel_reais NUMERIC)")
        connection.exec_driver_sql("INSERT INTO gold_v2.diagnostico_receita VALUES ('2026-06','A','RESIDENCIAL',30,3),('2026-06','A','COMERCIAL',20,2),('2026-06','B','RESIDENCIAL',50,5),('2026-06','B','COMERCIAL',NULL,NULL),('2026-05','A','RESIDENCIAL',15,1),('2026-05','A','COMERCIAL',15,1),('2026-05','B','RESIDENCIAL',20,2),('2026-05','B','COMERCIAL',NULL,NULL)")
        connection.exec_driver_sql("INSERT INTO gold_v2.consumo_receita_bairro VALUES ('2026-06','A','RESIDENCIAL','X',20),('2026-06','A','RESIDENCIAL','Y',10)")
        yield GoldPanoramaRepository(SimpleNamespace(connection=connection, imported_at=datetime.now(timezone.utc), lote="test", fingerprint="a"*64))
    engine.dispose()


def prepare(repository, municipality="todos", consumption_class="todas", **kwargs):
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    return build_gold_panorama_insight(repository, PanoramaInsightRequest(loteVersao="test", filters=dict(periodo="2026-06", comparacao="anterior", municipio=municipality, classe=consumption_class)), **kwargs)


@pytest.mark.parametrize("municipality, consumption_class, allow, dimension, segment, value, share", [
    ("todos", "todas", False, "municipio", "A", 50, 50),
    ("A", "todas", False, "classe", "RESIDENCIAL", 30, 60),
    ("A", "RESIDENCIAL", True, "bairro", "X", 20, 66.7),
])
def test_snapshot_composition_respects_filters(snapshot_repository, municipality, consumption_class, allow, dimension, segment, value, share):
    # No previous month comparison for partial totals, otherwise request none
    # to exercise the composition of the selected month independently.
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    result = build_gold_panorama_insight(snapshot_repository, PanoramaInsightRequest(loteVersao="test", filters=dict(periodo="2026-06", comparacao="nenhuma", municipio=municipality, classe=consumption_class)), allow_neighborhood=allow)
    prepared, metric, source, analysis = result
    item = analysis.composicaoAtual
    assert (item.dimension, item.segmento, item.valor, item.participacaoPercentual) == (dimension, segment, value, share)
    assert prepared.screen.filters["municipio"] == municipality
    assert prepared.screen.observations[1].value == value
    assert analysis.direcao == "indisponivel"


def test_snapshot_keeps_temporal_comparison_when_valid(snapshot_repository):
    prepared, _, _, analysis = prepare(snapshot_repository, "A", "RESIDENCIAL", allow_neighborhood=True)
    assert analysis.direcao == "alta"
    assert analysis.variacaoPercentual == 100
    assert analysis.composicaoAtual is None
    assert [v.value for v in prepared.screen.observations[:3]] == [30, 15, 15]


def test_neighborhood_requires_permission_and_reconciles(snapshot_repository):
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    request = PanoramaInsightRequest(loteVersao="test", filters=dict(periodo="2026-06", comparacao="nenhuma", municipio="A", classe="RESIDENCIAL"))
    assert build_gold_panorama_insight(snapshot_repository, request)[3].composicaoAtual is None
    snapshot_repository.connection.exec_driver_sql("UPDATE gold_v2.consumo_receita_bairro SET receita_base_comparavel_reais=19 WHERE bairro='X'")
    assert build_gold_panorama_insight(snapshot_repository, request, allow_neighborhood=True)[3].composicaoAtual is None


@pytest.mark.parametrize("value, expected", [(0, "observed_zero"), (None, "no_evidence")])
def test_zero_and_missing_do_not_create_composition(snapshot_repository, value, expected):
    from sqlalchemy import text
    from app.schemas.ai_insight import AIInsightResponse
    snapshot_repository.connection.execute(text("UPDATE gold_v2.diagnostico_receita SET receita_base_comparavel_reais=:value WHERE competencia='2026-06'"), {"value": value})
    prepared, _, _, analysis = prepare(snapshot_repository)
    assert analysis.composicaoAtual is None
    if expected == "no_evidence":
        assert isinstance(prepared, AIInsightResponse)
        assert prepared.status == "no_evidence"
    else:
        assert prepared.screen.observations[0].value == 0


def test_partial_previous_comparison_falls_back_to_current_composition(snapshot_repository):
    prepared, _, source, analysis = prepare(snapshot_repository)
    assert analysis.direcao == "indisponivel"
    assert analysis.composicaoAtual.segmento == "A"
    assert [v.value for v in prepared.screen.observations] == [100, 50]
    assert any("ausentes" in limit for limit in source.limitacoes)


def test_unobserved_period_is_empty_not_zero(snapshot_repository):
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_insights import build_gold_panorama_insight
    request = PanoramaInsightRequest(loteVersao="test", filters=dict(periodo="2026-04", comparacao="nenhuma", municipio="todos", classe="todas"))
    prepared, _, _, analysis = build_gold_panorama_insight(snapshot_repository, request)
    assert prepared.status == "no_evidence"
    assert prepared.observation.values == []
    assert analysis.composicaoAtual is None


@pytest.mark.parametrize("count", [1000, 1001])
def test_composition_never_publishes_truncated_groups(count):
    rows = [{"segment": f"{i:04d}", "period": "2026-06", "revenue": Decimal(1)} for i in range(count)]
    item = current_revenue_composition(SimpleNamespace(revenue_groups=lambda *args: rows), dict(periodo="2026-06",municipio="todos",classe="todas"), {"revenue": Decimal(count)})
    if count == 1001:
        assert item is None
    else:
        assert item.segmento == "0000"
        assert item.valor == 1
        assert item.participacaoPercentual == 0.1


def test_neighborhood_not_authorized_does_not_query_repository():
    def deny(*args):
        raise AssertionError("unauthorized detail queried")
    assert current_revenue_composition(SimpleNamespace(revenue_groups=deny), dict(periodo="2026-06",municipio="A",classe="RESIDENCIAL"), {"revenue": Decimal(30)}) is None


@pytest.mark.parametrize("period,mode,previous", [("2026-01","anterior","2025-12"),("2024-03","anterior","2024-02"),("2026-06","ano_anterior","2025-06")])
def test_temporal_boundary_does_not_change_requested_month(period, mode, previous):
    from app.services.panorama import comparison_period
    assert comparison_period(period, mode) == previous
