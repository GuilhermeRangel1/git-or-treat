"""Conferência conservadora SQL/intenção F1; não é autorização de execução."""

import re
from dataclasses import dataclass

from sqlglot import exp, parse_one

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import F1_DIMENSIONS
from app.services.genai_sql_structure import (
    SqlStructureRejected,
    SqlStructureReview,
    review_sql_structure,
)

_GROUPS = {"competency": "competencia", "municipality": "municipio",
           "consumption_class": "classe_consumo"}
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")
GROWTH_PERCENT_COLUMN = "period_0_growth_percent"
_BACKEND_DERIVED_COLUMNS = frozenset({GROWTH_PERCENT_COLUMN})


@dataclass(frozen=True)
class SqlSemanticReview(SqlStructureReview):
    """Linhagem inferida da AST; ainda depende de prontidão e autorização final."""

    measure_semantics: tuple[tuple[str, str], ...]


def _period_months(period):
    return frozenset(range((period.start.year - 1) * 12 + period.start.month - 1,
                           (period.end.year - 1) * 12 + period.end.month))


def _combine(left, right):
    return {key: left[key] & right[key] if key in left and key in right
            else left.get(key, right.get(key)) for key in left.keys() | right.keys()}


def _unparen(node):
    while type(node) is exp.Paren:
        node = node.this
    return node


def _semantic_review(reviewed, meanings):
    return SqlSemanticReview(reviewed.canonical_sql, reviewed.parameter_items,
                             reviewed.source_columns, reviewed.output_names, tuple(meanings))


def _review_comparison(tree, candidate, reviewed, available):
    intent = candidate.interpretation
    _require(not intent.group_by and tree.args.get("group") is None,
             "Comparação F1 exige totais sem agrupamento.")
    _require(tree.args.get("limit") is None and tree.args.get("order") is None,
             "Comparação de totais não admite truncamento ou ranking.")
    periods = [_period_months(period) for period in intent.periods]
    _require(periods[0] != periods[1], "Comparação exige janelas distinguíveis.")
    _require(all(months <= available for months in periods),
             "Período sem cobertura mensal completa.")
    dimensions = {F1_DIMENSIONS[item.dimension_id]: frozenset(item.values)
                  for item in intent.filters}
    expected = [{"competencia": months, **dimensions} for months in periods]
    parameters = dict(reviewed.parameter_items)
    where = tree.args.get("where")
    actual = _selection(where.this, parameters) if where is not None else {}
    _require(actual == {"competencia": periods[0] | periods[1], **dimensions},
             "Recorte global da comparação diverge das janelas ou filtros.")

    def period_index(node):
        node = _unparen(node)
        selection = actual
        if type(node) is exp.Filter:
            selection = _combine(actual, _selection(node.expression.this, parameters))
            node = node.this
        _require(type(node) is exp.Sum, "Total da comparação exige SUM verificável.")
        matches = [index for index, target in enumerate(expected) if selection == target]
        _require(len(matches) == 1, "Medida da comparação mistura ou troca janelas/filtros.")
        return matches[0]

    meanings = []
    for output in tree.expressions:
        expression = _unparen(output.this)
        if type(expression) is exp.Sub:
            _require(period_index(expression.this) == 0
                     and period_index(expression.expression) == 1,
                     "Diferença deve subtrair a segunda janela da primeira.")
            meaning = "period_0_minus_period_1"
        else:
            meaning = f"period_{period_index(expression)}_total"
        meanings.append((output.alias, meaning))
    _require({meaning for _, meaning in meanings} == {
        "period_0_total", "period_1_total", "period_0_minus_period_1",
    } and len(meanings) == 3, "Comparação exige dois totais e uma diferença em reais.")
    return _semantic_review(reviewed, meanings)


def _require(value, message):
    if not value:
        raise SqlStructureRejected(message)


def _month(value):
    _require(isinstance(value, str) and _MONTH.fullmatch(value) and value[:4] != "0000",
             "Competência SQL deve usar YYYY-MM.")
    year, month = map(int, value.split("-"))
    return (year - 1) * 12 + month - 1


