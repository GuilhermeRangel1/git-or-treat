"""Monta contexto de insight a partir do mesmo recorte validado do Panorama."""

from calendar import monthrange
from datetime import date

from app.repositories.panorama import PanoramaRepository
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
from app.services.panorama import (
    build_panorama,
    comparison_period,
    filter_records,
    period_label,
    sum_records,
)


class StalePanoramaInsight(Exception):
    """O lote exibido pelo portal não corresponde mais ao lote atual do Backend."""


class UnsupportedPanoramaInsight(Exception):
    """A fonte atual não permite construir contexto sintético para a GenAI."""


def build_panorama_insight(
    repository: PanoramaRepository,
    request: PanoramaInsightRequest,
) -> tuple[
    AIInsightRequest | AIInsightResponse,
    PanoramaInsightMetric,
    PanoramaInsightSource,
    PanoramaInsightAnalysis,
]:
    """Prepara a chamada GenAI ou uma resposta local de ausência para o recorte."""

    filters = request.filters
    data = build_panorama(
        repository,
        competencia=filters.periodo,
        comparacao=filters.comparacao,
        municipio=filters.municipio,
        classe=filters.classe,
    )
    if data.loteVersao != request.loteVersao:
        raise StalePanoramaInsight
    if not repository.source_is_demo:
        raise UnsupportedPanoramaInsight

    metric = data.metricas["energiaFaturada"]
    analysis = _build_analysis(
        repository,
        filters,
        metric,
        has_data=data.totalRegistros > 0,
        period_incomplete=data.periodoIncompleto,
    )
    year, month = map(int, filters.periodo.split("-"))
    period = AIInsightPeriod(
        start=date(year, month, 1),
        end=date(year, month, monthrange(year, month)[1]),
        granularity="month",
    )
    observations = [
        AIInsightObservationValue(
            label=f"{period_label(filters.periodo)} · período atual",
            value=metric.valorAtual,
        )
    ]
    compared_period = comparison_period(filters.periodo, filters.comparacao)
    if compared_period is not None and metric.valorAnterior is not None:
        observations.extend(
            [
                AIInsightObservationValue(
                    label=f"{period_label(compared_period)} · período comparado",
                    value=metric.valorAnterior,
                ),
                AIInsightObservationValue(
                    label="Variação absoluta em relação ao período comparado",
                    value=metric.variacaoAbsoluta
                    if metric.variacaoAbsoluta is not None
                    else metric.valorAtual - metric.valorAnterior,
                ),
            ]
        )

    limitations = list(repository.source_limitations)
    if data.periodoIncompleto:
        limitations.append(
            f"A competência {filters.periodo} está incompleta; a comparação pode não estar disponível."
        )
    limitations.append(
        "A interpretação é uma sugestão de investigação, não uma causa comprovada."
    )

    context = AIInsightContextSummary(
        metric=metric.nome, unit=metric.unidade, period=period, filters=data.filtros
    )
    prepared: AIInsightRequest | AIInsightResponse
    if data.totalRegistros == 0:
        prepared = AIInsightResponse(
            contract_version="v1",
            correlation_id=None,
            audit_reference=None,
            error=None,
            status="no_evidence",
            context=context,
            observation=AIInsightObservation(values=[]),
            hypothesis=None,
            message="Não há dados para gerar uma interpretação deste recorte.",
            evidence=[],
            limitations=limitations,
        )
    else:
        prepared = AIInsightRequest(
            screen=AIInsightScreenContext(
                metric=metric.nome,
                unit=metric.unidade,
                period=period,
                filters=data.filtros,
                observations=observations,
                reference=AIInsightReference(
                    source="synthetic.panorama",
                    description=(
                        f"Dados sintéticos do Panorama; lote {data.loteVersao}; "
                        f"atualização {data.dataAtualizacao}."
                    ),
                    is_demo=True,
                ),
                limitations=limitations,
            )
        )
    source = PanoramaInsightSource(
        kind=repository.source_kind,
        loteVersao=data.loteVersao,
        dataAtualizacao=data.dataAtualizacao,
        isDemo=repository.source_is_demo,
        limitacoes=list(repository.source_limitations),
    )
    metric_detail = PanoramaInsightMetric(
        id=metric.id,
        definicao=metric.definicao,
        formula=metric.formula,
    )
    return prepared, metric_detail, source, analysis


def _build_analysis(
    repository: PanoramaRepository,
    filters,
    metric,
    *,
    has_data: bool,
    period_incomplete: bool,
) -> PanoramaInsightAnalysis:
    if not has_data or metric.valorAnterior is None or period_incomplete:
        return PanoramaInsightAnalysis(direcao="indisponivel")

    total_change = round(metric.valorAtual - metric.valorAnterior, 2)
    if total_change < 0:
        direction = "queda"
    elif total_change > 0:
        direction = "alta"
    else:
        direction = "estavel"

    comparison = comparison_period(filters.periodo, filters.comparacao)
    if comparison is None:
        return PanoramaInsightAnalysis(
            direcao=direction,
            variacaoPercentual=metric.variacaoPercentual,
        )

    if filters.municipio == "todos":
        dimension = "municipio"
    elif filters.classe == "todas":
        dimension = "classe"
    else:
        return PanoramaInsightAnalysis(
            direcao=direction,
            variacaoPercentual=metric.variacaoPercentual,
        )

    current_records = filter_records(
        repository.records,
        filters.periodo,
        "todos" if dimension == "municipio" else filters.municipio,
        "todas" if dimension == "classe" else filters.classe,
    )
    comparison_records = filter_records(
        repository.records,
        comparison,
        "todos" if dimension == "municipio" else filters.municipio,
        "todas" if dimension == "classe" else filters.classe,
    )
    groups = sorted({
        record[dimension]
        for record in [*current_records, *comparison_records]
    })
    deltas = {}
    for group in groups:
        current = sum_records(
            [record for record in current_records if record[dimension] == group]
        )["energia_faturada"]
        previous = sum_records(
            [record for record in comparison_records if record[dimension] == group]
        )["energia_faturada"]
        has_current_group = any(record[dimension] == group for record in current_records)
        has_previous_group = any(
            record[dimension] == group for record in comparison_records
        )
        if has_current_group and has_previous_group:
            deltas[group] = round(current - previous, 2)

    if total_change == 0:
        return PanoramaInsightAnalysis(
            direcao=direction,
            variacaoPercentual=metric.variacaoPercentual,
        )

    if direction == "queda":
        primary_values = [value for value in deltas.values() if value < 0]
        offset_values = [value for value in deltas.values() if value > 0]
        primary = min(primary_values, default=None)
        offset = max(offset_values, default=None)
    else:
        primary_values = [value for value in deltas.values() if value > 0]
        offset_values = [value for value in deltas.values() if value < 0]
        primary = max(primary_values, default=None)
        offset = min(offset_values, default=None)

    def contribution(change, related_changes):
        if change is None:
            return None
        segment = next(name for name, value in deltas.items() if value == change)
        related_total = sum(abs(value) for value in related_changes)
        return PanoramaInsightContribution(
            dimension=dimension,
            segmento=segment,
            variacaoAbsoluta=change,
            participacaoPercentual=(
                round(abs(change / related_total) * 100, 1)
                if related_total
                else None
            ),
        )

    return PanoramaInsightAnalysis(
        direcao=direction,
        variacaoPercentual=metric.variacaoPercentual,
        principalContribuicao=contribution(primary, primary_values),
        compensacao=contribution(offset, offset_values),
    )
