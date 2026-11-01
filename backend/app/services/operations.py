"""Continuity exploration using the same computation as DEV-01."""
from collections.abc import Iterator
from typing import Literal

from app.repositories.analytics import AnalyticsRepository
from app.repositories.gold_operations import GoldOperationsRepository
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsMetadata,
    AnalyticsPeriod,
    AnalyticsSource,
    AnalyticsStatus,
    Pagination,
)
from app.schemas.operations import (
    GoldFeederOption,
    GoldOperationOptions,
    GoldOperationOptionsResponse,
    OperationDetailData,
    OperationDetailResponse,
    OperationOccurrence,
    OperationPoint,
    RankedFeeder,
    OperationSummary,
    OperationSummaryData,
    OperationSummaryDefinition,
    OperationSummaryResponse,
    GoldContinuityResponse,
    GoldOperationDetailData,
    GoldOperationDetailResponse,
    GoldOperationPoint,
    GoldOperationRankingData,
    GoldOperationRankingResponse,
    GoldRankedFeeder,
    GoldOperationSeriesData,
    GoldOperationSeriesResponse,
    GoldOperationSummary,
    GoldOperationSummaryResponse,
)
from app.schemas.gold import GoldMetadata
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


def _gold_point(row: dict, start: str, end: str) -> GoldOperationPoint:
    observed_rows = int(row.get("observed_rows") or 0)
    expected_months = list(months_in_window(start, end))
    observed_months = row.get("observed_competencies", [])
    missing_months = [month for month in expected_months if month not in observed_months]
    denominator = row.get("min_denominator")
    max_denominator = row.get("max_denominator")
    duration = row.get("duration_sum")
    count = row.get("interruption_count")
    limitations = ["Linhas observadas não declaram cobertura mensal nem completude da origem."]
    constant_denominator = (
        isinstance(denominator, int) and not isinstance(denominator, bool)
        and denominator > 0 and denominator == max_denominator
        and row.get("denominator_values", observed_rows) == observed_rows
    )
    if observed_rows == 0:
        return GoldOperationPoint(
            feeder_id=row["feeder_id"], municipality=row["municipality"],
            period=AnalyticsPeriod(start=start, end=end), observed_period=None,
            observed_competencies=[], missing_competencies=expected_months,
            duration_hours_sum=None, interruption_count=None, denominator_uc_count=None,
            dec_hours_per_uc=None, fec_interruptions_per_uc=None, status="empty",
            dec_status="empty", fec_status="empty",
            limitations=["Nenhuma linha observada nesta janela; isso não comprova ausência de interrupções."],
        )
    observed_start, observed_end = row["observed_start"], row["observed_end"]
    observed = AnalyticsPeriod(start=observed_start, end=observed_end)
    if not constant_denominator:
        limitations.append("Denominador ausente, inválido ou variável na janela; DEC/FEC acumulados indisponíveis.")
    if missing_months:
        limitations.append("A janela contém competências sem linha observada; DEC/FEC acumulados indisponíveis para a janela toda.")
    if row.get("duration_values", observed_rows) != observed_rows or row.get("count_values", observed_rows) != observed_rows:
        limitations.append("Há numeradores ausentes em competências observadas; indicador acumulado indisponível.")
        if row.get("duration_values", observed_rows) != observed_rows:
            limitations.append("Duração ausente em competência observada; DEC indisponível.")
            duration = None
        if row.get("count_values", observed_rows) != observed_rows:
            limitations.append("Frequência ausente em competência observada; FEC indisponível.")
            count = None
    dec = float(duration) / denominator if constant_denominator and not missing_months and duration is not None else None
    fec = int(count) / denominator if constant_denominator and not missing_months and count is not None else None
    dec_status = "partial" if dec is not None else "unavailable"
    fec_status = "partial" if fec is not None else "unavailable"
    if not constant_denominator or missing_months:
        status = "unavailable"
    elif dec is not None or fec is not None:
        status = "partial"
    else:
        status = "unavailable"
    return GoldOperationPoint(
        feeder_id=row["feeder_id"], municipality=row["municipality"],
        period=AnalyticsPeriod(start=start, end=end), observed_period=observed,
        observed_competencies=observed_months, missing_competencies=missing_months,
        duration_hours_sum=float(duration) if duration is not None else None,
        interruption_count=int(count) if count is not None else None,
        denominator_uc_count=int(denominator) if isinstance(denominator, int) and not isinstance(denominator, bool) else None,
        dec_hours_per_uc=dec, fec_interruptions_per_uc=fec, status=status,
        dec_status=dec_status, fec_status=fec_status,
        limitations=limitations,
    )


