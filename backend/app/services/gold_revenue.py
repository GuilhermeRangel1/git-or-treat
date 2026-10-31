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
    return {
        "competencia": month, "billed_amount": number(sum(amounts)) if amounts else None,
        "billed_energy_kwh": None, "observed_price_brl_per_kwh": observed_price(rows),
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
        "billed_energy_change_kwh": None, "measured_energy_change_kwh": None,
        "billed_amount_change_percent": None,
    }


def quality(comp, *, v2=False):
    counts = [comp[name]["billed_uc_count"] for name in ("initial", "final")]
    return {"small_base_threshold_uc": 5, "small_base": any(count is not None and count < 5 for count in counts), "percent_change_eligible": False,
            "limitations": ["Comparação percentual entre competências aguarda cobertura homologada." if v2 else "Comparação percentual e preço-volume aguardam definição e cobertura homologadas."]}


WINDOW_COMPONENTS = {
    "volume": "efeito_volume_reais",
    "preco": "efeito_preco_observado_reais",
    "interacao": "efeito_interacao_reais",
    "entradas": "variacao_entradas_reais",
    "saidas": "variacao_saidas_reais",
    "sem_leitura": "variacao_sem_leitura_fora_base_reais",
    "outros": "variacao_outros_fora_base_reais",
}


def window_decomposition(repository, filters):
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
    rows = repository.revenue_decomposition_rows(filters)
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
    return {"status": "partial" if incomplete else "available", "windows": unavailable["windows"], "method": method,
            "components": components, "total_change_brl": total, "residual_brl": residual,
            "group_count": len(rows), "incomplete_groups": incomplete, "limitations": notes}


def build_gold_revenue(repository: GoldAnalyticsRepository, start, end, filters, group_by):
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
    return {
        "currency_unit": "BRL", "energy_unit": "kWh",
        "total_billed_amount": number(sum(amounts)) if amounts else None,
        "total_paid_amount": None, "total_billed_energy_kwh": None,
        "total_measured_energy_kwh": number(sum(energies)) if energies else None,
        "observed_price_brl_per_kwh": observed_price(rows), "series": series,
        "comparison": total_comparison, "quality": quality(total_comparison, v2=getattr(repository, "schema_version", "gold-csv-v1") == "gold-csv-v2"),
        "window_decomposition": window_decomposition(repository, filters),
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
