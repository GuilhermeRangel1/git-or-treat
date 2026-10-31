from app.repositories.analytics import AnalyticsRepository
from app.repositories.gold_inspections import GoldInspectionRepository
from app.schemas.analytics import AnalyticsFilters, AnalyticsSource, AnalyticsStatus
from app.schemas.gold import GoldMetadata
from app.schemas.inspection_queue import (
    GoldInspectionEvidence, GoldInspectionItem, GoldInspectionQueueResponse,
    GoldInspectionSummary, GoldInspectionVariation, GoldSuspicionDetail,
    GoldSuspicionResponse, QueueResponse, SuspicionResponse,
)
from app.services.analytics import (
    DEFAULT_END,
    DEFAULT_START,
    AnalyticsAPIError,
    apply_unit_filters,
    metadata,
)


RULE_VERSION = "dev05-v1"
SIGNALS = {
    "reading_gap": ("Lacuna de leitura", 0.60),
    "meter_removed": ("Medidor retirado", 0.32),
    "consumption_variation": ("Variação de consumo", 0.41),
    "distributed_generation": ("Geração distribuída; exige análise do contexto", 0.20),
}
LIMITATIONS = [
    "Regra sintética de triagem, não validada com dados reais. Pontuação não é probabilidade de irregularidade.",
    "Suspeita não confirma irregularidade. GD, sazonalidade e alterações cadastrais podem explicar os sinais.",
    "Estimativa mensal hipotética; não representa energia medida, faturada ou recuperação garantida.",
]


def build_suspicion(suspicion: dict, unit: dict) -> dict:
    signals = [{"id": key, "label": SIGNALS[key][0], "weight": SIGNALS[key][1]}
               for key in dict.fromkeys(suspicion["indicators"]) if key in SIGNALS]
    evidence = suspicion.get("estimate_evidence", {
        "baseline_kwh": None, "observed_kwh": None, "horizon_months": 1,
        "reference": "Sem referência sintética suficiente.",
    }).copy()
    baseline, observed = evidence["baseline_kwh"], evidence["observed_kwh"]
    estimate = None
    if baseline is not None and observed is not None:
        estimate = round(max(0, baseline - observed) * evidence["horizon_months"], 2)
    evidence["unavailable_reason"] = (
        "Referência ou observação sintética ausente; não estimamos energia nem substituímos ausência por zero."
        if estimate is None else None
    )
    return {
        "uc_id": unit["uc_id"], "municipality": unit["municipio"], "neighborhood": unit["bairro"],
        "class_name": unit["classe"], "feeder_id": unit["alimentador"],
        "priority": round(min(1, sum(signal["weight"] for signal in signals)), 2),
        "reason": suspicion["reason"], "potential_recoverable_energy_kwh": estimate,
        "indicators": [signal["id"] for signal in signals],
        "rule_version": RULE_VERSION, "signals": signals, "estimate_evidence": evidence,
        "limitations": list(LIMITATIONS),
    }


def build_inspection_queue(repository: AnalyticsRepository, filters: AnalyticsFilters) -> tuple[list[dict], AnalyticsStatus]:
    if not repository.source_is_demo:
        raise AnalyticsAPIError(503, "rule_unavailable", "Regra de inspeção real ainda não homologada.")
    selected_units = apply_unit_filters(repository.units, filters)
    selected_ids = {unit["uc_id"] for unit in selected_units}
    unit_by_id = {unit["uc_id"]: unit for unit in selected_units}
    items = []
    for suspicion in repository.suspicions:
        if suspicion["uc_id"] not in selected_ids:
            continue
        unit = unit_by_id[suspicion["uc_id"]]
        items.append(build_suspicion(suspicion, unit))
    state: AnalyticsStatus = "empty" if not items else ("partial" if any(item["potential_recoverable_energy_kwh"] is None for item in items) else "available")
    return items, state


def sort_queue(items: list[dict], order_by: str, direction: str) -> list[dict]:
    items = sorted(items, key=lambda item: item["uc_id"])
    items = sorted(items, key=lambda item: (
        item["potential_recoverable_energy_kwh"] is None,
        -(item["potential_recoverable_energy_kwh"] or 0),
    ))
    known = [item for item in items if item[order_by] is not None]
    missing = [item for item in items if item[order_by] is None]
    return sorted(known, key=lambda item: item[order_by], reverse=direction == "desc") + missing


