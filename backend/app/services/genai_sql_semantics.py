"""Conferência conservadora SQL/intenção F1; não é autorização de execução."""

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta

from sqlglot import exp, parse_one

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import (
    F1_DIMENSIONS,
    build_sql_generation_context,
    mentions_gd,
    requested_gd_filter_value,
)
from app.services.genai_sql_structure import (
    SqlStructureRejected,
    SqlStructureReview,
    review_sql_structure,
)

_GROUPS = {
    "competency": "competencia",
    "municipality": "municipio",
    "neighborhood": "bairro",
    "consumption_class": "classe_consumo",
    "feeder": "id_alimentador",
    "inspection_priority": "prioridade_inspecao",
}
_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")
GROWTH_PERCENT_COLUMN = "period_0_growth_percent"
_BACKEND_DERIVED_COLUMNS = frozenset({GROWTH_PERCENT_COLUMN})


@dataclass(frozen=True)
class SqlSemanticReview(SqlStructureReview):
    """Linhagem inferida da AST; ainda depende de prontidão e autorização final."""

    measure_semantics: tuple[tuple[str, str], ...]
    measure_value_type: str = "decimal"


def _period_months(period):
    return frozenset(
        range(
            (period.start.year - 1) * 12 + period.start.month - 1,
            (period.end.year - 1) * 12 + period.end.month,
        )
    )


def _combine(left, right):
    return {
        key: left[key] & right[key]
        if key in left and key in right
        else left.get(key, right.get(key))
        for key in left.keys() | right.keys()
    }


def _unparen(node):
    while type(node) is exp.Paren:
        node = node.this
    return node


def _semantic_review(reviewed, meanings):
    return SqlSemanticReview(
        reviewed.canonical_sql,
        reviewed.parameter_items,
        reviewed.source_columns,
        reviewed.output_names,
        tuple(meanings),
    )


def _review_comparison(tree, candidate, reviewed, available, request):
    intent = candidate.interpretation
    _require(
        "competency" not in intent.group_by,
        "Comparação não pode agrupar pelas competências das janelas.",
    )
    expected_groups = {_GROUPS[item] for item in intent.group_by}
    group = tree.args.get("group")
    actual_groups = {item.name for item in group.expressions} if group else set()
    _require(
        actual_groups == expected_groups,
        "Agrupamento da comparação diverge da interpretação estruturada.",
    )
    periods = [_period_months(period) for period in intent.periods]
    _require(periods[0] != periods[1], "Comparação exige janelas distinguíveis.")
    _require(
        all(months <= available for months in periods),
        "Período sem cobertura mensal completa.",
    )
    dimensions = {
        F1_DIMENSIONS[item.dimension_id]: frozenset(item.values)
        for item in intent.filters
    }
    expected = [{"competencia": months, **dimensions} for months in periods]
    parameters = dict(reviewed.parameter_items)
    where = tree.args.get("where")
    actual = _selection(where.this, parameters) if where is not None else {}
    _require(
        actual == {"competencia": periods[0] | periods[1], **dimensions},
        "Recorte global da comparação diverge das janelas ou filtros.",
    )

    def period_index(node):
        node = _unparen(node)
        selection = actual
        if type(node) is exp.Filter:
            selection = _combine(actual, _selection(node.expression.this, parameters))
            node = node.this
        _require(type(node) is exp.Sum, "Total da comparação exige SUM verificável.")
        matches = [
            index for index, target in enumerate(expected) if selection == target
        ]
        _require(
            len(matches) == 1, "Medida da comparação mistura ou troca janelas/filtros."
        )
        return matches[0]

    meanings = []
    dimensions = {}
    for output, declared in zip(
        tree.expressions, candidate.result_columns, strict=True
    ):
        expression = _unparen(output.this)
        if declared.role == "dimension":
            _require(
                type(expression) is exp.Column and expression.name in expected_groups,
                "Dimensão projetada diverge do agrupamento solicitado.",
            )
            dimensions[declared.name] = expression.name
            continue
        if type(expression) is exp.Sub:
            left_period = period_index(expression.this)
            right_period = period_index(expression.expression)
            _require(
                (left_period, right_period) in {(0, 1), (1, 0)},
                "Diferença deve comparar as duas janelas selecionadas.",
            )
            meaning = f"period_{left_period}_minus_period_{right_period}"
        else:
            meaning = f"period_{period_index(expression)}_total"
        meanings.append((output.alias, meaning))
    _require(
        set(dimensions.values()) == expected_groups,
        "Comparação exige todas as dimensões agrupadas no resultado.",
    )
    delta_meanings = {
        "period_0_minus_period_1",
        "period_1_minus_period_0",
    }
    present_meanings = {meaning for _, meaning in meanings}
    _require(
        {"period_0_total", "period_1_total"} <= present_meanings
        and len(present_meanings & delta_meanings) == 1
        and len(meanings) == 3,
        "Comparação exige dois totais e uma diferença entre as janelas.",
    )
    normalized_question = unicodedata.normalize("NFKD", request.question.casefold())
    normalized_question = "".join(
        char for char in normalized_question if not unicodedata.combining(char)
    )
    delta_meaning = next(iter(present_meanings & delta_meanings))
    if re.search(r"\b(?:aumento|aumentou|crescimento|subida)\b", normalized_question):
        _require(
            delta_meaning == "period_1_minus_period_0",
            "Aumento deve subtrair o período inicial do período final.",
        )
    if re.search(r"\b(?:queda|reducao|diminuicao)\b", normalized_question):
        _require(
            delta_meaning == "period_0_minus_period_1",
            "Queda deve subtrair o período final do período inicial.",
        )
    has_explicit_direction = re.search(
        r"\b(?:aumento|aumentou|crescimento|subida|queda|reducao|diminuicao)\b",
        normalized_question,
    )
    grouped_comparison = bool(candidate.interpretation.group_by) and bool(
        re.search(r"\b(?:compare|comparar|comparacao)\b", normalized_question)
    )
    if not has_explicit_direction and (
        re.search(r"\bvariacao\b", normalized_question) or grouped_comparison
    ):
        _require(
            delta_meaning == "period_1_minus_period_0",
            "Variação agrupada deve subtrair o período inicial do período final.",
        )
    elif not has_explicit_direction:
        _require(
            delta_meaning == "period_0_minus_period_1",
            "Diferença deve preservar a ordem dos períodos declarados.",
        )
    order, limit = tree.args.get("order"), tree.args.get("limit")
    if intent.ranking_direction is None:
        _require(
            order is None and limit is None,
            "Comparação agrupada sem ranking não admite ordenação ou truncamento.",
        )
    else:
        _require(
            order is not None
            and limit is not None
            and len(order.expressions) == len(dimensions) + 1,
            "Ranking de comparação exige diferença e desempate por todas as dimensões.",
        )
        delta_alias = next(
            alias for alias, meaning in meanings if meaning == delta_meaning
        )
        first = order.expressions[0]
        _require(
            type(first.this) is exp.Column
            and not first.this.table
            and first.this.name == delta_alias
            and bool(first.args.get("desc")) == (intent.ranking_direction == "desc")
            and first.args.get("nulls_first") is False,
            "Ordenação do ranking diverge da diferença solicitada.",
        )
        remaining_aliases = set(dimensions)
        for term in order.expressions[1:]:
            _require(
                type(term.this) is exp.Column
                and not term.this.table
                and term.this.name in remaining_aliases
                and term.args.get("desc") is False
                and term.args.get("nulls_first") is False,
                "Desempate deve ordenar cada dimensão ascendente e com nulos ao final.",
            )
            remaining_aliases.remove(term.this.name)
        _require(
            int(limit.expression.this) == intent.ranking_limit,
            "Limite SQL diverge do ranking solicitado.",
        )
    return _semantic_review(reviewed, meanings)