def build_gold_operation_options(repository: GoldOperationsRepository) -> GoldOperationOptionsResponse:
    periods, feeders = repository.options()
    context = repository.context
    return GoldOperationOptionsResponse(
        data=GoldOperationOptions(
            competencias=periods,
            municipios=sorted({municipality for municipality in feeders.values() if municipality is not None}),
            alimentadores=[GoldFeederOption(id=id_, municipio=municipality) for id_, municipality in sorted(feeders.items())],
        ),
        metadata=GoldMetadata(
            status="available" if periods else "empty",
            period=None,
            temporal_scope="snapshot",
            source=AnalyticsSource(kind="gold", version=context.lote, is_demo=False, updated_at=context.imported_at.isoformat()),
            schema_version=context.schema_version,
            fingerprint=context.fingerprint,
            limitations=["Opções observadas na publicação; não declaram fechamento ou completude mensal."],
        ),
    )


def _gold_metadata(repository: GoldOperationsRepository, status: str, start: str, end: str,
                   municipality: str | None, alimentador: str | None,
                   limitations: list[str]) -> GoldMetadata:
    context = repository.context
    return GoldMetadata(
        status=status,
        period=AnalyticsPeriod(start=start, end=end),
        filters=AnalyticsFilters(municipio=municipality, alimentador=alimentador),
        source=AnalyticsSource(
            kind="gold", version=context.lote, is_demo=False,
            updated_at=context.imported_at.isoformat(),
        ),
        limitations=list(dict.fromkeys(limitations)),
        temporal_scope="monthly", schema_version=context.schema_version,
        fingerprint=context.fingerprint,
    )


