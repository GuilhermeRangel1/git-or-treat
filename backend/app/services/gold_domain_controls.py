"""Controles internos da publicação: nenhuma medida ou identificador sai do Backend."""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext

from sqlalchemy import and_, case, func, or_, select

from app.models.gold_v2_load import TABLES

ANALYTICAL_CONTROLS = frozenset(
    {"C01", "C02", "C03", "C04", "C10", "C11", "C12", "C13"}
)


def _number(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def _dimension(value):
    return value if value else "Não informado"


def _add(bucket, value):
    if value is not None:
        bucket[0] += value
        bucket[1] += 1


def _totals(rows, fields, dimensions):
    result = defaultdict(lambda: [[Decimal(0), 0] for _ in fields])
    valid = True
    for row in rows:
        key = tuple(_dimension(row.get(name)) for name in dimensions)
        for target, field in zip(result[key], fields):
            raw = row.get(field)
            value = _number(raw)
            valid &= raw is None or value is not None
            _add(target, value)
    return result, valid


def _match(left, right, tolerances):
    if not left or set(left) != set(right):
        return False
    for key, values in left.items():
        for (total, count), (other, other_count), tolerance in zip(
            values, right[key], tolerances
        ):
            if bool(count) != bool(other_count) or abs(total - other) > tolerance:
                return False
    return True


def observe_domain_controls(
    connection, *, read_rows, requested_periods, origin, batch_ref
):
    """Chamado dentro do snapshot e prazo existentes; devolve apenas resultados técnicos."""
    with localcontext() as context:
        context.prec = 60
        return _observe(connection, read_rows, requested_periods, origin, batch_ref)


def _observe(connection, read_rows, periods, origin, batch_ref):
    population = {r["id_uc"]: r for r in read_rows(TABLES["visao_360_uc"])}
    monthly = _monthly_groups(read_rows)
    diag = list(read_rows(TABLES["diagnostico_receita"]))
    bairro = list(read_rows(TABLES["consumo_receita_bairro"]))
    enriched = monthly
    fields = ("consumo_kwh", "receita_reais")
    aggregates = ("consumo_total_kwh", "receita_total_reais")
    passed = {}
    for control, dimensions in (
        ("C01", ("competencia",)),
        ("C02", ("competencia", "classe_consumo")),
        ("C04", ("competencia", "municipio")),
    ):
        left, valid_left = _totals(enriched, fields, dimensions)
        right, valid_right = _totals(diag, aggregates, dimensions)
        passed[control] = (
            valid_left
            and valid_right
            and _match(left, right, (Decimal("0.01"), Decimal("0.01")))
        )
        passed[control] &= any(r["consumo_kwh"] is not None for r in monthly)
        passed[control] &= any(r["receita_reais"] is not None for r in monthly)
    passed["C03"] = bool(monthly) and all(r["invalid_rows"] == 0 for r in monthly)
    for control in ("C01", "C02", "C04"):
        passed[control] &= passed["C03"]
    # C10 documenta a população de nulos; não compara média por leitura com média mensal.
    passed["C10"] = (
        bool(population)
        and all(
            row["media_consumo_historico"] is None
            or _number(row["media_consumo_historico"]) is not None
            for row in population.values()
        )
        and all(
            row["consumo_kwh"] is None or _number(row["consumo_kwh"]) is not None
            for row in monthly
        )
    )
    left, lv = _totals(
        bairro, (*aggregates, "qtd_ucs_distintas_faturadas_no_mes"), ("competencia",)
    )
    right, rv = _totals(
        diag, (*aggregates, "qtd_ucs_distintas_faturadas_no_mes"), ("competencia",)
    )
    passed["C12"] = (
        passed["C01"]
        and lv
        and rv
        and _match(left, right, (Decimal("0.01"), Decimal("0.01"), Decimal(0)))
    )
    names = {(r["municipio"], r["bairro"]) for r in bairro}
    normalized = {(_normalize_name(m), _normalize_name(b)) for m, b in names}
    passed["C13"] = bool(bairro) and len(names) == len(normalized)
    counts = {"faturamento": Counter(), "consumo": Counter(), "ocorrencias": Counter()}
    for row in monthly:
        for domain, column in (
            ("faturamento", "qtd_faturas"),
            ("consumo", "qtd_leituras_observadas"),
        ):
            value = row[column]
            if value is not None and value >= 0:
                counts[domain][row["competencia"]] += value
    passed["C11"], counts["ocorrencias"], undated_events, feeders = _continuity(
        connection, read_rows, population
    )
    coverage = {}
    for capability, domain in (
        ("faturamento.receita", "faturamento"),
        ("faturamento.receita_bairro", "faturamento"),
        ("consumo.mensal_uc", "consumo"),
    ):
        coverage[capability] = _coverage(
            read_rows, domain, counts[domain], periods, origin, batch_ref
        )
        measure = "receita_reais" if domain == "faturamento" else "consumo_kwh"
        usable = {
            row["competencia"] for row in monthly if _number(row[measure]) is not None
        }
        coverage[capability]["observed_periods"] = sorted(
            set(coverage[capability]["observed_periods"]) & usable
        )

    coverage["interrupcoes.dec_fec"] = _coverage(
        read_rows, "ocorrencias", counts["ocorrencias"], periods, origin, batch_ref
    )
    coverage["interrupcoes.dec_fec"]["has_undated_records"] |= undated_events
    global_coverage = coverage["interrupcoes.dec_fec"]
    for feeder, feeder_counts in feeders.items():
        part = _coverage(
            read_rows,
            "ocorrencias",
            feeder_counts,
            periods,
            origin,
            batch_ref,
            recorte="ALIMENTADOR:" + feeder,
        )
        global_coverage["closed_periods"] = sorted(
            set(global_coverage["closed_periods"]) & set(part["closed_periods"])
        )
        global_coverage["zero_confirmed_periods"] = sorted(
            set(global_coverage["zero_confirmed_periods"])
            & set(part["zero_confirmed_periods"])
        )
        global_coverage["has_undated_records"] |= part["has_undated_records"]
    return passed, coverage


def _coverage(
    read_rows, domain, counts, periods, origin, batch_ref, *, recorte="DOMINIO"
):
    closed, zeros = set(), set()
    undated = False
    for row in read_rows(TABLES["cobertura_dominios"]):
        if row["dominio"] != domain or row["recorte"] != recorte:
            continue
        missing = row["qtd_sem_competencia"]
        undated |= missing is None or missing != 0
        month = row["competencia"]
        cut = row["data_corte_evidencia"]
        cut = (
            (cut.replace(tzinfo=UTC) if cut.tzinfo is None else cut.astimezone(UTC))
            if cut
            else None
        )
        if (
            row["estado_cobertura"] == "FECHADO"
            and missing == 0
            and row["qtd_registros"] == counts[month]
            and row["zero_registros_confirmado"] == (counts[month] == 0)
            and row["run_id_silver"] == origin["run_id_silver"]
            and row["lote_bronze_silver"] == origin["lote_bronze_silver"]
            and row["referencia_evidencia"]
            and cut is not None
            and cut <= datetime.now(UTC)
            and cut.strftime("%Y-%m") > month
            and _certification_valid(row)
        ):
            closed.add(month)
            if counts[month] == 0:
                zeros.add(month)
    return {
        "batch_ref": batch_ref,
        "requested_periods": list(periods),
        "observed_periods": sorted(m for m, c in counts.items() if c),
        "closed_periods": sorted(closed),
        "zero_confirmed_periods": sorted(zeros),
        "has_undated_records": undated,
    }


def _continuity(connection, read_rows, population):
    denominators = Counter(
        r["alimentador"] for r in population.values() if r["alimentador"]
    )
    table, cadastro = TABLES["ocorrencias_uc"], TABLES["visao_360_uc"]
    c = table.c
    month = (
        func.to_char(func.timezone("UTC", c.data_abertura), "YYYY-MM")
        if connection.dialect.name == "postgresql"
        else func.strftime("%Y-%m", c.data_abertura)
    )
    bad = or_(
        c.duracao_min.is_(None),
        c.duracao_min < 0,
        c.alimentador.is_(None),
        cadastro.c.id_uc.is_(None),
        c.alimentador != cadastro.c.alimentador,
        cadastro.c.alimentador.is_(None),
        c.flag_duracao_incompativel.is_not(False),
        c.flag_abertura_futura.is_not(False),
        c.flag_encerramento_futuro.is_not(False),
    )
    query = (
        select(
            c.alimentador,
            month.label("competencia"),
            func.count().label("frequency"),
            func.sum(c.duracao_min).label("minutes"),
            func.count(c.id_uc.distinct()).label("ucs"),
            func.sum(case((bad, 1), else_=0)).label("invalid_rows"),
        )
        .select_from(table.outerjoin(cadastro, c.id_uc == cadastro.c.id_uc))
        .group_by(c.alimentador, month)
    )
    events = {}
    counts = Counter()
    valid = True
    undated = False
    for row in read_rows(query):
        if row["competencia"] is None:
            undated = True
            valid = False
            continue
        minutes = _number(row["minutes"])
        valid &= row["invalid_rows"] == 0 and minutes is not None
        events[(row["alimentador"], row["competencia"])] = (
            row["frequency"],
            minutes / 60 if minutes is not None else None,
            row["ucs"],
        )
        counts[row["competencia"]] += row["frequency"]
    rows = list(read_rows(TABLES["indicadores_dec_fec"]))
    seen = set()
    for row in rows:
        feeder, month = row["id_alimentador"], row["competencia"]
        seen.add((feeder, month))
        frequency, hours, ucs = events.get((feeder, month), (0, Decimal(0), 0))
        denominator = _number(row["total_ucs_alimentador"])
        dec, fec = _number(row["DEC"]), _number(row["FEC"])
        published_hours = _number(row["duracao_total_interrupcoes_horas"])
        if (
            denominator is None
            or denominator <= 0
            or denominator != denominators[feeder]
            or row["frequencia_total_interrupcoes"] != frequency
            or row["ucs_interrompidas"] != ucs
            or hours is None
            or published_hours is None
            or abs(published_hours - hours) > Decimal("0.0001")
            or dec is None
            or fec is None
        ) or abs(dec - hours / denominator) > Decimal("0.0001") or abs(
            fec - frequency / denominator
        ) > Decimal("0.0001"):
            valid = False
    valid &= bool(rows) and not (events.keys() - seen)
    feeders = defaultdict(Counter)
    for (feeder, month), (frequency, _, _) in events.items():
        if feeder:
            feeders[feeder][month] = frequency
    for feeder in denominators:
        feeders[feeder]
    return bool(valid), counts, undated, feeders


def _monthly_groups(read_rows):
    table, cadastro = TABLES["consumo_mensal_uc"], TABLES["visao_360_uc"]
    c = table.c
    municipio = func.coalesce(func.nullif(cadastro.c.municipio, ""), "Não informado")
    classe = func.coalesce(func.nullif(cadastro.c.classe, ""), "Não informado")
    invalid = or_(
        c.tem_fatura.is_(None),
        c.tem_leitura.is_(None),
        and_(c.tem_fatura.is_(False), c.tem_leitura.is_(False)),
        c.qtd_faturas.is_(None),
        c.qtd_leituras_observadas.is_(None),
        c.qtd_faturas < 0,
        c.qtd_leituras_observadas < 0,
        c.tem_fatura != (c.qtd_faturas > 0),
        c.tem_leitura != (c.qtd_leituras_observadas > 0),
    )
    query = (
        select(
            c.competencia,
            municipio.label("municipio"),
            classe.label("classe_consumo"),
            func.sum(c.consumo_kwh).label("consumo_kwh"),
            func.sum(c.receita_reais).label("receita_reais"),
            func.sum(c.qtd_faturas).label("qtd_faturas"),
            func.sum(c.qtd_leituras_observadas).label("qtd_leituras_observadas"),
            func.sum(case((invalid, 1), else_=0)).label("invalid_rows"),
        )
        .select_from(table.outerjoin(cadastro, c.id_uc == cadastro.c.id_uc))
        .group_by(c.competencia, municipio, classe)
    )
    return list(read_rows(query))


def _certification_valid(row):
    raw = row["reconciliacao_extracao_json"]
    if row["natureza_certificacao"] == "FECHAMENTO_CONTABIL":
        return raw is None
    if (
        row["natureza_certificacao"] != "EXTRACAO"
        or row["recorte"] != "DOMINIO"
        or not raw
        or len(raw) > 65536
    ):
        return False

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Chave de reconciliação repetida.")
            result[key] = value
        return result

    try:
        values = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError, RecursionError):
        return False
    required = {
        "registros_origem",
        "registros_aceitos",
        "registros_excluidos",
        "hash_inventario",
    }
    if (
        not isinstance(values, dict)
        or not required <= values.keys()
        or values.keys() - required - {"registros_quarentena"}
    ):
        return False
    counts = [
        values.get(k, 0)
        for k in (
            "registros_origem",
            "registros_aceitos",
            "registros_excluidos",
            "registros_quarentena",
        )
    ]
    if any(type(v) is not int or v < 0 for v in counts):
        return False
    source, accepted, excluded, quarantine = counts
    digest = values["hash_inventario"]
    return (
        excluded == 0
        and source == accepted + excluded + quarantine
        and isinstance(digest, str)
        and re.fullmatch("[0-9a-f]{64}", digest) is not None
    )


def _normalize_name(value):
    try:
        value = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )
    return " ".join(value.upper().split())
