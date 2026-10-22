from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import AnalyticsFilters, AnalyticsStatus
from app.services.analytics import apply_unit_filters


def build_inspection_queue(repository: AnalyticsRepository, filters: AnalyticsFilters) -> tuple[list[dict], AnalyticsStatus]:
    selected_units = apply_unit_filters(repository.units, filters)
    selected_ids = {unit["uc_id"] for unit in selected_units}
    unit_by_id = {unit["uc_id"]: unit for unit in selected_units}
    items = []
    for suspicion in repository.suspicions:
        if suspicion["uc_id"] not in selected_ids:
            continue
        unit = unit_by_id[suspicion["uc_id"]]
        items.append({
            "uc_id": unit["uc_id"], "municipality": unit["municipio"], "neighborhood": unit["bairro"],
            "class_name": unit["classe"], "feeder_id": unit["alimentador"], "priority": suspicion["priority"],
            "reason": suspicion["reason"], "potential_recoverable_energy_kwh": suspicion["potential_recoverable_energy_kwh"],
            "indicators": suspicion["indicators"],
        })
    state: AnalyticsStatus = "empty" if not items else ("partial" if any(item["potential_recoverable_energy_kwh"] is None for item in items) else "available")
    return items, state
