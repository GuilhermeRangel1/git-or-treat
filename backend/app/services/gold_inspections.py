"""Fila publicada na Gold; preserva prioridade categórica e não inventa score."""
from sqlalchemy import select

from app.models.gold_v1 import TABLES
from app.schemas.analytics import AnalyticsFilters
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.services.analytics import AnalyticsAPIError, metadata

LIMITATIONS = [
    "Prioridade textual fornecida pela Gold; ordem categórica Alta, Média, Revisar e Baixa, sem score numérico.",
    "Critério de priorização ainda aguarda homologação no dicionário; suspeita não confirma irregularidade.",
    "Energia recuperável indisponível: os CSVs não fornecem estimativa homologada.",
    "Criação de ordens a partir da fila Gold aguarda homologação e identidade autorizada; consulta disponível.",
]


def item(row):
    reason = row["prioridade_inspecao"] or "Não informado"
    return {"uc_id": row["id_uc"], "municipality": row["municipio"] or "Não informado",
            "neighborhood": row["bairro"] or "Não informado", "class_name": row["classe"] or "Não informado",
            "feeder_id": row["alimentador"] or "Não informado", "priority": None, "priority_label": reason,
            "reason": reason, "potential_recoverable_energy_kwh": None,
            "indicators": [f"Inspeções anteriores: {row['total_inspecoes_realizadas'] if row['total_inspecoes_realizadas'] is not None else 'não informado'}",
                           f"Inspeções irregulares no histórico: {row['total_inspecoes_irregulares'] if row['total_inspecoes_irregulares'] is not None else 'não informado'}",
                           f"GD cadastrada: {row['possui_geracao_solar'] or 'não informado'}"], "signals": []}


def queue_response(repository, filters, page, page_size, order_by, direction):
    rows, pagination = repository.queue(filters, page, page_size, order_by, direction)
    options = repository.options()
    months = options["competencias"]
    meta = metadata(repository, "partial" if pagination["total"] else "empty", months[0], months[-1], filters)
    meta.contract_version = "1.1.0"
    meta.limitations.extend(LIMITATIONS)
    return QueueResponse(data={"items": [item(row) for row in rows],
                               "filter_options": {field: options[field] for field in ("municipio", "bairro", "classe", "alimentador")},
                               "summary": {"total_units": pagination["total"], "highest_priority": None,
                                           "estimated_units": 0, "unavailable_estimate_units": pagination["total"]}},
                         pagination=pagination, metadata=meta)


def suspicion_response(repository, uc_id):
    row = repository.unit(uc_id)
    table = TABLES["fila_inspecao"]
    result = repository.rows(select(table).where(table.c.id_uc == row["id_uc"]))
    if not result:
        raise AnalyticsAPIError(404, "not_found", "UC não encontrada na fila Gold.")
    data = {**item(result[0]), "rule_version": "gold-csv-v1", "limitations": list(LIMITATIONS),
            "estimate_evidence": {"baseline_kwh": None, "observed_kwh": None, "horizon_months": 1,
                                  "reference": "Gold CSV v1; sem estimativa publicada.", "unavailable_reason": LIMITATIONS[2]}}
    months = repository.options()["competencias"]
    meta = metadata(repository, "partial", months[0], months[-1], AnalyticsFilters())
    meta.contract_version = "1.1.0"
    meta.limitations.extend(LIMITATIONS)
    return SuspicionResponse(data=data, metadata=meta)
