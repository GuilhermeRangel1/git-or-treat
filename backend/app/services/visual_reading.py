"""Diferenças e destaques verificáveis, sem causa inferida nem nova chamada de modelo."""

import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.schemas.chat_visualization import ChatVisualPoint
from app.schemas.visual_reading import VisualReading

MONTHS = (
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
)


def label(value: str) -> str:
    return re.sub(
        r"(?<!\d)(\d{4})-(0[1-9]|1[0-2])$",
        lambda m: f"{MONTHS[int(m[2]) - 1]}/{m[1]}",
        value,
    )


def number(value: Decimal, precision: int) -> str:
    rounded = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    return (
        format(rounded, f",.{precision}f")
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
    )


def build_visual_reading(
    points: Sequence[ChatVisualPoint], *, kind: str, unit: str, precision: int
) -> VisualReading | None:
    if len(points) < 2:
        return None
    ids = tuple(p.observation_id for p in points)

    def amount(value: float | Decimal):
        text = number(Decimal(str(value)), precision)
        return f"R$ {text}" if unit in {"R$", "BRL"} else f"{text} {unit}"

    with localcontext() as context:
        context.prec = 400
        if kind in {"horizontal", "donut"} or [p.label for p in points] != sorted(
            p.label for p in points
        ):
            highest = max(points, key=lambda p: p.value)
            lowest = min(points, key=lambda p: p.value)
            if highest.value == lowest.value:
                summary = f"Os {len(points)} grupos exibidos têm o mesmo valor observado: {amount(highest.value)}."
            else:
                summary = f"Entre os grupos exibidos, {label(highest.label)} tem o maior valor: {amount(highest.value)}. {label(lowest.label)} tem o menor: {amount(lowest.value)}."
            summary += (
                " Os setores representam parcelas do total observado, conforme a legenda."
                if kind == "donut"
                else " Essa comparação não representa participação no total."
            )
            next_step = "Investigue os grupos exibidos mantendo o mesmo indicador e recorte antes de atribuir uma causa à diferença."
        else:
            first, last = points[0], points[-1]
            change = Decimal(str(last.value)) - Decimal(str(first.value))
            direction = (
                "aumento" if change > 0 else "redução" if change < 0 else "diferença"
            )
            summary = f"De {label(first.label)} a {label(last.label)}, o valor observado passou de {amount(first.value)} para {amount(last.value)}: {direction} de {amount(abs(change))}."
            if first.value > 0 and change:
                percent = change / Decimal(str(first.value)) * 100
                summary += f" Isso corresponde a {number(abs(percent), 2)}% em relação ao primeiro valor."
            if len(points) >= 3:
                highest = max(points, key=lambda p: p.value)
                summary += f" O maior valor exibido foi {amount(highest.value)}, em {label(highest.label)}."
            next_step = "Compare o mesmo indicador em outras competências, mantendo os filtros, para investigar se o movimento se repete."
    if len(summary) > 900:
        return None
    return VisualReading(summary=summary, observation_ids=ids, next_step=next_step)
