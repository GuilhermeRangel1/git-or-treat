from datetime import datetime
from typing import Iterable

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsMetadata,
    AnalyticsPeriod,
    AnalyticsSource,
    AnalyticsStatus,
    ContinuityItem,
    Metric,
)


DEFAULT_START = "2025-01"
DEFAULT_END = "2025-02"
CONTRACT_VERSION = "1.0.0"


class AnalyticsAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def parse_month(value: str, field: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError:
        raise AnalyticsAPIError(422, "invalid_query", "Competência inválida.", [{"field": field, "message": "Use uma competência real no formato YYYY-MM."}])
    if parsed.strftime("%Y-%m") != value:
        raise AnalyticsAPIError(422, "invalid_query", "Competência inválida.", [{"field": field, "message": "Use uma competência real no formato YYYY-MM."}])
    return parsed.year, parsed.month


def month_key(row: dict) -> str:
    return row["competencia"]


def validate_period(start: str | None, end: str | None) -> tuple[str, str]:
    start = DEFAULT_START if start is None else start
    end = DEFAULT_END if end is None else end
    start_parts = parse_month(start, "competencia_inicio")
    end_parts = parse_month(end, "competencia_fim")
    if start_parts > end_parts:
        raise AnalyticsAPIError(422, "invalid_query", "Intervalo de competências inválido.", [{"field": "competencia_inicio", "message": "A competência inicial deve ser menor ou igual à final."}])
    return start, end


def filters_model(municipio=None, bairro=None, classe=None, alimentador=None) -> AnalyticsFilters:
    values = {"municipio": municipio, "bairro": bairro, "classe": classe, "alimentador": alimentador}
    for name, value in values.items():
        if value is not None and (not value.strip() or len(value) > 100):
            raise AnalyticsAPIError(422, "invalid_query", "Filtro inválido.", [{"field": name, "message": "Informe de 1 a 100 caracteres."}])
    return AnalyticsFilters(**values)


def apply_unit_filters(units: Iterable[dict], filters: AnalyticsFilters) -> list[dict]:
    all_units = list(units)
    for key, value in filters.model_dump(exclude_none=True).items():
        if key not in {"municipio", "bairro", "classe", "alimentador"}:
            continue
        accepted_values = {unit[key] for unit in all_units}
        if value not in accepted_values:
            raise AnalyticsAPIError(422, "invalid_query", "Filtro desconhecido.", [{"field": key, "message": "O valor não existe na fonte demonstrativa."}])
    if filters.municipio and filters.bairro:
        matching_towns = {unit["municipio"] for unit in all_units if unit["bairro"] == filters.bairro}
        if filters.municipio not in matching_towns:
            raise AnalyticsAPIError(422, "invalid_query", "Combinação geográfica contraditória.", [{"field": "bairro", "message": "O bairro não pertence ao município informado."}])
    return [
        unit for unit in all_units
        if (filters.municipio is None or unit["municipio"] == filters.municipio)
        and (filters.bairro is None or unit["bairro"] == filters.bairro)
        and (filters.classe is None or unit["classe"] == filters.classe)
        and (filters.alimentador is None or unit["alimentador"] == filters.alimentador)
    ]


def row_in_period(row: dict, start: str, end: str) -> bool:
    return start <= month_key(row) <= end


def metadata(repository: AnalyticsRepository, status: AnalyticsStatus, start: str, end: str, filters: AnalyticsFilters) -> AnalyticsMetadata:
    return AnalyticsMetadata(
        contract_version=CONTRACT_VERSION,
        status=status,
        period=AnalyticsPeriod(start=start, end=end),
        filters=filters,
        source=AnalyticsSource(kind=repository.source_kind, version=repository.source_version, is_demo=repository.source_is_demo, updated_at=repository.source_updated_at),
        limitations=list(repository.source_limitations),
    )


def metric(metric_id: str, label: str, value: float | int | None, unit: str, status: AnalyticsStatus, limitations=None) -> Metric:
    return Metric(id=metric_id, label=label, value=value, unit=unit, status=status, limitations=limitations or [])


def _numeric_total(rows: list[dict], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    if not values:
        return None
    return round(sum(values), 2)


def build_kpis(repository: AnalyticsRepository, start: str, end: str, filters: AnalyticsFilters) -> tuple[list[Metric], AnalyticsStatus]:
    units = apply_unit_filters(repository.units, filters)
    ids = {unit["uc_id"] for unit in units}
    invoices = [row for row in repository.invoices if row["uc_id"] in ids and row_in_period(row, start, end)]
    readings = [row for row in repository.readings if row["uc_id"] in ids and row_in_period(row, start, end)]
    billed = _numeric_total(invoices, "billed_amount")
    paid_rows = [row for row in invoices if row["paid_amount"] is not None]
    paid = _numeric_total(paid_rows, "paid_amount")
    reading_values = [row for row in readings if row["measured_energy_kwh"] is not None]
    energy = _numeric_total(reading_values, "measured_energy_kwh")
    billed_energy = _numeric_total(invoices, "billed_energy_kwh")
    state_billed: AnalyticsStatus = "available" if billed is not None else "empty"
    state_paid: AnalyticsStatus = "empty" if not invoices else ("unavailable" if paid is None else ("partial" if len(paid_rows) < len(invoices) else "available"))
    state_energy: AnalyticsStatus = "empty" if not readings else ("unavailable" if energy is None else ("partial" if len(reading_values) < len(readings) else "available"))
    limitations = ["Há leituras ausentes no recorte; o total soma apenas valores observados."] if state_energy in {"partial", "unavailable"} else []
    paid_limitations = ["Há faturas sem informação de pagamento; o total pago soma somente valores conhecidos."] if state_paid in {"partial", "unavailable"} else []
    metrics = [
        metric("billed_amount", "Valor faturado", billed, "BRL", state_billed),
        metric("paid_amount", "Valor pago", paid, "BRL", state_paid, paid_limitations),
        metric("billed_energy_kwh", "Energia faturada", billed_energy, "kWh", "available" if billed_energy is not None else "empty"),
        metric("measured_energy_kwh", "Energia medida", energy, "kWh", state_energy, limitations),
        metric("active_units", "UCs ativas", sum(1 for unit in units if unit["status"] == "active") if units else None, "UC", "available" if units else "empty"),
    ]
    overall = "empty" if not units or not invoices and not readings else ("partial" if any(item.status in {"partial", "unavailable"} for item in metrics) else "available")
    return metrics, overall


def page_items(items: list[dict], page: int, page_size: int, order_by: str, allowed_order: set[str], descending: bool = False) -> tuple[list[dict], dict]:
    if order_by not in allowed_order:
        raise AnalyticsAPIError(422, "invalid_query", "Ordenação inválida.", [{"field": "order_by", "message": "Campo de ordenação não permitido."}])
    items = sorted(items, key=lambda item: item.get("uc_id", ""))
    items = sorted(items, key=lambda item: (item[order_by] is None, item[order_by]), reverse=descending)
    total = len(items)
    start_index = (page - 1) * page_size
    return items[start_index:start_index + page_size], {"page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}


def build_continuity(repository: AnalyticsRepository, start: str, end: str, filters: AnalyticsFilters) -> tuple[list[ContinuityItem], AnalyticsStatus]:
    feeders = [row for row in repository.feeders if filters.alimentador is None or row["feeder_id"] == filters.alimentador]
    if filters.alimentador and not feeders:
        raise AnalyticsAPIError(422, "invalid_query", "Alimentador desconhecido.", [{"field": "alimentador", "message": "O valor não existe na fonte demonstrativa."}])
    temporal_coverage = repository.continuity_coverage
    observed_start = max(start, temporal_coverage.start) if temporal_coverage else start
    observed_end = min(end, temporal_coverage.end) if temporal_coverage else end
    has_temporal_coverage = temporal_coverage is not None and observed_start <= observed_end
    temporal_limitations = []
    if temporal_coverage is None:
        temporal_limitations.append("Cobertura temporal da fonte de interrupções desconhecida; DEC/FEC não calculados.")
    elif not has_temporal_coverage:
        temporal_limitations.append(f"Janela solicitada fora da cobertura temporal da fonte ({temporal_coverage.start} a {temporal_coverage.end}); DEC/FEC não calculados.")
    elif observed_start != start or observed_end != end:
        temporal_limitations.append(f"Cobertura temporal parcial da fonte ({temporal_coverage.start} a {temporal_coverage.end}); DEC/FEC usam somente eventos observados de {observed_start} a {observed_end}, sem representar toda a janela solicitada.")
    result = []
    for feeder in sorted(feeders, key=lambda row: row["feeder_id"]):
        events = [row for row in repository.interruptions if has_temporal_coverage and row["feeder_id"] == feeder["feeder_id"] and observed_start <= row["competencia"] <= observed_end]
        denominator = feeder["denominator_uc_count"]
        served_count = sum(1 for unit in repository.units if unit["alimentador"] == feeder["feeder_id"] and unit["status"] == "active")
        covered_count = served_count
        valid_denominator = isinstance(denominator, int) and not isinstance(denominator, bool) and denominator > 0
        coverage = round(covered_count / denominator, 3) if valid_denominator else None
        status: AnalyticsStatus = "unavailable" if not valid_denominator or not has_temporal_coverage else ("partial" if covered_count != denominator or temporal_limitations else "available")
        coverage_limitations = list(temporal_limitations)
        if not valid_denominator:
            coverage_limitations.append("Denominador demonstrativo ausente, zero ou inválido; DEC/FEC não calculados.")
        if denominator is not None and covered_count != denominator:
            coverage_limitations.append("Contagem de UCs atendidas diverge do denominador configurado.")
        if feeder["territory_status"] == "multi_municipal":
            coverage_limitations.append("O alimentador atravessa mais de um município.")
        result.append(ContinuityItem(
            feeder_id=feeder["feeder_id"],
            municipalities=feeder["municipios"],
            territory_status=feeder["territory_status"],
            dec_hours_per_uc=round(sum(row["duration_hours"] for row in events) / denominator, 3) if valid_denominator and has_temporal_coverage else None,
            fec_interruptions_per_uc=round(len(events) / denominator, 3) if valid_denominator and has_temporal_coverage else None,
            interruption_count=len(events),
            denominator_uc_count=denominator,
            covered_uc_count=covered_count,
            coverage_ratio=coverage,
            served_uc_count=served_count,
            coverage_status="unavailable" if not valid_denominator else ("partial" if covered_count != denominator else "available"),
            status=status,
            limitations=coverage_limitations,
        ))
    if not result:
        overall: AnalyticsStatus = "empty"
    elif all(item.status == "unavailable" for item in result):
        overall = "unavailable"
    elif any(item.status in {"partial", "unavailable"} for item in result):
        overall = "partial"
    else:
        overall = "available"
    return result, overall
