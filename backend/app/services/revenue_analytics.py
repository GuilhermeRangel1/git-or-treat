from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import AnalyticsFilters, AnalyticsStatus
from app.services.analytics import AnalyticsAPIError


MISSING_DIMENSION = "__grid360_missing__"
MISSING_LABEL = "Não informado"
SMALL_BASE_THRESHOLD_UC = 5
MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.0001")
METHOD_LIMITATION = "Método demonstrativo por extremos; não identifica causalidade nem reajuste homologado."

GroupBy = Literal["municipio", "bairro", "classe"]


def _decimal(value: int | float | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _round(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _month_sequence(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    months = []
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def _dimension_value(unit: dict, dimension: str) -> str:
    value = unit.get(dimension)
    return MISSING_DIMENSION if value is None or not str(value).strip() else str(value)


def _validate_and_filter_units(units: list[dict], filters: AnalyticsFilters) -> list[dict]:
    dimensions = {"municipio", "bairro", "classe"}
    if any(
        unit.get(field) == MISSING_DIMENSION
        for unit in units
        for field in dimensions
    ):
        raise AnalyticsAPIError(
            503,
            "source_unavailable",
            "A fonte usa um valor reservado para dimensão ausente.",
            [{"field": "source", "message": "O marcador de ausência não pode ser um valor literal da fonte."}],
        )
    values_by_field = {
        field: {_dimension_value(unit, field) if field in dimensions else unit.get(field) for unit in units}
        for field in ("municipio", "bairro", "classe", "alimentador")
    }
    for field, value in filters.model_dump(exclude_none=True).items():
        if value == MISSING_DIMENSION and field not in dimensions:
            raise AnalyticsAPIError(422, "invalid_query", "Filtro inválido.", [{"field": field, "message": "O marcador representa somente município, bairro ou classe ausente."}])
        if value not in values_by_field[field]:
            raise AnalyticsAPIError(422, "invalid_query", "Filtro desconhecido.", [{"field": field, "message": "O valor não existe na fonte demonstrativa."}])

    if filters.municipio and filters.bairro:
        compatible_towns = {
            _dimension_value(unit, "municipio")
            for unit in units
            if _dimension_value(unit, "bairro") == filters.bairro
        }
        if filters.municipio not in compatible_towns:
            raise AnalyticsAPIError(422, "invalid_query", "Combinação geográfica contraditória.", [{"field": "bairro", "message": "O bairro não pertence ao município informado."}])

    return [
        unit
        for unit in units
        if all(
            value is None
            or (_dimension_value(unit, field) if field in dimensions else unit.get(field)) == value
            for field, value in filters.model_dump().items()
        )
    ]


def _sum_field(rows: Iterable[dict], field: str) -> Decimal | None:
    values = [_decimal(row[field]) for row in rows if row.get(field) is not None]
    return sum(values, Decimal("0")) if values else None


def _known_month_value(
    rows: list[dict], field: str, month: str, covered_months: frozenset[str], has_universe: bool
) -> Decimal | None:
    value = _sum_field(rows, field)
    if value is not None:
        return value
    if not rows and has_universe and month in covered_months:
        return Decimal("0")
    return None


def _coverage_status(
    months: list[str],
    covered_months: frozenset[str],
    has_universe: bool,
    has_partial_records: bool = False,
    non_financial: bool = False,
) -> tuple[AnalyticsStatus, list[str], list[str], list[str]]:
    covered = [month for month in months if month in covered_months]
    missing = [month for month in months if month not in covered_months]
    limitations = []
    if not has_universe:
        return "empty", covered, missing, ["O recorte não contém UCs no universo cadastral conhecido."]
    if missing:
        limitations.append("A fonte não declara cobertura completa para todas as competências solicitadas.")
    if has_partial_records:
        limitations.append("Há registros nulos ou incompletos nesta grandeza.")
    if non_financial and len(covered) == len(months) and not has_partial_records:
        return "available", covered, missing, limitations
    if missing and not covered:
        return "unavailable", covered, missing, limitations
    if missing or has_partial_records:
        return "partial" if covered else "unavailable", covered, missing, limitations
    return "available", covered, missing, limitations


def _snapshot(
    month: str,
    invoices: list[dict],
    units: list[dict],
    billed_coverage: frozenset[str],
    energy_coverage: frozenset[str],
) -> tuple[dict, Decimal | None, Decimal | None]:
    if not units:
        return ({
            "competencia": month,
            "billed_amount": None,
            "billed_energy_kwh": None,
            "observed_price_brl_per_kwh": None,
            "billed_uc_count": None,
            "status": "empty",
            "limitations": ["O recorte não contém UCs no universo cadastral conhecido."],
        }, None, None)

    month_invoices = [row for row in invoices if row["competencia"] == month]
    amount = _known_month_value(month_invoices, "billed_amount", month, billed_coverage, True)
    energy = _known_month_value(month_invoices, "billed_energy_kwh", month, energy_coverage, True)
    count = len({row["uc_id"] for row in month_invoices}) if month in billed_coverage else None
    limitations = []
    if count is None:
        limitations.append("A cobertura financeira do extremo não está comprovada; contagem de UCs faturadas desconhecida.")
    month_has_incomplete_billing = any(
        row.get("billed_amount") is None or row.get("billed_energy_kwh") is None
        for row in month_invoices
    )
    status: AnalyticsStatus = (
        "unavailable"
        if amount is None or energy is None or count is None
        else "partial" if month_has_incomplete_billing else "available"
    )
    if month_has_incomplete_billing:
        limitations.append("Há faturas sem valor faturado ou energia faturada observada neste extremo.")
    if amount is None or energy is None:
        limitations.append("Receita ou energia faturada não está coberta nesta competência.")
    observed_price = None
    if amount is not None and energy is not None and energy > 0:
        observed_price = _number(_round(amount / energy, PRICE_QUANTUM))
    return ({
        "competencia": month,
        "billed_amount": _number(_round(amount, MONEY_QUANTUM)) if amount is not None else None,
        "billed_energy_kwh": _number(_round(energy, MONEY_QUANTUM)) if energy is not None else None,
        "observed_price_brl_per_kwh": observed_price,
        "billed_uc_count": count,
        "status": status,
        "limitations": limitations,
    }, amount, energy)


def _quality(initial: dict, final: dict, finance_complete: bool, start: str, end: str) -> dict:
    counts = [initial["billed_uc_count"], final["billed_uc_count"]]
    small_base = any(count is not None and count < SMALL_BASE_THRESHOLD_UC for count in counts)
    limitations = []
    if small_base:
        limitations.append(f"Base pequena: menos de {SMALL_BASE_THRESHOLD_UC} UCs faturadas em pelo menos um extremo; percentuais não são elegíveis.")
    if any(count is None for count in counts):
        limitations.append("Contagem de UCs faturadas desconhecida em pelo menos um extremo; percentual não elegível.")
    eligible = (
        start != end
        and finance_complete
        and initial["billed_amount"] is not None
        and initial["billed_amount"] > 0
        and all(count is not None and count >= SMALL_BASE_THRESHOLD_UC for count in counts)
    )
    return {
        "small_base_threshold_uc": SMALL_BASE_THRESHOLD_UC,
        "small_base": small_base,
        "percent_change_eligible": eligible,
        "limitations": limitations,
    }


def _filter_options(units: list[dict]) -> dict:
    municipalities = sorted({_dimension_value(unit, "municipio") for unit in units})
    neighborhoods = sorted({(_dimension_value(unit, "municipio"), _dimension_value(unit, "bairro")) for unit in units})
    classes = sorted({_dimension_value(unit, "classe") for unit in units})
    return {
        "municipios": municipalities,
        "bairros": [{"municipio": municipality, "bairro": neighborhood} for municipality, neighborhood in neighborhoods],
        "classes": classes,
    }


def _unavailable_breakdown(group_by: GroupBy) -> dict:
    return {
        "dimension": group_by,
        "items": [],
        "reconciliation": {
            "status": "unavailable",
            "initial_known_sum_brl": None,
            "final_known_sum_brl": None,
            "comparable_change_sum_brl": None,
            "non_comparable_group_count": 0,
            "unattributed_change_brl": None,
            "residual_brl": None,
            "limitations": ["O detalhamento por grupo será disponibilizado na fatia de recortes."],
        },
    }


def _group_identity(unit: dict, dimension: GroupBy) -> tuple[tuple[str, ...], str, str, dict]:
    if dimension == "bairro":
        municipality = _dimension_value(unit, "municipio")
        neighborhood = _dimension_value(unit, "bairro")
        key = f"bairro:{len(municipality)}:{municipality}:{len(neighborhood)}:{neighborhood}"
        filters = {"municipio": municipality, "bairro": neighborhood}
        return (municipality, neighborhood), key, neighborhood if neighborhood != MISSING_DIMENSION else MISSING_LABEL, filters
    value = _dimension_value(unit, dimension)
    return (value,), f"{dimension}:{value}", value if value != MISSING_DIMENSION else MISSING_LABEL, {dimension: value}


def _build_breakdown(
    repository: AnalyticsRepository,
    start: str,
    end: str,
    filters: AnalyticsFilters,
    group_by: GroupBy,
    units: list[dict],
) -> dict:
    groups: dict[tuple[str, ...], tuple[str, str, dict]] = {}
    for unit in units:
        identity, key, label, overrides = _group_identity(unit, group_by)
        if identity not in groups:
            groups[identity] = (key, label, overrides)

    inherited = filters.model_dump()
    items = []
    for identity in sorted(groups, key=lambda value: (groups[value][1].casefold(), groups[value][0])):
        key, label, overrides = groups[identity]
        effective_filters = inherited | overrides
        summary = build_revenue(
            repository,
            start,
            end,
            AnalyticsFilters(**effective_filters),
            group_by=group_by,
            _include_breakdown=False,
        )
        items.append({
            "key": key,
            "label": label,
            "filters": effective_filters,
            "comparison": summary["comparison"],
            "quality": summary["quality"],
        })

    if not items:
        return {
            "dimension": group_by,
            "items": [],
            "reconciliation": {
                "status": "empty",
                "initial_known_sum_brl": None,
                "final_known_sum_brl": None,
                "comparable_change_sum_brl": None,
                "non_comparable_group_count": 0,
                "unattributed_change_brl": None,
                "residual_brl": None,
                "limitations": ["O recorte não contém grupos no universo cadastral conhecido."],
            },
        }

    initial_values = [
        _decimal(item["comparison"]["initial"]["billed_amount"])
        for item in items
        if item["comparison"]["initial"]["billed_amount"] is not None
    ]
    final_values = [
        _decimal(item["comparison"]["final"]["billed_amount"])
        for item in items
        if item["comparison"]["final"]["billed_amount"] is not None
    ]
    change_values = [
        _decimal(item["comparison"]["billed_amount_change_brl"])
        for item in items
        if item["comparison"]["billed_amount_change_brl"] is not None
    ]
    non_comparable = len(items) - len(change_values)
    initial_sum = _round(sum(initial_values, Decimal("0")), MONEY_QUANTUM) if initial_values else None
    final_sum = _round(sum(final_values, Decimal("0")), MONEY_QUANTUM) if final_values else None
    change_sum = _round(sum(change_values, Decimal("0")), MONEY_QUANTUM) if change_values else None
    total = build_revenue(
        repository, start, end, filters, group_by=group_by, _include_breakdown=False
    )
    total_change = total["comparison"]["billed_amount_change_brl"]
    initial_total = total["comparison"]["initial"]["billed_amount"]
    final_total = total["comparison"]["final"]["billed_amount"]
    extreme_mismatch = (
        (initial_sum is not None and initial_total is not None and initial_sum != _decimal(initial_total))
        or (final_sum is not None and final_total is not None and final_sum != _decimal(final_total))
    )
    residual = unattributed = None
    limitations = []
    if extreme_mismatch:
        limitations.append("A soma dos valores publicados por grupo diverge dos extremos agregados após arredondamento; fechamento visual indisponível.")
    if total_change is None:
        state: AnalyticsStatus = "unavailable"
        limitations.append("A variação total do recorte não é comparável; reconciliação da janela indisponível.")
    elif non_comparable:
        state = "unavailable" if extreme_mismatch else "partial"
        limitations.append("Há grupos sem variação comparável entre os extremos.")
        if change_sum is not None:
            unattributed = _round(_decimal(total_change) - change_sum, MONEY_QUANTUM)
    else:
        residual = _round(_decimal(total_change) - (change_sum or Decimal("0")), MONEY_QUANTUM)
        unattributed = Decimal("0.00")
        state = "available" if residual == Decimal("0.00") and not extreme_mismatch else "unavailable"
        if residual != Decimal("0.00"):
            limitations.append("A soma das variações por grupo não fecha com a variação total.")

    return {
        "dimension": group_by,
        "items": items,
        "reconciliation": {
            "status": state,
            "initial_known_sum_brl": _number(initial_sum),
            "final_known_sum_brl": _number(final_sum),
            "comparable_change_sum_brl": _number(change_sum),
            "non_comparable_group_count": non_comparable,
            "unattributed_change_brl": _number(unattributed),
            "residual_brl": _number(residual),
            "limitations": limitations,
        },
    }


def build_revenue(
    repository: AnalyticsRepository,
    start: str,
    end: str,
    filters: AnalyticsFilters,
    group_by: GroupBy = "municipio",
    _include_breakdown: bool = True,
) -> dict:
    months = _month_sequence(start, end)
    units = _validate_and_filter_units(repository.units, filters)
    unit_ids = {unit["uc_id"] for unit in units}
    invoices = [row for row in repository.invoices if row["uc_id"] in unit_ids and start <= row["competencia"] <= end]
    readings = [row for row in repository.readings if row["uc_id"] in unit_ids and start <= row["competencia"] <= end]
    coverage = repository.revenue_coverage
    has_universe = bool(units)

    series = []
    payment_partial = False
    measured_partial = False
    billed_amount_partial = False
    billed_energy_partial = False
    for month in months:
        month_invoices = [row for row in invoices if row["competencia"] == month]
        month_readings = [row for row in readings if row["competencia"] == month]
        paid_rows = [row for row in month_invoices if row.get("paid_amount") is not None]
        measured_rows = [row for row in month_readings if row.get("measured_energy_kwh") is not None]
        payment_partial |= len(paid_rows) < len(month_invoices)
        measured_partial |= len(measured_rows) < len(month_readings)
        billed_amount_partial |= any(row.get("billed_amount") is None for row in month_invoices)
        billed_energy_partial |= any(row.get("billed_energy_kwh") is None for row in month_invoices)
        billed_amount = _known_month_value(month_invoices, "billed_amount", month, coverage.billed_amount, has_universe)
        billed_energy = _known_month_value(month_invoices, "billed_energy_kwh", month, coverage.billed_energy_kwh, has_universe)
        paid_amount = (
            _known_month_value([], "paid_amount", month, coverage.paid_amount, has_universe)
            if not month_invoices
            else _sum_field(paid_rows, "paid_amount")
        )
        measured_energy = _sum_field(measured_rows, "measured_energy_kwh")
        series.append({
            "competencia": month,
            "billed_amount": _number(_round(billed_amount, MONEY_QUANTUM)) if billed_amount is not None else None,
            "paid_amount": _number(_round(paid_amount, MONEY_QUANTUM)) if paid_amount is not None else None,
            "measured_energy_kwh": _number(_round(measured_energy, MONEY_QUANTUM)) if measured_energy is not None else None,
            "billed_energy_kwh": _number(_round(billed_energy, MONEY_QUANTUM)) if billed_energy is not None else None,
        })

    metric_coverage = {}
    for field, covered_months, partial_records, non_financial in (
        ("billed_amount", coverage.billed_amount, billed_amount_partial, False),
        ("billed_energy_kwh", coverage.billed_energy_kwh, billed_energy_partial, False),
        ("paid_amount", coverage.paid_amount, payment_partial, False),
        ("measured_energy_kwh", coverage.measured_energy_kwh, measured_partial or any(
            {row["uc_id"] for row in readings if row["competencia"] == month} != unit_ids
            for month in months
        ), True),
    ):
        status, covered, missing, limitations = _coverage_status(
            months, covered_months, has_universe, partial_records, non_financial
        )
        metric_coverage[field] = {
            "status": status,
            "covered_months": covered,
            "missing_months": missing,
            "limitations": limitations,
        }

    finance_complete = (
        metric_coverage["billed_amount"]["status"] == "available"
        and metric_coverage["billed_energy_kwh"]["status"] == "available"
    )
    initial, initial_amount, initial_energy = _snapshot(start, invoices, units, coverage.billed_amount, coverage.billed_energy_kwh)
    final, final_amount, final_energy = _snapshot(end, invoices, units, coverage.billed_amount, coverage.billed_energy_kwh)
    quality = _quality(initial, final, finance_complete, start, end)

    billed_change = energy_change = measured_change = percent_change = None
    comparison_eligible = start != end and finance_complete and initial_amount is not None and final_amount is not None
    if comparison_eligible:
        displayed_initial_amount = _decimal(initial["billed_amount"])
        displayed_final_amount = _decimal(final["billed_amount"])
        billed_change = _round(displayed_final_amount - displayed_initial_amount, MONEY_QUANTUM)
        if initial["billed_energy_kwh"] is not None and final["billed_energy_kwh"] is not None:
            energy_change = _round(
                _decimal(final["billed_energy_kwh"]) - _decimal(initial["billed_energy_kwh"]),
                MONEY_QUANTUM,
            )
        if quality["percent_change_eligible"] and displayed_initial_amount > 0:
            percent_change = _round((billed_change / displayed_initial_amount) * Decimal("100"), PERCENT_QUANTUM)
    first_measured = next((point["measured_energy_kwh"] for point in series if point["competencia"] == start), None)
    last_measured = next((point["measured_energy_kwh"] for point in series if point["competencia"] == end), None)
    if start != end and first_measured is not None and last_measured is not None:
        measured_change = _round(_decimal(last_measured) - _decimal(first_measured), MONEY_QUANTUM)

    volume_effect = price_effect = interaction_effect = rounding_adjustment = None
    decomposition_status: AnalyticsStatus = "unavailable"
    decomposition_limitations = [METHOD_LIMITATION]
    if start == end:
        decomposition_limitations.append("A comparação preço-volume exige competências distintas.")
    elif not finance_complete:
        decomposition_limitations.append("As competências solicitadas não têm cobertura financeira completa para comparação; não substituímos extremos ausentes.")
    elif initial_amount is not None and final_amount is not None and initial_energy is not None and final_energy is not None:
        if initial_energy <= 0 or final_energy <= 0:
            decomposition_limitations.append("Energia faturada precisa ser positiva nos dois extremos para calcular preço-volume.")
        else:
            p0 = initial_amount / initial_energy
            p1 = final_amount / final_energy
            delta_price = p1 - p0
            delta_volume = final_energy - initial_energy
            volume_effect = _round(p0 * delta_volume, MONEY_QUANTUM)
            price_effect = _round(initial_energy * delta_price, MONEY_QUANTUM)
            interaction_effect = _round(delta_price * delta_volume, MONEY_QUANTUM)
            rounding_adjustment = _round(
                _decimal(billed_change) - volume_effect - price_effect - interaction_effect,
                MONEY_QUANTUM,
            )
            decomposition_status = "available" if abs(rounding_adjustment) <= MONEY_QUANTUM else "unavailable"
            if decomposition_status == "unavailable":
                decomposition_limitations.append("O ajuste de arredondamento excede R$ 0,01; a reconciliação falhou.")

    raw_billed_total = _sum_field(invoices, "billed_amount")
    raw_paid_total = _sum_field(invoices, "paid_amount")
    raw_billed_energy_total = _sum_field(invoices, "billed_energy_kwh")
    if raw_billed_total is None and any(point["billed_amount"] == 0 for point in series):
        raw_billed_total = Decimal("0")
    if raw_paid_total is None and any(point["paid_amount"] == 0 for point in series):
        raw_paid_total = Decimal("0")
    if raw_billed_energy_total is None and any(point["billed_energy_kwh"] == 0 for point in series):
        raw_billed_energy_total = Decimal("0")
    raw_measured_total = _sum_field(readings, "measured_energy_kwh")
    total_billed = _round(raw_billed_total, MONEY_QUANTUM) if raw_billed_total is not None else None
    total_paid = _round(raw_paid_total, MONEY_QUANTUM) if raw_paid_total is not None else None
    total_billed_energy = _round(raw_billed_energy_total, MONEY_QUANTUM) if raw_billed_energy_total is not None else None
    total_measured = _round(raw_measured_total, MONEY_QUANTUM) if raw_measured_total is not None else None
    observed_price = None
    if raw_billed_total is not None and raw_billed_energy_total is not None and raw_billed_energy_total > 0:
        observed_price = _number(_round(raw_billed_total / raw_billed_energy_total, PRICE_QUANTUM))

    return {
        "currency_unit": "BRL",
        "energy_unit": "kWh",
        "total_billed_amount": _number(total_billed),
        "total_paid_amount": _number(total_paid),
        "total_measured_energy_kwh": _number(total_measured),
        "total_billed_energy_kwh": _number(total_billed_energy),
        "observed_price_brl_per_kwh": observed_price,
        "series": series,
        "comparison": {
            "initial": initial,
            "final": final,
            "billed_amount_change_brl": _number(billed_change),
            "billed_energy_change_kwh": _number(energy_change),
            "measured_energy_change_kwh": _number(measured_change),
            "billed_amount_change_percent": _number(percent_change),
        },
        "price_volume": {
            "method": "endpoint_price_volume",
            "reference_version": "dev03-v1",
            "price_effect_brl": _number(price_effect),
            "volume_effect_brl": _number(volume_effect),
            "interaction_effect_brl": _number(interaction_effect),
            "rounding_adjustment_brl": _number(rounding_adjustment),
            "status": decomposition_status,
            "limitations": decomposition_limitations,
        },
        "coverage": {"requested_months": months, **metric_coverage},
        "quality": quality,
        "breakdown": _build_breakdown(repository, start, end, filters, group_by, units)
        if _include_breakdown else _unavailable_breakdown(group_by),
        "filter_options": _filter_options(repository.units),
    }