def suspicion_detail(repository: AnalyticsRepository, uc_id: str) -> dict:
    items, _ = build_inspection_queue(repository, AnalyticsFilters())
    item = next((item for item in items if item["uc_id"] == uc_id), None)
    if item is None:
        raise AnalyticsAPIError(404, "not_found", "Suspeita não encontrada.")
    return item


def build_queue_response(
    repository: AnalyticsRepository,
    filters: AnalyticsFilters,
    page: int,
    page_size: int,
    order_by: str,
    direction: str,
) -> QueueResponse:
    """Compose the product response before pagination, preserving source and scope."""
    items, state = build_inspection_queue(repository, filters)
    items = sort_queue(items, order_by, direction)
    total = len(items)
    result_metadata = metadata(repository, state, DEFAULT_START, DEFAULT_END, filters)
    if state == "partial":
        result_metadata.limitations.append(
            "Há suspeitas sem estimativa demonstrativa de energia recuperável."
        )
    result_metadata.limitations.extend(LIMITATIONS)
    options = {
        key: sorted({unit[key] for unit in repository.units})
        for key in ("municipio", "bairro", "classe", "alimentador")
    }
    return QueueResponse(
        data={
            "items": items[(page - 1) * page_size:page * page_size],
            "filter_options": options,
            "summary": {
                "total_units": total,
                "highest_priority": max((item["priority"] for item in items), default=None),
                "estimated_units": sum(item["potential_recoverable_energy_kwh"] is not None for item in items),
                "unavailable_estimate_units": sum(item["potential_recoverable_energy_kwh"] is None for item in items),
            },
        },
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
        metadata=result_metadata,
    )


def build_suspicion_response(
    repository: AnalyticsRepository, uc_id: str,
) -> SuspicionResponse:
    item = suspicion_detail(repository, uc_id)
    state = "partial" if item["potential_recoverable_energy_kwh"] is None else "available"
    result_metadata = metadata(
        repository, state, DEFAULT_START, DEFAULT_END, AnalyticsFilters()
    )
    result_metadata.limitations.extend(LIMITATIONS)
    return SuspicionResponse(data=item, metadata=result_metadata)


GOLD_INSPECTION_RULE_VERSION = "gold-fila-inspecao-v1"
GOLD_INSPECTION_LIMITATIONS = [
    "A fila é um snapshot cadastral sem competência mensal de triagem.",
    "A categoria reproduz a classificação Gold e não representa uma ordem de despacho nem uma probabilidade.",
    "REVISAR permanece uma categoria própria; a API não a converte em outra prioridade.",
    "A extração não publica energia recuperável; nenhum valor é estimado.",
    "Variação compara as janelas fixas jul/2022–jun/2023 e jul/2025–jun/2026 e não estima recuperação.",
]
GOLD_RECOVERY_UNAVAILABLE_REASONS = {
    "ESTIMATIVA_UC_INDISPONIVEL": "A Gold publica apenas referência histórica por inspeção; não estima recuperação para esta UC.",
    "BASE_INSUFICIENTE": "A base histórica é insuficiente para validar a referência de recuperação.",
    "CANDIDATO_REPROVADO_NA_VALIDACAO_TEMPORAL": "A referência de recuperação não passou na validação temporal.",
}


def _gold_recovery_unavailable_reason(status: str | None) -> str:
    if status in GOLD_RECOVERY_UNAVAILABLE_REASONS:
        return GOLD_RECOVERY_UNAVAILABLE_REASONS[status]
    if status is not None:
        return f"Estimativa individual indisponível (estado Gold: {status})."
    return "A Gold não informou um estado nem um valor de estimativa individual."


def _gold_metadata(repository: GoldInspectionRepository, state: AnalyticsStatus, filters: AnalyticsFilters) -> GoldMetadata:
    context = repository.context
    imported = context.imported_at
    updated_at = imported.isoformat() if imported is not None else ""
    return GoldMetadata(
        status=state, period=None, filters=filters,
        source=AnalyticsSource(kind="gold", version=context.lote, is_demo=False, updated_at=updated_at),
        limitations=list(GOLD_INSPECTION_LIMITATIONS), temporal_scope="snapshot",
        schema_version=context.schema_version, fingerprint=context.fingerprint,
    )


