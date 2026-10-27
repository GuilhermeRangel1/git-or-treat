import re
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.repositories.analytics import AnalyticsRepository, UCCoverage
from app.schemas.analytics import AnalyticsStatus
from app.services.analytics import AnalyticsAPIError, page_items

HISTORY_ORDER = {
    "consumption": {"competencia", "measured_energy_kwh"},
    "invoices": {
        "competencia",
        "invoice_id",
        "billed_amount",
        "due_date",
        "payment_date",
    },
    "meters": {"installed_at", "removed_at", "meter_id"},
    "distributed_generation": {"capacity_kw", "status"},
    "interruptions": {"competencia", "event_id", "duration_hours"},
    "calls": {"opened_at", "call_id", "category"},
}


def validate_uc_id(value: str) -> str:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 100
        or re.fullmatch(r"[A-Za-z0-9-]+", normalized, flags=re.ASCII) is None
    ):
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Identificador de UC inválido.",
            [
                {
                    "field": "uc_id",
                    "message": "Use de 1 a 100 caracteres ASCII alfanuméricos ou hífen.",
                }
            ],
        )
    return normalized


def validate_period(start: str | None, end: str | None) -> tuple[str, str]:
    if (start is None) != (end is None):
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Informe as duas competências.",
            [{"field": "start", "message": "start e end devem ser informados juntos."}],
        )
    if start is None or end is None:
        from app.services.analytics import DEFAULT_END, DEFAULT_START

        return DEFAULT_START, DEFAULT_END
    for field, value in (("start", start), ("end", end)):
        try:
            if (
                re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value, flags=re.ASCII) is None
                or value[:4] == "0000"
            ):
                raise ValueError
            date(int(value[:4]), int(value[5:]), 1)
        except (TypeError, ValueError):
            raise AnalyticsAPIError(
                422,
                "invalid_query",
                "Competência inválida.",
                [{"field": field, "message": "Use YYYY-MM com mês entre 01 e 12."}],
            ) from None
    if start > end:
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Janela inválida.",
            [{"field": "start", "message": "start deve ser anterior ou igual a end."}],
        )
    return start, end


def _coverage_months(
    coverage: UCCoverage | None, uc_id: str, start: str, end: str
) -> tuple[list[str], bool]:
    if (
        coverage is None
        or uc_id not in coverage.uc_ids
        or coverage.start is None
        or coverage.end is None
    ):
        return [], False
    first, last = max(start, coverage.start), min(end, coverage.end)
    if first > last:
        return [], False
    months = []
    year, month = map(int, first.split("-"))
    end_year, end_month = map(int, last.split("-"))
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months, first == start and last == end


def build_uc_search(
    repository: AnalyticsRepository,
    q: str | None,
    page: int,
    page_size: int,
    order_by: str,
) -> tuple[list[dict], dict, AnalyticsStatus]:
    from app.repositories.gold import GoldAnalyticsRepository
    if isinstance(repository, GoldAnalyticsRepository):
        from app.services.gold_uc import search
        return search(repository, q, page, page_size, order_by)
    if q is not None:
        q = validate_uc_id(q)
    items = [
        {
            key: unit[key]
            for key in (
                "uc_id",
                "municipio",
                "bairro",
                "classe",
                "alimentador",
                "status",
            )
        }
        for unit in repository.units
        if q is None or q.casefold() in unit["uc_id"].casefold()
    ]
    selected, pagination = page_items(
        items,
        page,
        page_size,
        order_by,
        {"uc_id", "municipio", "bairro", "classe", "alimentador", "status"},
    )
    return selected, pagination, "available" if items else "empty"


