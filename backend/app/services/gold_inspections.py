"""Fila publicada na Gold; preserva prioridade categórica e não inventa score."""
import json
import math
import re
from sqlalchemy import select

from app.schemas.analytics import AnalyticsFilters
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.services.analytics import AnalyticsAPIError, metadata

LIMITATIONS = [
    "Prioridade categórica publicada pela Gold, sem score numérico; regra candidata aguarda homologação.",
    "Categorias de triagem descritas no dicionário Gold; a prioridade e o histórico não confirmam uma nova irregularidade.",
    "Estimativa condicional de energia a recuperar se a irregularidade se confirmar; não garante recuperação na UC.",
    "Criação de ordens a partir da fila Gold aguarda homologação e identidade autorizada; consulta disponível.",
    "O período da resposta indica os extremos das competências de consumo observadas, sem comprovar todos os meses; a fila e seus históricos acumulados não informam janela temporal própria.",
]

RECOVERY_METHOD = "CONSUMO_CONDICIONAL_V1"
RECOVERY_STATUS = "ESTIMATIVA_UC_POR_CONSUMO_SE_CONFIRMADA"
RECOVERY_VALIDATION_STATUS = "CANDIDATO_PASSOU_VALIDACAO_TEMPORAL"
RECOVERY_UNAVAILABLE = "A Gold não publicou uma estimativa individual validada para esta UC."


def _recovery_validation(row):
    """Return only the approved temporal-validation fields for a candidate estimate."""
    raw = row.get("validacao_recuperacao_json")
    if not isinstance(raw, str) or len(raw) > 16_384:
        return None
    try:
        report = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (ValueError, TypeError):
        return None
    estimate = report.get("estimativa_uc") if isinstance(report, dict) else None
    if not isinstance(estimate, dict):
        return None
    criteria = estimate.get("criterios")
    window = estimate.get("janela_aplicacao")
    if (
        estimate.get("estado") != RECOVERY_VALIDATION_STATUS
        or estimate.get("metodo") != RECOVERY_METHOD
        or not isinstance(criteria, dict)
        or criteria.get("nivel_faixa") != 0.9
        or not isinstance(window, dict)
    ):
        return None
    anchor = window.get("ancora")
    months = window.get("meses")
    minimum_months = window.get("minimo_meses")
    if (
        not isinstance(anchor, str)
        or not re.fullmatch(r"(?!0000)\d{4}-(0[1-9]|1[0-2])", anchor)
        or type(months) is not int
        or months <= 0
        or type(minimum_months) is not int
        or minimum_months <= 0
        or minimum_months > months
    ):
        return None
    return {
        "confidence_level": 0.9,
        "window_anchor": anchor,
        "window_months": months,
        "minimum_window_months": minimum_months,
    }


def _recoverable_estimate(row):
    values = (
        row.get("energia_estimada_recuperavel_kwh"),
        row.get("intervalo_recuperacao_inferior_kwh"),
        row.get("intervalo_recuperacao_superior_kwh"),
    )
    if (
        row.get("estado_estimativa_recuperacao") != RECOVERY_STATUS
        or row.get("metodo_estimativa_recuperacao") != RECOVERY_METHOD
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in values
        )
        or values[1] > values[0]
        or values[0] > values[2]
    ):
        return None, None
    validation = _recovery_validation(row)
    if validation is None:
        return None, None
    return values[0], validation


