"""Projeção do agregado Gold no contrato de Receita, sem preço-volume presumido."""
import json
import math
from decimal import Decimal

from app.repositories.gold import MISSING, GoldAnalyticsRepository
from app.services.analytics import AnalyticsAPIError
from app.services.revenue_analytics import _month_sequence


def number(value):
    return None if value is None else float(value)


def observed_price(rows):
    if not rows or any(row.get("comparable_amount") is None or row.get("comparable_energy") is None for row in rows):
        return None
    energy = math.fsum(row["comparable_energy"] for row in rows)
    if energy <= 0:
        return None
    return float(sum(row["comparable_amount"] for row in rows)) / energy


def snapshot(month, rows):
    amounts = [row["amount"] for row in rows if row["amount"] is not None]
    energies = [row["energy"] for row in rows if row.get("energy") is not None]
    return {
        "competencia": month, "billed_amount": number(sum(amounts)) if amounts else None,
        "billed_energy_kwh": None, "measured_energy_kwh": number(sum(energies)) if energies else None,
        "observed_price_brl_per_kwh": observed_price(rows),
        "billed_uc_count": sum(row["uc_count"] for row in rows) if rows else None,
        "status": "partial" if amounts else "unavailable",
        "limitations": ["Faturamento publicado; preço observado usa apenas a base comparável, não tarifa homologada. Energia faturada separada indisponível."],
    }


def comparison(start, end, rows):
    initial = snapshot(start, [r for r in rows if r["competencia"] == start])
    final = snapshot(end, [r for r in rows if r["competencia"] == end])
    first, last = initial["billed_amount"], final["billed_amount"]
    change = None if first is None or last is None else float(Decimal(str(last)) - Decimal(str(first)))
    return {
        "initial": initial, "final": final, "billed_amount_change_brl": change,
        "billed_energy_change_kwh": None,
        "measured_energy_change_kwh": None if initial["measured_energy_kwh"] is None or final["measured_energy_kwh"] is None else final["measured_energy_kwh"] - initial["measured_energy_kwh"],
        "billed_amount_change_percent": None,
    }


def quality(comp, *, v2=False):
    counts = [comp[name]["billed_uc_count"] for name in ("initial", "final")]
    return {"small_base_threshold_uc": 5, "small_base": any(count is not None and count < 5 for count in counts), "percent_change_eligible": False,
            "limitations": ["Percentual não calculado: a publicação não comprova fechamento contábil do faturamento nos meses comparados." if v2 else "Comparação percentual e preço-volume aguardam definição e cobertura homologadas."]}


WINDOW_COMPONENTS = {
    "volume": "efeito_volume_reais",
    "preco": "efeito_preco_observado_reais",
    "interacao": "efeito_interacao_reais",
    "entradas": "variacao_entradas_reais",
    "saidas": "variacao_saidas_reais",
    "sem_leitura": "variacao_sem_leitura_fora_base_reais",
    "outros": "variacao_outros_fora_base_reais",
}