def _require(value, message):
    if not value:
        raise SqlStructureRejected(message)


def _month(value):
    _require(
        isinstance(value, str) and _MONTH.fullmatch(value) and value[:4] != "0000",
        "Competência SQL deve usar YYYY-MM.",
    )
    year, month = map(int, value.split("-"))
    return (year - 1) * 12 + month - 1


def _selection(node, parameters):
    if type(node) is exp.Paren:
        return _selection(node.this, parameters)
    if type(node) in (exp.And, exp.Or):
        left = _selection(node.this, parameters)
        right = _selection(node.expression, parameters)
        if type(node) is exp.Or:
            _require(
                len(left) == 1 and left.keys() == right.keys(),
                "OR entre recortes diferentes ainda não é verificável.",
            )
            return {key: left[key] | right[key] for key in left}
        return _combine(left, right)
    column = node.this.name
    if type(node) is exp.In:
        values = [parameters[item.name] for item in node.expressions]
    elif type(node) is exp.Between:
        _require(
            column == "competencia",
            "BETWEEN de dimensão fora do subconjunto verificável.",
        )
        low, high = (_month(parameters[node.args[key].name]) for key in ("low", "high"))
        return {column: frozenset(range(low, high + 1))}
    else:
        value = parameters[node.expression.name]
        if column in {"meses_com_leitura_p1", "meses_com_leitura_p2"} and type(node) is exp.GTE:
            _require(type(value) is int, "Mínimo de leituras exige parâmetro inteiro.")
            return {column: frozenset({("gte", value)})}
        if column == "competencia" and type(node) in (exp.GTE, exp.GT, exp.LTE, exp.LT):
            boundary = _month(value)
            low = (
                boundary + (type(node) is exp.GT)
                if type(node) in (exp.GTE, exp.GT)
                else 0
            )
            high = (
                boundary + (type(node) is exp.LTE)
                if type(node) in (exp.LTE, exp.LT)
                else 9999 * 12
            )
            return {column: frozenset(range(low, high))}
        _require(type(node) is exp.EQ, "Comparação fora do subconjunto verificável.")
        values = [value]
    return {
        column: frozenset(_month(value) for value in values)
        if column == "competencia"
        else frozenset(values)
    }


