from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import AnalyticsFilters, AnalyticsStatus
from app.services.analytics import AnalyticsAPIError, apply_unit_filters


RULE_VERSION = "dev05-v1"
SIGNALS = {
    "reading_gap": ("Lacuna de leitura", 0.60),
    "meter_removed": ("Medidor retirado", 0.32),
    "consumption_variation": ("Variação de consumo", 0.41),
    "distributed_generation": ("Geração distribuída; exige análise do contexto", 0.20),
}
LIMITATIONS = [
    "Regra sintética de triagem, não validada com dados reais. Pontuação não é probabilidade de irregularidade.",
    "Suspeita não confirma irregularidade. GD, sazonalidade e alterações cadastrais podem explicar os sinais.",
    "Estimativa mensal hipotética; não representa energia medida, faturada ou recuperação garantida.",
]


def build_suspicion(suspicion: dict, unit: dict) -> dict:
    signals = [{"id": key, "label": SIGNALS[key][0], "weight": SIGNALS[key][1]}
               for key in dict.fromkeys(suspicion["indicators"]) if key in SIGNALS]
    evidence = suspicion.get("estimate_evidence", {
        "baseline_kwh": None, "observed_kwh": None, "horizon_months": 1,
        "reference": "Sem referência sintética suficiente.",
    }).copy()
    baseline, observed = evidence["baseline_kwh"], evidence["observed_kwh"]
    estimate = None
    if baseline is not None and observed is not None:
        estimate = round(max(0, baseline - observed) * evidence["horizon_months"], 2)
    evidence["unavailable_reason"] = (
        "Referência ou observação sintética ausente; não estimamos energia nem substituímos ausência por zero."
        if estimate is None else None
    )
    return {
        "uc_id": unit["uc_id"], "municipality": unit["municipio"], "neighborhood": unit["bairro"],
        "class_name": unit["classe"], "feeder_id": unit["alimentador"],
        "priority": round(min(1, sum(signal["weight"] for signal in signals)), 2),
        "reason": suspicion["reason"], "potential_recoverable_energy_kwh": estimate,
        "indicators": [signal["id"] for signal in signals],
        "rule_version": RULE_VERSION, "signals": signals, "estimate_evidence": evidence,
        "limitations": list(LIMITATIONS),
    }


def build_inspection_queue(repository: AnalyticsRepository, filters: AnalyticsFilters) -> tuple[list[dict], AnalyticsStatus]:
    if not repository.source_is_demo:
        raise AnalyticsAPIError(503, "rule_unavailable", "Regra de inspeção real ainda não homologada.")
    selected_units = apply_unit_filters(repository.units, filters)
    selected_ids = {unit["uc_id"] for unit in selected_units}
    unit_by_id = {unit["uc_id"]: unit for unit in selected_units}
    items = []
    for suspicion in repository.suspicions:
        if suspicion["uc_id"] not in selected_ids:
            continue
        unit = unit_by_id[suspicion["uc_id"]]
        items.append(build_suspicion(suspicion, unit))
    state: AnalyticsStatus = "empty" if not items else ("partial" if any(item["potential_recoverable_energy_kwh"] is None for item in items) else "available")
    return items, state


def sort_queue(items: list[dict], order_by: str, direction: str) -> list[dict]:
    items = sorted(items, key=lambda item: item["uc_id"])
    items = sorted(items, key=lambda item: (
        item["potential_recoverable_energy_kwh"] is None,
        -(item["potential_recoverable_energy_kwh"] or 0),
    ))
    known = [item for item in items if item[order_by] is not None]
    missing = [item for item in items if item[order_by] is None]
    return sorted(known, key=lambda item: item[order_by], reverse=direction == "desc") + missing


def suspicion_detail(repository: AnalyticsRepository, uc_id: str) -> dict:
    items, _ = build_inspection_queue(repository, AnalyticsFilters())
    item = next((item for item in items if item["uc_id"] == uc_id), None)
    if item is None:
        raise AnalyticsAPIError(404, "not_found", "Suspeita não encontrada.")
    return item
