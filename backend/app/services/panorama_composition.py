"""Concentração da receita observada, reutilizada pelo Panorama e pela síntese."""
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Literal

from app.schemas.ai_insight import PanoramaCurrentComposition


def revenue_composition_from_groups(
    rows: Sequence[Mapping[str, Any]], *, total: Decimal,
    dimension: Literal["municipio", "classe", "bairro"],
) -> PanoramaCurrentComposition | None:
    if not total.is_finite() or total <= 0 or not rows or len(rows) > 1000:
        return None
    values = {row["segment"]: Decimal(str(row["revenue"]))
              for row in rows if row["revenue"] is not None}
    if not values or any(not v.is_finite() or v < 0 for v in values.values()):
        return None
    if len({row["segment"] for row in rows}) != len(rows):
        return None
    with localcontext() as context:
        context.prec = 100
        if sum(values.values()) != total:
            return None
        name = min(values, key=lambda key: (-values[key], key))
        return PanoramaCurrentComposition(
            dimension=dimension, segmento=name,
            valor=float(values[name].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            participacaoPercentual=float((values[name] / total * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP)),
        )
