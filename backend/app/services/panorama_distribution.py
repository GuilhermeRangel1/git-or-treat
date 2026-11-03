"""Partição limitada da mesma métrica/publicação exibida pelo Panorama."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import TYPE_CHECKING, Any, Literal

from app.schemas.chat_visualization import ChatVisualPoint
from app.schemas.panorama import (
    PanoramaDistribution,
    PanoramaDistributionPoint,
    PanoramaMetric,
)
from app.services.visual_reading import build_visual_reading

if TYPE_CHECKING:
    from app.repositories.panorama import GoldPanoramaRepository
    from app.services.panorama import GoldFinancialSnapshot


def distribution_from_groups(
    groups: Sequence[Mapping[str, Any]],
    *,
    dimension: Literal["municipio", "classe"],
    period: str,
    metric_id: str,
    unit: str,
    total: Decimal | float | None,
    complete: bool,
) -> PanoramaDistribution | None:

    if total is None or not 2 <= len(groups) <= 1000:
        return None

    if any(
        not isinstance(row["segment"], str)
        or not row["segment"].strip()
        or len(row["segment"]) > 120
        for row in groups
    ):
        return None

    if len({row["segment"] for row in groups}) != len(groups):
        return None

    with localcontext() as context:
        context.prec = 100

        expected = Decimal(str(total))

        observed = sum(
            (
                Decimal(str(row["revenue"]))
                for row in groups
                if row["revenue"] is not None
            ),
            Decimal(0),
        )

        if not expected.is_finite() or observed != expected:
            return None

        partition = (
            complete
            and expected > 0
            and all(
                row["revenue"] is not None and Decimal(str(row["revenue"])) >= 0
                for row in groups
            )
        )

        points = []

        for row in sorted(
            groups,
            key=lambda r: (
                r["revenue"] is None,
                -Decimal(str(r["revenue"] or 0)),
                r["segment"],
            ),
        ):
            value = None if row["revenue"] is None else Decimal(str(row["revenue"]))

            percent = (
                (value / expected * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if partition
                else None
            )

            points.append(
                PanoramaDistributionPoint(
                    segmento=row["segment"],
                    valor=None if value is None else float(value),
                    percentual=None if percent is None else float(percent),
                )
            )

    visual = points if len(points) <= 6 else points[:10]
    grouped = 0
    if partition and len(points) > 6:
        grouped = len(points) - 5
        ordered = sorted(
            groups, key=lambda row: (-Decimal(str(row["revenue"])), row["segment"])
        )
        with localcontext() as context:
            context.prec = 100
            rest = sum(
                (Decimal(str(row["revenue"])) for row in ordered[5:]), Decimal(0)
            )
            percent = (rest / expected * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        visual = points[:5] + [
            PanoramaDistributionPoint(
                segmento=f"Demais municípios ({grouped})"
                if dimension == "municipio"
                else f"Demais classes ({grouped})",
                valor=float(rest),
                percentual=float(percent),
            )
        ]

    result = PanoramaDistribution(
        reading=build_visual_reading(
            [
                ChatVisualPoint(
                    observation_id=f"row_{i}", label=p.segmento, value=p.valor
                )
                for i, p in enumerate(visual, 1)
            ],
            kind="donut" if partition and len(visual) <= 6 else "horizontal",
            unit=unit,
            precision=2,
        )
        if all(p.valor is not None for p in visual)
        else None,
        dimension=dimension,
        periodo=period,
        metricId=metric_id,
        unidade=unit,
        total=float(expected),
        completo=partition,
        pontos=points,
        visual=visual,
        agrupados=grouped,
    )
    return result if len(result.model_dump_json().encode("utf-8")) <= 262144 else None


def gold_distribution(
    repository: GoldPanoramaRepository,
    financials: GoldFinancialSnapshot,
    metric: PanoramaMetric,
) -> PanoramaDistribution | None:

    dimension = (
        "municipio"
        if financials.selected_municipality is None
        else "classe"
        if financials.selected_class is None
        else None
    )

    if dimension is None or metric.valorAtual is None:
        return None

    rows = repository.revenue_groups(
        financials.period,
        financials.period,
        dimension,
        financials.selected_municipality,
        financials.selected_class,
    )

    return distribution_from_groups(
        rows,
        dimension=dimension,
        period=financials.period,
        metric_id=metric.id,
        unit=metric.unidade,
        total=financials.actual["revenue"],
        complete=metric.status == "available"
        and all(row["rows"] == row["values"] for row in rows),
    )


def synthetic_distribution(
    records: Sequence[Mapping[str, Any]],
    filters: Mapping[str, Any],
    metric: PanoramaMetric,
) -> PanoramaDistribution | None:

    dimension = (
        "municipio"
        if filters["municipio"] == "todos"
        else "classe"
        if filters["classe"] == "todas"
        else None
    )

    if dimension is None:
        return None

    groups = {}

    for row in records:
        key = row[dimension]

        groups[key] = groups.get(key, Decimal(0)) + Decimal(
            str(row["energia_faturada_kwh"])
        )

    return distribution_from_groups(
        [{"segment": key, "revenue": value} for key, value in groups.items()],
        dimension=dimension,
        period=filters["periodo"],
        metric_id=metric.id,
        unit=metric.unidade,
        total=metric.valorAtual,
        complete=True,
    )
