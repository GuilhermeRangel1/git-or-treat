"""Apresenta a evidência F1 sem recalcular nem arredondar seus valores."""

from decimal import Decimal

from app.schemas.sql_analysis import (
    SqlAnalysisPresentation,
    SqlPresentationColumn,
    SqlPresentationRow,
)
from app.schemas.sql_evidence import SqlEvidence

_DIMENSIONS = {
    "competency": "Competência",
    "municipality": "Município",
    "neighborhood": "Bairro",
    "consumption_class": "Classe de consumo",
    "feeder": "Alimentador",
}
_MEASURES = {
    "revenue_total": "Faturamento",
    "energy_total": "Consumo medido",
    "attendance_total": "Protocolos abertos",
    "satisfaction_average": "Nota média de satisfação",
    "dec_value": "DEC",
    "fec_value": "FEC",
    "gd_units_total": "UCs com GD",
    "satisfaction_accumulated_average": "Nota média de satisfação no histórico",
    "period_0_total": "Faturamento no período 1",
    "period_1_total": "Faturamento no período 2",
    "period_0_minus_period_1": "Diferença (período 1 − período 2)",
    "period_0_growth_percent": "Variação percentual",
}
_FILTER_DIMENSIONS = {
    "geography.municipality": "Município",
    "geography.neighborhood": "Bairro",
    "customer.consumption_class": "Classe de consumo",
    "network.feeder": "Alimentador",
    "generation.distributed": "Geração distribuída (cadastro)",
}
_F1_LIMITATIONS = (
    "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
)
_MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _decimal_pt_br(value: str) -> str:
    """Agrupa milhares e troca separador decimal sem alterar a escala original."""
    number = Decimal(value)
    raw = format(number, "f")
    sign = "-" if raw.startswith("-") else ""
    unsigned = raw[1:] if sign else raw
    integer, separator, fraction = unsigned.partition(".")
    groups: list[str] = []
    while integer:
        groups.append(integer[-3:])
        integer = integer[:-3]
    formatted_integer = ".".join(reversed(groups)) or "0"
    return sign + formatted_integer + ("," + fraction if separator else "")


def _period(evidence: SqlEvidence) -> str:
    if evidence.interpretation.operation == "snapshot_total":
        return "Cadastro de GD no lote"
    windows = evidence.interpretation.periods
    if evidence.interpretation.operation in {"accumulated_total", "accumulated_average"}:
        return "Histórico acumulado"
    labels = tuple(f"{item.start:%Y-%m}" for item in windows)
    ends = tuple(f"{item.end:%Y-%m}" for item in windows)
    return " vs. ".join(
        start if start == end else f"{start} a {end}"
        for start, end in zip(labels, ends, strict=True)
    )


def _period_phrase(start, end) -> str:
    start_label = f"{_MONTH_NAMES[start.month - 1]} de {start.year}"
    end_label = f"{_MONTH_NAMES[end.month - 1]} de {end.year}"
    if start.year == end.year:
        if start.month == end.month:
            return start_label
        return f"{_MONTH_NAMES[start.month - 1]} a {_MONTH_NAMES[end.month - 1]} de {start.year}"
    return f"{start_label} a {end_label}"


def _filters(evidence: SqlEvidence) -> tuple[str, ...]:
    result = []
    for item in evidence.interpretation.filters:
        if evidence.metric_id == "energy.gd_units" and item.dimension_id == "generation.distributed":
            continue
        label = _FILTER_DIMENSIONS[item.dimension_id]
        values = ", ".join(item.values)
        result.append(f"{label}: {values}")
    return tuple(result)


def _universe(evidence: SqlEvidence) -> tuple[str, ...]:
    if evidence.interpretation.operation not in {
        "grouped_total", "ranking", "comparison", "snapshot_total",
    }:
        return ()
    filtered = {item.dimension_id for item in evidence.interpretation.filters}
    labels = {
        "competency": "Competências",
        "municipality": "Municípios",
        "neighborhood": "Bairros",
        "consumption_class": "Classes de consumo",
    }
    ids = {
        "competency": "time.competency",
        "municipality": "geography.municipality",
        "neighborhood": "geography.neighborhood",
        "consumption_class": "customer.consumption_class",
    }
    return tuple(
        f"{labels[item]}: "
        + (
            "valores filtrados"
            if ids[item] in filtered
            else "todos os valores disponíveis no recorte"
        )
        for item in evidence.interpretation.group_by
    )


