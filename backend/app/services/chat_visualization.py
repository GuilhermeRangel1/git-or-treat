"""Monta pontos de negócio sem extrair números da prosa ou executar consultas."""

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from itertools import pairwise
from math import isfinite

from app.schemas.ai import AIAnalysisContext, AIQuestionResponse
from app.schemas.chat_visualization import (
    ChatVisualization,
    ChatVisualPoint,
    ChatVisualSector,
)
from app.schemas.genai_evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.genai_plan import LogicalReadPlan
from app.services.genai_client import GenAIResponseInvalid
from app.services.gold_catalog import load_gold_catalog
from app.services.visual_reading import build_visual_reading

_FIELDS = {
    "geography.municipality": ("municipality", "Município"),
    "geography.neighborhood": ("neighborhood", "Bairro"),
    "customer.consumption_class": ("consumption_class", "Classe"),
    "tariff.subgroup": ("tariff_subgroup", "Subgrupo"),
    "tariff.flag": ("tariff_flag", "Bandeira"),
    "network.feeder": ("feeder", "Alimentador"),
}


def build_visual_preview(
    plan: LogicalReadPlan, lookup: EvidenceLookupResult
) -> AIQuestionResponse | None:
    """Dados já consultados; esta prévia nunca é uma interpretação do modelo."""
    if lookup.status != EvidenceLookupStatus.AVAILABLE or lookup.evidence is None:
        return None
    origin = lookup.evidence.provenance
    if origin is None or origin.published_windows is not None:
        return None
    metric = next(
        (m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id), None
    )
    if metric is None:
        raise GenAIResponseInvalid
    response = AIQuestionResponse(
        status="answered",
        answer="Dados da consulta disponíveis. Preparando a interpretação.",
        evidence=[lookup.evidence.reference],
        limitations=lookup.limitations,
        analysis_context=AIAnalysisContext(
            metric=plan.metric_id,
            metric_label=metric.label,
            metric_definition=metric.definition,
            unit=plan.unit,
            period=plan.window.phrase or f"{plan.window.start} a {plan.window.end}",
            batch_reference=origin.batch_ref,
            filters={
                f.dimension_id: f.values[0]
                if len(f.values) == 1
                else ", ".join(str(v) for v in f.values)
                for f in plan.filters
            },
            filter_labels={
                f.dimension_id: _FIELDS[f.dimension_id][1]
                for f in plan.filters
                if f.dimension_id in _FIELDS
            },
        ),
    )
    visual = build_chat_visualization(plan, lookup, response)
    return (
        response.model_copy(update={"visualization": visual})
        if visual is not None
        else None
    )


