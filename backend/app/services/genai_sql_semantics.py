"""Conferência conservadora SQL/intenção F1; não é autorização de execução."""

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone

from sqlglot import exp, parse_one

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import F1_DIMENSIONS, build_sql_generation_context
from app.services.genai_sql_structure import (
    SqlStructureRejected,
    SqlStructureReview,
    review_sql_structure,
)

_GROUPS = {"competency": "competencia", "municipality": "municipio",
           "neighborhood": "bairro", "consumption_class": "classe_consumo",
           "feeder": "id_alimentador"}
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")
GROWTH_PERCENT_COLUMN = "period_0_growth_percent"
_BACKEND_DERIVED_COLUMNS = frozenset({GROWTH_PERCENT_COLUMN})


@dataclass(frozen=True)
class SqlSemanticReview(SqlStructureReview):
    """Linhagem inferida da AST; ainda depende de prontidão e autorização final."""

    measure_semantics: tuple[tuple[str, str], ...]
    measure_value_type: str = "decimal"


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
    _require("competency" not in intent.group_by,
             "Comparação não pode agrupar pelas competências das janelas.")
    expected_groups = {_GROUPS[item] for item in intent.group_by}
    group = tree.args.get("group")
    actual_groups = {item.name for item in group.expressions} if group else set()
    _require(actual_groups == expected_groups,
             "Agrupamento da comparação diverge da interpretação estruturada.")
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
    dimensions = {}
    for output, declared in zip(tree.expressions, candidate.result_columns, strict=True):
        expression = _unparen(output.this)
        if declared.role == "dimension":
            _require(type(expression) is exp.Column and expression.name in expected_groups,
                     "Dimensão projetada diverge do agrupamento solicitado.")
            dimensions[declared.name] = expression.name
            continue
        if type(expression) is exp.Sub:
            _require(period_index(expression.this) == 0
                     and period_index(expression.expression) == 1,
                     "Diferença deve subtrair a segunda janela da primeira.")
            meaning = "period_0_minus_period_1"
        else:
            meaning = f"period_{period_index(expression)}_total"
        meanings.append((output.alias, meaning))
    _require(set(dimensions.values()) == expected_groups,
             "Comparação exige todas as dimensões agrupadas no resultado.")
    _require({meaning for _, meaning in meanings} == {
        "period_0_total", "period_1_total", "period_0_minus_period_1",
    } and len(meanings) == 3, "Comparação exige dois totais e uma diferença em reais.")
    order, limit = tree.args.get("order"), tree.args.get("limit")
    if intent.ranking_direction is None:
        _require(order is None and limit is None,
                 "Comparação agrupada sem ranking não admite ordenação ou truncamento.")
    else:
        _require(order is not None
                 and limit is not None and len(order.expressions) == len(dimensions) + 1,
                 "Ranking de comparação exige diferença e desempate por todas as dimensões.")
        delta_alias = next(alias for alias, meaning in meanings
                           if meaning == "period_0_minus_period_1")
        first = order.expressions[0]
        _require(type(first.this) is exp.Column and not first.this.table
                 and first.this.name == delta_alias
                 and bool(first.args.get("desc")) == (intent.ranking_direction == "desc")
                 and first.args.get("nulls_first") is False,
                 "Ordenação do ranking diverge da diferença solicitada.")
        remaining_aliases = set(dimensions)
        for term in order.expressions[1:]:
            _require(type(term.this) is exp.Column and not term.this.table
                     and term.this.name in remaining_aliases
                     and term.args.get("desc") is False
                     and term.args.get("nulls_first") is False,
                     "Desempate deve ordenar cada dimensão ascendente e com nulos ao final.")
            remaining_aliases.remove(term.this.name)
        _require(int(limit.expression.this) == intent.ranking_limit,
                 "Limite SQL diverge do ranking solicitado.")
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
    context = json.loads(build_sql_generation_context(request).contents)
    metric = context["metric"]
    _require(intent.metric_id == metric["id"],
             "Métrica da interpretação diverge da pergunta e do contexto autorizado.")
    _require(intent.aggregation == metric["aggregation"],
             "Agregação da interpretação diverge da definição Gold autorizada.")
    _require(all(item.unit == metric["unit"] for item in candidate.result_columns
                 if item.role == "measure"),
             "Unidade SQL diverge da métrica; percentuais são derivados no Backend.")
    neighborhood_filters = [item for item in intent.filters
                            if item.dimension_id == "geography.neighborhood"]
    if neighborhood_filters:
        values = next((item["values"] for item in context["dimension_values"]
                       if item["dimension_id"] == "geography.neighborhood"), [])
        normalize = lambda value: "".join(
            char for char in unicodedata.normalize("NFD", value.casefold())
            if not unicodedata.combining(char)
        )
        authorized = {normalize(value) for value in values}
        _require(all(normalize(value) in authorized for item in neighborhood_filters
                     for value in item.values),
                 "Bairro solicitado não está no vocabulário Gold autorizado.")
    _require(not (_BACKEND_DERIVED_COLUMNS & {item.name for item in candidate.result_columns}),
             "Alias reservado para medida derivada pelo Backend.")
    _require((intent.operation != "monthly_series" or "competency" in intent.group_by)
             and (intent.operation not in ("grouped_total", "ranking") or bool(intent.group_by)),
             "Operação exige dimensões de agrupamento compatíveis.")
    tree = parse_one(reviewed.canonical_sql, read="postgres", error_message_context=0,
                     max_nodes=512)
    if intent.metric_id == "service.accumulated_attendance":
        _require(intent.operation == "accumulated_total"
                 and intent.aggregation == "sum" and not intent.periods
                 and not intent.filters and not intent.group_by
                 and intent.ranking_direction is None and intent.ranking_limit is None,
                 "Atendimento acumulado aceita somente o histórico total sem período.")
        _require(len(candidate.result_columns) == 1
                 and candidate.result_columns[0].role == "measure"
                 and candidate.result_columns[0].value_type == "integer"
                 and candidate.result_columns[0].unit == "protocolos",
                 "Atendimento acumulado exige total inteiro em protocolos.")
        output = tree.expressions[0]
        _require(type(output.this) is exp.Sum
                 and type(output.this.this) is exp.Column
                 and output.this.this.name == metric["measure_column"]
                 and tree.args.get("where") is None
                 and tree.args.get("group") is None
                 and tree.args.get("order") is None
                 and tree.args.get("limit") is None,
                 "Atendimento acumulado deve somar o histórico sem filtros ou períodos.")
        return replace(
            _semantic_review(reviewed, [(output.alias, "attendance_accumulated_total")]),
            measure_value_type="integer_sum",
        )
    coverage = next(item for item in request.temporal_coverage
                    if item.metric_id == intent.metric_id)
    available = frozenset(_month(value) for value in coverage.competencies)
    if intent.metric_id in {
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        feeder_filters = [item for item in intent.filters
                          if item.dimension_id == "network.feeder"]
        _require(intent.operation == "grain_read"
                 and intent.aggregation == "key_grain_read"
                 and len(intent.periods) == 1
                 and intent.periods[0].start == intent.periods[0].end.replace(day=1)
                 and len(_period_months(intent.periods[0])) == 1
                 and len(feeder_filters) == 1
                 and feeder_filters[0].operator == "eq"
                 and len(feeder_filters[0].values) == 1
                 and not intent.group_by
                 and intent.ranking_direction is None
                 and intent.ranking_limit is None,
                 "DEC/FEC admite somente leitura por alimentador em uma competência.")
        month = _period_months(intent.periods[0])
        _require(month <= available, "Competência sem cobertura mensal disponível.")
        expected = {
            "competencia": month,
            "id_alimentador": frozenset(feeder_filters[0].values),
        }
        where = tree.args.get("where")
        _require(where is not None
                 and _selection(where.this, dict(reviewed.parameter_items)) == expected,
                 "DEC/FEC exige competência e alimentador únicos no SQL.")
        _require(not tree.args.get("group") and not tree.args.get("order")
                 and not tree.args.get("limit")
                 and len(tree.expressions) == 1
                 and type(tree.expressions[0].this) is exp.Column
                 and tree.expressions[0].this.name == metric["measure_column"],
                 "DEC/FEC deve ler o valor físico sem agregar ou truncar.")
        expected_meaning = (
            "dec_value" if intent.metric_id == "network.equivalent_interruption_duration"
            else "fec_value"
        )
        return replace(
            _semantic_review(reviewed, [(tree.expressions[0].alias, expected_meaning)]),
            measure_value_type="double",
        )
    if intent.metric_id == "service.attendance":
        _require(intent.aggregation == "count_non_null" and intent.operation == "total"
                 and not intent.group_by and not intent.filters and len(intent.periods) == 1,
                 "Atendimento SQL F1 libera somente a contagem mensal total.")
        _require(all(item.value_type == "integer" and item.unit == "protocolos"
                     for item in candidate.result_columns if item.role == "measure"),
                 "Atendimento exige medida inteira em protocolos.")
        months = _period_months(intent.periods[0])
        _require(months <= available, "Período sem cobertura mensal completa.")
        expected_start = datetime.combine(intent.periods[0].start, time.min, tzinfo=timezone.utc)
        expected_end = datetime.combine(intent.periods[0].end + timedelta(days=1), time.min,
                                        tzinfo=timezone.utc)
        parameters = dict(reviewed.parameter_items)
        where = tree.args.get("where")
        _require(where is not None and type(where.this) is exp.And,
                 "Contagem de atendimento exige limites mensais UTC explícitos.")
        predicates = (where.this.this, where.this.expression)
        actual = {}
        for predicate in predicates:
            _require(type(predicate) in (exp.GTE, exp.LT)
                     and type(predicate.this) is exp.Column
                     and predicate.this.name == "data_abertura"
                     and type(predicate.expression) is exp.Placeholder,
                     "Recorte de atendimento deve limitar data_abertura em UTC.")
            actual[type(predicate)] = parameters[predicate.expression.name]
        _require(actual == {exp.GTE: expected_start, exp.LT: expected_end},
                 "Limites SQL divergem do mês solicitado em UTC.")
        _require(not tree.args.get("group") and not tree.args.get("order")
                 and not tree.args.get("limit"),
                 "Contagem mensal total de atendimento não admite agrupamento ou limite.")
        _require(all(type(output.this) is exp.Count
                     and type(output.this.this) is exp.Column
                     and output.this.this.name == "protocolo"
                     for output in tree.expressions),
                 "Atendimento deve contar protocolos não nulos.")
        semantics = [(item.name, "attendance_total") for item in candidate.result_columns
                     if item.role == "measure"]
        return replace(_semantic_review(reviewed, semantics), measure_value_type="integer")
    if intent.operation == "comparison":
        result = _review_comparison(tree, candidate, reviewed, available)
        return replace(result, measure_value_type=metric["measure_type"])
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
    total_meaning = "energy_total" if intent.metric_id == "energy.consumption" else "revenue_total"
    result = _semantic_review(reviewed, [(item.name, total_meaning)
                                         for item in candidate.result_columns
                                         if item.role == "measure"])
    return replace(result, measure_value_type=metric["measure_type"])
