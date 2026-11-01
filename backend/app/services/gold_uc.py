"""UC Gold: agregado mensal e cadastro observado; detalhes ausentes explícitos."""
from sqlalchemy import case, select
from datetime import datetime, timezone
from decimal import Decimal

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
    uc = repository.tables["visao_360_uc"]
    if order_by not in {"uc_id", "municipio", "bairro", "classe", "alimentador", "status"}:
        raise AnalyticsAPIError(422, "invalid_query", "Ordenação inválida.")
    statement = select(uc)
    if q is not None:
        statement = statement.where(uc.c.id_uc.ilike(f"%{validate_uc_id(q)}%"))
    sort = uc.c.id_uc if order_by == "uc_id" else uc.c[order_by]
    rows, pagination = repository.page(statement, page, page_size, sort.asc(), uc.c.id_uc.asc())
    items = [{key: value for key, value in profile(row).items() if key not in {"customer_name", "customer_reference"}} for row in rows]
    return items, pagination, "available" if pagination["total"] else "empty"


def meter_at_reference(rows):
    """Seleção indicativa no instante da Gold, sem presumir histórico completo."""
    unavailable = {"item": None, "status": "unavailable", "limitations": ["Dados insuficientes para identificar o medidor na data de referência da Gold."]}
    if not rows or any(row["ingestao_data"] is None for row in rows):
        return unavailable
    dates = {row["ingestao_data"].date() for row in rows}
    if len(dates) != 1:
        return unavailable
    reference = dates.pop()
    candidates = []
    for row in rows:
        installed, removed = row["data_instalacao"], row["data_retirada"]
        if removed is not None and removed < reference:
            continue
        if installed is not None and installed > reference:
            continue
        if (installed is None or removed == reference or
                row["flag_instalacao_sentinela"] or row["flag_instalacao_futura"] or
                row["flag_retirada_sentinela"] or row["flag_retirada_futura"]):
            return unavailable
        candidates.append(row)
    if len(candidates) != 1:
        return unavailable
    row = candidates[0]
    return {"item": {"meter_id": row["id_medidor"], "installed_at": row["data_instalacao"].isoformat(),
                     "removed_at": row["data_retirada"].isoformat() if row["data_retirada"] else None},
            "status": "partial", "limitations": [f"Medidor indicado pelas datas na referência Gold de {reference.isoformat()}; ausência de retirada não comprova atividade e o histórico pode estar incompleto."]}


