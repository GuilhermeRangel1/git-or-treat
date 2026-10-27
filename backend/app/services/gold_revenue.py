"""Projeção do agregado Gold no contrato de Receita, sem preço-volume presumido."""
import json
from decimal import Decimal

from app.repositories.gold import MISSING, GoldAnalyticsRepository
from app.services.analytics import AnalyticsAPIError
from app.services.revenue_analytics import _month_sequence


def number(value):
    return None if value is None else float(value)


def snapshot(month, rows):
    amounts = [row["amount"] for row in rows if row["amount"] is not None]
    return {
        "competencia": month, "billed_amount": number(sum(amounts)) if amounts else None,
        "billed_energy_kwh": None, "observed_price_brl_per_kwh": None,
        "billed_uc_count": sum(row["uc_count"] for row in rows) if rows else None,
        "status": "partial" if amounts else "unavailable",
        "limitations": ["Somente faturamento publicado na Gold; energia faturada separada indisponível."],
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


def quality(comp):
    counts = [comp[name]["billed_uc_count"] for name in ("initial", "final")]
    return {"small_base_threshold_uc": 5, "small_base": any(count is not None and count < 5 for count in counts), "percent_change_eligible": False,
            "limitations": ["Comparação percentual e preço-volume aguardam definição e cobertura homologadas."]}


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
                      "filters": scoped, "comparison": group_comparison, "quality": quality(group_comparison)})
    total_comparison = comparison(start, end, rows)
    changes = [item["comparison"]["billed_amount_change_brl"] for item in items]
    comparable = sum(Decimal(str(value)) for value in changes if value is not None)
    delta = total_comparison["billed_amount_change_brl"]
    unassigned = None if delta is None else Decimal(str(delta)) - comparable
    missing = [month for month in months if not any(row["competencia"] == month for row in rows)]
    coverage = {}
    for name in ("billed_amount", "measured_energy_kwh", "billed_energy_kwh", "paid_amount"):
        observed = name in {"billed_amount", "measured_energy_kwh"}
        coverage[name] = {"status": "partial" if observed and rows else "unavailable",
                          "covered_months": [m for m in months if m not in missing] if observed else [],
                          "missing_months": missing if observed else months,
                          "limitations": list(repository.source_limitations) if observed else ["Grandeza ausente nos CSVs; não substituímos por zero."]}
    options = repository.options()
    amounts = [r["amount"] for r in rows if r["amount"] is not None]
    energies = [r["energy"] for r in rows if r["energy"] is not None]
    return {
        "currency_unit": "BRL", "energy_unit": "kWh",
        "total_billed_amount": number(sum(amounts)) if amounts else None,
        "total_paid_amount": None, "total_billed_energy_kwh": None,
        "total_measured_energy_kwh": number(sum(energies)) if energies else None,
        "observed_price_brl_per_kwh": None, "series": series,
        "comparison": total_comparison, "quality": quality(total_comparison),
        "price_volume": {"method": "endpoint_price_volume", "reference_version": "gold-csv-v1",
                         "price_effect_brl": None, "volume_effect_brl": None, "interaction_effect_brl": None,
                         "rounding_adjustment_brl": None, "status": "unavailable",
                         "limitations": ["Gold sem energia faturada separada e sem definição homologada de preço-volume."]},
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