def item(row):
    reason = row["prioridade_inspecao"] or "Não informado"
    average = row["media_consumo_historico"]
    average_label = f"{average:.2f} kWh/leitura" if average is not None else "não informada"
    estimate, validation = _recoverable_estimate(row)
    return {"uc_id": row["id_uc"], "municipality": row["municipio"] or "Não informado",
            "neighborhood": row["bairro"] or "Não informado", "class_name": row["classe"] or "Não informado",
            "feeder_id": row["alimentador"] or "Não informado", "priority": None, "priority_label": reason,
            "reason": row.get("motivo_prioridade") or reason, "potential_recoverable_energy_kwh": estimate,
            "recovery_unavailable_reason": None if estimate is not None else RECOVERY_UNAVAILABLE,
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


def _six_months(end):
    year, month = map(int, end.split("-"))
    last = year * 12 + month - 1
    return [f"{value // 12:04d}-{value % 12 + 1:02d}" for value in range(last - 5, last + 1)]


def consumption_comparison(repository, uc_id, end):
    months = _six_months(end)
    t = repository.tables["consumo_mensal_uc"]
    rows = repository.rows(select(t).where(t.c.id_uc == uc_id, t.c.competencia.in_(months)))
    return comparison_from_rows(rows, end)


def comparison_from_rows(rows, end):
    months = _six_months(end)
    by_month = {row["competencia"]: row for row in rows}
    result = {"baseline_start": months[0], "baseline_end": months[2], "recent_start": months[3],
              "recent_end": months[5], "baseline_kwh": None, "recent_kwh": None, "change_percent": None,
              "unavailable_reason": None}
    for month in months:
        row = by_month.get(month)
        value = row["consumo_kwh"] if row else None
        if (not row or value is None or not math.isfinite(value) or value < 0 or
                not row["qtd_leituras_observadas"] or row["qtd_leituras_validas"] != row["qtd_leituras_observadas"]):
            result["unavailable_reason"] = "São necessárias leituras válidas nos seis meses; ausência ou leitura inválida não é zero."
            return result
    before = math.fsum(by_month[month]["consumo_kwh"] for month in months[:3])
    recent = math.fsum(by_month[month]["consumo_kwh"] for month in months[3:])
    result.update(baseline_kwh=before, recent_kwh=recent,
                  change_percent=(recent - before) / before * 100 if before else None,
                  unavailable_reason="Percentual indisponível porque o consumo anterior é zero." if not before else None)
    return result


def investigation_potential_from_rows(rows, end, meters=()):
    """Cenário de queda de consumo em trimestres homólogos, não recuperação comprovada."""
    year, month = map(int, end.split("-"))
    last = year * 12 + month - 1
    if last - 14 < 12:
        return None
    recent = [f"{value // 12:04d}-{value % 12 + 1:02d}" for value in range(last - 2, last + 1)]
    baseline = [f"{value // 12:04d}-{value % 12 + 1:02d}" for value in range(last - 14, last - 11)]
    result = {"baseline_start": baseline[0], "baseline_end": baseline[-1],
              "recent_start": recent[0], "recent_end": recent[-1],
              "baseline_kwh": None, "recent_kwh": None, "potential_kwh": None,
              "unavailable_reason": None}
    for meter in meters:
        for field, sentinel, future in (("data_instalacao", "flag_instalacao_sentinela", "flag_instalacao_futura"),
                                        ("data_retirada", "flag_retirada_sentinela", "flag_retirada_futura")):
            event_date = meter[field]
            if (event_date is not None and not meter[sentinel] and not meter[future] and
                    baseline[0] <= event_date.strftime("%Y-%m") <= recent[-1]):
                result["unavailable_reason"] = "Instalação ou retirada de medidor registrada entre os períodos; a comparação exige revisão."
                return result
    by_month = {row["competencia"]: row for row in rows}
    for competence in baseline + recent:
        row = by_month.get(competence)
        value = row["consumo_kwh"] if row else None
        if (row is None or value is None or not math.isfinite(value) or value < 0 or
                not row["qtd_leituras_observadas"] or row["qtd_leituras_observadas"] < 0 or
                row["qtd_leituras_validas"] != row["qtd_leituras_observadas"]):
            result["unavailable_reason"] = "São necessárias leituras válidas nos seis meses correspondentes; lacunas não são zero."
            return result
    earlier = math.fsum(by_month[m]["consumo_kwh"] for m in baseline)
    current = math.fsum(by_month[m]["consumo_kwh"] for m in recent)
    result.update(baseline_kwh=earlier, recent_kwh=current, potential_kwh=max(0.0, earlier - current))
    return result


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
    months = repository.options()["competencias"]
    if not months:
        raise AnalyticsAPIError(503, "source_unavailable", "Gold sem competências de consumo observadas.")
    comparison = consumption_comparison(repository, uc_id, months[-1]) if repository.schema_version == "gold-csv-v2" else None
    data = {**item(source), "rule_version": repository.schema_version, "limitations": list(LIMITATIONS),
            "historical_recovery": historical, "consumption_comparison": comparison,
            "estimate_evidence": {"baseline_kwh": None, "observed_kwh": None, "horizon_months": None,
                                  "reference": "Gold CSV; sem estimativa individual homologada.", "unavailable_reason": LIMITATIONS[2]}}
    meta = metadata(repository, "partial", months[0], months[-1], AnalyticsFilters())
    meta.contract_version = "1.1.0"
    meta.limitations.extend(LIMITATIONS)
    return SuspicionResponse(data=data, metadata=meta)