def _answer(evidence: SqlEvidence, filters: tuple[str, ...]) -> str:
    operation = evidence.interpretation.operation
    window = evidence.interpretation.periods[0] if evidence.interpretation.periods else None
    scope = " no histórico acumulado" if operation in {
        "accumulated_total", "accumulated_average",
    } else (
        " no lote publicado" if operation == "snapshot_total" else
        f" nos períodos {_period(evidence)}"
        if operation == "comparison"
        else f" no período {_period_phrase(window.start, window.end)}"
    )
    if filters:
        scope += " (" + "; ".join(filters) + ")"
    metric_label = (
        "protocolos de atendimento" if evidence.metric_id in {
            "service.attendance", "service.accumulated_attendance",
        }
        else "DEC" if evidence.metric_id == "network.equivalent_interruption_duration"
        else "FEC" if evidence.metric_id == "network.equivalent_interruption_frequency"
        else "unidades consumidoras com GD cadastrada" if evidence.metric_id == "energy.gd_units"
        else "nota média de satisfação" if evidence.metric_id == "service.accumulated_satisfaction"
        else "consumo medido" if evidence.metric_id == "energy.consumption" else "faturamento"
    )
    measure_unit = (
        "pontos" if evidence.metric_id == "service.satisfaction"
        else
        "protocolos" if evidence.metric_id in {
            "service.attendance", "service.accumulated_attendance",
        }
        else "horas por UC" if evidence.metric_id == "network.equivalent_interruption_duration"
        else "interrupções por UC" if evidence.metric_id == "network.equivalent_interruption_frequency"
        else "UCs" if evidence.metric_id == "energy.gd_units"
        else "pontos" if evidence.metric_id == "service.accumulated_satisfaction"
        else "kWh" if evidence.metric_id == "energy.consumption" else "R$"
    )

    def formatted(value: str) -> str:
        number = _decimal_pt_br(value)
        return (f"{number} {measure_unit}" if measure_unit in {
            "kWh", "protocolos", "UCs", "pontos", "horas por UC", "interrupções por UC",
        }
                else f"R$ {number}")

    if evidence.status == "empty":
        return f"Não há linhas de {metric_label} para o recorte consultado{scope}."
    if evidence.status == "all_measures_null":
        return f"O recorte foi consultado{scope}, mas a fonte não trouxe valores de {metric_label}."

    if operation == "accumulated_total":
        column = next(
            name for name, meaning in evidence.measure_semantics.items()
            if meaning == "attendance_accumulated_total"
        )
        value = evidence.rows[0][next(
            index for index, item in enumerate(evidence.columns) if item.name == column
        )]
        if value is None:
            return "O total do histórico acumulado está indisponível."
        return (f"No histórico publicado, foram registrados {formatted(value)}. "
                "A fonte não informa o intervalo nem certifica a completude histórica.")

    if operation == "snapshot_total":
        column = next(name for name, meaning in evidence.measure_semantics.items()
                      if meaning == "gd_units_total")
        value = evidence.rows[0][next(
            index for index, item in enumerate(evidence.columns) if item.name == column
        )]
        if value is None:
            return "A contagem de UCs com GD cadastrada está indisponível no lote publicado."
        return f"Foram identificadas {formatted(value)} com GD cadastrada{scope}."

    if operation == "accumulated_average":
        column = next(name for name, meaning in evidence.measure_semantics.items()
                      if meaning == "satisfaction_accumulated_average")
        value = evidence.rows[0][next(
            index for index, item in enumerate(evidence.columns) if item.name == column
        )]
        if value is None:
            return "Não há notas válidas no histórico publicado de satisfação."
        return (
            "A média das notas individuais válidas no histórico publicado foi "
            f"{formatted(value)}. O intervalo e a completude histórica não são conhecidos."
        )

    if operation == "total":
        column = next(
            item
            for item, meaning in evidence.measure_semantics.items()
            if meaning in {"revenue_total", "energy_total", "attendance_total"}
        )
        value = evidence.rows[0][
            next(i for i, item in enumerate(evidence.columns) if item.name == column)
        ]
        if value is None:
            return f"O valor de {metric_label} está indisponível{scope}."
        if evidence.metric_id == "billing.revenue":
            return f"O faturamento total{scope} foi {formatted(value)}."
        if evidence.metric_id == "service.attendance":
            return f"Foram abertos {formatted(value)}{scope}."
        return f"O consumo medido total{scope} foi {formatted(value)}."

    if operation == "average":
        column = next(
            name for name, meaning in evidence.measure_semantics.items()
            if meaning == "satisfaction_average"
        )
        value = evidence.rows[0][next(
            index for index, item in enumerate(evidence.columns) if item.name == column
        )]
        if value is None:
            return f"A nota média de satisfação está indisponível{scope}."
        return f"A nota média de satisfação{scope} foi {formatted(value)}."

    if operation == "grain_read":
        meaning = ("dec_value" if evidence.metric_id == "network.equivalent_interruption_duration"
                   else "fec_value")
        column = next(name for name, item_meaning in evidence.measure_semantics.items()
                      if item_meaning == meaning)
        value = evidence.rows[0][next(
            index for index, item in enumerate(evidence.columns) if item.name == column
        )]
        if value is None:
            return f"O valor de {metric_label} está indisponível{scope}."
        return f"{metric_label}{scope}: {formatted(value)}."

    if operation == "comparison":
        if evidence.interpretation.group_by:
            grouping = " e ".join(
                _DIMENSIONS[item] for item in evidence.interpretation.group_by
            )
            if evidence.interpretation.ranking_direction is None:
                return (f"A comparação de {metric_label} por {grouping}{scope} "
                        "está detalhada na tabela.")
            if evidence.interpretation.ranking_direction == "desc":
                ranked_change = "maiores diferenças"
            else:
                ranked_change = "menores diferenças"
            return (
                f"A tabela lista as {ranked_change} de {metric_label} "
                f"(primeiro período − segundo período), por {grouping}{scope}."
            )
        values: dict[str, str | None] = {}
        for name, meaning in evidence.measure_semantics.items():
            index = next(
                i for i, item in enumerate(evidence.columns) if item.name == name
            )
            values[meaning] = evidence.rows[0][index]
        first = values.get("period_0_total")
        second = values.get("period_1_total")
        difference = values.get("period_0_minus_period_1")
        if first is None or second is None or difference is None:
            return f"A comparação não tem todos os valores disponíveis{scope}."
        windows = evidence.interpretation.periods
        first_period = _period_phrase(windows[0].start, windows[0].end)
        second_period = _period_phrase(windows[1].start, windows[1].end)
        filter_scope = f" para {'; '.join(filters)}" if filters else ""
        answer = (
            f"O faturamento foi {formatted(first)} de {first_period} e "
            f"{formatted(second)} de {second_period}. A diferença "
            f"(primeiro período − segundo período) foi {formatted(difference)}{filter_scope}."
            if evidence.metric_id == "billing.revenue"
            else f"O consumo medido foi {formatted(first)} de {first_period} e "
            f"{formatted(second)} de {second_period}. A diferença "
            f"(primeiro período − segundo período) foi {formatted(difference)}{filter_scope}."
        )
        if "period_0_growth_percent" not in evidence.measure_semantics.values():
            return answer
        growth = values.get("period_0_growth_percent")
        if growth is not None:
            return (
                answer + " A variação percentual sobre o período de referência foi "
                f"{_decimal_pt_br(growth)}%."
            )
        if Decimal(second) == 0:
            return (
                answer + " A variação percentual não é definida porque "
                "o período de referência tem base zero."
            )
        if Decimal(second) < 0:
            return (
                answer + " A variação percentual não é definida porque "
                "o período de referência não é positivo."
            )
        return (
            answer + " A variação percentual não pôde ser calculada porque "
            "falta valor em um dos períodos."
        )

    dimensions = tuple(_DIMENSIONS[item] for item in evidence.interpretation.group_by)
    grouping = " e ".join(dimensions)
    if operation == "ranking":
        direction = (
            "maiores"
            if evidence.interpretation.ranking_direction == "desc"
            else "menores"
        )
        dimension = next(item for item in evidence.columns if item.role == "dimension")
        measure = next(item for item in evidence.columns if item.role == "measure")
        dimension_index = next(
            index for index, item in enumerate(evidence.columns)
            if item.name == dimension.name
        )
        measure_index = next(
            index for index, item in enumerate(evidence.columns)
            if item.name == measure.name
        )
        first = evidence.rows[0]
        if first[dimension_index] is None or first[measure_index] is None:
            return (
                f"O ranking de {metric_label} por {grouping}{scope} está na tabela, "
                "mas o primeiro grupo não tem identificação ou valor disponível."
            )
        extremum = "maior" if direction == "maiores" else "menor"
        return (
            f"O {extremum} {metric_label} do recorte foi de {first[dimension_index]}: "
                f"{formatted(first[measure_index])}{scope}. "
            f"A tabela lista os {direction} grupos por {grouping}."
        )
    if operation == "monthly_series":
        return f"A série mensal de {metric_label}{scope} está na tabela."
    if evidence.metric_id == "billing.revenue":
        return f"O faturamento por {grouping}{scope} está detalhado na tabela."
    return f"O consumo medido por {grouping}{scope} está detalhado na tabela."


