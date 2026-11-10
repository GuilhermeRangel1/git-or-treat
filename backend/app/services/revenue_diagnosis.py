"""Achados observados na mesma publicação e recorte da Receita, sem síntese causal."""
import math


def build_revenue_diagnosis(repository, filters, window, rows):
    result = {"status": "unavailable", "volume_offset_percent": None, "population": None,
              "concentration": None, "gd": {"status": "unavailable", "cohorts": [],
              "share_negative_volume_percent": None}, "limitations": []}
    if not window or window["status"] == "unavailable" or len(window.get("windows", [])) != 4:
        result["limitations"] = ["Não há janelas publicadas válidas para investigar este recorte."]
        return result
    result["status"] = window["status"]
    components = window["components"]
    price, volume = components.get("preco"), components.get("volume")
    if price is not None and volume is not None and price > 0 and volume < 0:
        result["volume_offset_percent"] = abs(volume) / price * 100
    dimension = "municipio" if not filters.municipio else "bairro" if not filters.bairro else "classe_consumo"
    groups = {}
    for row in rows:
        value = row.get("efeito_volume_reais")
        if value is not None and math.isfinite(value):
            key = row.get(dimension) or "Não informado"
            groups[key] = groups.get(key, 0) + value
    negative = sorted(((key, value) for key, value in groups.items() if value < 0), key=lambda item: (item[1], item[0]))
    if negative:
        first = negative[:2]
        result["concentration"] = {"dimension": dimension, "labels": [key for key, _ in first],
                                   "share_negative_volume_percent": sum(value for _, value in first) / sum(value for _, value in negative) * 100}
    population = repository.revenue_billed_population(filters, window["windows"])
    initial, final = population["initial"], population["final"]
    result["population"] = {"initial_billed_uc_count": initial, "final_billed_uc_count": final,
                            "change_percent": (final - initial) / initial * 100 if initial >= 5 and final >= 5 else None}
    cohorts = repository.revenue_gd_cohort_rows(filters, window["windows"])
    valid = all(all(row.get(field) is not None and math.isfinite(row[field]) for field in
                    ("q0", "q1", "volume_effect", "uc_count")) and row["q0"] > 0 and row["uc_count"] > 0 for row in cohorts)
    if not cohorts or not valid or volume is None or not math.isclose(
        math.fsum(row["volume_effect"] for row in cohorts), volume, abs_tol=0.01, rel_tol=1e-9,
    ):
        result["gd"]["limitations"] = ["A comparação de GD não reconciliou com o efeito-volume deste recorte."]
        return result
    negative_sum = math.fsum(-row["volume_effect"] for row in cohorts if row["volume_effect"] < 0)
    connected = {"connected_between", "connected_during"}
    connected_negative = math.fsum(-row["volume_effect"] for row in cohorts if row["cohort"] in connected and row["volume_effect"] < 0)
    displayed = {}
    for row in cohorts:
        entry = displayed.setdefault(row["cohort"], {"cohort":row["cohort"], "uc_count":0, "q0":0.0, "q1":0.0})
        for field in ("uc_count", "q0", "q1"):
            entry[field] += row[field]
    small = any(row["uc_count"] < 5 for row in displayed.values())
    result["gd"] = {
        "status": "partial" if small else "available",
        "cohorts": [{"group": row["cohort"], "uc_count": row["uc_count"],
                     "measured_energy_change_percent": (row["q1"] - row["q0"]) / row["q0"] * 100 if row["uc_count"] >= 5 else None} for row in displayed.values()],
        "share_negative_volume_percent": connected_negative / negative_sum * 100 if negative_sum > 0 else None,
        "limitations": ["Mesmas UCs e pares mensais, com pelo menos seis pares válidos. Associação com a data de conexão; não mede geração ou compensação nem comprova causalidade."]
                       + (["Grupos com menos de cinco UCs não recebem variação percentual."] if small else []),
    }
    result["limitations"] = ["UCs faturadas são observadas nas janelas; não representam histórico completo de clientes cadastrados."]
    return result
