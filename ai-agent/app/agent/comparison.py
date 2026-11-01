"""Deriva variação somente dos dois agregados mensais já validados."""

from decimal import ROUND_HALF_EVEN, Decimal
from math import isfinite

from app.ports.evidence import EvidenceContractInvalid
from app.schemas.read_plan import LogicalReadPlan


class ComparisonUnavailable(Exception):
    """A fonte não sustenta uma comparação completa no mesmo recorte."""


def comparison_records(
    plan: LogicalReadPlan, records: list[dict[str, object]],
) -> list[dict[str, object]]:
    assert plan.comparison_periods is not None
    baseline, target = plan.comparison_periods
    if plan.group_by_dimension_ids:
        dimension = plan.group_by_dimension_ids[0]
        groups: dict[str, list[dict[str, object]]] = {}
        for row in records:
            value = row.get("dimensions", {}).get(dimension)
            if not isinstance(value, str):
                raise EvidenceContractInvalid("rótulo do grupo ausente")
            groups.setdefault(value, []).append(row)
        if not groups:
            raise ComparisonUnavailable
        candidates = []
        for name, rows in groups.items():
            periods = {row["period"]: row for row in rows}
            if len(rows) != 2 or set(periods) != {baseline, target}:
                raise ComparisonUnavailable
            delta = (Decimal(str(periods[target]["value"]))
                     - Decimal(str(periods[baseline]["value"])))
            candidates.append((delta, name, rows))
        # O ranking usa a variação absoluta e desempata pelo rótulo, após conferir todos os grupos.
        _, _, records = min(candidates, key=lambda item: (item[0], item[1]))
    by_period = {row.get("period"): row for row in records}
    if len(records) != 2 or set(by_period) != {baseline, target}:
        raise ComparisonUnavailable
    first, last = by_period[baseline], by_period[target]
    if first.get("dimensions", {}) != last.get("dimensions", {}):
        raise EvidenceContractInvalid("comparação entre recortes diferentes")
    initial, final = Decimal(str(first["value"])), Decimal(str(last["value"]))
    delta = final - initial
    def displayed(value: Decimal) -> float:
        number = float(value.quantize(Decimal("0.01"), ROUND_HALF_EVEN))
        if not isfinite(number):
            raise ComparisonUnavailable
        return number

    result = [dict(first, observation_id="row_1", value=displayed(initial)),
              dict(last, observation_id="row_2", value=displayed(final))]
    result.append({
        "observation_id": "row_3", "value": displayed(delta), "unit": plan.unit,
        "period": f"Variação absoluta de {baseline} a {target}",
        **({"dimensions": first["dimensions"]} if "dimensions" in first else {}),
    })
    # Base zero ou negativa não autoriza crescimento percentual convencional.
    if initial > 0:
        percentage = (delta / initial * 100).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
        result.append({
            "observation_id": "row_4", "value": displayed(percentage), "unit": "%",
            "period": f"Variação percentual de {baseline} a {target}",
            **({"dimensions": first["dimensions"]} if "dimensions" in first else {}),
        })
    return result