def review_sql_semantics(
    candidate: SqlGenerationCandidate,
    request: QuestionPlanRequest,
) -> SqlSemanticReview:
    reviewed = review_sql_structure(candidate, request)
    intent = candidate.interpretation
    context = json.loads(build_sql_generation_context(request).contents)
    metric = context["metric"]
    _require(
        intent.metric_id == metric["id"],
        "Métrica da interpretação diverge da pergunta e do contexto autorizado.",
    )
    if intent.operation == "weighted_continuity":
        meaning = (
            "dec_value"
            if intent.metric_id == "network.equivalent_interruption_duration"
            else "fec_value"
        )
        _require(
            intent.aggregation == "weighted_ratio"
            and intent.metric_id.startswith("network.equivalent_interruption_")
            and tuple(item.name for item in candidate.result_columns)
            == (meaning, "feeders_included", "feeders_excluded")
            and candidate.result_columns[0].unit == metric["unit"]
            and all(
                item.unit == "alimentadores" and item.value_type == "integer"
                for item in candidate.result_columns[1:]
            ),
            "DEC/FEC ponderado diverge da unidade, operação ou contrato Gold.",
        )
        return SqlSemanticReview(
            reviewed.canonical_sql,
            reviewed.parameter_items,
            reviewed.source_columns,
            reviewed.output_names,
            (
                (meaning, meaning),
                ("feeders_included", "feeders_included"),
                ("feeders_excluded", "feeders_excluded"),
            ),
        )
    _require(
        intent.aggregation == metric["aggregation"],
        "Agregação da interpretação diverge da definição Gold autorizada.",
    )
    _require(
        all(
            item.unit == metric["unit"]
            for item in candidate.result_columns
            if item.role == "measure"
        ),
        "Unidade SQL diverge da métrica; percentuais são derivados no Backend.",
    )
    neighborhood_filters = [
        item for item in intent.filters if item.dimension_id == "geography.neighborhood"
    ]
    if neighborhood_filters:
        values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == "geography.neighborhood"
            ),
            [],
        )
        normalize = lambda value: "".join(
            char
            for char in unicodedata.normalize("NFD", value.casefold())
            if not unicodedata.combining(char)
        )
        authorized = {normalize(value) for value in values}
        _require(
            all(
                normalize(value) in authorized
                for item in neighborhood_filters
                for value in item.values
            ),
            "Bairro solicitado não está no vocabulário Gold autorizado.",
        )
    normalized_question = unicodedata.normalize("NFKD", request.question.casefold())
    normalized_question = "".join(
        char for char in normalized_question if not unicodedata.combining(char)
    )
    for dimension_id in ("tariff.subgroup", "tariff.flag"):
        dimension_filters = [
            item for item in intent.filters if item.dimension_id == dimension_id
        ]
        if not dimension_filters:
            continue
        values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == dimension_id
            ),
            [],
        )
        normalize = lambda value: "".join(
            char
            for char in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(char)
        )
        authorized = {normalize(value) for value in values}
        requested = {
            normalize(value)
            for item in dimension_filters
            for value in item.values
        }
        _require(
            requested <= authorized
            and all(
                re.search(
                    rf"(?<![\w]){re.escape(value)}(?![\w])",
                    normalized_question,
                )
                for value in requested
            ),
            "Filtro tarifário precisa estar explícito e no vocabulário Gold autorizado.",
        )
    municipality_filters = [
        item for item in intent.filters if item.dimension_id == "geography.municipality"
    ]
    if municipality_filters and intent.metric_id == "energy.gd_consumption_drop":
        values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == "geography.municipality"
            ),
            [],
        )
        normalize = lambda value: "".join(
            char
            for char in unicodedata.normalize("NFD", value.casefold())
            if not unicodedata.combining(char)
        )
        authorized = {normalize(value) for value in values}
        _require(
            all(
                normalize(value) in authorized
                for item in municipality_filters
                for value in item.values
            ),
            "Município solicitado não está no vocabulário Gold autorizado.",
        )
    gd_filters = [
        item for item in intent.filters if item.dimension_id == "generation.distributed"
    ]
    expected_gd = requested_gd_filter_value(request.question, request.context)
    if intent.metric_id == "energy.gd_units":
        gd_values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == "generation.distributed"
            ),
            [],
        )
        _require(
            len(gd_filters) == 1
            and gd_filters[0].operator == "eq"
            and gd_filters[0].values == ("Sim",)
            and "Sim" in gd_values,
            "Contagem de UCs com GD exige o filtro cadastral aprovado.",
        )
    elif intent.metric_id == "energy.gd_consumption_drop":
        gd_values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == "generation.distributed"
            ),
            [],
        )
        _require(
            expected_gd == "Sim"
            and len(gd_filters) == 1
            and gd_filters[0].operator == "eq"
            and gd_filters[0].values == ("Sim",)
            and "Sim" in gd_values,
            "Queda de consumo exige GD cadastral explícita e autorizada.",
        )
    elif expected_gd is None:
        _require(
            not mentions_gd(request.question, request.context),
            "Pedido de GD ambíguo exige esclarecimento.",
        )
        _require(not gd_filters, "Filtro GD não foi solicitado explicitamente.")
    else:
        _require(
            intent.metric_id in {
                "energy.consumption",
                "energy.average_consumption_per_uc",
                "billing.average_ticket",
                "billing.effective_tariff",
                "billing.revenue",
            }
            and len(gd_filters) == 1
            and gd_filters[0].operator == "eq"
            and len(gd_filters[0].values) == 1,
            "Consumo com GD exige o filtro cadastral explícito.",
        )
        normalize = lambda value: "".join(
            char
            for char in unicodedata.normalize("NFD", value.casefold())
            if not unicodedata.combining(char)
        )
        gd_values = next(
            (
                item["values"]
                for item in context["dimension_values"]
                if item["dimension_id"] == "generation.distributed"
            ),
            [],
        )
        expected_value = normalize(expected_gd)
        _require(
            normalize(gd_filters[0].values[0]) == expected_value
            and expected_value in {normalize(value) for value in gd_values},
            "Filtro GD diverge da pergunta ou do vocabulário Gold.",
        )
    _require(
        not (
            _BACKEND_DERIVED_COLUMNS & {item.name for item in candidate.result_columns}
        ),
        "Alias reservado para medida derivada pelo Backend.",
    )
    _require(
        (intent.operation != "monthly_series" or "competency" in intent.group_by)
        and (
            intent.operation not in ("grouped_total", "ranking")
            or bool(intent.group_by)
        ),
        "Operação exige dimensões de agrupamento compatíveis.",
    )
    tree = parse_one(
        reviewed.canonical_sql, read="postgres", error_message_context=0, max_nodes=512
    )
    if intent.metric_id == "service.accumulated_attendance":
        _require(
            intent.operation == "accumulated_total"
            and intent.aggregation == "sum"
            and not intent.periods
            and not intent.filters
            and intent.group_by in (
                (),
                ("consumption_class",) if intent.metric_id == "customer.units_by_class"
                else ("inspection_priority",),
            )
            and intent.ranking_direction is None
            and intent.ranking_limit is None,
            "Atendimento acumulado aceita somente o histórico total sem período.",
        )
        _require(
            len(candidate.result_columns) == 1
            and candidate.result_columns[0].role == "measure"
            and candidate.result_columns[0].value_type == "integer"
            and candidate.result_columns[0].unit == "protocolos",
            "Atendimento acumulado exige total inteiro em protocolos.",
        )
        output = tree.expressions[0]
        _require(
            type(output.this) is exp.Sum
            and type(output.this.this) is exp.Column
            and output.this.this.name == metric["measure_column"]
            and tree.args.get("where") is None
            and tree.args.get("group") is None
            and tree.args.get("order") is None
            and tree.args.get("limit") is None,
            "Atendimento acumulado deve somar o histórico sem filtros ou períodos.",
        )
        return replace(
            _semantic_review(
                reviewed, [(output.alias, "attendance_accumulated_total")]
            ),
            measure_value_type="integer_sum",
        )
    if intent.metric_id == "service.accumulated_satisfaction":
        _require(
            intent.operation == "accumulated_average"
            and not intent.periods
            and intent.aggregation == "average_non_null"
            and not intent.filters
            and not intent.group_by
            and intent.ranking_direction is None
            and intent.ranking_limit is None,
            "Satisfação acumulada aceita somente média sem período ou recortes.",
        )
        _require(
            len(candidate.result_columns) == 1
            and candidate.result_columns[0].role == "measure"
            and candidate.result_columns[0].value_type == "decimal"
            and candidate.result_columns[0].unit == "pontos",
            "Satisfação acumulada exige média decimal em pontos.",
        )
        _require(
            len(tree.expressions) == 1
            and type(tree.expressions[0].this) is exp.Avg
            and type(tree.expressions[0].this.this) is exp.Column
            and tree.expressions[0].this.this.name == metric["measure_column"]
            and tree.args.get("where") is None
            and tree.args.get("group") is None
            and tree.args.get("order") is None
            and tree.args.get("limit") is None,
            "Satisfação acumulada deve ser a média das notas individuais publicadas.",
        )
        return replace(
            _semantic_review(
                reviewed,
                [
                    (tree.expressions[0].alias, "satisfaction_accumulated_average"),
                ],
            ),
            measure_value_type="double",
        )
    if intent.metric_id == "energy.gd_units":
        _require(
            intent.operation == "snapshot_total"
            and not intent.periods
            and intent.aggregation == "count_non_null"
            and intent.ranking_direction is None
            and intent.ranking_limit is None,
            "Contagem de GD aceita somente o retrato cadastral do lote.",
        )
        _require(
            len(candidate.result_columns) in (1, 2)
            and all(
                item.value_type == "integer" and item.unit == "UCs"
                for item in candidate.result_columns
                if item.role == "measure"
            ),
            "Contagem de GD exige medida inteira em UCs.",
        )
        expected = {"possui_gd": frozenset({"Sim"})}
        for item in intent.filters:
            if item.dimension_id != "generation.distributed":
                expected[F1_DIMENSIONS[item.dimension_id]] = frozenset(item.values)
        where = tree.args.get("where")
        _require(
            where is not None
            and _selection(where.this, dict(reviewed.parameter_items)) == expected,
            "Recorte SQL deve preservar GD cadastrada e filtros geográficos pedidos.",
        )
        _require(
            not any(
                item.dimension_id
                not in {"generation.distributed", "geography.municipality"}
                for item in intent.filters
            )
            and intent.group_by in ((), ("municipality",)),
            "Contagem de GD só admite o agrupamento legado por município.",
        )
        _require(
            all(
                type(output.this) is exp.Count
                and type(output.this.this) is exp.Column
                and output.this.this.name == "possui_gd"
                for output in tree.expressions
                if output.alias
                in {
                    item.name
                    for item in candidate.result_columns
                    if item.role == "measure"
                }
            ),
            "Contagem de GD deve contar os registros cadastrais da fonte aprovada.",
        )
        return replace(
            _semantic_review(
                reviewed,
                [
                    (item.name, "gd_units_total")
                    for item in candidate.result_columns
                    if item.role == "measure"
                ],
            ),
            measure_value_type="integer",
        )
    if intent.metric_id == "energy.gd_consumption_drop":
        _require(
            intent.operation == "snapshot_total"
            and not intent.periods
            and intent.aggregation == "count_gd_drop"
            and intent.ranking_direction is None
            and intent.ranking_limit is None,
            "Queda com GD aceita somente o retrato das janelas fixas aprovadas.",
        )
        _require(
            len(candidate.result_columns) in (1, 2)
            and all(
                item.value_type == "integer" and item.unit == "UCs"
                for item in candidate.result_columns
                if item.role == "measure"
            ),
            "Queda com GD exige contagem inteira de UCs elegíveis.",
        )
        expected = {
            "possui_gd": frozenset({"Sim"}),
            "queda_consumo_superior_30_pct": frozenset({True}),
            "meses_com_leitura_p1": frozenset({("gte", 6)}),
            "meses_com_leitura_p2": frozenset({("gte", 6)}),
        }
        for item in intent.filters:
            if item.dimension_id != "generation.distributed":
                expected[F1_DIMENSIONS[item.dimension_id]] = frozenset(item.values)
        where = tree.args.get("where")
        _require(
            where is not None
            and _selection(where.this, dict(reviewed.parameter_items)) == expected,
            "SQL deve contar somente UCs com GD e flag de queda aprovada.",
        )
        _require(
            not any(
                item.dimension_id
                not in {"generation.distributed", "geography.municipality"}
                for item in intent.filters
            )
            and intent.group_by in ((), ("municipality",)),
            "Queda com GD só admite o recorte legado por município.",
        )
        _require(
            all(
                type(output.this) is exp.Count
                and type(output.this.this) is exp.Column
                and output.this.this.name == "queda_consumo_superior_30_pct"
                for output in tree.expressions
                if output.alias
                in {
                    item.name
                    for item in candidate.result_columns
                    if item.role == "measure"
                }
            ),
            "Contagem deve usar a flag booleana reconciliada pela Gold.",
        )
        return replace(
            _semantic_review(
                reviewed,
                [
                    (item.name, "gd_consumption_drop_units")
                    for item in candidate.result_columns
                    if item.role == "measure"
                ],
            ),
            measure_value_type="integer",
        )
    if intent.metric_id in {"customer.units_by_class", "inspection.units_by_priority"}:
        dimension_id = (
            "customer.consumption_class"
            if intent.metric_id == "customer.units_by_class"
            else "inspection.priority"
        )
        dimension_column = context["dimensions"][dimension_id]
        source_table = context["source"]["table"]
        expected_source = (
            "visao_360_uc"
            if intent.metric_id == "customer.units_by_class"
            else "fila_inspecao"
        )
        _require(
            source_table == expected_source
            and intent.operation == "snapshot_total"
            and intent.aggregation == "count_distinct"
            and not intent.periods
            and intent.group_by in (
                (),
                ("consumption_class",)
                if intent.metric_id == "customer.units_by_class"
                else ("inspection_priority",),
            )
            and intent.ranking_direction is None
            and intent.ranking_limit is None
            and all(item.dimension_id == dimension_id for item in intent.filters),
            "Contagem cadastral exige retrato Gold e somente o recorte aprovado.",
        )
        allowed = next(
            (item["values"] for item in context["dimension_values"]
             if item["dimension_id"] == dimension_id),
            [],
        )
        requested = {value.casefold() for item in intent.filters for value in item.values}
        if intent.metric_id == "inspection.units_by_priority":
            # The category is approved by the Gold semantic vocabulary. Its
            # absence in this publication is a valid zero, not missing coverage.
            allowed = [*allowed, "ALTA - CONSUMO ZERO"]
            normalized_question = unicodedata.normalize(
                "NFKD", request.question.casefold()
            )
            normalized_question = "".join(
                char for char in normalized_question
                if not unicodedata.combining(char)
            )
            if re.search(r"\bconsumo\s+zero\b", normalized_question):
                _require(
                    requested == {"alta - consumo zero"},
                    "Consumo zero exige a categoria Gold ALTA - CONSUMO ZERO.",
                )
        _require(
            requested <= {value.casefold() for value in allowed},
            "Filtro cadastral fora do vocabulário observado na Gold.",
        )
        expected = {
            dimension_column: frozenset(
                value for item in intent.filters for value in item.values
            )
        } if intent.filters else {}
        where = tree.args.get("where")
        actual = _selection(where.this, dict(reviewed.parameter_items)) if where else {}
        _require(actual == expected, "Filtro SQL diverge do retrato cadastral solicitado.")
        groups = tree.args.get("group")
        actual_groups = {item.name for item in groups.expressions} if groups else set()
        expected_groups = {dimension_column} if intent.group_by else set()
        order = tree.args.get("order")
        dimension_aliases = {
            item.name
            for item in candidate.result_columns
            if item.role == "dimension"
        }
        order_is_dimension_ascending = (
            order is None
            or (
                intent.group_by
                and len(order.expressions) == 1
                and type(order.expressions[0]) is exp.Ordered
                and type(order.expressions[0].this) is exp.Column
                and order.expressions[0].this.name
                in ({dimension_column} | dimension_aliases)
                and not order.expressions[0].args.get("desc")
            )
        )
        measure_outputs = [
            (output, declared)
            for output, declared in zip(tree.expressions, candidate.result_columns, strict=True)
            if declared.role == "measure"
        ]
        dimension_outputs = [
            (output, declared)
            for output, declared in zip(tree.expressions, candidate.result_columns, strict=True)
            if declared.role == "dimension"
        ]
        _require(
            actual_groups == expected_groups
            and order_is_dimension_ascending
            and not tree.args.get("limit")
            and len(measure_outputs) == 1
            and len(dimension_outputs) == (1 if intent.group_by else 0)
            and measure_outputs[0][1].value_type == "integer"
            and measure_outputs[0][1].unit == "UCs"
            and type(measure_outputs[0][0].this) is exp.Count
            and type(measure_outputs[0][0].this.this) is exp.Distinct
            and len(measure_outputs[0][0].this.this.expressions) == 1
            and type(measure_outputs[0][0].this.this.expressions[0]) is exp.Column
            and measure_outputs[0][0].this.this.expressions[0].name == "id_uc"
            and all(
                type(output.this) is exp.Column
                and output.this.name == dimension_column
                and declared.role == "dimension"
                for output, declared in dimension_outputs
            ),
            "Contagem cadastral deve contar UCs distintas no retrato e grupo autorizado.",
        )
        return replace(
            _semantic_review(
                reviewed,
                [(output.alias, "units_count") for output, _ in measure_outputs],
            ),
            measure_value_type="integer",
        )
    coverage = next(
        item for item in request.temporal_coverage if item.metric_id == intent.metric_id
    )
    available = frozenset(_month(value) for value in coverage.competencies)
    if intent.metric_id in {
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        feeder_filters = [
            item for item in intent.filters if item.dimension_id == "network.feeder"
        ]
        _require(
            intent.operation == "grain_read"
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
            "DEC/FEC admite somente leitura por alimentador em uma competência.",
        )
        month = _period_months(intent.periods[0])
        _require(month <= available, "Competência sem cobertura mensal disponível.")
        expected = {
            "competencia": month,
            "id_alimentador": frozenset(feeder_filters[0].values),
        }
        where = tree.args.get("where")
        _require(
            where is not None
            and _selection(where.this, dict(reviewed.parameter_items)) == expected,
            "DEC/FEC exige competência e alimentador únicos no SQL.",
        )
        _require(
            not tree.args.get("group")
            and not tree.args.get("order")
            and not tree.args.get("limit")
            and len(tree.expressions) == 1
            and type(tree.expressions[0].this) is exp.Column
            and tree.expressions[0].this.name == metric["measure_column"],
            "DEC/FEC deve ler o valor físico sem agregar ou truncar.",
        )
        expected_meaning = (
            "dec_value"
            if intent.metric_id == "network.equivalent_interruption_duration"
            else "fec_value"
        )
        return replace(
            _semantic_review(reviewed, [(tree.expressions[0].alias, expected_meaning)]),
            measure_value_type="double",
        )
    if intent.metric_id == "service.attendance":
        _require(
            intent.aggregation == "count_non_null"
            and intent.operation == "total"
            and not intent.group_by
            and not intent.filters
            and len(intent.periods) == 1,
            "Atendimento SQL F1 libera somente a contagem mensal total.",
        )
        _require(
            all(
                item.value_type == "integer" and item.unit == "protocolos"
                for item in candidate.result_columns
                if item.role == "measure"
            ),
            "Atendimento exige medida inteira em protocolos.",
        )
        months = _period_months(intent.periods[0])
        _require(months <= available, "Período sem cobertura mensal completa.")
        expected_start = datetime.combine(intent.periods[0].start, time.min, tzinfo=UTC)
        expected_end = datetime.combine(
            intent.periods[0].end + timedelta(days=1), time.min, tzinfo=UTC
        )
        parameters = dict(reviewed.parameter_items)
        where = tree.args.get("where")
        _require(
            where is not None and type(where.this) is exp.And,
            "Contagem de atendimento exige limites mensais UTC explícitos.",
        )
        predicates = (where.this.this, where.this.expression)
        actual = {}
        for predicate in predicates:
            _require(
                type(predicate) in (exp.GTE, exp.LT)
                and type(predicate.this) is exp.Column
                and predicate.this.name == "data_abertura"
                and type(predicate.expression) is exp.Placeholder,
                "Recorte de atendimento deve limitar data_abertura em UTC.",
            )
            actual[type(predicate)] = parameters[predicate.expression.name]
        _require(
            actual == {exp.GTE: expected_start, exp.LT: expected_end},
            "Limites SQL divergem do mês solicitado em UTC.",
        )
        _require(
            not tree.args.get("group")
            and not tree.args.get("order")
            and not tree.args.get("limit"),
            "Contagem mensal total de atendimento não admite agrupamento ou limite.",
        )
        _require(
            all(
                type(output.this) is exp.Count
                and type(output.this.this) is exp.Column
                and output.this.this.name == "protocolo"
                for output in tree.expressions
            ),
            "Atendimento deve contar protocolos não nulos.",
        )
        semantics = [
            (item.name, "attendance_total")
            for item in candidate.result_columns
            if item.role == "measure"
        ]
        return replace(
            _semantic_review(reviewed, semantics), measure_value_type="integer"
        )
    if intent.metric_id == "service.satisfaction":
        _require(
            intent.aggregation == "average_non_null"
            and intent.operation == "average"
            and not intent.group_by
            and not intent.filters
            and len(intent.periods) == 1,
            "Satisfação F1 libera somente a média mensal sem recortes.",
        )
        _require(
            len(candidate.result_columns) == 1
            and candidate.result_columns[0].role == "measure"
            and candidate.result_columns[0].value_type == "decimal"
            and candidate.result_columns[0].unit == "pontos",
            "Satisfação exige uma média decimal em pontos.",
        )
        months = _period_months(intent.periods[0])
        _require(months <= available, "Período sem cobertura mensal completa.")
        expected_start = datetime.combine(intent.periods[0].start, time.min, tzinfo=UTC)
        expected_end = datetime.combine(
            intent.periods[0].end + timedelta(days=1), time.min, tzinfo=UTC
        )
        parameters = dict(reviewed.parameter_items)
        where = tree.args.get("where")
        _require(
            where is not None and type(where.this) is exp.And,
            "Média de satisfação exige limites mensais UTC explícitos.",
        )
        predicates = (where.this.this, where.this.expression)
        actual = {}
        for predicate in predicates:
            _require(
                type(predicate) in (exp.GTE, exp.LT)
                and type(predicate.this) is exp.Column
                and predicate.this.name == "data_abertura"
                and type(predicate.expression) is exp.Placeholder,
                "Recorte de satisfação deve limitar data_abertura em UTC.",
            )
            actual[type(predicate)] = parameters[predicate.expression.name]
        _require(
            actual == {exp.GTE: expected_start, exp.LT: expected_end},
            "Limites SQL divergem do mês solicitado em UTC.",
        )
        _require(
            not tree.args.get("group")
            and not tree.args.get("order")
            and not tree.args.get("limit"),
            "Média mensal de satisfação não admite agrupamento ou limite.",
        )
        output = tree.expressions[0]
        _require(
            type(output.this) is exp.Avg
            and type(output.this.this) is exp.Column
            and output.this.this.name == "nota_satisfacao",
            "Satisfação deve calcular AVG(nota_satisfacao); zero é valor válido.",
        )
        return replace(
            _semantic_review(reviewed, [(output.alias, "satisfaction_average")]),
            measure_value_type="double",
        )
    if intent.metric_id in {
        "energy.average_consumption_per_uc",
        "billing.average_ticket",
        "billing.effective_tariff",
    }:
        _require(
            intent.aggregation == "ratio_of_sums"
            and intent.operation == "ratio_of_sums"
            and not intent.group_by
            and intent.ranking_direction is None
            and intent.ranking_limit is None,
            "Razão mensal das somas exige uma métrica F1 autorizada, sem grupos.",
        )
        formulas = {
            "energy.average_consumption_per_uc": (
                "consumo_total_kwh", "qtd_ucs_com_leitura",
                "average_consumption_per_uc", "kWh por UC com leitura no mês", None,
            ),
            "billing.average_ticket": (
                "receita_total_reais", "qtd_ucs_distintas_faturadas_no_mes",
                "average_ticket", "R$ por UC faturada no mês", 2,
            ),
            "billing.effective_tariff": (
                "receita_base_comparavel_reais", "consumo_base_comparavel_kwh",
                "effective_tariff", "R$/kWh", 4,
            ),
        }
        numerator, denominator, meaning, unit, decimals = formulas[intent.metric_id]
        _require(
            len(candidate.result_columns) == 1
            and candidate.result_columns[0].role == "measure"
            and candidate.result_columns[0].value_type == "decimal"
            and candidate.result_columns[0].unit == unit,
            "Razão exige uma medida decimal com unidade autorizada.",
        )
        months = _period_months(intent.periods[0])
        _require(months <= available, "Período sem cobertura mensal completa.")
        expected = {"competencia": months}
        for item in intent.filters:
            expected[F1_DIMENSIONS[item.dimension_id]] = frozenset(item.values)
        where = tree.args.get("where")
        actual = _selection(where.this, dict(reviewed.parameter_items)) if where else {}
        _require(actual == expected, "Recortes SQL divergem da razão solicitada.")
        _require(
            not tree.args.get("group")
            and not tree.args.get("order")
            and not tree.args.get("limit"),
            "Razão mensal não admite agrupamento ou truncamento nesta versão.",
        )
        expression = tree.expressions[0].this
        if decimals is not None:
            _require(
                type(expression) is exp.Round
                and type(expression.args.get("decimals")) is exp.Literal
                and not expression.args["decimals"].is_string
                and expression.args["decimals"].this == str(decimals),
                f"Razão exige arredondamento Gold de {decimals} casas decimais.",
            )
            expression = expression.this
        denominator_expression = (
            expression.expression.this
            if type(expression) is exp.Div and type(expression.expression) is exp.Nullif
            else None
        )
        denominator_sum = denominator_expression
        if intent.metric_id == "billing.effective_tariff":
            denominator_sum = (
                denominator_expression.this
                if type(denominator_expression) is exp.Cast
                and type(denominator_expression.args.get("to")) is exp.DataType
                and denominator_expression.args["to"].this.value == "DECIMAL"
                else None
            )
        _require(
            type(expression) is exp.Div
            and type(expression.this) is exp.Sum
            and type(expression.this.this) is exp.Column
            and expression.this.this.name == numerator
            and type(expression.expression) is exp.Nullif
            and type(denominator_sum) is exp.Sum
            and type(denominator_sum.this) is exp.Column
            and denominator_sum.this.name == denominator
            and type(expression.expression.expression) is exp.Literal
            and expression.expression.expression.this == "0"
            and not expression.expression.expression.is_string,
            f"Use SUM({numerator}) / NULLIF(SUM({denominator}), 0).",
        )
        return replace(
            _semantic_review(reviewed, [(tree.expressions[0].alias, meaning)]),
            measure_value_type="double"
            if intent.metric_id == "energy.average_consumption_per_uc"
            else "decimal",
        )
    if intent.operation == "comparison":
        result = _review_comparison(tree, candidate, reviewed, available, request)
        return replace(result, measure_value_type=metric["measure_type"])
    _require(
        not any(tree.find_all(exp.Filter, exp.Sub)),
        "Medida condicional fora do subconjunto verificável desta operação.",
    )
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
    _require(
        actual_groups == {_GROUPS[item] for item in intent.group_by},
        "Agrupamento SQL diverge da interpretação estruturada.",
    )
    order, limit = tree.args.get("order"), tree.args.get("limit")
    if intent.operation == "ranking":
        _require(
            order is not None and len(order.expressions) >= 1 and limit is not None,
            "Ranking exige ordenação e limite.",
        )
        first = order.expressions[0]
        measures = {
            item.name for item in candidate.result_columns if item.role == "measure"
        }
        _require(
            not first.this.table
            and first.this.name in measures
            and bool(first.args.get("desc")) == (intent.ranking_direction == "desc")
            and first.args.get("nulls_first") is False
            and int(limit.expression.this) == intent.ranking_limit,
            "Ordenação ou limite SQL divergem do ranking solicitado.",
        )
    else:
        _require(limit is None, "Consulta sem ranking não pode truncar o resultado.")
    total_meaning = (
        "energy_total" if intent.metric_id == "energy.consumption" else "revenue_total"
    )
    result = _semantic_review(
        reviewed,
        [
            (item.name, total_meaning)
            for item in candidate.result_columns
            if item.role == "measure"
        ],
    )
    return replace(result, measure_value_type=metric["measure_type"])
