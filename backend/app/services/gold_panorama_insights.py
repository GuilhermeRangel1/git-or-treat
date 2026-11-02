"""Contexto Gold do insight derivado do cálculo efetivamente exibido no Panorama."""

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, TypeAlias

from app.repositories.panorama import GoldPanoramaRepository
from app.schemas.ai_insight import (
    AIInsightContextSummary,
    AIInsightObservation,
    AIInsightObservationValue,
    AIInsightPeriod,
    AIInsightReference,
    AIInsightRequest,
    AIInsightResponse,
    AIInsightScreenContext,
    PanoramaInsightAnalysis,
    PanoramaInsightContribution,
    PanoramaInsightMetric,
    PanoramaInsightRequest,
    PanoramaInsightSource,
)
from app.schemas.panorama import PanoramaMetric
from app.services.panorama import (
    comparison_period,
    gold_panorama_revenue_metric,
    period_label,
    read_gold_panorama_financials,
)
from app.services.panorama_insights import StalePanoramaInsight

GoldPanoramaInsightPreparation: TypeAlias = tuple[
    AIInsightRequest | AIInsightResponse,
    PanoramaInsightMetric,
    PanoramaInsightSource,
    PanoramaInsightAnalysis,
]


def build_gold_panorama_insight(
    repository: GoldPanoramaRepository,
    request: PanoramaInsightRequest,
) -> GoldPanoramaInsightPreparation:
    """Recalcula receita comparável no snapshot já autorizado pelo servidor.

    A referência do navegador serve apenas para detectar desatualização.
    A função não concede acesso nem habilita o endpoint de síntese externa.
    """
    filters = request.filters
    financials = read_gold_panorama_financials(
        repository,
        filters.periodo,
        filters.comparacao,
        filters.municipio,
        filters.classe,
    )
    period, compare = financials.period, financials.comparison
    municipality, consumption_class = (
        financials.municipality,
        financials.consumption_class,
    )
    reference, actual, prior = financials.reference, financials.actual, financials.prior
    applied_filters = {
        "periodo": period,
        "comparacao": compare,
        "municipio": municipality,
        "classe": consumption_class,
    }
    if repository.context.lote != request.loteVersao:
        raise StalePanoramaInsight
    metric = gold_panorama_revenue_metric(actual, prior, reference)
    analysis = PanoramaInsightAnalysis(direcao="indisponivel")
    year, month = map(int, applied_filters["periodo"].split("-"))
    period = AIInsightPeriod(
        start=date(year, month, 1),
        end=date(year, month, monthrange(year, month)[1]),
        granularity="month",
    )
    limitations = list(
        dict.fromkeys(
            [
                *repository.source_limitations,
                *metric.limitacoes,
                *metric.limitacoesComparacao,
                "A interpretação é uma sugestão de investigação, não uma causa comprovada.",
            ]
        )
    )
    context = AIInsightContextSummary(
        metric=metric.nome,
        unit=metric.unidade,
        period=period,
        filters=applied_filters,
    )
    if metric.valorAtual is None:
        prepared = AIInsightResponse(
            contract_version="v1",
            correlation_id=None,
            audit_reference=None,
            error=None,
            status="no_evidence",
            context=context,
            observation=AIInsightObservation(values=[]),
            hypothesis=None,
            message="Não há receita comparável suficiente para interpretar este recorte.",
            evidence=[],
            limitations=limitations,
        )
    else:
        observations = [
            AIInsightObservationValue(
                label=f"{period_label(applied_filters['periodo'])} · período atual",
                value=metric.valorAtual,
            )
        ]
        previous = comparison_period(applied_filters["periodo"], filters.comparacao)
        if previous is not None and metric.valorAnterior is not None:
            observations.append(
                AIInsightObservationValue(
                    label=f"{period_label(previous)} · período comparado",
                    value=metric.valorAnterior,
                )
            )
            change = metric.variacaoAbsoluta
            if change is None:
                change = round(metric.valorAtual - metric.valorAnterior, 2)
            observations.append(
                AIInsightObservationValue(
                    label="Variação absoluta dos valores publicados",
                    value=change,
                )
            )
            analysis = PanoramaInsightAnalysis(
                direcao="alta" if change > 0 else "queda" if change < 0 else "estavel",
                variacaoPercentual=metric.variacaoPercentual,
            )
        if metric.valorAnterior is not None and previous is not None:
            analysis, contribution_limits = build_gold_revenue_analysis(
                repository,
                applied_filters,
                previous,
                metric,
                actual,
                prior,
            )
            limitations.extend(contribution_limits)
            for contribution in (analysis.principalContribuicao, analysis.compensacao):
                if contribution is not None:
                    observations.append(
                        AIInsightObservationValue(
                            label=f"Variação · {contribution.segmento}",
                            value=contribution.variacaoAbsoluta,
                        )
                    )
        prepared = AIInsightRequest(
            screen=AIInsightScreenContext(
                metric=metric.nome,
                unit=metric.unidade,
                period=period,
                filters=applied_filters,
                observations=observations,
                reference=AIInsightReference(
                    source="gold.local",
                    description=f"Receita comparável do Panorama; lote {repository.context.lote}.",
                    is_demo=False,
                ),
                limitations=limitations,
            )
        )
    return (
        prepared,
        PanoramaInsightMetric(
            id=metric.id, definicao=metric.definicao, formula=metric.formula
        ),
        PanoramaInsightSource(
            fingerprint=repository.context.fingerprint,
            kind=repository.source_kind,
            loteVersao=repository.context.lote,
            dataAtualizacao=repository.source_updated_at,
            isDemo=False,
            limitacoes=limitations,
        ),
        analysis,
    )