def gold_operation_points(
    repository: GoldOperationsRepository, start: str, end: str,
    municipio: str | None = None, alimentador: str | None = None,
) -> tuple[list[GoldOperationPoint], GoldMetadata]:
    periods, municipality_by_feeder = repository.options()
    feeder_ids = sorted(municipality_by_feeder)
    if municipio is not None and municipio not in set(municipality_by_feeder.values()):
        raise AnalyticsAPIError(422, "invalid_query", "Município desconhecido.", [{"field": "municipio", "message": "O valor não existe na fonte Gold."}])
    if alimentador is not None and alimentador not in feeder_ids:
        raise AnalyticsAPIError(422, "invalid_query", "Alimentador desconhecido.", [{"field": "alimentador", "message": "O valor não existe na fonte Gold."}])
    if alimentador is not None and municipio is not None and municipality_by_feeder[alimentador] != municipio:
        raise AnalyticsAPIError(422, "invalid_query", "Combinação de filtros inválida.", [{"field": "municipio", "message": "O alimentador não pertence ao município informado."}])
    rows = repository.aggregate(start, end, municipio, alimentador)
    inventory = municipality_by_feeder
    monthly_by_feeder: dict[str, list[dict]] = {}
    for row in rows:
        monthly_by_feeder.setdefault(row["feeder_id"], []).append(row)
    candidates = [alimentador] if alimentador else [
        feeder for feeder in feeder_ids if municipio is None or inventory.get(feeder) == municipio
    ]
    points = []
    for feeder in candidates:
        monthly = monthly_by_feeder.get(feeder, [])
        if monthly:
            denominators = [item["min_denominator"] for item in monthly if item["denominator_values"]]
            row = {
                "feeder_id": feeder, "municipality": inventory.get(feeder, ""),
                "observed_rows": sum(item["observed_rows"] for item in monthly),
                "min_denominator": min(denominators) if denominators else None,
                "max_denominator": max(item["max_denominator"] for item in monthly if item["denominator_values"]) if denominators else None,
                "denominator_values": sum(item["denominator_values"] for item in monthly),
                "duration_sum": sum(item["duration_sum"] for item in monthly if item["duration_sum"] is not None) if all(item["duration_values"] == item["observed_rows"] for item in monthly) else None,
                "interruption_count": sum(item["interruption_count"] for item in monthly if item["interruption_count"] is not None) if all(item["count_values"] == item["observed_rows"] for item in monthly) else None,
                "duration_values": sum(item["duration_values"] for item in monthly),
                "count_values": sum(item["count_values"] for item in monthly),
                "observed_start": min(item["competencia"] for item in monthly),
                "observed_end": max(item["competencia"] for item in monthly),
                "observed_competencies": [item["competencia"] for item in monthly],
            }
        else:
            row = {"feeder_id": feeder, "municipality": inventory.get(feeder, ""), "observed_rows": 0}
        points.append(_gold_point(row, start, end))
    status = "empty" if all(p.status == "empty" for p in points) else ("partial" if any(p.status == "partial" for p in points) else "unavailable")
    limitations = [message for point in points for message in point.limitations]
    if not periods:
        limitations.append("A Gold não apresenta competências de continuidade.")
    meta = _gold_metadata(repository, status, start, end, municipio, alimentador, limitations)
    return points, meta


def gold_operation_series(repository: GoldOperationsRepository, start: str, end: str,
                          municipio: str | None = None, alimentador: str | None = None) -> GoldOperationSeriesResponse:
    periods, inventory = repository.options()
    feeder_ids = sorted(inventory)
    if municipio is not None and municipio not in set(inventory.values()):
        raise AnalyticsAPIError(422, "invalid_query", "Município desconhecido.", [{"field": "municipio", "message": "O valor não existe na fonte Gold."}])
    if alimentador is not None and alimentador not in inventory:
        raise AnalyticsAPIError(422, "invalid_query", "Alimentador desconhecido.", [{"field": "alimentador", "message": "O valor não existe na fonte Gold."}])
    if alimentador is not None and municipio is not None and inventory[alimentador] != municipio:
        raise AnalyticsAPIError(422, "invalid_query", "Combinação de filtros inválida.", [{"field": "municipio", "message": "O alimentador não pertence ao município informado."}])
    candidates = [alimentador] if alimentador else [
        feeder for feeder in feeder_ids if municipio is None or inventory.get(feeder) == municipio
    ]
    grouped = repository.aggregate(start, end, municipio, alimentador)
    by_key = {(row["feeder_id"], row["competencia"]): row for row in grouped}
    items = []
    for month in months_in_window(start, end):
        for feeder in candidates:
            row = by_key.get((feeder, month))
            if row is None:
                row = {"feeder_id": feeder, "municipality": inventory.get(feeder, ""), "observed_rows": 0}
            else:
                row = {**row, "observed_start": month, "observed_end": month, "observed_competencies": [month]}
            items.append(_gold_point(row, month, month))
    meta = _gold_metadata(
        repository, "empty" if all(p.status == "empty" for p in items) else ("partial" if any(p.status == "partial" for p in items) else "unavailable"), start, end, municipio,
        alimentador,
        ["Competências observadas não declaram cobertura ou fechamento mensal.",
         "Ocorrências individuais não estão disponíveis na Gold."],
    )
    return GoldOperationSeriesResponse(data=GoldOperationSeriesData(items=items), metadata=meta)


