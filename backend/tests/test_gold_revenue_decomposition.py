from types import SimpleNamespace

from app.schemas.analytics import AnalyticsFilters
from app.services.gold_revenue import (
    observed_price,
    window_breakdown,
    window_decomposition,
)


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


def test_window_bases_and_observed_percentages_reconcile():
    repo = fixture_repo([row(faturamento_p0_reais=100, faturamento_p1_reais=135, qtd_ucs_observadas=8)])
    result = window_decomposition(repo, AnalyticsFilters())
    assert result["initial_amount_brl"] == 100
    assert result["final_amount_brl"] == 135
    assert result["change_percent"] == 35
    assert result["component_percentage_points"]["volume"] == 10


def test_window_percentages_refuse_small_missing_and_inconsistent_bases():
    for changes in ({"qtd_ucs_observadas": 2}, {"faturamento_p0_reais": 0},
                    {"faturamento_p1_reais": 999}, {"faturamento_p0_reais": None}):
        values = {"faturamento_p0_reais": 100, "faturamento_p1_reais": 135, "qtd_ucs_observadas": 8} | changes
        result = window_decomposition(fixture_repo([row(**values)]), AnalyticsFilters())
        assert result["change_percent"] is None


def test_window_breakdown_keeps_neighborhood_parent_and_inherited_class():
    rows = [row(municipio="A", bairro="Centro", classe_consumo="Residencial"),
            row(municipio="B", bairro="Centro", classe_consumo="Residencial")]
    result = window_breakdown(fixture_repo(rows), AnalyticsFilters(classe="Residencial"), "bairro")
    assert len(result) == 2
    assert result[0]["key"] != result[1]["key"]
    assert result[0]["filters"] == {"municipio": "A", "bairro": "Centro", "classe": "Residencial", "alimentador": None}
    assert sum(item["decomposition"]["total_change_brl"] for item in result) == 70


def test_financial_percent_survives_an_incomplete_effect_in_a_small_subgroup():
    large = row(faturamento_p0_reais=100, faturamento_p1_reais=135, qtd_ucs_observadas=8)
    small = row(faturamento_p0_reais=100, faturamento_p1_reais=135, qtd_ucs_observadas=2,
                estado_decomposicao="SEM_BASE_COMUM", efeito_volume_reais=None)
    result = window_decomposition(fixture_repo([large, small]), AnalyticsFilters())
    assert result["status"] == "partial"
    assert result["change_percent"] == 35
    assert "volume" not in result["component_percentage_points"]
    assert result["component_percentage_points"]["preco"] == 20
