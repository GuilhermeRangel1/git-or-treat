"""Fila publicada na Gold; preserva prioridade categórica e não inventa score."""
import math
from sqlalchemy import select

from app.schemas.analytics import AnalyticsFilters
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.services.analytics import AnalyticsAPIError, metadata

LIMITATIONS = [
    "Prioridade categórica publicada pela Gold, sem score numérico; regra candidata aguarda homologação.",
    "Categorias de triagem descritas no dicionário Gold; a prioridade e o histórico não confirmam uma nova irregularidade.",
    "Energia recuperável indisponível: os CSVs não fornecem estimativa homologada.",
    "Criação de ordens a partir da fila Gold aguarda homologação e identidade autorizada; consulta disponível.",
    "O período da resposta indica os extremos das competências de consumo observadas, sem comprovar todos os meses; a fila e seus históricos acumulados não informam janela temporal própria.",
]


def item(row):
    reason = row["prioridade_inspecao"] or "Não informado"
    average = row["media_consumo_historico"]
    average_label = f"{average:.2f} kWh/leitura" if average is not None else "não informada"
    return {"uc_id": row["id_uc"], "municipality": row["municipio"] or "Não informado",
            "neighborhood": row["bairro"] or "Não informado", "class_name": row["classe"] or "Não informado",
            "feeder_id": row["alimentador"] or "Não informado", "priority": None, "priority_label": reason,
            "reason": row.get("motivo_prioridade") or reason, "potential_recoverable_energy_kwh": None,
            "indicators": [f"Inspeções anteriores: {row['total_inspecoes_realizadas'] if row['total_inspecoes_realizadas'] is not None else 'não informado'}",
                           f"Inspeções irregulares no histórico: {row['total_inspecoes_irregulares'] if row['total_inspecoes_irregulares'] is not None else 'não informado'}",
                           f"Média histórica por leitura: {average_label}",
                           f"GD cadastrada: {row['possui_geracao_solar'] or 'não informado'}"], "signals": []}


def queue_response(repository, filters, page, page_size, order_by, direction):
    rows, pagination = repository.queue(filters, page, page_size, order_by, direction)
    options = repository.options()
    queue_options = repository.queue_options()
    months = options["competencias"]
    if not months:
        raise AnalyticsAPIError(503, "source_unavailable", "Gold sem competências de consumo observadas.")
    meta = metadata(repository, "partial" if pagination["total"] else "empty", months[0], months[-1], filters)
    meta.contract_version = "1.1.0"
    meta.limitations.extend(LIMITATIONS)
    return QueueResponse(data={"items": [item(row) for row in rows],
                               "filter_options": queue_options, "neighborhoods": repository.queue_neighborhoods(),
                               "summary": {"total_units": pagination["total"], "highest_priority": None,
                                           "estimated_units": 0, "unavailable_estimate_units": pagination["total"]}},
                         pagination=pagination, metadata=meta)


def suspicion_response(repository, uc_id):
    row = repository.unit(uc_id)
    table = repository.tables["fila_inspecao"]
    result = repository.rows(select(table).where(table.c.id_uc == row["id_uc"]))
    if not result:
        raise AnalyticsAPIError(404, "not_found", "UC não encontrada na fila Gold.")
    source = result[0]
    historical = None
    if source.get("estado_media_historica_recuperacao") == "DISPONIVEL_REFERENCIA_HISTORICA":
        mean = source.get("media_historica_recuperacao_kwh_por_inspecao")
        lower = source.get("intervalo_historico_recuperacao_inferior_kwh")
        upper = source.get("intervalo_historico_recuperacao_superior_kwh")
        reference = source.get("referencia_media_historica_recuperacao")
        if (all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in (mean, lower, upper))
                and lower <= upper and reference in {"global", "0", "1"}):
            historical = {"mean_kwh_per_inspection": mean, "lower_kwh_per_inspection": lower,
                          "upper_kwh_per_inspection": upper, "reference": reference}
    data = {**item(source), "rule_version": repository.schema_version, "limitations": list(LIMITATIONS),
            "historical_recovery": historical,
            "estimate_evidence": {"baseline_kwh": None, "observed_kwh": None, "horizon_months": None,
                                  "reference": "Gold CSV; sem estimativa individual homologada.", "unavailable_reason": LIMITATIONS[2]}}
    months = repository.options()["competencias"]
    if not months:
        raise AnalyticsAPIError(503, "source_unavailable", "Gold sem competências de consumo observadas.")
    meta = metadata(repository, "partial", months[0], months[-1], AnalyticsFilters())
    meta.contract_version = "1.1.0"
    meta.limitations.extend(LIMITATIONS)
    return SuspicionResponse(data=data, metadata=meta)
