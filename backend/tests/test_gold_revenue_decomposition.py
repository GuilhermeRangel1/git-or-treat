from types import SimpleNamespace

from app.schemas.analytics import AnalyticsFilters
from app.services.gold_revenue import observed_price, window_decomposition


def fixture_repo(rows):
    windows = {"inicio_p0": "2023-01", "fim_p0": "2023-12", "inicio_p1": "2024-01", "fim_p1": "2024-12"}
    method = "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3"
    for row in rows:
        row.update(windows, metodo=method)
    return SimpleNamespace(schema_version="gold-csv-v2", origin={"preco_volume_configuracao": {
        "estado": "CONFIGURADA", "janelas": windows, "metodo": method,
    }}, revenue_decomposition_rows=lambda filters: rows)


def row(**changes):
    result = {"estado_decomposicao": "CALCULADA_BASE_COMUM", "efeito_volume_reais": 10.,
              "efeito_preco_observado_reais": 20., "efeito_interacao_reais": 1.,
              "variacao_entradas_reais": 4., "variacao_saidas_reais": -3.,
              "variacao_sem_leitura_fora_base_reais": 2., "variacao_outros_fora_base_reais": 1.,
              "variacao_faturamento_total_reais": 35.}
    return result | changes


def test_complete_window_components_reconcile_and_keep_their_own_windows():
    result = window_decomposition(fixture_repo([row(), row()]), AnalyticsFilters())
    assert result["status"] == "available"
    assert result["windows"] == ["2023-01", "2023-12", "2024-01", "2024-12"]
    assert result["total_change_brl"] == 70
    assert result["residual_brl"] == 0
    assert result["components"]["preco"] == 40


def test_missing_base_is_partial_and_feeder_does_not_use_wrong_grain():
    incomplete = row(estado_decomposicao="SEM_BASE_COMUM", efeito_volume_reais=None,
                     efeito_preco_observado_reais=None, efeito_interacao_reais=None)
    repo = fixture_repo([row(), incomplete])
    result = window_decomposition(repo, AnalyticsFilters())
    assert result["status"] == "partial"
    assert result["incomplete_groups"] == 1
    assert result["components"]["preco"] == 20
    assert result["residual_brl"] is None
    assert window_decomposition(repo, AnalyticsFilters(alimentador="A"))["status"] == "unavailable"


def test_invalid_reconciliation_and_uncertified_coverage_are_unavailable():
    assert window_decomposition(fixture_repo([row(variacao_faturamento_total_reais=100)]), AnalyticsFilters())["status"] == "unavailable"
    assert window_decomposition(fixture_repo([row(estado_decomposicao="COBERTURA_NAO_CERTIFICADA")]), AnalyticsFilters())["status"] == "unavailable"


def test_observed_price_uses_only_comparable_base_and_refuses_missing_or_zero_energy():
    assert observed_price([{"comparable_amount": 30, "comparable_energy": 20}, {"comparable_amount": 10, "comparable_energy": 30}]) == 0.8
    assert observed_price([{"comparable_amount": 30, "comparable_energy": 0}]) is None
    assert observed_price([{"comparable_amount": 30, "comparable_energy": None}]) is None
