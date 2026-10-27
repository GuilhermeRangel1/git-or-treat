"""Continuity exploration using the same computation as DEV-01."""
from collections.abc import Iterator
from typing import Literal

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsMetadata,
    AnalyticsPeriod,
    AnalyticsStatus,
    Pagination,
)
from app.schemas.operations import (
    OperationDetailData,
    OperationDetailResponse,
    OperationOccurrence,
    OperationPoint,
    RankedFeeder,
    OperationSummary,
    OperationSummaryData,
    OperationSummaryDefinition,
    OperationSummaryResponse,
)
from app.services.analytics import (
    AnalyticsAPIError,
    build_continuity,
    filters_model,
    metadata,
)


def validate_operation_window(start: str, end: str) -> None:
    months = (int(end[:4]) - int(start[:4])) * 12 + int(end[5:]) - int(start[5:]) + 1
    if months > 120:
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "A janela de Operação permite até 120 competências.",
            [{
                "field": "competencia_fim",
                "message": "Reduza a janela para até 120 meses.",
            }],
        )


def months_in_window(start: str, end: str) -> Iterator[str]:
    first = int(start[:4]) * 12 + int(start[5:]) - 1
    last = int(end[:4]) * 12 + int(end[5:]) - 1
    for index in range(first, last + 1):
        year, month = divmod(index, 12)
        yield f"{year:04d}-{month + 1:02d}"


def observed_window(
    repository: AnalyticsRepository, start: str, end: str,
) -> AnalyticsPeriod | None:
    coverage = repository.continuity_coverage
    if coverage is None:
        return None
    first, last = max(start, coverage.start), min(end, coverage.end)
    return AnalyticsPeriod(start=first, end=last) if first <= last else None


def observed_events(
    repository: AnalyticsRepository, feeder_id: str, start: str, end: str,
) -> list[dict]:
    observed = observed_window(repository, start, end)
    if observed is None:
        return []
    return sorted(
        (row for row in repository.interruptions
         if row["feeder_id"] == feeder_id and observed.start <= row["competencia"] <= observed.end),
        key=lambda row: (row["competencia"], row["event_id"], row["uc_id"]),
    )


def operation_points(
    repository: AnalyticsRepository, start: str, end: str, filters: AnalyticsFilters,
) -> tuple[list[OperationPoint], AnalyticsStatus]:
    items, state = build_continuity(repository, start, end, filters)
    observed = observed_window(repository, start, end)
    points = []
    for item in items:
        dec = "indisponível" if item.dec_hours_per_uc is None else str(item.dec_hours_per_uc)
        fec = "indisponível" if item.fec_interruptions_per_uc is None else str(item.fec_interruptions_per_uc)
        denominator = "ausente" if item.denominator_uc_count is None else str(item.denominator_uc_count)
        points.append(
            OperationPoint(
                **item.model_dump(),
                period=AnalyticsPeriod(start=start, end=end),
                observed_period=observed,
                duration_hours_sum=sum(
                    row["duration_hours"]
                    for row in observed_events(repository, item.feeder_id, start, end)
                ),
                text_alternative=(
                    f"{item.feeder_id}, {start} a {end}: DEC {dec} h/UC; "
                    f"FEC {fec} interrupções/UC; denominador {denominator} UCs; "
                    f"estado {item.status}. Indicadores simplificados de demonstração."
                ),
            )
        )
    return points, state


def operation_series(
    repository: AnalyticsRepository, start: str, end: str, filters: AnalyticsFilters,
) -> list[OperationPoint]:
    return [
        point
        for month in months_in_window(start, end)
        for point in operation_points(repository, month, month, filters)[0]
    ]


def operation_metadata(
    repository: AnalyticsRepository, state: AnalyticsStatus, start: str, end: str,
    filters: AnalyticsFilters, points: list[OperationPoint],
) -> AnalyticsMetadata:
    result = metadata(repository, state, start, end, filters)
    result.contract_version = "1.1.0"
    for point in points:
        for limitation in point.limitations:
            if limitation not in result.limitations:
                result.limitations.append(limitation)
    return result