def window_decomposition(repository, filters, *, rows=None):
    if getattr(repository, "schema_version", "gold-csv-v1") != "gold-csv-v2":
        return None
    unavailable = {"status": "unavailable", "windows": [], "method": None, "components": {},
                   "total_change_brl": None, "residual_brl": None, "group_count": 0,
                   "incomplete_groups": 0, "limitations": []}
    if filters.alimentador:
        unavailable["limitations"] = ["A decomposição publicada não possui recorte por alimentador."]
        return unavailable
    config = repository.origin.get("preco_volume_configuracao") or {}
    windows = config.get("janelas") or {}
    keys = ("inicio_p0", "fim_p0", "inicio_p1", "fim_p1")
    if config.get("estado") != "CONFIGURADA" or not all(isinstance(windows.get(k), str) for k in keys):
        unavailable["limitations"] = ["A publicação não informa janelas configuradas para a decomposição."]
        return unavailable
    unavailable["windows"] = [windows[k] for k in keys]
    rows = repository.revenue_decomposition_rows(filters) if rows is None else rows
    if not rows:
        unavailable["limitations"] = ["Não há decomposição publicada para este recorte."]
        return unavailable
    method = config.get("metodo")
    if (method != "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3" or
        any(tuple(row[k] for k in keys) != tuple(windows[k] for k in keys) or row["metodo"] != method for row in rows)):
        unavailable["limitations"] = ["As janelas ou o método da decomposição divergem da publicação."]
        return unavailable
    if any(row["estado_decomposicao"] not in {"CALCULADA_BASE_COMUM", "SEM_BASE_COMUM"} for row in rows):
        unavailable["limitations"] = ["Cobertura insuficiente para a decomposição deste recorte."]
        return unavailable
    fields = [*WINDOW_COMPONENTS.values(), "variacao_faturamento_total_reais"]
    if any(value is not None and not math.isfinite(value) for row in rows for value in (row[field] for field in fields)):
        unavailable["limitations"] = ["A decomposição contém valores inválidos."]
        return unavailable
    def known_sum(field):
        values = [row[field] for row in rows if row[field] is not None]
        return math.fsum(values) if values else None
    incomplete = sum(any(row[field] is None for field in fields) for row in rows)
    components = {key: known_sum(field) for key, field in WINDOW_COMPONENTS.items()}
    total = (known_sum("variacao_faturamento_total_reais")
             if all(row["variacao_faturamento_total_reais"] is not None for row in rows) else None)
    residual = None
    if not incomplete and total is not None:
        residual = total - math.fsum(components.values())
        if abs(residual) > max(0.000001, abs(total) * 1e-9):
            unavailable["limitations"] = ["Os componentes não reconciliam com a variação da publicação."]
            return unavailable
    notes = ["Preço observado e consumo medido na base comparável; não representam tarifa homologada nem energia faturada.",
             "Método candidato; dimensões cadastrais atuais e cobertura de extração não comprovam fechamento contábil."]
    if incomplete:
        notes.append("Somas dos componentes apresentam somente grupos com valor conhecido; há grupos sem base comum. Não são um fechamento integral.")
    def complete_sum(field):
        values = [row.get(field) for row in rows]
        return math.fsum(values) if all(value is not None and math.isfinite(value) for value in values) else None
    initial = complete_sum("faturamento_p0_reais")
    final = complete_sum("faturamento_p1_reais")
    bases_match = (initial is not None and final is not None and total is not None
                   and abs(final - initial - total) <= max(0.000001, abs(total) * 1e-9))
    eligible = (bases_match and initial > 0
                and any((row.get("qtd_ucs_observadas") or 0) >= 5 for row in rows))
    if not eligible:
        notes.append("Percentual financeiro exige bases reconciliadas, P0 positivo e base mínima de cinco UCs garantida no recorte.")
    else:
        notes.append("Percentuais observados sobre o faturamento P0; não certificam fechamento contábil.")
    return {"status": "partial" if incomplete else "available", "windows": unavailable["windows"], "method": method,
            "components": components, "total_change_brl": total, "residual_brl": residual,
            "initial_amount_brl": initial if bases_match else None,
            "final_amount_brl": final if bases_match else None,
            "change_percent": 100 * total / initial if eligible else None,
            "component_percentage_points": {key: 100 * value / initial for key, value in components.items()
                                            if value is not None and all(row[WINDOW_COMPONENTS[key]] is not None for row in rows)} if eligible else {},
            "group_count": len(rows), "incomplete_groups": incomplete, "limitations": notes}


def window_breakdown(repository, filters, group_by, *, rows=None):
    """Agrupa os mesmos fatos V3, sem consultas por linha ou médias recalculadas."""
    if getattr(repository, "schema_version", None) != "gold-csv-v2" or filters.alimentador:
        return []
    rows = repository.revenue_decomposition_rows(filters) if rows is None else rows
    dimensions = ["municipio", "bairro"] if group_by == "bairro" else [group_by]
    columns = {"municipio": "municipio", "bairro": "bairro", "classe": "classe_consumo"}
    groups = {}
    for row in rows:
        key = tuple(row.get(columns[field]) for field in dimensions)
        groups.setdefault(key, []).append(row)
    result = []
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        scoped = filters.model_dump()
        scoped.update({field: value if value is not None else MISSING for field, value in zip(dimensions, key)})
        result.append({"key": json.dumps(key, ensure_ascii=True), "label": " / ".join(value or "Não informado" for value in key),
                       "filters": scoped, "decomposition": window_decomposition(repository, filters, rows=group)})
    return result


