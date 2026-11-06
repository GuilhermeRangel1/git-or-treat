from types import SimpleNamespace

from app.schemas.analytics import AnalyticsFilters
from app.services.revenue_diagnosis import build_revenue_diagnosis


def test_diagnosis_uses_current_cohorts_and_reconciles_the_volume_effect():
    repo = SimpleNamespace(
        revenue_gd_cohort_rows=lambda filters, windows: [
            {"cohort": "connected_between", "uc_count": 10, "q0": 100, "q1": 30, "volume_effect": -70},
            {"cohort": "no_record", "uc_count": 20, "q0": 100, "q1": 110, "volume_effect": 10},
        ],
        revenue_billed_population=lambda filters, windows: {"initial": 20, "final": 22},
    )
    window = {"status": "partial", "windows": ["2022-07","2023-06","2025-07","2026-06"],
              "components": {"volume": -60, "preco": 120}, "initial_amount_brl": 100,
              "total_change_brl": 60}
    rows = [{"municipio":"A", "efeito_volume_reais":-50}, {"municipio":"B","efeito_volume_reais":-10}]
    result = build_revenue_diagnosis(repo, AnalyticsFilters(), window, rows)
    assert result["volume_offset_percent"] == 50
    assert result["population"]["change_percent"] == 10
    assert result["gd"]["cohorts"][0]["measured_energy_change_percent"] == -70
    assert result["gd"]["share_negative_volume_percent"] == 100
    assert result["concentration"]["labels"] == ["A", "B"]


def test_diagnosis_refuses_a_cohort_effect_from_another_universe():
    repo = SimpleNamespace(
        revenue_gd_cohort_rows=lambda *args: [{"cohort":"connected_between","uc_count":10,"q0":100,"q1":30,"volume_effect":-70}],
        revenue_billed_population=lambda *args: {"initial":0,"final":1},
    )
    result = build_revenue_diagnosis(repo, AnalyticsFilters(),
        {"status":"available","windows":["2022-07","2023-06","2025-07","2026-06"],"components":{"volume":-60,"preco":0}}, [])
    assert result["gd"]["status"] == "unavailable"
    assert result["gd"]["cohorts"] == []
    assert result["volume_offset_percent"] is None
    assert result["population"]["change_percent"] is None


def test_no_extra_queries_when_the_published_windows_are_unavailable():
    result = build_revenue_diagnosis(SimpleNamespace(), AnalyticsFilters(), {"status":"unavailable"}, [])
    assert result["status"] == "unavailable"


def test_gd_negative_share_does_not_hide_a_decline_in_another_class():
    repo = SimpleNamespace(
        revenue_gd_cohort_rows=lambda *args: [
            {"cohort":"connected_between","class_name":"R","uc_count":10,"q0":100,"q1":30,"volume_effect":-70},
            {"cohort":"no_record","class_name":"R","uc_count":10,"q0":100,"q1":120,"volume_effect":20},
            {"cohort":"no_record","class_name":"C","uc_count":10,"q0":100,"q1":90,"volume_effect":-10},
        ],
        revenue_billed_population=lambda *args: {"initial":30,"final":30},
    )
    result = build_revenue_diagnosis(repo, AnalyticsFilters(),
        {"status":"available","windows":["2022-07","2023-06","2025-07","2026-06"],"components":{"volume":-60,"preco":120}}, [])
    assert result["gd"]["share_negative_volume_percent"] == 87.5
    assert len(result["gd"]["cohorts"]) == 2
    assert result["gd"]["cohorts"][1]["measured_energy_change_percent"] == 5