def _selection(node, parameters):
    if type(node) is exp.Paren:
        return _selection(node.this, parameters)
    if type(node) in (exp.And, exp.Or):
        left = _selection(node.this, parameters)
        right = _selection(node.expression, parameters)
        if type(node) is exp.Or:
            _require(len(left) == 1 and left.keys() == right.keys(),
                     "OR entre recortes diferentes ainda não é verificável.")
            return {key: left[key] | right[key] for key in left}
        return _combine(left, right)
    column = node.this.name
    if type(node) is exp.In:
        values = [parameters[item.name] for item in node.expressions]
    elif type(node) is exp.Between:
        _require(column == "competencia", "BETWEEN de dimensão fora do subconjunto verificável.")
        low, high = (_month(parameters[node.args[key].name]) for key in ("low", "high"))
        return {column: frozenset(range(low, high + 1))}
    else:
        value = parameters[node.expression.name]
        if column == "competencia" and type(node) in (exp.GTE, exp.GT, exp.LTE, exp.LT):
            boundary = _month(value)
            low = boundary + (type(node) is exp.GT) if type(node) in (exp.GTE, exp.GT) else 0
            high = boundary + (type(node) is exp.LTE) if type(node) in (exp.LTE, exp.LT) else 9999 * 12
            return {column: frozenset(range(low, high))}
        _require(type(node) is exp.EQ, "Comparação fora do subconjunto verificável.")
        values = [value]
    return {column: frozenset(_month(value) for value in values) if column == "competencia"
            else frozenset(values)}


def review_sql_semantics(
    candidate: SqlGenerationCandidate, request: QuestionPlanRequest,
) -> SqlSemanticReview:
    reviewed = review_sql_structure(candidate, request)
    intent = candidate.interpretation
    _require(all(item.unit == "R$" for item in candidate.result_columns
                 if item.role == "measure"),
             "SQL F1 só retorna valores monetários; percentuais são derivados no Backend.")
    _require(not (_BACKEND_DERIVED_COLUMNS & {item.name for item in candidate.result_columns}),
             "Alias reservado para medida derivada pelo Backend.")
    _require((intent.operation != "monthly_series" or "competency" in intent.group_by)
             and (intent.operation not in ("grouped_total", "ranking") or bool(intent.group_by)),
             "Operação exige dimensões de agrupamento compatíveis.")
    tree = parse_one(reviewed.canonical_sql, read="postgres", error_message_context=0,
                     max_nodes=512)
    coverage = next(item for item in request.temporal_coverage if item.metric_id == "billing.revenue")
    available = frozenset(_month(value) for value in coverage.competencies)
    if intent.operation == "comparison":
        return _review_comparison(tree, candidate, reviewed, available)
    _require(not any(tree.find_all(exp.Filter, exp.Sub)),
             "Medida condicional fora do subconjunto verificável desta operação.")
    months = _period_months(intent.periods[0])
    _require(months <= available, "Período sem cobertura mensal completa.")
    expected = {"competencia": months}
    for item in intent.filters:
        expected[F1_DIMENSIONS[item.dimension_id]] = frozenset(item.values)
    where = tree.args.get("where")
    _require(where is not None, "Consulta exige recorte temporal explícito.")
    actual = _selection(where.this, dict(reviewed.parameter_items))
    _require(actual == expected, "Recortes SQL divergem da interpretação estruturada.")
    group = tree.args.get("group")
    actual_groups = {item.name for item in group.expressions} if group else set()
    _require(actual_groups == {_GROUPS[item] for item in intent.group_by},
             "Agrupamento SQL diverge da interpretação estruturada.")
    order, limit = tree.args.get("order"), tree.args.get("limit")
    if intent.operation == "ranking":
        _require(order is not None and len(order.expressions) >= 1 and limit is not None,
                 "Ranking exige ordenação e limite.")
        first = order.expressions[0]
        measures = {item.name for item in candidate.result_columns if item.role == "measure"}
        _require(not first.this.table and first.this.name in measures
                 and bool(first.args.get("desc")) == (intent.ranking_direction == "desc")
                 and first.args.get("nulls_first") is False
                 and int(limit.expression.this) == intent.ranking_limit,
                 "Ordenação ou limite SQL divergem do ranking solicitado.")
    else:
        _require(limit is None, "Consulta sem ranking não pode truncar o resultado.")
    return _semantic_review(reviewed, [(item.name, "revenue_total")
                                      for item in candidate.result_columns if item.role == "measure"])
