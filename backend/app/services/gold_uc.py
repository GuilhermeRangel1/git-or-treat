"""UC Gold: agregado mensal e cadastro observado; detalhes ausentes explícitos."""
from sqlalchemy import select
from decimal import Decimal

from app.models.gold_load import TABLES
from app.services.analytics import AnalyticsAPIError

ABSENT = "Detalhe não fornecido nos CSVs Gold desta versão; ausência não equivale a zero."


def profile(row):
    return {"uc_id": row["id_uc"], "customer_reference": None, "customer_name": None,
            **{key: row[key] or "Não informado" for key in ("municipio", "bairro", "classe", "alimentador", "status")}}


def period(repository, start, end):
    from app.services.uc_analytics import validate_period
    if start is None and end is None:
        months = repository.options()["competencias"]
        if not months:
            raise AnalyticsAPIError(503, "source_unavailable", "Gold sem competências observadas.")
        start, end = months[max(0, len(months) - 12)], months[-1]
    return validate_period(start, end)


def search(repository, q, page, page_size, order_by):
    from app.services.uc_analytics import validate_uc_id
    uc = TABLES["visao_360_uc"]
    if order_by not in {"uc_id", "municipio", "bairro", "classe", "alimentador", "status"}:
        raise AnalyticsAPIError(422, "invalid_query", "Ordenação inválida.")
    statement = select(uc)
    if q is not None:
        statement = statement.where(uc.c.id_uc.ilike(f"%{validate_uc_id(q)}%"))
    sort = uc.c.id_uc if order_by == "uc_id" else uc.c[order_by]
    rows, pagination = repository.page(statement, page, page_size, sort.asc(), uc.c.id_uc.asc())
    items = [{key: value for key, value in profile(row).items() if key not in {"customer_name", "customer_reference"}} for row in rows]
    return items, pagination, "available" if pagination["total"] else "empty"


def overview(repository, uc_id, start, end):
    from app.services.uc_analytics import _measure_change
    start, end = period(repository, start, end)
    row = repository.unit(uc_id)
    monthly = TABLES["consumo_mensal_uc"]
    rows = repository.rows(select(monthly).where(monthly.c.id_uc == row["id_uc"], monthly.c.competencia.in_([start, end])))
    snapshots = {}
    for name, month in (("initial", start), ("final", end)):
        point = next((r for r in rows if r["competencia"] == month), None)
        measures = {}
        for field, column in (("measured_energy_kwh", "consumo_kwh"), ("billed_amount", "receita_reais"), ("billed_energy_kwh", None), ("paid_amount", None)):
            value = point[column] if point is not None and column else None
            measures[field] = {"value": Decimal(str(value)) if value is not None else None, "status": "available" if value is not None else "unavailable",
                               "limitations": [] if value is not None else [ABSENT]}
        snapshots[name] = {"competencia": month, **measures}
    comparison = {**snapshots, **{key: _measure_change(snapshots["initial"][key], snapshots["final"][key], key.endswith("amount")) for key in ("measured_energy_kwh", "billed_energy_kwh", "billed_amount", "paid_amount")}}
    return {"data": {"profile": profile(row), "period": {"start": start, "end": end, "granularity": "month"},
                     "comparison": comparison, "open_invoices": {"count": None, "status": "unavailable", "limitations": [ABSENT]},
                     "current_meter": {"item": None, "status": "unavailable", "limitations": [ABSENT]},
                     "distributed_generation": {"items": [], "status": "unavailable", "limitations": [ABSENT, f"Indicador cadastral de GD: {row['possui_gd'] or 'não informado'}; sem potência ou histórico."]},
                     "section_status": {name: "partial" if name == "consumption" else "unavailable" for name in ("consumption", "invoices", "meters", "distributed_generation", "interruptions", "calls")}},
            "status": "partial", "limitations": [ABSENT, "Consumo e receita mensais são agregados publicados; não são faturas individuais."]}


def history(repository, uc_id, section, start, end, page, page_size, order_by):
    from app.services.uc_analytics import HISTORY_ORDER
    start, end = period(repository, start, end)
    row = repository.unit(uc_id)
    if section not in HISTORY_ORDER or (order_by is not None and order_by not in HISTORY_ORDER[section]):
        raise AnalyticsAPIError(422, "invalid_query", "Seção ou ordenação inválida.")
    items, pagination = [], {"page": page, "page_size": page_size, "total": 0, "total_pages": 0}
    if section == "consumption":
        monthly = TABLES["consumo_mensal_uc"]
        sort = monthly.c.consumo_kwh if order_by == "measured_energy_kwh" else monthly.c.competencia
        rows, pagination = repository.page(select(monthly).where(monthly.c.id_uc == row["id_uc"], monthly.c.competencia.between(start, end)), page, page_size, sort.desc().nulls_last(), monthly.c.competencia.desc())
        items = [{"competencia": point["competencia"], "measured_energy_kwh": point["consumo_kwh"],
                  "billed_amount": point["receita_reais"], "status": "available" if point["consumo_kwh"] is not None else "unavailable"} for point in rows]
    return {"data": {"items": items}, "pagination": pagination, "status": "partial" if items else "unavailable",
            "period": {"start": start, "end": end, "granularity": "month"}, "limitations": [ABSENT] if section != "consumption" else ["Histórico mensal agregado da Gold; competências sem registro não são zero conhecido."]}
