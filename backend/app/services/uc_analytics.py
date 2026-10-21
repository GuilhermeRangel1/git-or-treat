from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import AnalyticsStatus
from app.services.analytics import AnalyticsAPIError, page_items


def build_uc_search(
    repository: AnalyticsRepository, q: str | None, page: int, page_size: int, order_by: str,
) -> tuple[list[dict], dict, AnalyticsStatus]:
    if q is not None and (not q.strip() or len(q) > 100):
        raise AnalyticsAPIError(422, "invalid_query", "Busca inválida.", [{"field": "q", "message": "Use de 1 a 100 caracteres."}])
    items = [
        {key: unit[key] for key in ("uc_id", "municipio", "bairro", "classe", "alimentador", "status")}
        for unit in repository.units
        if q is None or q.lower() in unit["uc_id"].lower()
    ]
    selected, pagination = page_items(items, page, page_size, order_by, {"uc_id", "municipio", "bairro", "classe", "alimentador", "status"})
    return selected, pagination, "available" if items else "empty"


def build_uc_detail(repository: AnalyticsRepository, uc_id: str) -> tuple[dict, AnalyticsStatus, list[str]]:
    unit = next((item for item in repository.units if item["uc_id"] == uc_id), None)
    if unit is None:
        raise AnalyticsAPIError(404, "not_found", "Unidade consumidora não encontrada.", [{"field": "uc_id", "message": "Nenhuma UC corresponde ao identificador."}])
    readings = [row for row in repository.readings if row["uc_id"] == uc_id]
    invoices = [row for row in repository.invoices if row["uc_id"] == uc_id]
    meters = [row for row in repository.meters if row["uc_id"] == uc_id]
    generation = [row for row in repository.generation if row["uc_id"] == uc_id]
    interruptions = [row for row in repository.interruptions if row["uc_id"] == uc_id]
    calls = [row for row in repository.calls if row["uc_id"] == uc_id]
    missing_readings = any(row["measured_energy_kwh"] is None for row in readings)
    section_status = {
        "profile": "available",
        "consumption": "partial" if missing_readings else ("available" if readings else "empty"),
        "invoices": "available" if invoices else "empty",
        "meters": "available" if meters else "empty",
        "distributed_generation": "available" if generation else "empty",
        "interruptions": "available" if interruptions else "empty",
        "calls": "available" if calls else "empty",
    }
    state: AnalyticsStatus = "partial" if "partial" in section_status.values() else "available"
    limitations = ["Há leitura ausente no histórico; valores ausentes permanecem nulos."] if missing_readings else []
    data = {
        "profile": {key: unit.get(key) for key in ("uc_id", "customer_reference", "customer_name", "municipio", "bairro", "classe", "alimentador", "status")},
        "consumption": [{key: row.get(key) for key in ("competencia", "measured_energy_kwh", "status")} for row in readings],
        "invoices": [{key: row.get(key) for key in ("invoice_id", "competencia", "billed_amount", "paid_amount", "billed_energy_kwh", "due_date", "payment_date", "payment_status")} for row in invoices],
        "meters": [{key: row.get(key) for key in ("meter_id", "installed_at", "removed_at")} for row in meters],
        "distributed_generation": [{key: row.get(key) for key in ("capacity_kw", "status")} for row in generation],
        "interruptions": [{key: row.get(key) for key in ("event_id", "feeder_id", "competencia", "duration_hours")} for row in interruptions],
        "calls": [{key: row.get(key) for key in ("call_id", "opened_at", "category")} for row in calls],
        "section_status": section_status,
    }
    return data, state, limitations