def build_gold_revenue(repository: GoldAnalyticsRepository, start, end, filters, group_by, *, include_diagnosis=False):
    if (int(end[:4]) - int(start[:4])) * 12 + int(end[5:]) - int(start[5:]) >= 120:
        raise AnalyticsAPIError(422, "invalid_query", "Consulte até 120 competências por vez.")
    months = _month_sequence(start, end)
    rows = repository.revenue_groups(start, end, filters, group_by)
    series = []
    for month in months:
        selected = [row for row in rows if row["competencia"] == month]
        amounts = [r["amount"] for r in selected if r["amount"] is not None]
        energies = [r["energy"] for r in selected if r["energy"] is not None]
        series.append({
            "competencia": month, "billed_amount": number(sum(amounts)) if amounts else None,
            "measured_energy_kwh": number(sum(energies)) if energies else None,
            "paid_amount": None, "billed_energy_kwh": None,
        })
    grouped = {}
    dimensions = ["municipio", "bairro"] if group_by == "bairro" else [group_by]
    for row in rows:
        key = tuple(row[field] for field in dimensions)
        grouped.setdefault(key, []).append(row)
    items = []
    for key, group in sorted(grouped.items(), key=lambda item: str(item[0])):
        scoped = filters.model_dump()
        scoped.update({field: value if value is not None else MISSING for field, value in zip(dimensions, key)})
        group_comparison = comparison(start, end, group)
        items.append({"key": json.dumps(key, ensure_ascii=True), "label": " / ".join(v or "Não informado" for v in key),
                      "filters": scoped, "comparison": group_comparison, "quality": quality(group_comparison, v2=getattr(repository, "schema_version", "gold-csv-v1") == "gold-csv-v2")})
    total_comparison = comparison(start, end, rows)
    changes = [item["comparison"]["billed_amount_change_brl"] for item in items]
    comparable = sum(Decimal(str(value)) for value in changes if value is not None)
    delta = total_comparison["billed_amount_change_brl"]
    unassigned = None if delta is None else Decimal(str(delta)) - comparable
    coverage = {}
    for name in ("billed_amount", "measured_energy_kwh", "billed_energy_kwh", "paid_amount"):
        observed = name in {"billed_amount", "measured_energy_kwh"}
        covered = [row["competencia"] for row in series if row[name] is not None] if observed else []
        coverage[name] = {"status": "partial" if covered else "unavailable",
                          "covered_months": covered,
                          "missing_months": [month for month in months if month not in covered],
                          "limitations": list(repository.source_limitations) if observed else ["Grandeza ausente nos CSVs; não substituímos por zero."]}
    options = repository.options()
    amounts = [r["amount"] for r in rows if r["amount"] is not None]
    energies = [r["energy"] for r in rows if r["energy"] is not None]
    decomposition_rows = (repository.revenue_decomposition_rows(filters)
                          if getattr(repository, "schema_version", None) == "gold-csv-v2" and not filters.alimentador
                          and (repository.origin.get("preco_volume_configuracao") or {}).get("estado") == "CONFIGURADA" else [])
    window = window_decomposition(repository, filters, rows=decomposition_rows)
    diagnosis = None
    if include_diagnosis:
        from app.services.revenue_diagnosis import build_revenue_diagnosis
        diagnosis = build_revenue_diagnosis(repository, filters, window, decomposition_rows)
    return {
        "currency_unit": "BRL", "energy_unit": "kWh",
        "total_billed_amount": number(sum(amounts)) if amounts else None,
        "total_paid_amount": None, "total_billed_energy_kwh": None,
        "total_measured_energy_kwh": number(sum(energies)) if energies else None,
        "observed_price_brl_per_kwh": observed_price(rows), "series": series,
        "comparison": total_comparison, "quality": quality(total_comparison, v2=getattr(repository, "schema_version", "gold-csv-v1") == "gold-csv-v2"),
        "window_decomposition": window,
        "diagnosis": diagnosis,
        "window_breakdown": window_breakdown(repository, filters, group_by, rows=decomposition_rows),
        "price_volume": {"method": "endpoint_price_volume", "reference_version": getattr(repository, "schema_version", "gold-csv-v1"),
                         "price_effect_brl": None, "volume_effect_brl": None, "interaction_effect_brl": None,
                         "rounding_adjustment_brl": None, "status": "unavailable",
                         "limitations": ["Decomposição da publicação ainda não foi integrada a esta comparação entre competências; suas janelas e cobertura precisam ser conferidas."]},
        "coverage": {"requested_months": months, **coverage},
        "breakdown": {"dimension": group_by, "items": items, "reconciliation": {
            "status": "partial" if delta is None or any(v is None for v in changes) else "available",
            "initial_known_sum_brl": total_comparison["initial"]["billed_amount"],
            "final_known_sum_brl": total_comparison["final"]["billed_amount"],
            "comparable_change_sum_brl": number(comparable) if items else None,
            "non_comparable_group_count": sum(v is None for v in changes),
            "unattributed_change_brl": number(unassigned), "residual_brl": 0 if delta is not None else None,
            "limitations": ["Grupos sem um dos extremos não recebem variação zero."],
        }},
        "filter_options": {"municipios": options["municipio"], "bairros": options["bairros"], "classes": options["classe"]},
    }
