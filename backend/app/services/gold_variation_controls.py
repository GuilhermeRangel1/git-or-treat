"""Reconcilia a comparação fixa por UC com a série mensal do mesmo snapshot."""

from decimal import Decimal, DecimalException

from sqlalchemy import case, func, select

from app.models.gold_v2_load import TABLES


def observe_variation_controls(read_rows, *, population) -> dict[str, bool]:
    monthly = TABLES["consumo_mensal_uc"].c
    windows = (("2022-07", "2023-06"), ("2025-07", "2026-06"))
    columns = [monthly.id_uc]
    for index, (start, end) in enumerate(windows):
        measured = case((monthly.competencia.between(start, end), monthly.consumo_kwh))
        columns.extend((func.avg(measured).label(f"mean{index}"),
                        func.count(measured).label(f"months{index}")))
    source = {row["id_uc"]: row for row in read_rows(select(*columns).group_by(monthly.id_uc))}
    published = list(read_rows(TABLES["variacao_consumo_uc"]))
    keys = [row["id_uc"] for row in published]
    complete = bool(published) and len(keys) == len(set(keys)) and set(keys) == set(population)
    flags = complete

    def number(value):
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
        except DecimalException:
            return None
        return parsed if parsed.is_finite() else None

    for row in published:
        reference = population.get(row["id_uc"], {})
        complete &= ((row["municipio"] or "Não informado")
                     == (reference.get("municipio") or "Não informado"))
        complete &= row["possui_gd"] == reference.get("possui_gd")
        expected = source.get(row["id_uc"], {})
        means = []
        for index, suffix in enumerate(("inicial", "final")):
            raw = number(expected.get(f"mean{index}"))
            observed = number(row[f"consumo_medio_{suffix}"])
            complete &= expected.get(f"mean{index}") is None or raw is not None
            complete &= row[f"consumo_medio_{suffix}"] is None or observed is not None
            count = expected.get(f"months{index}", 0)
            complete &= row[f"meses_com_leitura_p{index + 1}"] == count
            complete &= ((raw is None and observed is None) or (
                raw is not None and observed is not None and abs(raw - observed) <= Decimal("0.01")
            ))
            means.append(raw)
        initial, final = means
        available = initial is not None and initial > 0 and final is not None
        expected_drop = bool(available and (final - initial) / initial < Decimal("-0.30"))
        flags &= row["queda_consumo_superior_30_pct"] is expected_drop
        flags &= (row["variacao_pct"] is None) == (not available)
        flags &= row["variacao_pct"] is None or number(row["variacao_pct"]) is not None
    return {"C08": bool(complete and flags), "C09": bool(complete)}