def _metric_measure_label(evidence: SqlEvidence, meaning: str) -> str:
    if evidence.metric_id == "service.accumulated_satisfaction":
        return "Nota média de satisfação no histórico"
    if evidence.metric_id == "energy.gd_units":
        return "UCs com GD cadastrada"
    if evidence.metric_id == "service.accumulated_attendance":
        return "Chamados no histórico"
    if evidence.metric_id == "service.attendance":
        return "Protocolos abertos"
    if evidence.metric_id == "service.satisfaction":
        return "Nota média de satisfação"
    if evidence.metric_id == "billing.revenue":
        return _MEASURES[meaning]
    if evidence.metric_id in {
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        return _MEASURES[meaning]
    return {
        "energy_total": "Consumo medido",
        "period_0_total": "Consumo no período 1",
        "period_1_total": "Consumo no período 2",
        "period_0_minus_period_1": "Diferença de consumo (período 1 − período 2)",
        "period_0_growth_percent": "Variação percentual do consumo",
    }[meaning]


def present_sql_evidence(evidence: SqlEvidence) -> SqlAnalysisPresentation:
    """Cria texto e tabela alinhados, célula a célula, à evidência validada."""
    columns = tuple(
        SqlPresentationColumn(
            key=column.name,
            label=(
                _metric_measure_label(evidence, evidence.measure_semantics[column.name])
                if column.role == "measure"
                else _DIMENSIONS[evidence.dimension_semantics[column.name]]
            ),
            role=column.role,
            semantic_id=(
                evidence.measure_semantics[column.name]
                if column.role == "measure"
                else evidence.dimension_semantics[column.name]
            ),
            unit=column.unit,
        )
        for column in evidence.columns
    )
    rows = tuple(
        SqlPresentationRow(
            observation_id=f"row_{row_index}",
            cells=row,
        )
        for row_index, row in enumerate(evidence.rows, start=1)
    )
    period = _period(evidence)
    filters = _filters(evidence)
    state = {
        "available": "ready",
        "empty": "empty",
        "all_measures_null": "all_measures_null",
    }[evidence.status]
    answer = _answer(evidence, filters)
    limitations = (
        ("Valores observados; cobertura do alimentador não certificada.",)
        if evidence.coverage_quality == "observed_uncertified"
        else ("Consumo medido não é energia faturada.",)
        if evidence.metric_id == "energy.consumption"
        else _F1_LIMITATIONS if evidence.metric_id == "billing.revenue" else ()
    )
    if evidence.metric_id == "service.satisfaction":
        limitations = ("Média das notas informadas; valores ausentes são excluídos e zero é válido.",)
    if evidence.metric_id == "service.accumulated_attendance":
        limitations = (
            "Histórico publicado sem intervalo conhecido ou certificação de completude histórica.",
        )
    if evidence.metric_id == "energy.gd_units":
        limitations = (
            "Retrato do cadastro no lote publicado; não informa quando a GD entrou em operação nem confirma geração ou injeção.",
        )
    if evidence.metric_id == "service.accumulated_satisfaction":
        limitations = (
            "Média das notas válidas do histórico publicado; o intervalo e a completude histórica não são conhecidos.",
        )
    if evidence.coverage_quality == "observed_uncertified":
        answer += " Valores observados; cobertura do alimentador não certificada."
    return SqlAnalysisPresentation(
        contract_version=(
            "text-to-sql-f1-presentation-v2"
            if evidence.interpretation.operation == "comparison"
            and "period_0_growth_percent" in evidence.measure_semantics.values()
            else "text-to-sql-f1-presentation-v3"
            if evidence.metric_id == "service.attendance"
            else "text-to-sql-f1-presentation-v6"
            if evidence.metric_id == "service.satisfaction"
            else "text-to-sql-f1-presentation-v7"
            if evidence.metric_id == "energy.gd_units"
            else "text-to-sql-f1-presentation-v8"
            if evidence.metric_id == "service.accumulated_satisfaction"
            else "text-to-sql-f1-presentation-v5"
            if evidence.metric_id == "service.accumulated_attendance"
            else "text-to-sql-f1-presentation-v4"
            if evidence.metric_id in {
                "network.equivalent_interruption_duration",
                "network.equivalent_interruption_frequency",
            }
            else "text-to-sql-f1-presentation-v1"
        ),
        state=state,
        operation=evidence.interpretation.operation,
        answer=answer,
        period=period,
        filters=filters,
        universe=_universe(evidence),
        limitations=limitations,
        columns=columns,
        rows=rows,
        evidence_digest=evidence.evidence_digest,
    )
