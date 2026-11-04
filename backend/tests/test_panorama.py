import pytest

from tests.support.platform_auth import login_as_profile

from app.repositories.panorama import SyntheticPanoramaRepository
from app.services.panorama import build_panorama


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


@pytest.fixture(autouse=True)
def authenticated_commercial_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial")


def test_get_panorama_default_benchmark(client):
    """Verifica os controles da base sintética no benchmark 2024-04 vs 2024-03."""
    response = client.get("/api/v1/panorama?competencia=2024-04&comparacao=anterior")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    metricas = data["metricas"]

    # Controles do benchmark PRD WEB-01 / Figma
    rec_fat = metricas["receitaFaturada"]
    assert rec_fat["valorAtual"] == 76500.0
    assert rec_fat["valorAnterior"] == 80000.0
    assert rec_fat["variacaoAbsoluta"] == -3500.0
    assert rec_fat["variacaoPercentual"] == -4.38
    assert rec_fat["tipoGrandeza"] == "faturado"

    rec_pag = metricas["receitaPaga"]
    assert rec_pag["valorAtual"] == 74200.0
    assert rec_pag["valorAnterior"] == 78500.0
    assert rec_pag["tipoGrandeza"] == "pago"
    assert rec_pag["valorAtual"] != rec_fat["valorAtual"]  # Distinção faturado vs pago

    ene_con = metricas["energiaConsumida"]
    assert ene_con["valorAtual"] == 90000.0
    assert ene_con["valorAnterior"] == 100000.0
    assert ene_con["variacaoPercentual"] == -10.0
    assert ene_con["tipoGrandeza"] == "consumido"

    ene_fat = metricas["energiaFaturada"]
    assert ene_fat["valorAtual"] == 90000.0
    assert ene_fat["tipoGrandeza"] == "faturado"

    # Preço médio = 76500 / 90000 = 0.85
    prc_med = metricas["precoMedioEfetivo"]
    assert prc_med["valorAtual"] == 0.85
    assert prc_med["valorAnterior"] == 0.80

    assert data["periodoIncompleto"] is False
    assert data["totalRegistros"] > 0
    assert len(data["serieMensal"]) == 2
    assert body["metadata"]["lote_gold_versao"] == data["loteVersao"]


def test_get_panorama_filters_by_municipio(client):
    """Verifica se o filtro por município altera os dados agregados (Recife = R$ 38.000)."""
    response = client.get("/api/v1/panorama?competencia=2024-04&municipio=Recife")
    assert response.status_code == 200
    data = response.json()["data"]
    metricas = data["metricas"]

    assert metricas["receitaFaturada"]["valorAtual"] == 38000.0
    assert metricas["energiaConsumida"]["valorAtual"] == 45000.0
    assert metricas["ucsAtivas"]["valorAtual"] == 620


def test_get_panorama_empty_recorte(client):
    """Verifica tratamento de estado vazio legítimo quando a combinação válida não tem fatos."""
    response = client.get("/api/v1/panorama?competencia=2024-05&municipio=Olinda&classe=Comercial")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["totalRegistros"] == 0
    assert data["metricas"]["receitaFaturada"]["valorAtual"] == 0.0


def test_get_panorama_incomplete_period(client):
    """Verifica sinalização de período incompleto na competência 2024-05."""
    response = client.get("/api/v1/panorama?competencia=2024-05")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["periodoIncompleto"] is True


def _build_panorama_with_coverage(incomplete_periods: set[str], competencia: str):
    repository = SyntheticPanoramaRepository()
    repository.incomplete_periods = frozenset(incomplete_periods)
    return build_panorama(repository, competencia=competencia)


def test_current_incomplete_period_comes_from_selected_repository() -> None:
    data = _build_panorama_with_coverage({"2024-04"}, "2024-04")

    assert data.periodoIncompleto is True
    assert data.metricas["receitaFaturada"].valorAnterior is None


def test_repository_can_mark_fixture_partial_period_as_complete() -> None:
    data = _build_panorama_with_coverage(set(), "2024-05")

    assert data.periodoIncompleto is False
    assert data.metricas["receitaFaturada"].valorAtual == 31000.0
    assert data.metricas["receitaFaturada"].valorAnterior == 76500.0


def test_incomplete_comparison_period_suppresses_only_comparison() -> None:
    data = _build_panorama_with_coverage({"2024-03"}, "2024-04")

    assert data.periodoIncompleto is False
    assert data.metricas["receitaFaturada"].valorAtual == 76500.0
    assert data.metricas["receitaFaturada"].valorAnterior is None


def test_unrelated_incomplete_period_does_not_suppress_comparison() -> None:
    data = _build_panorama_with_coverage({"2024-05"}, "2024-04")

    assert data.periodoIncompleto is False
    assert data.metricas["receitaFaturada"].valorAnterior == 80000.0


def test_get_panorama_without_comparison(client):
    """Verifica que a comparação desativada não fabricate valor anterior."""
    response = client.get("/api/v1/panorama?competencia=2024-04&comparacao=nenhuma")
    assert response.status_code == 200
    metricas = response.json()["data"]["metricas"]

    assert metricas["receitaFaturada"]["valorAnterior"] is None
    assert metricas["receitaFaturada"]["variacaoPercentual"] is None


def test_get_panorama_rejects_unknown_filter(client):
    """Verifica recusa de município e competência fora da fonte demonstrativa."""
    response = client.get("/api/v1/panorama?competencia=2024-04&municipio=Natal")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"

    response = client.get("/api/v1/panorama?competencia=2024-13")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_get_panorama_fails_closed_without_source(client, monkeypatch):
    """Verifica que a rota analítica não responde números sem fonte explicitamente escolhida."""
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get("/api/v1/panorama?competencia=2024-04")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "source_unavailable"

def test_missing_comparison_is_not_zero(client):
    response = client.get('/api/v1/panorama?competencia=2024-04&comparacao=ano_anterior')
    assert response.status_code == 200
    for metric in response.json()['data']['metricas'].values():
        assert metric['valorAnterior'] is None
        assert metric['variacaoPercentual'] is None
        assert metric['baseZero'] is False


def test_history_never_includes_future_periods(client):
    response = client.get('/api/v1/panorama?competencia=2024-03')
    assert [point['competencia'] for point in response.json()['data']['serieMensal']] == ['2024-03']


def test_history_includes_selected_partial_period(client):
    response = client.get('/api/v1/panorama?competencia=2024-05&municipio=Recife')
    data = response.json()['data']
    assert data['serieMensal'][-1]['competencia'] == '2024-05'
    assert data['serieMensal'][-1]['receitaFaturada'] == data['metricas']['receitaFaturada']['valorAtual'] == 22000


@pytest.mark.parametrize("comparison", ["anterior", "ano_anterior", "nenhuma"])
def test_partial_totals_are_preserved_without_misleading_comparison(client, comparison):
    response = client.get(f"/api/v1/panorama?competencia=2024-05&comparacao={comparison}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metricas"]["receitaFaturada"]["valorAtual"] == 31000
    assert data["periodoIncompleto"] is True
    for metric in data["metricas"].values():
        assert metric["valorAnterior"] is None
        assert metric["variacaoAbsoluta"] is None
        assert metric["variacaoPercentual"] is None
        assert metric["baseZero"] is False
