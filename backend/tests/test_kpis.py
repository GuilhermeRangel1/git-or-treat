def test_get_kpis_default_benchmark(client):
    """Verifica os controles da base sintética no benchmark 2024-04 vs 2024-03."""
    response = client.get("/api/v1/kpis?competencia=2024-04&comparacao=anterior")
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


def test_get_kpis_filters_by_municipio(client):
    """Verifica se o filtro por município altera os dados agregados (Recife = R$ 38.000)."""
    response = client.get("/api/v1/kpis?competencia=2024-04&municipio=Recife")
    assert response.status_code == 200
    data = response.json()["data"]
    metricas = data["metricas"]

    assert metricas["receitaFaturada"]["valorAtual"] == 38000.0
    assert metricas["energiaConsumida"]["valorAtual"] == 45000.0
    assert metricas["ucsAtivas"]["valorAtual"] == 620


def test_get_kpis_empty_recorte(client):
    """Verifica tratamento de estado vazio legítimo quando recorte não possui dados."""
    response = client.get("/api/v1/kpis?competencia=2024-04&classe=Rural")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["totalRegistros"] == 0
    assert data["metricas"]["receitaFaturada"]["valorAtual"] == 0.0


def test_get_kpis_incomplete_period(client):
    """Verifica sinalização de período incompleto na competência 2024-05."""
    response = client.get("/api/v1/kpis?competencia=2024-05")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["periodoIncompleto"] is True