def build_chat_visualization(
    plan: LogicalReadPlan, lookup: EvidenceLookupResult, response: AIQuestionResponse
) -> ChatVisualization | None:
    if (
        response.status != "answered"
        or lookup.status != EvidenceLookupStatus.AVAILABLE
        or lookup.evidence is None
    ):
        return None
    evidence = lookup.evidence
    origin = evidence.provenance
    context = response.analysis_context
    if origin is None or origin.published_windows is not None:
        return None
    expected_filters = {
        f.dimension_id: f.values[0]
        if len(f.values) == 1
        else ", ".join(str(v) for v in f.values)
        for f in plan.filters
    }
    expected_period = (
        plan.window.phrase
        if plan.window.phrase is not None
        else f"{plan.window.start} a {plan.window.end}"
    )
    if (
        context is None
        or evidence.reference.is_demo
        or evidence.reference.source != "gold.local"
        or any(
            e.source
            not in {
                "gold.local",
                "gold.local:"
                + sha256(evidence.reference.source.encode("utf-8")).hexdigest(),
            }
            or e.is_demo
            for e in response.evidence
        )
        or origin.plan_fingerprint != plan.fingerprint()
        or origin.window != plan.window
        or origin.filters != plan.filters
        or origin.source_id != plan.source_id
        or origin.metric_id != plan.metric_id
        or origin.unit != plan.unit
        or context.metric != plan.metric_id
        or context.unit != plan.unit
        or context.period != expected_period
        or context.batch_reference != origin.batch_ref
        or not (origin.batch_ref or "").startswith("gold-csv-v2:")
        or context.filters != expected_filters
    ):
        raise GenAIResponseInvalid
    if len(plan.group_by_dimension_ids) > 1 or any(
        d not in _FIELDS for d in plan.group_by_dimension_ids
    ):
        return None
    metric = next(
        (m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id), None
    )
    if metric is None or context.period is None or metric.unit != plan.unit:
        raise GenAIResponseInvalid
    category = (
        _FIELDS[plan.group_by_dimension_ids[0]] if plan.group_by_dimension_ids else None
    )
    periods = set()
    points = []
    for i, row in enumerate(evidence.records, 1):
        value, period = row.get("value"), row.get("period")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or row.get("unit") != plan.unit
            or not isinstance(period, str)
        ):
            raise GenAIResponseInvalid
        if plan.window.kind == "bounded":
            try:
                stamp = datetime.strptime(
                    period, "%Y-%m" if plan.window.granularity == "month" else "%Y"
                ).date()
            except ValueError:
                raise GenAIResponseInvalid from None
            if (
                stamp.strftime("%Y-%m" if plan.window.granularity == "month" else "%Y")
                != period
                or not plan.window.start <= stamp <= plan.window.end
                or plan.comparison_periods is not None
                and period not in plan.comparison_periods
            ):
                raise GenAIResponseInvalid
        elif period != plan.window.phrase:
            raise GenAIResponseInvalid
        periods.add(period)
        label = period
        if category:
            name = row.get(category[0])
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise GenAIResponseInvalid
            label = f"{name} · {period}"
        if len(label) > 200:
            return None
        points.append(
            ChatVisualPoint(observation_id=f"row_{i}", label=label, value=value)
        )
    if not points:
        return None
    chronological = sorted(periods)
    continuous = False
    if len(chronological) == len(points) and len(points) >= 3:
        try:
            indices = (
                [int(p[:4]) * 12 + int(p[5:7]) for p in chronological]
                if all(len(p) == 7 and p[4] == "-" for p in chronological)
                else [int(p) for p in chronological]
            )
            continuous = all(last - first == 1 for first, last in pairwise(indices))
        except ValueError:
            continuous = False
    continuous = continuous and [p.label for p in points] == chronological
    kind = (
        "horizontal" if category else "line" if not category and continuous else "bars"
    )
    # Participação do total observado só para somas de uma única competência,
    # sem ranking nem resultado possivelmente cortado pelo limite da consulta.
    if (
        category
        and len(periods) == 1
        and plan.order is None
        and plan.metric_id in {"billing.revenue", "energy.consumption"}
        and 1 < len(points) < plan.limit
        and len({p.label for p in points}) == len(points)
        and all(p.value >= 0 for p in points)
        and 0 < sum(Decimal(str(p.value)) for p in points) < Decimal("1e308")
    ):
        kind = "donut"
    maximum = 100 if kind == "donut" else 10 if kind == "horizontal" else 24
    # Sem ranking explícito, os maiores grupos dão uma visão útil do recorte;
    # a tabela/CSV preservam todos os pontos e sua ordem original.
    display_points = (
        sorted(points, key=lambda point: (-point.value, point.label))
        if kind == "horizontal" and plan.order is None
        else points
    )
    plotted = display_points[:maximum] if kind == "horizontal" else points[-maximum:]
    note = (
        "1 observação retornada pela consulta autorizada."
        if len(points) == 1 else f"{len(points)} observações retornadas pela consulta autorizada."
    )
    if kind == "donut":
        note += " Participação no total observado; até seis setores, com grupos excedentes reunidos em Demais."
    if plan.order is not None and plan.group_by_dimension_ids:
        note += " O resultado pode ser um ranking, não uma distribuição completa."
    if len(plotted) != len(points):
        subset = (
            "maiores valores"
            if kind == "horizontal" and plan.order is None
            else "observações"
        )
        note += (
            f" Gráfico: {len(plotted)} {subset}; tabela e CSV: todas as {len(points)}."
        )
    total, sectors = None, None
    if kind == "donut":
        ranked = sorted(points, key=lambda p: (-p.value, p.label))
        total = sum(Decimal(str(p.value)) for p in ranked)
        groups = (
            [[p] for p in ranked]
            if len(ranked) <= 6
            else [
                *[[p] for p in ranked[:5]],
                ranked[5:],
            ]
        )
        sectors = []
        for group in groups:
            value = sum(Decimal(str(p.value)) for p in group)
            sectors.append(
                ChatVisualSector(
                    label=group[0].label
                    if len(group) == 1
                    else f"Demais grupos ({len(group)})",
                    value=float(value),
                    percentage=float(value / total * 100),
                    observation_ids=tuple(p.observation_id for p in group),
                )
            )
    result = ChatVisualization(
        kind=kind,
        metric=plan.metric_id,
        title=metric.label[:200],
        unit=plan.unit,
        precision=metric.rounding.decimals,
        dimension_ids=plan.dimension_ids,
        period=context.period,
        category_label=category[1] if category else "Período",
        note=note,
        points=points,
        plot_points=plotted,
        total=float(total) if total is not None else None,
        sectors=sectors,
        reading=(
            build_visual_reading(
                plotted, kind=kind, unit=plan.unit, precision=metric.rounding.decimals
            )
            if len(plotted) <= 24
            else None
        ),
    )
    return result if len(result.model_dump_json().encode("utf-8")) <= 32768 else None