def build_gold_operation_summary(repository: GoldOperationsRepository, start: str, end: str,
                                 municipio: str | None = None, alimentador: str | None = None) -> GoldOperationSummaryResponse:
    points, meta = gold_operation_points(repository, start, end, municipio, alimentador)
    dec_eligible = [point for point in points if point.dec_hours_per_uc is not None]
    fec_eligible = [point for point in points if point.fec_interruptions_per_uc is not None]
    dec_excluded = [point for point in points if point not in dec_eligible]
    fec_excluded = [point for point in points if point not in fec_eligible]
    duration = sum(point.duration_hours_sum or 0 for point in dec_eligible) if dec_eligible else None
    interruptions = sum(point.interruption_count or 0 for point in fec_eligible) if fec_eligible else None
    dec_denominator = sum(point.denominator_uc_count or 0 for point in dec_eligible) if dec_eligible else None
    fec_denominator = sum(point.denominator_uc_count or 0 for point in fec_eligible) if fec_eligible else None
    dec = duration / dec_denominator if dec_denominator else None
    fec = interruptions / fec_denominator if fec_denominator else None
    dec_ids = [point.feeder_id for point in dec_eligible]
    fec_ids = [point.feeder_id for point in fec_eligible]
    same_population = dec_ids == fec_ids
    included = dec_ids if same_population else None
    excluded = [point.feeder_id for point in dec_excluded] if same_population else None
    denominator = dec_denominator if same_population else None
    if not same_population:
        meta.limitations.append("DEC e FEC usam populações elegíveis diferentes; base comum indisponível.")
    empty = all(point.status == "empty" for point in points)
    dec_status = "partial" if dec_eligible else ("empty" if empty else "unavailable")
    fec_status = "partial" if fec_eligible else ("empty" if empty else "unavailable")
    status = "empty" if empty else ("partial" if dec_eligible or fec_eligible else "unavailable")
    observed_points = {point.feeder_id: point for point in (*dec_eligible, *fec_eligible)}.values()
    limitations = list(dict.fromkeys([message for point in points for message in point.limitations]))
    if not same_population:
        limitations.append("DEC e FEC usam populações elegíveis diferentes; campos genéricos de base comum indisponíveis.")
    summary = GoldOperationSummary(
        period=AnalyticsPeriod(start=start, end=end),
        observed_period=AnalyticsPeriod(
            start=min((p.observed_period.start for p in observed_points if p.observed_period), default=start),
            end=max((p.observed_period.end for p in observed_points if p.observed_period), default=end),
        ) if dec_eligible or fec_eligible else None,
        duration_hours_sum=duration, interruption_count=interruptions,
        denominator_uc_count=denominator, dec_hours_per_uc=dec, fec_interruptions_per_uc=fec,
        dec_denominator_uc_count=dec_denominator, fec_denominator_uc_count=fec_denominator,
        dec_included_feeder_ids=dec_ids, fec_included_feeder_ids=fec_ids,
        dec_excluded_feeder_ids=[point.feeder_id for point in dec_excluded],
        fec_excluded_feeder_ids=[point.feeder_id for point in fec_excluded],
        included_feeder_ids=included, excluded_feeder_ids=excluded,
        dec_status=dec_status, fec_status=fec_status,
        status=status,
        limitations=limitations,
    )
    meta.status = status
    return GoldOperationSummaryResponse(data=summary, metadata=meta)


def build_gold_feeder_detail(repository: GoldOperationsRepository, feeder_id: str,
                             start: str, end: str, municipio: str | None = None) -> GoldOperationDetailResponse:
    _, inventory = repository.options()
    if feeder_id not in inventory:
        raise AnalyticsAPIError(404, "not_found", "Alimentador não encontrado na fonte Gold.")
    points, meta = gold_operation_points(repository, start, end, municipio=municipio, alimentador=feeder_id)
    point = points[0]
    series = gold_operation_series(repository, start, end, municipio=municipio, alimentador=feeder_id).data.items
    return GoldOperationDetailResponse(
        data=GoldOperationDetailData(summary=point, series=series), metadata=meta,
    )