def build_uc_detail(
    repository: AnalyticsRepository, uc_id: str
) -> tuple[dict, AnalyticsStatus, list[str]]:
    from app.repositories.gold import GoldAnalyticsRepository
    if isinstance(repository, GoldAnalyticsRepository):
        from app.services.gold_uc import profile
        return {"profile": profile(repository.unit(uc_id)), **{section: [] for section in ("consumption", "invoices", "meters", "distributed_generation", "interruptions", "calls")},
                "section_status": {section: "unavailable" for section in ("consumption", "invoices", "meters", "distributed_generation", "interruptions", "calls")}}, "partial", list(repository.source_limitations)
    unit = next((item for item in repository.units if item["uc_id"] == uc_id), None)
    if unit is None:
        raise AnalyticsAPIError(
            404,
            "not_found",
            "Unidade consumidora não encontrada.",
            [{"field": "uc_id", "message": "Nenhuma UC corresponde ao identificador."}],
        )
    readings = [row for row in repository.readings if row["uc_id"] == uc_id]
    invoices = [row for row in repository.invoices if row["uc_id"] == uc_id]
    meters = [row for row in repository.meters if row["uc_id"] == uc_id]
    generation = [row for row in repository.generation if row["uc_id"] == uc_id]
    interruptions = [row for row in repository.interruptions if row["uc_id"] == uc_id]
    calls = [row for row in repository.calls if row["uc_id"] == uc_id]
    missing_readings = any(row["measured_energy_kwh"] is None for row in readings)
    section_status = {
        "profile": "available",
        "consumption": "partial"
        if missing_readings
        else ("available" if readings else "empty"),
        "invoices": "available" if invoices else "empty",
        "meters": "available" if meters else "empty",
        "distributed_generation": "available" if generation else "empty",
        "interruptions": "available" if interruptions else "empty",
        "calls": "available" if calls else "empty",
    }
    state: AnalyticsStatus = (
        "partial" if "partial" in section_status.values() else "available"
    )
    limitations = (
        ["Há leitura ausente no histórico; valores ausentes permanecem nulos."]
        if missing_readings
        else []
    )
    data = {
        "profile": {
            key: unit.get(key)
            for key in (
                "uc_id",
                "customer_reference",
                "customer_name",
                "municipio",
                "bairro",
                "classe",
                "alimentador",
                "status",
            )
        },
        "consumption": [
            {
                key: row.get(key)
                for key in ("competencia", "measured_energy_kwh", "status")
            }
            for row in readings
        ],
        "invoices": [
            {
                key: row.get(key)
                for key in (
                    "invoice_id",
                    "competencia",
                    "billed_amount",
                    "paid_amount",
                    "billed_energy_kwh",
                    "due_date",
                    "payment_date",
                    "payment_status",
                )
            }
            for row in invoices
        ],
        "meters": [
            {key: row.get(key) for key in ("meter_id", "installed_at", "removed_at")}
            for row in meters
        ],
        "distributed_generation": [
            {key: row.get(key) for key in ("capacity_kw", "status")}
            for row in generation
        ],
        "interruptions": [
            {
                key: row.get(key)
                for key in ("event_id", "feeder_id", "competencia", "duration_hours")
            }
            for row in interruptions
        ],
        "calls": [
            {key: row.get(key) for key in ("call_id", "opened_at", "category")}
            for row in calls
        ],
        "section_status": section_status,
    }
    return data, state, limitations


def _lookup_unit(repository: AnalyticsRepository, uc_id: str) -> dict:
    normalized = validate_uc_id(uc_id)
    unit = next(
        (
            row
            for row in repository.units
            if row["uc_id"].casefold() == normalized.casefold()
        ),
        None,
    )
    if unit is None:
        raise AnalyticsAPIError(
            404,
            "not_found",
            "Unidade consumidora não encontrada.",
            [{"field": "uc_id", "message": "Nenhuma UC corresponde ao identificador."}],
        )
    return unit


