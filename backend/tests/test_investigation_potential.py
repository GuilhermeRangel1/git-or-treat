from datetime import date

from app.services.gold_inspections import investigation_potential_from_rows


def readings(values):
    return [{"competencia": month, "consumo_kwh": value, "qtd_leituras_observadas": 1, "qtd_leituras_validas": 1} for month, value in values.items()]


def test_compares_same_months_last_year_and_keeps_consecutive_comparison_separate():
    rows = readings({"2023-11": 300, "2023-12": 300, "2024-01": 300,
                     "2024-11": 200, "2024-12": 200, "2025-01": 200,
                     "2024-08": 9000})
    result = investigation_potential_from_rows(rows, "2025-01")
    assert (result["baseline_start"], result["baseline_end"], result["recent_start"], result["recent_end"]) == ("2023-11", "2024-01", "2024-11", "2025-01")
    assert (result["baseline_kwh"], result["recent_kwh"], result["potential_kwh"]) == (900, 600, 300)


def test_no_decrease_is_zero_and_missing_or_invalid_is_unavailable():
    values = {"2024-01": 0, "2024-02": 0, "2024-03": 0,
              "2025-01": 1, "2025-02": 2, "2025-03": 3}
    rows = readings(values)
    assert investigation_potential_from_rows(rows, "2025-03")["potential_kwh"] == 0
    missing = investigation_potential_from_rows(rows[:-1], "2025-03")
    assert missing["potential_kwh"] is None and missing["unavailable_reason"]
    rows[-1]["qtd_leituras_validas"] = 0
    assert investigation_potential_from_rows(rows, "2025-03")["potential_kwh"] is None


def test_meter_change_inside_comparison_window_blocks_calculation():
    rows = readings({"2024-01": 300, "2024-02": 300, "2024-03": 300,
                     "2025-01": 200, "2025-02": 200, "2025-03": 200})
    meter = {"data_instalacao": date(2024, 9, 1), "data_retirada": None,
             "flag_instalacao_sentinela": False, "flag_instalacao_futura": False,
             "flag_retirada_sentinela": False, "flag_retirada_futura": False}
    result = investigation_potential_from_rows(rows, "2025-03", [meter])
    assert result["potential_kwh"] is None and "medidor" in result["unavailable_reason"]
    meter["data_instalacao"] = date(2023, 12, 1)
    assert investigation_potential_from_rows(rows, "2025-03", [meter])["potential_kwh"] == 300
    rows[-1]["qtd_leituras_observadas"] = -1
    rows[-1]["qtd_leituras_validas"] = -1
    assert investigation_potential_from_rows(rows, "2025-03")["potential_kwh"] is None
