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
    "consumption_class": "Classe de consumo",
}
_MEASURES = {
    "revenue_total": "Faturamento",
    "period_0_total": "Faturamento no período 1",
    "period_1_total": "Faturamento no período 2",
    "period_0_minus_period_1": "Diferença (período 1 − período 2)",
}
_FILTER_DIMENSIONS = {
    "geography.municipality": "Município",
    "customer.consumption_class": "Classe de consumo",
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
    windows = evidence.interpretation.periods
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
        label = _FILTER_DIMENSIONS[item.dimension_id]
        values = ", ".join(item.values)
        result.append(f"{label}: {values}")
    return tuple(result)


def _universe(evidence: SqlEvidence) -> tuple[str, ...]:
    if evidence.interpretation.operation not in {"grouped_total", "ranking"}:
        return ()
    filtered = {item.dimension_id for item in evidence.interpretation.filters}
    labels = {
        "competency": "Competências",
        "municipality": "Municípios",
        "consumption_class": "Classes de consumo",
    }
    ids = {
        "competency": "time.competency",
        "municipality": "geography.municipality",
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
    window = evidence.interpretation.periods[0]
    scope = f" no período {_period_phrase(window.start, window.end)}"
    if filters:
        scope += " (" + "; ".join(filters) + ")"
    if evidence.status == "empty":
        return f"Não há linhas de faturamento para o recorte consultado{scope}."
    if evidence.status == "all_measures_null":
        return f"O recorte foi consultado{scope}, mas a fonte não trouxe valores de faturamento."

    operation = evidence.interpretation.operation
    if operation == "total":
        column = next(
            item
            for item, meaning in evidence.measure_semantics.items()
            if meaning == "revenue_total"
        )
        value = evidence.rows[0][
            next(i for i, item in enumerate(evidence.columns) if item.name == column)
        ]
        if value is None:
            return f"O faturamento está sem valor disponível{scope}."
        return f"O faturamento total{scope} foi R$ {_decimal_pt_br(value)}."

    if operation == "comparison":
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
        return (
            f"O faturamento foi R$ {_decimal_pt_br(first)} de {first_period} e "
            f"R$ {_decimal_pt_br(second)} de {second_period}. A diferença "
            f"(primeiro período − segundo período) foi R$ "
            f"{_decimal_pt_br(difference)}{filter_scope}."
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
                f"O ranking de faturamento por {grouping}{scope} está na tabela, "
                "mas o primeiro grupo não tem identificação ou valor disponível."
            )
        extremum = "maior" if direction == "maiores" else "menor"
        return (
            f"O {extremum} faturamento do recorte foi de {first[dimension_index]}: "
            f"R$ {_decimal_pt_br(first[measure_index])}{scope}. "
            f"A tabela lista os {direction} grupos por {grouping}."
        )
    if operation == "monthly_series":
        return f"A série mensal de faturamento{scope} está na tabela."
    return f"O faturamento por {grouping}{scope} está detalhado na tabela."


def present_sql_evidence(evidence: SqlEvidence) -> SqlAnalysisPresentation:
    """Cria texto e tabela alinhados, célula a célula, à evidência validada."""
    columns = tuple(
        SqlPresentationColumn(
            key=column.name,
            label=(
                _MEASURES[evidence.measure_semantics[column.name]]
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
    return SqlAnalysisPresentation(
        contract_version="text-to-sql-f1-presentation-v1",
        state=state,
        operation=evidence.interpretation.operation,
        answer=_answer(evidence, filters),
        period=period,
        filters=filters,
        universe=_universe(evidence),
        limitations=_F1_LIMITATIONS,
        columns=columns,
        rows=rows,
        evidence_digest=evidence.evidence_digest,
    )