def overview(repository, uc_id, start, end):
    from app.services.uc_analytics import _measure_change
    start, end = period(repository, start, end)
    row = repository.unit(uc_id)
    monthly = repository.tables["consumo_mensal_uc"]
    rows = repository.rows(select(monthly).where(monthly.c.id_uc == row["id_uc"], monthly.c.competencia.in_([start, end])))
    snapshots = {}
    for name, month in (("initial", start), ("final", end)):
        point = next((r for r in rows if r["competencia"] == month), None)
        measures = {}
        for field, column in (("measured_energy_kwh", "consumo_kwh"), ("billed_amount", "receita_reais"), ("billed_energy_kwh", None), ("paid_amount", None)):
            value = point[column] if point is not None and column else None
            is_v2 = repository.schema_version == "gold-csv-v2"
            incomplete = is_v2 and field == "measured_energy_kwh" and point is not None and point["qtd_leituras_observadas"] is not None and point["qtd_leituras_validas"] is not None and point["qtd_leituras_validas"] < point["qtd_leituras_observadas"]
            measures[field] = {"value": Decimal(str(value)) if value is not None else None, "status": ("partial" if is_v2 else "available") if value is not None else "unavailable",
                               "limitations": (["Valor observado parcial: há leituras inválidas ou cobertura individual não certificada."] if incomplete else ["Valor observado; cobertura individual da competência não certificada."] if is_v2 and value is not None else [] if value is not None else [ABSENT])}
        snapshots[name] = {"competencia": month, **measures}
    comparison = {**snapshots, **{key: _measure_change(snapshots["initial"][key], snapshots["final"][key], key.endswith("amount")) for key in ("measured_energy_kwh", "billed_energy_kwh", "billed_amount", "paid_amount")}}
    is_v2 = repository.schema_version == "gold-csv-v2"
    generation = None
    current_meter = {"item": None, "status": "unavailable", "limitations": [ABSENT]}
    if is_v2:
        meters = repository.tables["medidor_uc"]
        current_meter = meter_at_reference(repository.rows(select(meters).where(meters.c.id_uc == row["id_uc"])))
        table = repository.tables["gd_uc"]
        gd_rows = repository.rows(select(table).where(table.c.id_uc == row["id_uc"]))
        if gd_rows:
            gd = gd_rows[0]
            generation = {"capacity_kwp": gd["potencia_kwp"], "connection_date": gd["data_conexao"].isoformat() if gd["data_conexao"] else None, "modality": gd["modalidade"]}
    return {"data": {"profile": profile(row), "period": {"start": start, "end": end, "granularity": "month"},
                     "comparison": comparison, "open_invoices": {"count": None, "status": "unavailable", "limitations": [ABSENT]},
                     "current_meter": current_meter,
                     "distributed_generation": {"items": [], "status": "unavailable", "limitations": ([f"Indicador cadastral de GD: {row['possui_gd'] or 'não informado'}; a potência em kWp aparece separadamente como cadastro observado."] if is_v2 else [ABSENT, f"Indicador cadastral de GD: {row['possui_gd'] or 'não informado'}; sem potência ou histórico."])},
                     "gold_generation": generation,
                     "section_status": {name: "partial" if name == "consumption" or (is_v2 and name in {"invoices", "meters", "interruptions", "calls"}) else "unavailable" for name in ("consumption", "invoices", "meters", "distributed_generation", "interruptions", "calls")}},
            "status": "partial", "limitations": (["Consumo e receita mensais são agregados publicados; não são faturas individuais.",
                "Nome do titular, pagamento efetivo e energia faturada não estão disponíveis no pacote analítico.",
                "Históricos são observados, sem certificar ausência de registros ou vigência cadastral.",
                "GD em kWp não é energia gerada nem potência em kW; apresentação detalhada ainda não integrada."] if is_v2 else [ABSENT,
                "Consumo e receita mensais são agregados publicados; não são faturas individuais.",
                "Cliente/titular, pagamentos, medidores e históricos individuais de faturas, chamados e interrupções não foram exportados.",
                "GD é um indicador cadastral; potência, geração e compensação mensal não são fornecidas."])}


def history(repository, uc_id, section, start, end, page, page_size, order_by):
    from app.services.uc_analytics import HISTORY_ORDER
    start, end = period(repository, start, end)
    row = repository.unit(uc_id)
    if section not in HISTORY_ORDER or (order_by is not None and order_by not in HISTORY_ORDER[section]):
        raise AnalyticsAPIError(422, "invalid_query", "Seção ou ordenação inválida.")
    items, pagination = [], {"page": page, "page_size": page_size, "total": 0, "total_pages": 0}
    if section == "consumption":
        monthly = repository.tables["consumo_mensal_uc"]
        sort = monthly.c.consumo_kwh if order_by == "measured_energy_kwh" else monthly.c.competencia
        if order_by == "measured_energy_kwh" and repository.schema_version == "gold-csv-v2":
            sort = case((monthly.c.qtd_leituras_validas < monthly.c.qtd_leituras_observadas, None), else_=monthly.c.consumo_kwh)
        rows, pagination = repository.page(select(monthly).where(monthly.c.id_uc == row["id_uc"], monthly.c.competencia.between(start, end)), page, page_size, sort.desc().nulls_last(), monthly.c.competencia.desc())
        items = []
        for point in rows:
            incomplete = repository.schema_version == "gold-csv-v2" and point["qtd_leituras_observadas"] is not None and point["qtd_leituras_validas"] is not None and point["qtd_leituras_validas"] < point["qtd_leituras_observadas"]
            value = None if incomplete else point["consumo_kwh"]
            items.append({"competencia": point["competencia"], "measured_energy_kwh": value,
                          "billed_amount": point["receita_reais"], "status": "partial" if incomplete else "available" if value is not None else "unavailable"})
    elif repository.schema_version == "gold-csv-v2" and section in {"invoices", "meters", "interruptions", "calls"}:
        items, pagination = history_v2(repository, row["id_uc"], section, start, end, page, page_size, order_by)
    notes = (["Histórico mensal agregado da Gold; competências sem registro não são zero conhecido; leituras inválidas tornam o consumo indisponível."] if section == "consumption" else
             ["Registros observados na Gold; ausência de registros não comprova cobertura completa.",
              "Datas ausentes não podem ser atribuídas ao período selecionado." if section in {"calls", "interruptions"} else
              "O período não filtra vínculos de medidores; datas ausentes permanecem indisponíveis." if section == "meters" else
              "Situação declarada e valor nominal em aberto vêm da fonte; não comprovam pagamento nem saldo contábil."]
             if repository.schema_version == "gold-csv-v2" and section in {"invoices", "meters", "interruptions", "calls"} else [ABSENT])
    return {"data": {"items": items}, "pagination": pagination, "status": "partial" if pagination["total"] else "unavailable",
            "period": {"start": start, "end": end, "granularity": "month"}, "limitations": notes}