def _measure_for_month(
    repository: AnalyticsRepository, uc_id: str, month: str, measure: str
) -> dict:
    coverage = repository.uc_monthly_coverage.get(measure)
    months, _ = _coverage_months(coverage, uc_id, month, month)
    if not months:
        return {
            "value": None,
            "status": "unavailable",
            "limitations": [f"Cobertura de {measure} desconhecida para {month}."],
        }
    source = (
        repository.readings if measure == "measured_energy_kwh" else repository.invoices
    )
    rows = [r for r in source if r["uc_id"] == uc_id and r["competencia"] == month]
    if measure == "measured_energy_kwh" and len(rows) > 1:
        return {
            "value": None,
            "status": "unavailable",
            "limitations": [
                "Múltiplas leituras na competência sem regra aprovada de agregação."
            ],
        }
    if not rows:
        if measure == "measured_energy_kwh":
            return {
                "value": None,
                "status": "partial",
                "limitations": [
                    f"Nenhuma leitura registrada em {month}; a lacuna não foi preenchida."
                ],
            }
        return {"value": None, "status": "empty", "limitations": []}
    values = [Decimal(str(r[measure])) for r in rows if r.get(measure) is not None]
    if not values:
        return {
            "value": None,
            "status": "partial",
            "limitations": [f"Valores de {measure} ausentes em {month}."],
        }
    value = sum(values, Decimal(0))
    if measure in {"billed_amount", "paid_amount"}:
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if len(values) != len(rows):
        return {
            "value": value,
            "status": "partial",
            "limitations": [
                f"Subtotal de {measure}; há registros sem valor em {month}."
            ],
        }
    return {"value": value, "status": "available", "limitations": []}


