from decimal import Decimal
from types import SimpleNamespace

from app.schemas.analytics import AnalyticsFilters
from app.services.gold_revenue import build_gold_revenue


def test_null_measure_and_zero_are_distinct_in_coverage_and_comparison():
    rows = [
        {"competencia": "2025-01", "municipio": "A", "amount": Decimal("0"), "energy": None, "uc_count": 1},
        {"competencia": "2025-03", "municipio": "A", "amount": None, "energy": Decimal("0"), "uc_count": 1},
    ]
    repo = SimpleNamespace(
        revenue_groups=lambda *args: rows,
        source_limitations=["Cobertura não homologada."],
        options=lambda: {"municipio": ["A"], "bairros": [], "classe": []},
    )
    data = build_gold_revenue(repo, "2025-01", "2025-03", AnalyticsFilters(), "municipio")
    assert data["total_billed_amount"] == 0
    assert data["total_measured_energy_kwh"] == 0
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert data["coverage"]["billed_amount"]["covered_months"] == ["2025-01"]
    assert data["coverage"]["billed_amount"]["missing_months"] == ["2025-02", "2025-03"]
    assert data["coverage"]["measured_energy_kwh"]["covered_months"] == ["2025-03"]
    assert data["coverage"]["measured_energy_kwh"]["missing_months"] == ["2025-01", "2025-02"]
    assert data["total_paid_amount"] is None
    assert data["total_billed_energy_kwh"] is None