def history_v2(repository, uc_id, section, start, end, page, page_size, order_by):
    tables = repository.tables
    if section == "invoices":
        if order_by == "payment_date":
            raise AnalyticsAPIError(422, "invalid_query", "Ordenação por pagamento indisponível nesta projeção.")
        t = tables["faturas_uc"]
        columns = {"competencia": t.c.mes_referencia, "invoice_id": t.c.id_fatura, "billed_amount": t.c.valor_total,
                   "due_date": t.c.data_vencimento, "payment_date": t.c.data_pagamento}
        stmt = select(t).where(t.c.id_uc == uc_id, t.c.mes_referencia.between(start, end))
        sort = columns[order_by or "competencia"]
        rows, pagination = repository.page(stmt, page, page_size, sort.desc().nulls_last(), t.c.id_fatura.asc())
        return [{"invoice_id": r["id_fatura"], "competencia": r["mes_referencia"], "billed_amount": r["valor_total"],
                 "paid_amount": None, "billed_energy_kwh": None, "due_date": r["data_vencimento"].isoformat() if r["data_vencimento"] else None,
                 "payment_date": None, "payment_status": "unknown", "currency_unit": "BRL",
                 "declared_status": r["status"], "declared_open_amount": r["valor_fatura_declarada_em_aberto_reais"]} for r in rows], pagination
    if section == "meters":
        t = tables["medidor_uc"]
        columns = {"installed_at": t.c.data_instalacao, "removed_at": t.c.data_retirada, "meter_id": t.c.id_medidor}
        rows, pagination = repository.page(select(t).where(t.c.id_uc == uc_id), page, page_size,
                                           columns[order_by or "installed_at"].desc().nulls_last(), t.c.id_medidor.asc())
        return [{"meter_id": r["id_medidor"], "installed_at": r["data_instalacao"].isoformat() if r["data_instalacao"] else None,
                 "removed_at": r["data_retirada"].isoformat() if r["data_retirada"] else None} for r in rows], pagination
    first = datetime(int(start[:4]), int(start[5:]), 1, tzinfo=timezone.utc)
    year, month = int(end[:4]), int(end[5:])
    last = None if (year, month) == (9999, 12) else datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    t = tables["ocorrencias_uc" if section == "interruptions" else "atendimentos_uc"]
    opened = t.c.data_abertura
    if section == "interruptions":
        columns = {"competencia": opened, "event_id": t.c.id_ocorrencia, "duration_hours": t.c.duracao_min}
        identifier = t.c.id_ocorrencia
    else:
        columns = {"opened_at": opened, "call_id": t.c.protocolo, "category": t.c.assunto}
        identifier = t.c.protocolo
    conditions = [t.c.id_uc == uc_id, opened >= first]
    if last is not None:
        conditions.append(opened < last)
    rows, pagination = repository.page(select(t).where(*conditions), page, page_size,
                                       columns[order_by or ("competencia" if section == "interruptions" else "opened_at")].desc().nulls_last(), identifier.asc())
    if section == "interruptions":
        return [{"event_id": r["id_ocorrencia"], "feeder_id": r["alimentador"] or "Não informado", "competencia": r["data_abertura"].strftime("%Y-%m"),
                 "duration_hours": r["duracao_min"] / 60 if r["duracao_min"] is not None else None} for r in rows], pagination
    return [{"call_id": r["protocolo"], "opened_at": r["data_abertura"].isoformat(), "category": r["assunto"] or "Não informado"} for r in rows], pagination