def _gold_item(row: dict) -> GoldInspectionItem:
    variation = None
    if row.get("variation_uc_id") is not None:
        variation = GoldInspectionVariation(
            p1_months_observed=row["meses_com_leitura_p1"],
            p1_average_kwh_per_month=row["consumo_medio_inicial"],
            p2_months_observed=row["meses_com_leitura_p2"],
            p2_average_kwh_per_month=row["consumo_medio_final"],
            variation_kwh=row["variacao_kwh"], variation_pct=row["variacao_pct"],
            drop_over_30_pct=row["queda_consumo_superior_30_pct"],
        )
    return GoldInspectionItem(
        uc_id=row["id_uc"], municipality=row["municipio"], neighborhood=row["bairro"],
        class_name=row["classe"], feeder_id=row["alimentador"],
        category=row["prioridade_inspecao"], reason=row["motivo_prioridade"],
        queue_position=row["posicao_fila_inspecao"],
        recovery_unavailable_reason=_gold_recovery_unavailable_reason(row["estado_estimativa_recuperacao"]),
        evidence=GoldInspectionEvidence(
            inspections_performed=row["total_inspecoes_realizadas"],
            confirmed_irregular_inspections=row["total_inspecoes_irregulares"],
            historical_average_kwh_per_reading=row["media_consumo_historico"],
            distributed_generation_present=row["possui_geracao_solar"],
            cadastral_status=row["status"], call_center_contacts=row["total_chamados_callcenter"],
            interruptions=row["total_interrupcoes_sofridas"],
            priority_order=row["ordem_prioridade_inspecao"],
            historical_recovery_mean_kwh_per_inspection=row["media_historica_recuperacao_kwh_por_inspecao"],
            historical_recovery_interval_lower_kwh=row["intervalo_historico_recuperacao_inferior_kwh"],
            historical_recovery_interval_upper_kwh=row["intervalo_historico_recuperacao_superior_kwh"],
            historical_recovery_reference=row["referencia_media_historica_recuperacao"],
            historical_recovery_status=row["estado_media_historica_recuperacao"],
            estimated_recoverable_energy_kwh=row["energia_estimada_recuperavel_kwh"],
            recovery_interval_lower_kwh=row["intervalo_recuperacao_inferior_kwh"],
            recovery_interval_upper_kwh=row["intervalo_recuperacao_superior_kwh"],
            recovery_estimate_status=row["estado_estimativa_recuperacao"],
            recovery_estimate_method=row["metodo_estimativa_recuperacao"],
        ), variation=variation,
    )


def _validate_gold_filters(repository: GoldInspectionRepository, filters: AnalyticsFilters, options: dict[str, list[str]]) -> None:
    for key, value in filters.model_dump(exclude_none=True).items():
        if value not in options[key]:
            raise AnalyticsAPIError(422, "invalid_query", "Filtro desconhecido.", [{"field": key, "message": "O valor não existe na publicação Gold atual."}])
    if filters.municipio and filters.bairro:
        if not repository.bairro_belongs_to_municipio(filters.bairro, filters.municipio):
            raise AnalyticsAPIError(422, "invalid_query", "Combinação geográfica contraditória.", [{"field": "bairro", "message": "O bairro não pertence ao município informado."}])


def build_gold_queue_response(
    repository: GoldInspectionRepository, filters: AnalyticsFilters, page: int, page_size: int,
    order_by: str, direction: str,
) -> GoldInspectionQueueResponse:
    options = repository.filter_options()
    _validate_gold_filters(repository, filters, options)
    total = repository.count(filters)
    category_counts = repository.category_counts(filters)
    rows = repository.list_page(filters, page, page_size, order_by, direction)
    items = [_gold_item(row) for row in rows]
    state: AnalyticsStatus = "empty" if total == 0 else "available"
    return GoldInspectionQueueResponse(
        data={
            "items": items, "filter_options": options,
            "summary": {
                "total_units": total,
                "categories": {key: count for key, count in category_counts.items() if key is not None},
                "uncategorized_units": category_counts.get(None, 0),
                "estimated_units": 0, "unavailable_estimate_units": total,
            },
        },
        pagination={"page": page, "page_size": page_size, "total": total,
                    "total_pages": (total + page_size - 1) // page_size},
        metadata=_gold_metadata(repository, state, filters),
    )


def build_gold_suspicion_response(repository: GoldInspectionRepository, uc_id: str) -> GoldSuspicionResponse:
    row = repository.detail(uc_id)
    if row is None:
        raise AnalyticsAPIError(404, "not_found", "Suspeita não encontrada na publicação Gold atual.")
    item = _gold_item(row)
    return GoldSuspicionResponse(
        data=GoldSuspicionDetail(**item.model_dump(), rule_version=GOLD_INSPECTION_RULE_VERSION,
                                 limitations=list(GOLD_INSPECTION_LIMITATIONS)),
        metadata=_gold_metadata(repository, "available", AnalyticsFilters()),
    )
