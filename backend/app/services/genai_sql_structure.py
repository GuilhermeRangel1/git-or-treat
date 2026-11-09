"""Revisão estrutural F1 sem conexão ao banco nem aprovação de execução.

O resultado ainda exige validação de intenção, período, cobertura, prontidão e
vínculo da autorização antes de poder entrar em um executor.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlglot import exp, parse
from sqlglot.errors import ErrorLevel, SqlglotError

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_parameters import prepare_sql_parameters

_ARGS = {
    exp.Select: {"expressions", "from_", "where", "group", "order", "limit"},
    exp.From: {"this"},
    exp.Table: {"this", "db", "catalog", "alias"},
    exp.TableAlias: {"this", "columns"},
    exp.Identifier: {"this", "quoted"},
    exp.Alias: {"this", "alias"},
    exp.Column: {"this", "table", "db", "catalog"},
    exp.Sum: {"this"},
    exp.Count: {"this", "expressions", "big_int"},
    exp.Avg: {"this"},
    exp.Filter: {"this", "expression"},
    exp.Sub: {"this", "expression"},
    exp.Div: {"this", "expression", "typed", "safe"},
    exp.Round: {"this", "decimals"},
    exp.Cast: {"this", "to"},
    exp.DataType: {"this", "expressions", "nested"},
    exp.Nullif: {"this", "expression"},
    exp.Where: {"this"},
    exp.Group: {"expressions"},
    exp.Order: {"expressions"},
    exp.Ordered: {"this", "desc", "nulls_first"},
    exp.Limit: {"expression"},
    exp.Literal: {"this", "is_string"},
    exp.Placeholder: {"this"},
    exp.EQ: {"this", "expression"},
    exp.NEQ: {"this", "expression"},
    exp.LT: {"this", "expression"},
    exp.LTE: {"this", "expression"},
    exp.GT: {"this", "expression"},
    exp.GTE: {"this", "expression"},
    exp.And: {"this", "expression"},
    exp.Or: {"this", "expression"},
    exp.Paren: {"this"},
    exp.In: {"this", "expressions"},
    exp.Between: {"this", "low", "high"},
}
_COMPARISONS = frozenset({exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE})


class SqlStructureRejected(ValueError):
    """Erro estável que não inclui SQL ou valores do candidato."""


@dataclass(frozen=True)
class SqlStructureReview:
    """Inspeção intermediária imutável; não é artefato de execução aprovado."""

    canonical_sql: str
    parameter_items: tuple[
        tuple[str, str | int | float | bool | date | datetime | Decimal], ...
    ]
    source_columns: frozenset[str]
    output_names: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SqlStructureRejected(message)


def _predicate(
    node: exp.Expression,
    measure_column: str,
    *,
    allow_measure_filter: bool = False,
) -> bool:
    if type(node) is exp.Paren:
        return _predicate(
            node.this, measure_column, allow_measure_filter=allow_measure_filter
        )
    if type(node) in (exp.And, exp.Or):
        return _predicate(
            node.this, measure_column, allow_measure_filter=allow_measure_filter
        ) and _predicate(
            node.expression, measure_column, allow_measure_filter=allow_measure_filter
        )
    if type(node) in _COMPARISONS:
        return (
            type(node.this) is exp.Column
            and (allow_measure_filter or node.this.name != measure_column)
            and type(node.expression) is exp.Placeholder
        )
    if type(node) is exp.In:
        return (
            type(node.this) is exp.Column
            and (allow_measure_filter or node.this.name != measure_column)
            and bool(node.expressions)
            and all(type(item) is exp.Placeholder for item in node.expressions)
        )
    if type(node) is exp.Between:
        return (
            type(node.this) is exp.Column
            and (allow_measure_filter or node.this.name != measure_column)
            and type(node.args.get("low")) is exp.Placeholder
            and type(node.args.get("high")) is exp.Placeholder
        )
    return False


def _measure(node: exp.Expression, measure_column: str, metric_id: str) -> bool:
    if type(node) is exp.Paren:
        return _measure(node.this, measure_column, metric_id)
    if type(node) is exp.Sum:
        return type(node.this) is exp.Column and node.this.name == measure_column
    if type(node) is exp.Count:
        return type(node.this) is exp.Column and node.this.name == measure_column
    if type(node) is exp.Avg:
        return (
            metric_id
            in {
                "service.satisfaction",
                "service.accumulated_satisfaction",
            }
            and type(node.this) is exp.Column
            and node.this.name == measure_column
        )
    if type(node) is exp.Filter:
        return (
            type(node.this) is exp.Sum
            and _measure(node.this, measure_column, metric_id)
            and type(node.expression) is exp.Where
            and _predicate(node.expression.this, measure_column)
        )
    if type(node) is exp.Sub:
        return _measure(node.this, measure_column, metric_id) and _measure(
            node.expression, measure_column, metric_id
        )
    ratio_specs = {
        "energy.average_consumption_per_uc": (
            "consumo_total_kwh", "qtd_ucs_com_leitura", None,
        ),
        "billing.average_ticket": (
            "receita_total_reais", "qtd_ucs_distintas_faturadas_no_mes", 2,
        ),
        "billing.effective_tariff": (
            "receita_base_comparavel_reais", "consumo_base_comparavel_kwh", 4,
        ),
    }
    if metric_id in ratio_specs:
        numerator_column, denominator_column, rounding = ratio_specs[metric_id]
        expression = node
        if rounding is not None:
            if type(expression) is not exp.Round:
                return False
            decimals = expression.args.get("decimals")
            if (
                type(decimals) is not exp.Literal
                or decimals.is_string
                or decimals.this != str(rounding)
            ):
                return False
            expression = expression.this
        elif type(expression) is exp.Round:
            return False
        if type(expression) is not exp.Div:
            return False
        numerator, denominator = expression.this, expression.expression
        denominator_expression = denominator.this if type(denominator) is exp.Nullif else None
        denominator_sum = denominator_expression
        if metric_id == "billing.effective_tariff":
            denominator_sum = (
                denominator_expression.this
                if type(denominator_expression) is exp.Cast
                and type(denominator_expression.args.get("to")) is exp.DataType
                and denominator_expression.args["to"].this.value == "DECIMAL"
                else None
            )
        return (
            type(numerator) is exp.Sum
            and type(numerator.this) is exp.Column
            and numerator.this.name == numerator_column
            and type(denominator) is exp.Nullif
            and type(denominator_sum) is exp.Sum
            and type(denominator_sum.this) is exp.Column
            and denominator_sum.this.name == denominator_column
            and type(denominator.expression) is exp.Literal
            and denominator.expression.this == "0"
            and not denominator.expression.is_string
        )
    return False


def _normalized_placeholders(tree: exp.Expression) -> exp.Expression:
    # SQLGlot representa :nome como string e %(nome)s como Identifier.
    # Normaliza apenas essa diferença de representação para comparar a AST.
    result = tree.copy()
    for placeholder in result.find_all(exp.Placeholder):
        placeholder.set("this", placeholder.name)
    return result


def _review_weighted_continuity(candidate, request, context, source, metric, metric_id):
    intent = candidate.interpretation
    _require(
        candidate.generation_contract_version == "text-to-sql-f1-v12"
        and intent is not None
        and intent.operation == "weighted_continuity"
        and candidate.sql is None
        and not candidate.parameters,
        "DEC/FEC ponderado exige o contrato tipado sem SQL do modelo.",
    )
    _require(
        len(intent.periods) == 1 and not intent.group_by,
        "DEC/FEC ponderado exige uma única janela sem agrupamento.",
    )
    period = intent.periods[0]
    months = []
    year, month = period.start.year, period.start.month
    while (year, month) <= (period.end.year, period.end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    _require(1 <= len(months) <= 120, "Janela DEC/FEC deve conter de 1 a 120 meses.")
    temporal = context["temporal_coverage"]
    available = set(temporal.get("competencies", ()))
    _require(set(months) <= available, "Janela DEC/FEC sem cobertura temporal Gold.")
    feeder_filter = next(
        (item for item in intent.filters if item.dimension_id == "network.feeder"),
        None,
    )
    expected_filter_values = {}
    if feeder_filter is not None:
        feeder_values = {
            value
            for item in context["dimension_values"]
            if item["dimension_id"] == "network.feeder"
            for value in item["values"]
        }
        _require(
            set(feeder_filter.values) <= feeder_values,
            "Alimentador fora do vocabulário Gold autorizado.",
        )
        expected_filter_values = dict(enumerate(feeder_filter.values))
    meaning = (
        "dec_value"
        if metric_id == "network.equivalent_interruption_duration"
        else "fec_value"
    )
    measure_alias = meaning
    expected_columns = (
        (measure_alias, "decimal", metric["unit"]),
        ("feeders_included", "integer", "alimentadores"),
        ("feeders_excluded", "integer", "alimentadores"),
    )
    _require(
        tuple((item.name, item.value_type, item.unit) for item in candidate.result_columns)
        == expected_columns
        and all(item.role == "measure" for item in candidate.result_columns),
        "DEC/FEC exige valor ponderado e contagens de alimentadores elegíveis/excluídos.",
    )
    numerator = (
        "duracao_total_interrupcoes_horas"
        if meaning == "dec_value"
        else "frequencia_total_interrupcoes"
    )
    feeder_predicate = ""
    parameters = {
        "period_start": f"{period.start.year:04d}-{period.start.month:02d}",
        "period_end": f"{period.end.year:04d}-{period.end.month:02d}",
        "expected_months": len(months),
    }
    if feeder_filter is not None:
        placeholders = []
        for index, value in expected_filter_values.items():
            name = f"feeder_{index}"
            placeholders.append(f"%({name})s")
            parameters[name] = value
        if feeder_filter.operator == "eq":
            feeder_predicate = f" AND id_alimentador = {placeholders[0]}"
        else:
            feeder_predicate = f" AND id_alimentador IN ({', '.join(placeholders)})"
    sql = f'''WITH feeder_universe AS (
    SELECT DISTINCT id_alimentador
    FROM {source["schema"]}.{source["table"]}
    WHERE TRUE{feeder_predicate}
), feeder_windows AS (
    SELECT id_alimentador,
           COUNT(DISTINCT competencia) = %(expected_months)s
             AND COUNT(*) = %(expected_months)s
             AND COUNT({numerator}) = %(expected_months)s
             AND COUNT(total_ucs_alimentador) = %(expected_months)s
             AND MIN(total_ucs_alimentador) > 0
             AND MIN(total_ucs_alimentador) = MAX(total_ucs_alimentador) AS eligible,
           SUM({numerator}) AS numerator,
           MIN(total_ucs_alimentador) AS denominator
    FROM {source["schema"]}.{source["table"]}
    WHERE competencia BETWEEN %(period_start)s AND %(period_end)s{feeder_predicate}
    GROUP BY id_alimentador
), evaluated AS (
    SELECT universe.id_alimentador,
           COALESCE(windows.eligible, FALSE) AS eligible,
           windows.numerator,
           windows.denominator
    FROM feeder_universe AS universe
    LEFT JOIN feeder_windows AS windows USING (id_alimentador)
)
SELECT
    SUM(CASE WHEN eligible THEN numerator END)::numeric
      / NULLIF(SUM(CASE WHEN eligible THEN denominator END), 0) AS {measure_alias},
    COUNT(*) FILTER (WHERE eligible)::numeric AS feeders_included,
    COUNT(*) FILTER (WHERE NOT eligible)::numeric AS feeders_excluded
FROM evaluated'''
    source_columns = frozenset(
        {
            "id_alimentador",
            "competencia",
            "total_ucs_alimentador",
            numerator,
        }
    )
    return SqlStructureReview(
        sql,
        tuple(sorted(parameters.items())),
        source_columns,
        tuple(item.name for item in candidate.result_columns),
    )


def review_sql_structure(
    candidate: SqlGenerationCandidate,
    request: QuestionPlanRequest,
) -> SqlStructureReview:
    context = build_sql_generation_context(request)
    _require(candidate.status == "sql_candidate", "Estado sem consulta candidata.")
    _require(
        candidate.context_version == context.context_version, "Contexto divergente."
    )
    source = json.loads(context.contents)["source"]
    measure_column = json.loads(context.contents)["metric"]["measure_column"]
    metric_id = json.loads(context.contents)["metric"]["id"]
    context_body = json.loads(context.contents)
    if candidate.interpretation and candidate.interpretation.operation == "weighted_continuity":
        _require(candidate.sql is None, "DEC/FEC ponderado não aceita SQL gerado pelo modelo.")
        return _review_weighted_continuity(
            candidate, request, context_body, source, context_body["metric"], metric_id
        )
    _require(candidate.sql is not None, "Estado sem consulta candidata.")
    key_grain_read = metric_id in {
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }
    allowed_columns = frozenset(source["columns"])
    try:
        statements = parse(
            candidate.sql,
            read="postgres",
            error_level=ErrorLevel.RAISE,
            error_message_context=0,
            max_errors=1,
            max_nodes=512,
        )
    except (SqlglotError, RecursionError):
        raise SqlStructureRejected("SQL não analisável no dialeto F1.") from None
    _require(
        len(statements) == 1 and type(statements[0]) is exp.Select,
        "F1 exige uma única instrução SELECT.",
    )
    tree = statements[0]
    stack = [(tree, 0)]
    nodes = []
    while stack:
        node, depth = stack.pop()
        _require(depth <= 32 and len(nodes) < 512, "Complexidade SQL excedida.")
        _require(
            type(node) in _ARGS and not node.comments, "Construção SQL fora da F1."
        )
        _require(
            all(
                key in _ARGS[type(node)] or value in (None, False, [])
                for key, value in node.args.items()
            ),
            "Modificador SQL fora da F1.",
        )
        nodes.append(node)
        stack.extend((child, depth + 1) for child in node.iter_expressions())
    _require(sum(type(n) is exp.Select for n in nodes) == 1, "Subconsulta fora da F1.")
    tables = [n for n in nodes if type(n) is exp.Table]
    _require(len(tables) == 1, "F1 exige uma única fonte física.")
    table = tables[0]
    _require(
        not table.catalog
        and table.db == source["schema"]
        and table.name == source["table"],
        "Fonte fora do contexto autorizado.",
    )
    _require(
        tree.args.get("from_") is not None and tree.args["from_"].this is table,
        "Fonte derivada fora da F1.",
    )
    alias = table.alias or table.name
    _require(
        not table.args.get("alias") or not table.args["alias"].columns,
        "Renomeação de colunas da fonte fora da F1.",
    )
    outputs = tree.expressions
    _require(
        all(type(item) is exp.Alias for item in outputs),
        "Resultado exige aliases explícitos.",
    )
    names = tuple(item.alias for item in outputs)
    _require(
        names == tuple(item.name for item in candidate.result_columns),
        "Aliases divergem do contrato de resultado.",
    )
    group = tree.args.get("group")
    groups = group.expressions if group is not None else []
    _require(
        all(
            type(item) is exp.Column and item.name != measure_column for item in groups
        ),
        "Agrupamento fora da F1.",
    )
    group_names = {item.name for item in groups}
    projected_dimensions = set()
    for item, declared in zip(outputs, candidate.result_columns, strict=True):
        if type(item.this) is exp.Column:
            if key_grain_read and item.this.name == measure_column:
                _require(
                    declared.role == "measure",
                    "Leitura DEC/FEC exige a medida física sem agregação.",
                )
                # PostgreSQL folds unquoted DEC/FEC to lowercase. The catalog
                # preserves these physical names in uppercase, so quote this
                # exact approved measure during canonicalization.
                item.this.this.set("quoted", True)
            else:
                _require(
                    item.this.name in group_names and declared.role == "dimension",
                    "Dimensão exige agrupamento e papel compatíveis.",
                )
                projected_dimensions.add(item.this.name)
        else:
            _require(
                _measure(item.this, measure_column, metric_id)
                and declared.role == "measure",
                "Medida fora da agregação F1.",
            )
        _require(
            item.alias not in allowed_columns
            or type(item.this) is exp.Column
            and item.alias == item.this.name,
            "Alias ambíguo com coluna física.",
        )
    _require(
        group_names == projected_dimensions,
        "Agrupamento difere das dimensões exibidas.",
    )
    where = tree.args.get("where")
    _require(
        where is None
        or _predicate(
            where.this,
            measure_column,
            allow_measure_filter=metric_id
            in {
                "energy.gd_units",
                "energy.gd_consumption_drop",
            },
        ),
        "Predicado fora da F1.",
    )
    order = tree.args.get("order")
    order_alias_nodes = set()
    if order is not None:
        for ordered in order.expressions:
            term = ordered.this
            _require(
                type(term) is exp.Column, "Ordenação exige alias ou dimensão agrupada."
            )
            if not term.table and term.name in names:
                order_alias_nodes.add(id(term))
            else:
                _require(term.name in group_names, "Ordenação fora do agrupamento.")
    columns = set()
    for node in nodes:
        if type(node) is exp.Column and id(node) not in order_alias_nodes:
            _require(
                not node.catalog
                and not node.db
                and node.table in ("", alias)
                and node.name in allowed_columns,
                "Coluna fora do contexto autorizado.",
            )
            columns.add(node.name)
    limit = tree.args.get("limit")
    limit_value = limit.expression if limit is not None else None
    if limit_value is not None:
        _require(
            type(limit_value) is exp.Literal
            and not limit_value.is_string
            and limit_value.this.isascii()
            and limit_value.this.isdigit()
            and 1 <= int(limit_value.this) <= 100,
            "LIMIT fora da F1.",
        )
    _require(
        all(
            type(node) is not exp.Literal
            or node is limit_value
            or (
                metric_id in {
                    "energy.average_consumption_per_uc",
                    "billing.average_ticket",
                    "billing.effective_tariff",
                }
                and node.this == "0"
                and not node.is_string
                and type(node.parent) is exp.Nullif
                and (
                    type(node.parent.this) is exp.Sum
                    or metric_id == "billing.effective_tariff"
                    and type(node.parent.this) is exp.Cast
                    and type(node.parent.this.this) is exp.Sum
                )
                and type(node.parent.parent) is exp.Div
                and node.parent.parent.expression is node.parent
            )
            or (
                metric_id in {"billing.average_ticket", "billing.effective_tariff"}
                and node.this == ("2" if metric_id == "billing.average_ticket" else "4")
                and not node.is_string
                and type(node.parent) is exp.Round
                and node.parent.args.get("decimals") is node
            )
            for node in nodes
        ),
        "Valores de filtro exigem parâmetros nomeados.",
    )
    placeholders = [node for node in nodes if type(node) is exp.Placeholder]
    _require(
        all(
            node.this
            and not any(value for key, value in node.args.items() if key != "this")
            for node in placeholders
        ),
        "Placeholder fora do contrato nomeado.",
    )
    references = frozenset(node.name for node in placeholders)
    parameters = prepare_sql_parameters(
        candidate.parameters, referenced_names=references
    )
    metric_id = json.loads(context.contents)["metric"]["id"]
    if metric_id in {"service.attendance", "service.satisfaction"}:
        _require(
            all(type(value) is datetime for value in parameters.values()),
            "Limites de atendimento exigem parâmetros UTC tipados.",
        )
        _require(
            all(
                value.utcoffset().total_seconds() == 0 for value in parameters.values()
            ),
            "Limites de atendimento devem estar em UTC.",
        )
    elif metric_id == "energy.gd_consumption_drop":
        raw_parameters = {
            name: parameter.value for name, parameter in candidate.parameters.items()
        }
        _require(
            all(
                type(value) in (str, bool)
                or name == "minimum_months" and type(value) is int and value == 6
                for name, value in raw_parameters.items()
            ),
            "Filtros da métrica GD exigem texto/booleano ou mínimo inteiro igual a seis.",
        )
    else:
        _require(
            all(type(value) is str for value in parameters.values()),
            "Filtros textuais F1 exigem parâmetros string.",
        )
    try:
        canonical = tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
        round_trip = parse(
            canonical,
            read="postgres",
            error_level=ErrorLevel.RAISE,
            error_message_context=0,
            max_errors=1,
            max_nodes=512,
        )
        _require(
            len(round_trip) == 1
            and _normalized_placeholders(round_trip[0])
            == _normalized_placeholders(tree),
            "Round-trip SQL divergente.",
        )
    except (SqlglotError, RecursionError):
        raise SqlStructureRejected("SQL não representável no dialeto F1.") from None
    return SqlStructureReview(
        canonical, tuple(sorted(parameters.items())), frozenset(columns), names
    )
