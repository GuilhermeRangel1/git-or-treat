"""Read the checked local price-volume staging file and independent Gold totals."""

import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.models.gold_v2 import TABLES
from app.repositories.gold_publication import publication_lineage
from app.schemas.genai_evidence import PublishedWindows
from app.schemas.sql_analysis import (
    ObservedComparisonWindows,
    SqlFinancialComparison,
    SqlFinancialComparisonRow,
    SqlFeederOccurrences,
    SqlPublishedDecomposition,
    SqlServiceSummary,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_compound import (
    CompoundEvidenceUnavailable,
    ConsumptionTotals,
    EvidenceScope,
    RevenueEffect,
    compose_consumption_revenue,
)
from app.services.gold_price_volume import (
    decomposition_query,
    decomposition_records,
)

EXPECTED_WINDOWS = {
    "inicio_p0": "2024-07",
    "fim_p0": "2025-06",
    "inicio_p1": "2025-07",
    "fim_p1": "2026-06",
}
EXPECTED_METHOD = "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3"
REQUIRED_COLUMNS = {
    "municipio", "bairro", "classe_consumo", "variacao_faturamento_total_reais",
    "efeito_volume_reais", "efeito_preco_observado_reais", "efeito_interacao_reais",
    "estado_decomposicao", "inicio_p0", "fim_p0", "inicio_p1", "fim_p1", "metodo",
}
MAX_MANIFEST_BYTES = 64 * 1024
MAX_CSV_BYTES = 8 * 1024 * 1024
MONTH_NUMBER = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

PUBLISHED_PRICE_WINDOWS = PublishedWindows(
    p0_start="2022-07", p0_end="2023-06",
    p1_start="2025-07", p1_end="2026-06", method=EXPECTED_METHOD,
)


def published_decomposition_scope(question: str) -> tuple[str, str | None] | None:
    match = re.fullmatch(
        r"(?:como se decompoe a variacao de receita por preco e volume em (?P<city>[a-z ]+), |"
        r"para a classe (?P<class>[a-z ]+) de (?P<class_city>[a-z ]+), "
        r"qual foi a decomposicao preco-volume entre )"
        r"jul/2022[–-]jun/2023 (?:contra|e) jul/2025[–-]jun/2026[?.]?",
        _normalize_question(question),
    )
    return (match["city"] or match["class_city"], match["class"]) if match else None


def query_published_decomposition(engine, publication, scope_filter):
    city, consumption_class = scope_filter
    c = TABLES["decomposicao_receita"].c
    windows = PUBLISHED_PRICE_WINDOWS
    where = (
        c.inicio_p0 == windows.p0_start, c.fim_p0 == windows.p0_end,
        c.inicio_p1 == windows.p1_start, c.fim_p1 == windows.p1_end,
        c.metodo == windows.method,
    )
    dimensions = {"geography.municipality"}
    if consumption_class:
        dimensions.add("customer.consumption_class")
    with publication.execution_snapshot(
        engine, validate_f1_catalog=True, dimension_ids=frozenset(dimensions),
        metric_ids=frozenset({"billing.price_volume"}),
    ) as connection:
        connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
        pairs = connection.execute(select(c.municipio, c.classe_consumo).where(*where).distinct()).all()
        municipalities = {m for m, _ in pairs if _normalize_question(m) == city}
        if len(municipalities) != 1:
            raise CompoundEvidenceUnavailable("Município ausente na decomposição publicada.")
        municipality = next(iter(municipalities))
        filters = [SimpleNamespace(dimension_id="geography.municipality", values=[municipality])]
        criteria = [c.municipio == municipality]
        if consumption_class:
            classes = {k for m, k in pairs if m == municipality and _normalize_question(k) == consumption_class}
            if len(classes) != 1:
                raise CompoundEvidenceUnavailable("Classe ausente na decomposição publicada.")
            value = next(iter(classes))
            filters.append(SimpleNamespace(dimension_id="customer.consumption_class", values=[value]))
            criteria.append(c.classe_consumo == value)
        plan = SimpleNamespace(filters=filters, window=SimpleNamespace(phrase="Janelas publicadas"))
        rows = connection.execute(decomposition_query(plan).where(
            *where, c.estado_decomposicao == "CALCULADA_BASE_COMUM",
        )).mappings().all()
        excluded = connection.scalar(select(func.count()).where(
            *where, *criteria, c.estado_decomposicao == "SEM_BASE_COMUM",
        ))
        try:
            records, published = decomposition_records(
                rows, plan, publication_lineage(connection, publication.batch_ref),
            )
        except ValueError as exc:
            raise CompoundEvidenceUnavailable(str(exc)) from exc
    answer = f"Decomposição da receita em {municipality}"
    if consumption_class:
        answer += f", classe {value}"
    answer += " (jul/2022–jun/2023 versus jul/2025–jun/2026)."
    if excluded:
        answer += f" Os componentes abrangem a base comum. {excluded} grupos ficaram fora por falta de base comparável."
    data = {
        "active_gold_batch": publication.batch_ref, "answer": answer,
        "windows": published.model_dump(mode="json"),
        "groups_without_base": excluded,
        "records": tuple((r["label"], r["unit"], str(r["value"])) for r in records),
    }
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return SqlPublishedDecomposition(**data, evidence_digest=digest)


def annual_class_comparison_scope(question: str) -> str | None:
    """Recognize an annual class comparison and retain its optional municipality."""
    match = re.fullmatch(
        r"compare (?:a variacao d[ao] )?"
        r"(?:consumo e receita(?: faturada)?|receita(?: faturada)? e (?:(?:o|do) )?consumo)"
        r" por classe(?: de consumo)?(?: (?:de|em) (?P<city>[a-z ]+))?"
        r" entre jul/2024[–-]jun/2025 e jul/2025[–-]jun/2026[?.]?",
        _normalize_question(question),
    )
    return (match.group("city") or "") if match else None


MONTHS = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def feeder_occurrence_scope(question: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        rf"quantas ocorrencias distintas houve no alimentador (?P<feeder>[a-z0-9-]+) "
        rf"em (?P<month>{'|'.join(MONTHS)}) de (?P<year>20[0-9]{{2}})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return None
    return match["feeder"].upper(), f"{match['year']}-{MONTHS.index(match['month']) + 1:02d}"


def query_feeder_occurrences(engine, publication, feeder, month):
    table = TABLES["ocorrencias_uc"]
    start = datetime.fromisoformat(month + "-01").replace(tzinfo=UTC)
    end = start.replace(year=start.year + (start.month == 12), month=start.month % 12 + 1)
    statement = select(func.count(table.c.id_ocorrencia.distinct())).where(
        table.c.alimentador == feeder,
        table.c.data_abertura >= start,
        table.c.data_abertura < end,
    )
    with publication.execution_snapshot(
        engine, validate_f1_catalog=True,
        dimension_ids=frozenset({"network.feeder"}),
        metric_ids=frozenset({"network.interruption_events"}),
    ) as connection:
        connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
        count = connection.scalar(statement)
    if not count:
        return None
    data = {
        "active_gold_batch": publication.batch_ref, "feeder": feeder,
        "month": month, "occurrences": count,
    }
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return SqlFeederOccurrences(**data, evidence_digest=digest)


def service_summary_months(question: str) -> tuple[str, ...]:
    months = "|".join(MONTHS)
    match = re.fullmatch(
        rf"(?:compare|mostre) o total de (?:atendimentos|protocolos) e a satisfacao media "
        rf"de (?P<first>{months}) a (?P<last>{months}) de (?P<year>20[0-9]{{2}})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return ()
    first, last = (MONTHS.index(match[key]) + 1 for key in ("first", "last"))
    return tuple(f"{match['year']}-{month:02d}" for month in range(first, last + 1))


def monthly_consumption_satisfaction(question: str) -> tuple[str, ...]:
    match = re.fullmatch(
        r"mostre o consumo mensal e a satisfacao media dos atendimentos "
        r"no (?P<half>primeiro|segundo) semestre de (?P<year>20[0-9]{2})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return ()
    first = 1 if match["half"] == "primeiro" else 7
    return tuple(f"{match['year']}-{month:02d}" for month in range(first, first + 6))


def query_service_summary(engine, publication, periods, *, monthly=False):
    table = TABLES["atendimentos_uc"]
    start = datetime.fromisoformat(periods[0] + "-01").replace(tzinfo=UTC)
    last = datetime.fromisoformat(periods[-1] + "-01").replace(tzinfo=UTC)
    end = last.replace(year=last.year + (last.month == 12), month=last.month % 12 + 1)
    statement = select(
        func.count(table.c.protocolo.distinct()), func.avg(table.c.nota_satisfacao),
    ).where(table.c.data_abertura >= start, table.c.data_abertura < end)
    metrics = {"service.attendance", "service.satisfaction"}
    if monthly:
        metrics.add("energy.consumption")
    with publication.execution_snapshot(
        engine, validate_f1_catalog=True,
        metric_ids=frozenset(metrics),
        source_capability_ids={"energy.consumption": "faturamento.receita"} if monthly else None,
    ) as connection:
        connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
        count, average = connection.execute(statement).one()
        series = ()
        if monthly:
            billing = TABLES["diagnostico_receita"]
            consumption = dict(connection.execute(
                select(billing.c.competencia, func.sum(billing.c.consumo_total_kwh))
                .where(billing.c.competencia.in_(periods)).group_by(billing.c.competencia)
            ).all())
            month = func.to_char(func.timezone("UTC", table.c.data_abertura), "YYYY-MM")
            satisfaction = dict(connection.execute(
                select(month, func.avg(table.c.nota_satisfacao))
                .where(table.c.data_abertura >= start, table.c.data_abertura < end)
                .group_by(month)
            ).all())
            if any(consumption.get(p) is None or satisfaction.get(p) is None for p in periods):
                raise CompoundEvidenceUnavailable("Série mensal incompleta no recorte.")
            series = tuple(
                (p, f"{Decimal(str(consumption[p])):.2f}", f"{Decimal(str(satisfaction[p])):.2f}")
                for p in periods
            )
    data = {
        "active_gold_batch": publication.batch_ref,
        "start_month": periods[0],
        "end_month": periods[-1],
        "protocols": count,
        "satisfaction": f"{Decimal(str(average)):.2f}" if average is not None else None,
        "monthly": series,
    }
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return SqlServiceSummary(**data, evidence_digest=digest)


def monthly_municipality_totals(question: str) -> str | None:
    match = re.fullmatch(
        rf"compare (?:o )?consumo medido e (?:a )?receita faturada por municipio "
        rf"em (?P<month>{'|'.join(MONTHS)}) de (?P<year>20[0-9]{{2}})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return None
    return f"{match.group('year')}-{MONTHS.index(match.group('month')) + 1:02d}"


def monthly_class_average(question: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        rf"compare o consumo medio por uc com leitura e o faturamento por classe "
        rf"em (?P<city>[a-z ]+) em (?P<month>{'|'.join(MONTHS)}) de (?P<year>20[0-9]{{2}})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return None
    return match["city"], f"{match['year']}-{MONTHS.index(match['month']) + 1:02d}"


def monthly_class_opposite_changes(question: str) -> tuple[str, tuple[str, str]] | None:
    months = MONTHS
    month_pattern = "|".join(months)
    match = re.fullmatch(
        rf"quais classes de (?P<city>[a-z ]+) tiveram queda de consumo e alta de receita "
        rf"entre (?P<first>{month_pattern}) e (?P<last>{month_pattern}) de (?P<year>20[0-9]{{2}})[?.]?",
        _normalize_question(question),
    )
    if match is None:
        return None
    first, last = (months.index(match.group(key)) + 1 for key in ("first", "last"))
    if first >= last:
        return None
    year = match.group("year")
    return match.group("city"), (f"{year}-{first:02d}", f"{year}-{last:02d}")


def query_observed_consumption_revenue(
    engine: Engine, publication: GoldPublicationContext, periods, *, class_scope: str | None = None,
    opposite_changes: bool = False,
):
    """Compare published monthly aggregates by municipality and class."""
    table = TABLES["diagnostico_receita"]
    statement = (
        select(
            table.c.municipio,
            table.c.classe_consumo,
            table.c.competencia,
            func.sum(table.c.consumo_total_kwh),
            func.sum(table.c.receita_total_reais),
            func.sum(table.c.qtd_ucs_com_leitura),
        )
        .where(table.c.competencia.in_(periods))
        .group_by(table.c.municipio, table.c.classe_consumo, table.c.competencia)
    )
    class_average = len(periods) == 1 and class_scope is not None
    metrics = {"billing.revenue", "energy.consumption"}
    if class_average:
        metrics.add("energy.average_consumption_per_uc")
    with publication.execution_snapshot(
        engine,
        validate_f1_catalog=True,
        dimension_ids=frozenset({"geography.municipality", "customer.consumption_class"}),
        metric_ids=frozenset(metrics),
        source_capability_ids=dict.fromkeys(metrics, "faturamento.receita"),
    ) as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
        rows = connection.execute(statement).all()
    periods_set = set(periods)
    split = len(periods) // 2
    snapshot = len(periods) == 1
    previous = set(periods[:split])
    coverage = defaultdict(set)
    groups = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
    group_coverage = defaultdict(set)
    readers = {}
    for municipality, consumption_class, period, consumption, revenue, reader_count in rows:
        if not municipality or not consumption_class:
            raise CompoundEvidenceUnavailable("Há grupos Gold sem município ou classe.")
        window = 0 if period in previous else 1
        coverage[municipality].add(period)
        group_coverage[municipality, consumption_class].add(window)
        totals = groups[municipality, consumption_class]
        if class_average:
            readers[municipality, consumption_class] = reader_count
        if consumption is not None:
            totals[window] += Decimal(str(consumption))
        if revenue is not None:
            totals[window + 2] += Decimal(str(revenue))
    if not coverage or any(months != periods_set for months in coverage.values()):
        raise CompoundEvidenceUnavailable("Cobertura municipal incompleta nas janelas.")
    if not snapshot and any(windows != {0, 1} for windows in group_coverage.values()):
        raise CompoundEvidenceUnavailable("Há classes sem população nas duas janelas.")
    if snapshot and not class_average:
        rollup = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
        for (city, _), (_, kwh, _, brl) in groups.items():
            rollup[city, "Todas"] = [
                rollup[city, "Todas"][1] + kwh,
                rollup[city, "Todas"][1] + kwh,
                rollup[city, "Todas"][3] + brl,
                rollup[city, "Todas"][3] + brl,
            ]
        groups = rollup
    elif snapshot:
        for totals in groups.values():
            totals[0] = totals[1]
            totals[2] = totals[3]
    if class_scope is not None:
        selected = {city for city in coverage if _normalize_question(city) == class_scope}
        if class_scope and len(selected) != 1:
            raise CompoundEvidenceUnavailable("Município não encontrado no recorte publicado.")
        rollup = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
        label = next(iter(selected)) if class_scope else "Todos os municípios"
        for (city, consumption_class), totals in groups.items():
            if not class_scope or city in selected:
                for index, total in enumerate(totals):
                    rollup[label, consumption_class][index] += total
        groups = rollup
        coverage = {label: periods_set}
    consumption_by_municipality = defaultdict(lambda: [Decimal(0), Decimal(0)])
    effects = []
    for (municipality, consumption_class), (kwh0, kwh1, brl0, brl1) in groups.items():
        consumption_by_municipality[municipality][0] += kwh0
        consumption_by_municipality[municipality][1] += kwh1
        effects.append(RevenueEffect(
            municipality, consumption_class, brl1 if snapshot else brl1 - brl0,
            None, None, None,
            state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=kwh1 - kwh0,
            average_consumption_kwh=(
                kwh1 / Decimal(str(readers[municipality, consumption_class]))
                if class_average and readers.get((municipality, consumption_class)) else None
            ),
        ))
    windows = ObservedComparisonWindows(
        p0_start=periods[0], p0_end=periods[split - 1],
        p1_start=periods[split], p1_end=periods[-1], method="VARIACAO_OBSERVADA",
    )
    digest = hashlib.sha256(f"{publication.batch_ref}:{periods}".encode()).hexdigest()
    scope = EvidenceScope(publication.batch_ref, digest, windows)
    result = compose_consumption_revenue(
        scope, scope,
        tuple(ConsumptionTotals(city, *totals) for city, totals in consumption_by_municipality.items()),
        tuple(effects), expected_municipalities=frozenset(coverage),
        expected_revenue_groups=frozenset(groups),
        only_declines=class_scope is None and not snapshot,
        snapshot=snapshot,
    )
    if opposite_changes:
        from dataclasses import replace

        filtered = []
        for row in result.municipalities:
            effects = tuple(
                effect for effect in row.revenue_by_class
                if effect.consumption_change_kwh < 0 < effect.variation_brl
            )
            if effects:
                filtered.append(replace(row, revenue_by_class=effects))
        result = replace(result, municipalities=tuple(filtered))
    return result, None, None


class CompoundStagingUnavailable(ValueError):
    """The staging artifact is absent, stale, malformed, or out of scope."""


def is_price_volume_question(question: str) -> bool:
    normalized = _normalize_question(question)
    asks_composition = any(
        phrase in normalized
        for phrase in ("preço-volume", "preco-volume", "efeito preço e volume", "efeito preco e volume", "decomposição preço", "decomposicao preco")
    )
    asks_metrics = any(token in normalized for token in ("consumo", "kwh")) and any(
        token in normalized for token in ("receita", "faturamento", "faturamento")
    )
    return (asks_composition and asks_metrics) or is_ranked_consumption_revenue_impact_question(question)


def _normalize_question(question: str) -> str:
    value = unicodedata.normalize("NFKD", question.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class FinancialComparisonScope:
    municipality: str
    periods: tuple[str, ...]
    metric_ids: tuple[str, ...]


def financial_comparison_scope(question: str) -> FinancialComparisonScope | None:
    """Recognize the two typed multi-metric financial questions in the MGC set."""
    normalized = _normalize_question(question)
    month_pattern = "|".join(MONTHS)
    range_match = re.fullmatch(
        rf"como variaram consumo e preco observado por kwh em (?P<city>[a-z ]+) "
        rf"entre (?P<first>{month_pattern}) e (?P<last>{month_pattern}) "
        rf"de (?P<year>20[0-9]{{2}})[?.]?",
        normalized,
    )
    if range_match is not None:
        first = MONTH_NUMBER[range_match["first"]]
        last = MONTH_NUMBER[range_match["last"]]
        if first > last:
            return None
        year = int(range_match["year"])
        periods = tuple(f"{year}-{month:02d}" for month in range(first, last + 1))
        return FinancialComparisonScope(
            municipality=range_match["city"].strip(),
            periods=periods,
            metric_ids=("energy.consumption", "billing.effective_tariff"),
        )

    snapshot_match = re.fullmatch(
        rf"para (?P<city>[a-z ]+) em (?P<month>{month_pattern}) de "
        rf"(?P<year>20[0-9]{{2}}),? mostre faturamento, consumo e preco observado "
        rf"na base comparavel[?.]?",
        normalized,
    )
    if snapshot_match is not None:
        period = f"{snapshot_match['year']}-{MONTH_NUMBER[snapshot_match['month']]:02d}"
        return FinancialComparisonScope(
            municipality=snapshot_match["city"].strip(),
            periods=(period,),
            metric_ids=("billing.revenue", "energy.consumption", "billing.effective_tariff"),
        )
    return None


def query_financial_comparison(engine, publication, request_scope: FinancialComparisonScope):
    """Read each requested Gold measure at monthly grain without joining facts."""
    table = TABLES["diagnostico_receita"]
    metrics = frozenset(request_scope.metric_ids)
    dimensions = frozenset({"geography.municipality"})
    selections = [table.c.competencia]
    if "energy.consumption" in metrics:
        selections.append(func.sum(table.c.consumo_total_kwh).label("consumption_kwh"))
    if "billing.revenue" in metrics:
        selections.append(func.sum(table.c.receita_total_reais).label("revenue_brl"))
    if "billing.effective_tariff" in metrics:
        selections.extend((
            func.sum(table.c.receita_base_comparavel_reais).label("price_numerator"),
            func.sum(table.c.consumo_base_comparavel_kwh).label("price_denominator"),
        ))

    with publication.execution_snapshot(
        engine,
        validate_f1_catalog=True,
        dimension_ids=dimensions,
        metric_ids=metrics,
        source_capability_ids=dict.fromkeys(metrics, "faturamento.receita"),
    ) as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
        cities = connection.execute(
            select(table.c.municipio).where(
                table.c.competencia.in_(request_scope.periods),
                table.c.municipio.is_not(None),
            ).distinct()
        ).scalars().all()
        matches = [city for city in cities if _normalize_question(str(city)) == request_scope.municipality]
        if len(matches) != 1:
            raise CompoundEvidenceUnavailable("Município ausente ou ambíguo na Gold ativa.")
        municipality = str(matches[0])
        statement = (
            select(*selections)
            .where(
                table.c.municipio == municipality,
                table.c.competencia.in_(request_scope.periods),
            )
            .group_by(table.c.competencia)
            .order_by(table.c.competencia)
        )
        source_rows = connection.execute(statement).mappings().all()

    by_period = {str(row["competencia"]): row for row in source_rows}
    if tuple(sorted(by_period)) != request_scope.periods:
        raise CompoundEvidenceUnavailable("A cobertura mensal está incompleta nesse recorte.")
    monthly = []
    raw_prices: list[Decimal | None] = []
    for period in request_scope.periods:
        source = by_period[period]
        consumption = source.get("consumption_kwh")
        revenue = source.get("revenue_brl")
        if "energy.consumption" in metrics and consumption is None:
            raise CompoundEvidenceUnavailable("Consumo medido ausente em uma competência solicitada.")
        if "billing.revenue" in metrics and revenue is None:
            raise CompoundEvidenceUnavailable("Faturamento ausente em uma competência solicitada.")
        price = None
        if "billing.effective_tariff" in metrics:
            numerator = source.get("price_numerator")
            denominator = source.get("price_denominator")
            if numerator is not None and denominator is not None and Decimal(str(denominator)) > 0:
                price = Decimal(str(numerator)) / Decimal(str(denominator))
        raw_prices.append(price)
        monthly.append({
            "period": period,
            "consumption_kwh": _decimal_text(consumption) if consumption is not None else None,
            "revenue_brl": _decimal_text(revenue) if revenue is not None else None,
            "observed_price_brl_per_kwh": (
                _decimal_text(price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN))
                if price is not None else None
            ),
        })

    limitations = [
        "Preço observado é a razão entre faturamento e consumo com base comparável; não é tarifa regulada nem demonstra causalidade."
    ]
    if any(price is None for price in raw_prices):
        limitations.append("Preço indisponível nas competências sem denominador comparável positivo.")
    if "billing.revenue" in metrics and "billing.effective_tariff" in metrics:
        limitations.append("Faturamento total e preço observado usam universos diferentes; o preço considera somente a base comparável.")

    if len(request_scope.periods) > 1:
        first, last = monthly[0], monthly[-1]
        first_period, last_period = request_scope.periods[0], request_scope.periods[-1]
        consumption_change = Decimal(last["consumption_kwh"]) - Decimal(first["consumption_kwh"])
        consumption_percent = consumption_change * 100 / Decimal(first["consumption_kwh"])
        if consumption_change < 0:
            consumption_phrase = f"consumo caiu {_pt_br(abs(consumption_change), 0)} kWh ({_pt_br(abs(consumption_percent), 2)}%)"
        elif consumption_change > 0:
            consumption_phrase = f"consumo subiu {_pt_br(consumption_change, 0)} kWh ({_pt_br(consumption_percent, 2)}%)"
        else:
            consumption_phrase = "o consumo permaneceu estável"
        first_price, last_price = raw_prices[0], raw_prices[-1]
        if first_price is None or last_price is None or first_price == 0:
            price_phrase = "o preço observado não pôde ser comparado por falta de base válida em uma das pontas"
        else:
            price_change_percent = (last_price - first_price) * 100 / first_price
            direction = "subiu" if price_change_percent > 0 else "caiu" if price_change_percent < 0 else "permaneceu estável"
            price_phrase = (
                f"o preço observado {direction} de R$ {_pt_br(first_price, 4)} para "
                f"R$ {_pt_br(last_price, 4)}/kWh ({_signed_pt_br(price_change_percent, 2)}%)"
            )
        year = first_period[:4]
        first_month = MONTHS[int(first_period[5:7]) - 1]
        last_month = MONTHS[int(last_period[5:7]) - 1]
        answer = (
            f"De {first_month} a {last_month} de {year}, em {municipality}, {consumption_phrase}; "
            f"{price_phrase}. As duas séries são observacionais e não indicam causalidade."
        )
    else:
        row = monthly[0]
        period = request_scope.periods[0]
        year = period[:4]
        month = MONTHS[int(period[5:7]) - 1]
        pieces = []
        if row["revenue_brl"] is not None:
            pieces.append(f"faturamento total de R$ {_pt_br(Decimal(row['revenue_brl']), 2)}")
        if row["consumption_kwh"] is not None:
            pieces.append(f"consumo medido de {_pt_br(Decimal(row['consumption_kwh']), 0)} kWh")
        if raw_prices[0] is None:
            pieces.append("preço observado indisponível por falta de base comparável positiva")
        else:
            pieces.append(f"preço observado de R$ {_pt_br(raw_prices[0], 4)}/kWh na base comparável")
        answer = f"Em {month} de {year}, em {municipality}, " + "; ".join(pieces) + "."

    data = {
        "contract_version": "text-to-sql-f1-financial-comparison-v1",
        "answer": answer,
        "active_gold_batch": publication.batch_ref,
        "municipality": municipality,
        "start_month": request_scope.periods[0],
        "end_month": request_scope.periods[-1],
        "metric_ids": request_scope.metric_ids,
        "monthly": monthly,
        "limitations": tuple(limitations),
    }
    digest = hashlib.sha256(json.dumps(
        data, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return SqlFinancialComparison(**data, evidence_digest=digest)


def _decimal_text(value) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _pt_br(value: Decimal, places: int) -> str:
    formatted = f"{value:,.{places}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _signed_pt_br(value: Decimal, places: int) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}{_pt_br(abs(value), places)}"


def is_ranked_consumption_revenue_impact_question(question: str) -> bool:
    """Recognize only the published 12-month grouped-impact investigation.

    This operation uses the validated 2024-07–2025-06 and 2025-07–2026-06
    staging pair. Other periods or generic multi-metric questions must continue
    through normal planning, where unsupported/clarification remains possible.
    """
    normalized = _normalize_question(question)
    asks_ranked_decline = "queda" in normalized and "consumo" in normalized
    asks_revenue_effect = "receita" in normalized and (
        "impact" in normalized or "compare" in normalized
    )
    asks_class_detail = "classe" in normalized
    latest_available_window = (
        "ultimos 12 meses" in normalized
        or "ultimos doze meses" in normalized
        or (
            "jul/2024" in normalized and "jun/2025" in normalized
            and "jul/2025" in normalized and "jun/2026" in normalized
        )
    )
    return (
        asks_ranked_decline and asks_revenue_effect and asks_class_detail
        and latest_available_window
    )


def _decimal(value: str, field: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        raise CompoundStagingUnavailable(f"Campo {field} inválido no staging.") from None
    if not number.is_finite():
        raise CompoundStagingUnavailable(f"Campo {field} não finito no staging.")
    return number


def _optional_decimal(value: str, field: str) -> Decimal | None:
    if value == r"\N":
        return None
    return _decimal(value, field)


def load_price_volume_staging(directory: str | Path, *, expected_lot: str):
    """Validate the immutable manifest and CSV before exposing any rows."""
    root = Path(directory).resolve()
    manifest_path = (root / "manifest-staging.json").resolve()
    csv_path = (root / "decomposicao_receita.csv").resolve()
    if root not in manifest_path.parents or root not in csv_path.parents:
        raise CompoundStagingUnavailable("Caminho de staging inválido.")
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES or csv_path.stat().st_size > MAX_CSV_BYTES:
            raise CompoundStagingUnavailable("Artefato de staging excede o limite permitido.")
        manifest_bytes = manifest_path.read_bytes()
        csv_bytes = csv_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError, json.JSONDecodeError):
        raise CompoundStagingUnavailable("Manifesto ou CSV de staging indisponível.") from None
    if (
        manifest.get("schema_version") != "gold-v2-price-volume-staging-v1"
        or manifest.get("status") != "STAGING_ONLY_NOT_ACTIVE"
        or manifest.get("source_publication", {}).get("lote") != expected_lot
        or manifest.get("requested_price_volume_windows") != EXPECTED_WINDOWS
        or manifest.get("method") != EXPECTED_METHOD
        or manifest.get("csv_file") != csv_path.name
        or hashlib.sha256(csv_bytes).hexdigest() != manifest.get("csv_sha256")
    ):
        raise CompoundStagingUnavailable("Staging não corresponde à publicação Gold ativa.")
    try:
        text = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines(), delimiter=";")
        if reader.fieldnames is None or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise CompoundStagingUnavailable("Estrutura do CSV de staging inválida.")
        effects: list[RevenueEffect] = []
        for row in reader:
            if any(row.get(name) != value for name, value in EXPECTED_WINDOWS.items()):
                raise CompoundStagingUnavailable("Janela divergente no CSV de staging.")
            if row.get("metodo") != EXPECTED_METHOD:
                raise CompoundStagingUnavailable("Método divergente no CSV de staging.")
            if row.get("estado_decomposicao") not in {"CALCULADA_BASE_COMUM", "SEM_BASE_COMUM"}:
                raise CompoundStagingUnavailable("Estado de decomposição desconhecido.")
            state = row["estado_decomposicao"]
            volume, price, interaction = (
                _optional_decimal(row["efeito_volume_reais"], "efeito_volume_reais"),
                _optional_decimal(row["efeito_preco_observado_reais"], "efeito_preco_observado_reais"),
                _optional_decimal(row["efeito_interacao_reais"], "efeito_interacao_reais"),
            )
            if (state == "CALCULADA_BASE_COMUM") != all(
                value is not None for value in (volume, price, interaction)
            ):
                raise CompoundStagingUnavailable("Efeitos divergem do estado de decomposição.")
            effects.append(RevenueEffect(
                municipality=(row.get("municipio") or "").strip(),
                consumption_class=(row.get("classe_consumo") or "").strip(),
                variation_brl=_decimal(row["variacao_faturamento_total_reais"], "variacao_faturamento_total_reais"),
                volume_effect_brl=volume,
                price_effect_brl=price,
                interaction_effect_brl=interaction,
                state=state,
                neighborhood=(row.get("bairro") or "").strip(),
            ))
    except (UnicodeDecodeError, KeyError, csv.Error):
        raise CompoundStagingUnavailable("CSV de staging inválido.") from None
    if not effects or len(effects) != manifest.get("group_rows"):
        raise CompoundStagingUnavailable("Quantidade de grupos diverge do manifesto.")
    return manifest, tuple(effects), hashlib.sha256(manifest_bytes).hexdigest()


def query_compound_from_sources(
    engine: Engine,
    staging_dir: str | Path,
    *,
    batch_ref: str,
    publication: GoldPublicationContext | None = None,
):
    """Aggregate monthly consumption separately, then compose published effects.

    No raw fact join is performed. The output explicitly keeps staging separate
    from the active Gold publication and carries both source identities.
    """
    expected_lot = batch_ref.split(":")[1] if batch_ref.startswith("gold-csv-v2:") else ""
    manifest, revenue, manifest_digest = load_price_volume_staging(
        staging_dir, expected_lot=expected_lot
    )
    expected_municipalities = frozenset(item.municipality for item in revenue)
    expected_groups = frozenset((item.municipality, item.neighborhood, item.consumption_class) for item in revenue)
    table = TABLES["diagnostico_receita"]
    periods = tuple(
        f"{year:04d}-{month:02d}"
        for start, end in (("2024-07", "2025-06"), ("2025-07", "2026-06"))
        for year in range(int(start[:4]), int(end[:4]) + 1)
        for month in range(1, 13)
        if f"{year:04d}-{month:02d}" >= start and f"{year:04d}-{month:02d}" <= end
    )
    statement = (
        select(
            table.c.municipio,
            table.c.competencia,
            func.sum(table.c.consumo_total_kwh).label("consumo_kwh"),
            func.count(table.c.competencia.distinct()).label("competencias"),
        )
        .where(table.c.competencia.in_(periods))
        .group_by(table.c.municipio, table.c.competencia)
        .order_by(table.c.municipio, table.c.competencia)
    )
    try:
        if publication is None:
            with engine.connect() as connection:
                rows = connection.execute(statement).mappings().all()
        else:
            with publication.execution_snapshot(
                engine,
                validate_f1_catalog=True,
                dimension_ids=frozenset({"geography.municipality", "customer.consumption_class"}),
                metric_ids=frozenset({"billing.revenue", "energy.consumption"}),
                source_capability_ids={
                    "billing.revenue": "faturamento.receita",
                    "energy.consumption": "faturamento.receita",
                },
            ) as connection:
                if connection.dialect.name == "postgresql":
                    connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
                rows = connection.execute(statement).mappings().all()
    except SQLAlchemyError as exc:
        # Don't surface driver details or SQL in the public API.
        raise CompoundEvidenceUnavailable("Consumo Gold indisponível para a comparação.") from exc
    monthly: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        if row["municipio"] is None or row["consumo_kwh"] is None:
            raise CompoundEvidenceUnavailable("Consumo Gold contém valores ausentes.")
        monthly[str(row["municipio"])][str(row["competencia"])] = Decimal(str(row["consumo_kwh"]))
    if frozenset(monthly) != expected_municipalities or any(
        set(values) != set(periods) for values in monthly.values()
    ):
        raise CompoundEvidenceUnavailable("Cobertura mensal de consumo diverge do staging.")
    previous = set(periods[:12])
    current = set(periods[12:])
    consumption = tuple(
        ConsumptionTotals(
            municipality,
            sum((value for month, value in months.items() if month in previous), Decimal(0)),
            sum((value for month, value in months.items() if month in current), Decimal(0)),
        )
        for municipality, months in monthly.items()
    )
    windows = PublishedWindows(
        p0_start=EXPECTED_WINDOWS["inicio_p0"], p0_end=EXPECTED_WINDOWS["fim_p0"],
        p1_start=EXPECTED_WINDOWS["inicio_p1"], p1_end=EXPECTED_WINDOWS["fim_p1"],
        method=EXPECTED_METHOD,
    )
    scope_digest = hashlib.sha256(
        json.dumps({"batch": batch_ref, "manifest": manifest_digest, "csv": manifest["csv_sha256"]}, sort_keys=True).encode()
    ).hexdigest()
    scope = EvidenceScope(batch_ref, scope_digest, windows)
    result = compose_consumption_revenue(
        scope, scope, consumption, revenue,
        expected_municipalities=expected_municipalities,
        expected_revenue_groups=expected_groups,
    )
    return result, manifest, manifest_digest
