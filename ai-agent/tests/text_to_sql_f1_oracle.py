"""Independent Decimal oracle for the authored F1 questions, never generated SQL."""

from decimal import Decimal


def reference_rows(case_id, rows):
    selected = [r for r in rows if "2026-01" <= r["competencia"] <= "2026-06"]
    if case_id != "F1-06":
        selected = [r for r in selected if r["municipio"] == "Recife"]
    if case_id in ("F1-01", "F1-07", "F1-08"):
        selected = [r for r in selected if r["competencia"] == "2026-06"]

    def total(items):
        values = [
            Decimal(r["receita_total_reais"]) for r in items if r["receita_total_reais"] is not None
        ]
        return format(sum(values, Decimal(0)), ".2f") if values else None

    key = {"F1-05": "competencia", "F1-06": "municipio", "F1-07": "classe_consumo"}.get(case_id)
    if key:
        result = [
            {key: value, "revenue": total([r for r in selected if r[key] == value])}
            for value in sorted({r[key] for r in selected})
        ]
        if case_id == "F1-06":
            result.sort(key=lambda r: (-Decimal(r["revenue"]), r[key]))
            result = result[:5]
        return result
    if case_id == "F1-04":
        previous = [
            r
            for r in rows
            if r["municipio"] == "Recife" and "2025-01" <= r["competencia"] <= "2025-06"
        ]
        return [
            {"year": "2025", "revenue": total(previous)},
            {"year": "2026", "revenue": total(selected)},
        ]
    return [{"revenue": total(selected)}]