def build_gold_revenue_analysis(
    repository: GoldPanoramaRepository,
    filters: dict[str, str],
    previous: str,
    metric: PanoramaMetric,
    actual: dict[str, Any],
    prior: dict[str, Any],
) -> tuple[PanoramaInsightAnalysis, list[str]]:
    """Participação sobre os movimentos de mesmo sinal, nunca sobre variação líquida."""
    change = metric.variacaoAbsoluta
    direction = "alta" if change > 0 else "queda" if change < 0 else "estavel"
    empty = PanoramaInsightAnalysis(
        direcao=direction, variacaoPercentual=metric.variacaoPercentual
    )
    if change == 0 or (
        filters["municipio"] != "todos" and filters["classe"] != "todas"
    ):
        return empty, []
    dimension = "municipio" if filters["municipio"] == "todos" else "classe"
    rows = repository.revenue_groups(
        filters["periodo"],
        previous,
        dimension,
        None if filters["municipio"] == "todos" else filters["municipio"],
        None if filters["classe"] == "todas" else filters["classe"],
    )
    incomplete = [
        "As contribuições não foram calculadas: os grupos não têm valores completos nas duas competências."
    ]
    if len(rows) > 1000 or any(row["values"] != row["rows"] for row in rows):
        return empty, incomplete
    grouped = {}
    for row in rows:
        grouped.setdefault(row["segment"], {})[row["period"]] = row["revenue"]
    if not grouped or any(
        set(pair) != {filters["periodo"], previous} for pair in grouped.values()
    ):
        return empty, incomplete
    with localcontext() as context:
        context.prec = 100
        if (
            sum(pair[filters["periodo"]] for pair in grouped.values())
            != actual["revenue"]
            or sum(pair[previous] for pair in grouped.values()) != prior["revenue"]
        ):
            return empty, ["As contribuições não reconciliaram com o total publicado."]
        deltas = {
            name: pair[filters["periodo"]] - pair[previous]
            for name, pair in grouped.items()
        }
        positive = {name: value for name, value in deltas.items() if value > 0}
        negative = {name: value for name, value in deltas.items() if value < 0}

        def contribution(values):
            if not values:
                return None
            name = min(values, key=lambda key: (-abs(values[key]), key))
            denominator = sum(abs(value) for value in values.values())
            return PanoramaInsightContribution(
                dimension=dimension,
                segmento=name,
                variacaoAbsoluta=float(
                    values[name].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                participacaoPercentual=float(
                    (abs(values[name]) / denominator * 100).quantize(
                        Decimal("0.1"), rounding=ROUND_HALF_UP
                    )
                ),
            )

        return PanoramaInsightAnalysis(
            direcao=direction,
            variacaoPercentual=metric.variacaoPercentual,
            principalContribuicao=contribution(positive if change > 0 else negative),
            compensacao=contribution(negative if change > 0 else positive),
        ), [
            "Participações representam o total dos movimentos de mesmo sinal, não a variação líquida; a comparação usa valores publicados sem fechamento mensal certificado."
        ]
