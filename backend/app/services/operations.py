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