def build_operation_summary(
    repository: AnalyticsRepository,
    start: str,
    end: str,
    filters: AnalyticsFilters,
) -> OperationSummaryResponse:
    """Aggregate original interruption records across fully eligible feeders."""
    points, _ = operation_points(repository, start, end, filters)
    eligible = [point for point in points if point.status == "available"]
    included_ids = [point.feeder_id for point in eligible]
    excluded = [point for point in points if point.status != "available"]
    excluded_ids = [point.feeder_id for point in excluded]
    served_uc_count = sum(point.served_uc_count for point in points)
    observed = observed_window(repository, start, end)

    if eligible:
        denominator = sum(point.denominator_uc_count for point in eligible)
        events = [
            row
            for feeder_id in included_ids
            for row in observed_events(repository, feeder_id, start, end)
        ]
        duration_sum = sum(row["duration_hours"] for row in events)
        interruption_count = len(events)
        dec = round(duration_sum / denominator, 3)
        fec = round(interruption_count / denominator, 3)
        status = "partial" if excluded else "available"
        included_uc_count = denominator
    else:
        denominator = duration_sum = interruption_count = dec = fec = None
        status = "empty" if not points else "unavailable"
        included_uc_count = 0

    limitations = list(repository.source_limitations)
    if not points:
        limitations.append("A fonte não contém alimentadores para o recorte solicitado.")
    for point in excluded:
        reason = "; ".join(point.limitations) or f"estado {point.status}."
        limitations.append(f"{point.feeder_id} excluído do consolidado: {reason}")
    if eligible and excluded:
        limitations.append(
            "Consolidado parcial: indicadores calculados somente sobre os alimentadores incluídos."
        )

    dec_label = "indisponível" if dec is None else str(dec)
    fec_label = "indisponível" if fec is None else str(fec)
    base_label = "indisponível" if denominator is None else str(denominator)
    text_alternative = (
        f"Consolidado de {start} a {end}: DEC {dec_label} h/UC; "
        f"FEC {fec_label} interrupções/UC; base incluída {base_label} UCs; "
        f"alimentadores incluídos {', '.join(included_ids) or 'nenhum'}; "
        f"excluídos {', '.join(excluded_ids) or 'nenhum'}; estado {status}. "
        "Indicadores simplificados de demonstração."
    )
    summary = OperationSummary(
        period=AnalyticsPeriod(start=start, end=end),
        observed_period=observed,
        dec_hours_per_uc=dec,
        fec_interruptions_per_uc=fec,
        duration_hours_sum=duration_sum,
        interruption_count=interruption_count,
        denominator_uc_count=denominator,
        served_uc_count=served_uc_count,
        included_uc_count=included_uc_count,
        included_feeder_ids=included_ids,
        excluded_feeder_ids=excluded_ids,
        status=status,
        limitations=limitations,
        text_alternative=text_alternative,
    )
    result_metadata = metadata(repository, status, start, end, filters)
    result_metadata.contract_version = "1.2.0"
    for limitation in limitations:
        if limitation not in result_metadata.limitations:
            result_metadata.limitations.append(limitation)
    return OperationSummaryResponse(
        data=OperationSummaryData(
            summary=summary,
            definition=OperationSummaryDefinition(
                dec_formula=(
                    "Soma das durações originais em horas dos registros UC-interrupção "
                    "/ soma dos denominadores dos alimentadores incluídos."
                ),
                fec_formula=(
                    "Quantidade original de registros UC-interrupção "
                    "/ soma dos denominadores dos alimentadores incluídos."
                ),
                population=(
                    "População atendida é a contagem cadastral ativa no recorte; "
                    "a base incluída é a soma dos denominadores dos alimentadores elegíveis."
                ),
            ),
        ),
        metadata=result_metadata,
    )


def operation_ranking(
    points: list[OperationPoint], metric: Literal["dec", "fec"],
) -> tuple[list[RankedFeeder], list[OperationPoint]]:
    field = "dec_hours_per_uc" if metric == "dec" else "fec_interruptions_per_uc"
    # Partial observations are disclosed but cannot compete against complete windows.
    eligible = [point for point in points if point.status == "available"]
    ordered = sorted(eligible, key=lambda point: (-getattr(point, field), point.feeder_id))
    ranked = [
        RankedFeeder(**point.model_dump(), rank=index)
        for index, point in enumerate(ordered, 1)
    ]
    return ranked, [point for point in points if point.status != "available"]


def build_feeder_detail(
    repository: AnalyticsRepository,
    feeder_id: str,
    start: str,
    end: str,
    page: int,
    page_size: int,
) -> OperationDetailResponse:
    """Build the full-period summary independently of the occurrence page."""
    filters = filters_model(alimentador=feeder_id)
    if not any(row["feeder_id"] == feeder_id for row in repository.feeders):
        raise AnalyticsAPIError(404, "not_found", "Alimentador não encontrado.")
    points, state = operation_points(repository, start, end, filters)
    series = operation_series(repository, start, end, filters)
    events = observed_events(repository, feeder_id, start, end)
    total = len(events)
    offset = (page - 1) * page_size
    return OperationDetailResponse(
        data=OperationDetailData(
            summary=points[0],
            series=series,
            occurrences=[
                OperationOccurrence.model_validate(event)
                for event in events[offset:offset + page_size]
            ],
        ),
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
        metadata=operation_metadata(
            repository, state, start, end, filters, points + series,
        ),
    )