def _measure_change(initial: dict, final: dict, money: bool = False) -> dict:
    limitations = list(dict.fromkeys(initial["limitations"] + final["limitations"]))
    if initial["value"] is None or final["value"] is None:
        statuses = {initial["status"], final["status"]}
        if statuses == {"empty"}:
            status: AnalyticsStatus = "empty"
        elif "available" in statuses or "partial" in statuses:
            status = "partial"
        else:
            status = "unavailable"
        return {
            "delta": None,
            "percent_change": None,
            "status": status,
            "limitations": limitations,
        }
    delta = final["value"] - initial["value"]
    if money:
        delta = delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if initial["status"] == "partial" or final["status"] == "partial":
        status = "partial"
    else:
        status = "available"
    if initial["status"] != "available" or final["status"] != "available":
        limitations.append(
            "Percentual indisponível porque pelo menos um extremo tem cobertura incompleta."
        )
        percent = None
    elif initial["value"] <= 0:
        limitations.append(
            "Percentual indisponível porque a base inicial não é positiva (non_positive_base)."
        )
        percent = None
    else:
        percent = (delta / initial["value"] * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return {
        "delta": delta,
        "percent_change": percent,
        "status": status,
        "limitations": limitations,
    }


def build_uc_overview(
    repository: AnalyticsRepository, uc_id: str, start: str | None, end: str | None
) -> dict:
    from app.repositories.gold import GoldAnalyticsRepository
    if isinstance(repository, GoldAnalyticsRepository):
        from app.services.gold_uc import overview
        return overview(repository, uc_id, start, end)
    start, end = validate_period(start, end)
    unit = _lookup_unit(repository, uc_id)
    uc_id = unit["uc_id"]
    profile_coverage = repository.uc_snapshot_coverage.get("profile")
    if profile_coverage is None or uc_id not in profile_coverage.uc_ids:
        raise AnalyticsAPIError(
            503, "source_unavailable", "Cobertura do cadastro da UC indisponível.", []
        )

    measures = (
        "measured_energy_kwh",
        "billed_energy_kwh",
        "billed_amount",
        "paid_amount",
    )
    initial = {
        "competencia": start,
        **{m: _measure_for_month(repository, uc_id, start, m) for m in measures},
    }
    final = {
        "competencia": end,
        **{m: _measure_for_month(repository, uc_id, end, m) for m in measures},
    }
    comparison = {"initial": initial, "final": final}
    comparison.update(
        {
            m: _measure_change(
                initial[m], final[m], money=m in {"billed_amount", "paid_amount"}
            )
            for m in measures
        }
    )

    invoice_coverage = repository.uc_monthly_coverage.get("billed_amount")
    covered, full = _coverage_months(invoice_coverage, uc_id, start, end)
    if not covered:
        open_invoices = {
            "count": None,
            "status": "unavailable",
            "limitations": ["Cobertura de faturas desconhecida para o intervalo."],
        }
    else:
        count = sum(
            1
            for r in repository.invoices
            if r["uc_id"] == uc_id
            and r["competencia"] in covered
            and r.get("payment_status") in {"unpaid", "partial"}
        )
        open_invoices = {
            "count": count,
            "status": "available" if full else "partial",
            "limitations": []
            if full
            else [
                f"Cobertura parcial, de {covered[0]} a {covered[-1]}; contagem parcial."
            ],
        }

    meter_coverage = repository.uc_snapshot_coverage.get("meters")
    if (
        meter_coverage is None
        or uc_id not in meter_coverage.uc_ids
        or not meter_coverage.snapshot_at
    ):
        current_meter = {
            "item": None,
            "status": "unavailable",
            "limitations": ["Cobertura do cadastro de medidores desconhecida."],
        }
    else:
        as_of = meter_coverage.snapshot_at
        current = [
            r
            for r in repository.meters
            if r["uc_id"] == uc_id
            and r["installed_at"] <= as_of
            and (r.get("removed_at") is None or r["removed_at"] > as_of)
        ]
        if len(current) > 1:
            current_meter = {
                "item": None,
                "status": "partial",
                "limitations": [
                    "Vínculos de medidor sobrepostos no snapshot; nenhum foi escolhido como atual."
                ],
            }
        elif current:
            current_meter = {
                "item": {
                    k: current[0].get(k)
                    for k in ("meter_id", "installed_at", "removed_at")
                },
                "status": "available",
                "limitations": [],
            }
        else:
            current_meter = {"item": None, "status": "empty", "limitations": []}

    generation_coverage = repository.uc_snapshot_coverage.get("distributed_generation")
    if generation_coverage is None or uc_id not in generation_coverage.uc_ids:
        generation = {
            "items": [],
            "status": "unavailable",
            "limitations": [
                "Cobertura do cadastro de geração distribuída desconhecida."
            ],
        }
    else:
        records = [r for r in repository.generation if r["uc_id"] == uc_id]
        generation = {
            "items": [
                {"capacity_kw": r["capacity_kw"], "status": r["status"]}
                for r in records
            ],
            "status": "available" if records else "empty",
            "limitations": [
                "Cadastro no snapshot; potência em kW não representa energia compensada."
            ],
        }

    statuses: dict[str, AnalyticsStatus] = {}
    for section, key in (
        ("consumption", "measured_energy_kwh"),
        ("invoices", "billed_amount"),
        ("interruptions", "interruptions"),
        ("calls", "calls"),
    ):
        months, full = _coverage_months(
            repository.uc_monthly_coverage.get(key), uc_id, start, end
        )
        if not months:
            statuses[section] = "unavailable"
            continue
        records = {
            "consumption": repository.readings,
            "invoices": repository.invoices,
            "interruptions": repository.interruptions,
            "calls": repository.calls,
        }[section]
        if section == "calls":
            found = [
                r
                for r in records
                if r["uc_id"] == uc_id and r["opened_at"][:7] in months
            ]
        else:
            found = [
                r for r in records if r["uc_id"] == uc_id and r["competencia"] in months
            ]
        incomplete = False
        if section == "consumption":
            readings_by_month: dict[str, list[dict]] = {}
            for row in found:
                readings_by_month.setdefault(row["competencia"], []).append(row)
            if not any(
                len(rows) == 1 and rows[0].get("measured_energy_kwh") is not None
                for rows in readings_by_month.values()
            ):
                statuses[section] = "unavailable"
                continue
            incomplete = any(
                len(readings_by_month.get(month, [])) != 1
                or readings_by_month[month][0].get("measured_energy_kwh") is None
                for month in months
            )
        elif section == "invoices":
            incomplete = any(
                row.get(field) is None
                for row in found
                for field in ("billed_amount", "billed_energy_kwh", "paid_amount")
            )
        if not full or incomplete:
            statuses[section] = "partial"
        else:
            statuses[section] = (
                "available"
                if found
                else ("partial" if section == "consumption" else "empty")
            )
    for section, key, records in (
        ("meters", "meters", repository.meters),
        ("distributed_generation", "distributed_generation", repository.generation),
    ):
        coverage = repository.uc_snapshot_coverage.get(key)
        statuses[section] = (
            "unavailable"
            if coverage is None or uc_id not in coverage.uc_ids
            else ("available" if any(r["uc_id"] == uc_id for r in records) else "empty")
        )

    profile = {
        k: unit.get(k)
        for k in (
            "uc_id",
            "customer_reference",
            "customer_name",
            "municipio",
            "bairro",
            "classe",
            "alimentador",
            "status",
        )
    }
    all_statuses = list(statuses.values()) + [
        open_invoices["status"],
        current_meter["status"],
        generation["status"],
    ]
    all_statuses.extend(initial[m]["status"] for m in measures)
    all_statuses.extend(final[m]["status"] for m in measures)
    all_statuses.extend(comparison[m]["status"] for m in measures)
    overall = (
        "partial"
        if any(s in {"partial", "unavailable"} for s in all_statuses)
        else "available"
    )
    limitations = list(repository.source_limitations)
    for value in comparison.values():
        if isinstance(value, dict) and "limitations" in value:
            limitations.extend(value["limitations"])
        elif isinstance(value, dict):
            for measure in measures:
                limitations.extend(value[measure]["limitations"])
    limitations.extend(open_invoices["limitations"])
    limitations.extend(current_meter["limitations"])
    limitations.extend(generation["limitations"])
    return {
        "data": {
            "profile": profile,
            "period": {"start": start, "end": end, "granularity": "month"},
            "comparison": comparison,
            "open_invoices": open_invoices,
            "current_meter": current_meter,
            "distributed_generation": generation,
            "section_status": statuses,
        },
        "status": overall,
        "limitations": list(dict.fromkeys(limitations)),
    }


def build_uc_history(
    repository: AnalyticsRepository,
    uc_id: str,
    section: str,
    start: str | None,
    end: str | None,
    page: int,
    page_size: int,
    order_by: str | None,
) -> dict:
    from app.repositories.gold import GoldAnalyticsRepository
    if isinstance(repository, GoldAnalyticsRepository):
        from app.services.gold_uc import history
        return history(repository, uc_id, section, start, end, page, page_size, order_by)
    start, end = validate_period(start, end)
    unit = _lookup_unit(repository, uc_id)
    uc_id = unit["uc_id"]
    if section not in HISTORY_ORDER:
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Seção de histórico inválida.",
            [{"field": "section", "message": "Seção não permitida."}],
        )
    defaults = {
        "consumption": "competencia",
        "invoices": "competencia",
        "meters": "installed_at",
        "distributed_generation": "capacity_kw",
        "interruptions": "competencia",
        "calls": "opened_at",
    }
    order_by = order_by or defaults[section]
    if order_by not in HISTORY_ORDER[section]:
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Ordenação inválida.",
            [{"field": "order_by", "message": "Campo não permitido para esta seção."}],
        )
    records_by_section = {
        "consumption": repository.readings,
        "invoices": repository.invoices,
        "meters": repository.meters,
        "distributed_generation": repository.generation,
        "interruptions": repository.interruptions,
        "calls": repository.calls,
    }
    monthly = section not in {"meters", "distributed_generation"}
    coverage = None
    if section == "invoices":
        invoice_measure_coverage = {
            measure: _coverage_months(
                repository.uc_monthly_coverage.get(measure), uc_id, start, end
            )
            for measure in ("billed_amount", "billed_energy_kwh", "paid_amount")
        }
        covered_months_by_measure = {
            measure: set(measure_months)
            for measure, (measure_months, _) in invoice_measure_coverage.items()
        }
        # Keep invoice months covered by any measure; each value is masked by
        # its own coverage below.
        months = sorted(set().union(*covered_months_by_measure.values()))
        full = all(measure_full for _, measure_full in invoice_measure_coverage.values())
    else:
        coverage_key = {
            "consumption": "measured_energy_kwh",
        }.get(section, section)
        coverage = (
            repository.uc_monthly_coverage
            if monthly
            else repository.uc_snapshot_coverage
        ).get(coverage_key)
        months, full = (
            _coverage_months(coverage, uc_id, start, end) if monthly else ([], False)
        )
    snapshot_known = not monthly and coverage is not None and uc_id in coverage.uc_ids
    if section == "consumption":
        by_month: dict[str, list[dict]] = {}
        for row in records_by_section[section]:
            if row["uc_id"] == uc_id and row["competencia"] in months:
                by_month.setdefault(row["competencia"], []).append(row)
        rows = [
            {
                "competencia": m,
                "measured_energy_kwh": by_month[m][0].get("measured_energy_kwh")
                if len(by_month.get(m, [])) == 1
                else None,
                "status": (
                    "unavailable"
                    if len(by_month.get(m, [])) > 1
                    else (
                        "available"
                        if len(by_month.get(m, [])) == 1
                        and by_month[m][0].get("measured_energy_kwh") is not None
                        else "partial"
                    )
                ),
            }
            for m in months
        ]
        status: AnalyticsStatus = (
            "unavailable"
            if not any(r["status"] == "available" for r in rows)
            else (
                "partial"
                if not full or any(r["status"] != "available" for r in rows)
                else "available"
            )
        )
        limitations = (
            []
            if status == "available"
            else [
                "Cobertura incompleta ou competência sem leitura; não houve interpolação."
            ]
        )
    else:
        rows = [r for r in records_by_section[section] if r["uc_id"] == uc_id]
        if section in {"invoices", "interruptions"}:
            rows = [r for r in rows if r["competencia"] in months]
        elif section == "calls":
            rows = [r for r in rows if r["opened_at"][:7] in months]
        elif section == "meters":
            first_day, last_day = (
                start + "-01",
                end + f"-{monthrange(int(end[:4]), int(end[5:]))[1]:02d}",
            )
            rows = [
                r
                for r in rows
                if r["installed_at"] <= last_day
                and (r.get("removed_at") is None or r["removed_at"] >= first_day)
            ]
        keys = {
            "invoices": (
                "invoice_id",
                "competencia",
                "billed_amount",
                "paid_amount",
                "billed_energy_kwh",
                "due_date",
                "payment_date",
                "payment_status",
            ),
            "meters": ("meter_id", "installed_at", "removed_at"),
            "distributed_generation": ("capacity_kw", "status"),
            "interruptions": ("event_id", "feeder_id", "competencia", "duration_hours"),
            "calls": ("call_id", "opened_at", "category"),
        }[section]
        rows = [{k: r.get(k) for k in keys} for r in rows]
        if section == "invoices":
            for row in rows:
                month = row["competencia"]
                for measure, covered_months in covered_months_by_measure.items():
                    if month not in covered_months:
                        row[measure] = None
        if monthly:
            if section == "invoices":
                missing_measures = [
                    measure
                    for measure in invoice_measure_coverage
                    if any(row[measure] is None for row in rows)
                ]
                status = (
                    "unavailable"
                    if not months
                    else (
                        "partial"
                        if not full or missing_measures
                        else ("available" if rows else "empty")
                    )
                )
                limitations = [
                    f"Cobertura de {measure} desconhecida ou incompleta para a janela."
                    for measure, (_, measure_full) in invoice_measure_coverage.items()
                    if not measure_full
                ]
                limitations.extend(
                    f"Há faturas sem valor de {measure}; histórico incompleto."
                    for measure in missing_measures
                )
            else:
                status = (
                    "unavailable"
                    if not months
                    else ("partial" if not full else ("available" if rows else "empty"))
                )
                limitations = (
                    []
                    if full
                    else [
                        f"Cobertura de {section} desconhecida ou incompleta para a janela."
                    ]
                )
        else:
            status = (
                "unavailable"
                if not snapshot_known
                else ("available" if rows else "empty")
            )
            limitations = (
                [] if snapshot_known else [f"Cobertura de {section} desconhecida."]
            )
            if not snapshot_known:
                rows = []
            if section == "distributed_generation" and snapshot_known:
                limitations.append(
                    "Cadastro no snapshot; capacidade em kW não representa energia compensada."
                )
    tie = {
        "consumption": "competencia",
        "invoices": "invoice_id",
        "meters": "meter_id",
        "distributed_generation": "capacity_kw",
        "interruptions": "event_id",
        "calls": "call_id",
    }[section]
    rows.sort(
        key=lambda r: (r.get(order_by) is None, r.get(order_by), r.get(tie)),
        reverse=True,
    )
    total = len(rows)
    selected = rows[(page - 1) * page_size : page * page_size]
    return {
        "data": {"items": selected},
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
        "status": status,
        "period": {"start": start, "end": end, "granularity": "month"},
        "limitations": limitations,
    }
