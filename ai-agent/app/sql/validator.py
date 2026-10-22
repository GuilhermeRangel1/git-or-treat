"""Validação independente do SQL gerado, com lista branca derivada do dicionário.

O SQL recebido nunca é executado. O validador analisa a árvore do sqlglot, recusa o que não
estiver explicitamente permitido, qualifica todas as colunas contra o esquema do dicionário
e devolve o SQL regenerado dessa árvore qualificada.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from app.sql.dictionary import SqlDictionary

Dialect = Literal["sqlite", "postgres"]
SUPPORTED_DIALECTS: frozenset[str] = frozenset({"sqlite", "postgres"})

# Nós que alteram estado, mudam a sessão ou ampliam a superfície de leitura.
_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.DML,
    exp.DDL,
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Use,
    exp.Copy,
    exp.Grant,
    exp.Revoke,
    exp.Describe,
    exp.Analyze,
    exp.Kill,
    exp.LoadData,
    exp.Cache,
    exp.Uncache,
    exp.Refresh,
    exp.Show,
    exp.Into,
    exp.Lock,
    exp.Lateral,
    exp.Unnest,
    exp.Values,
    exp.Parameter,
    exp.SessionParameter,
    exp.Dot,
)

# No sqlglot, AND/OR (Connector) e algumas construções sintáticas herdam de Func. Elas não
# são funções do banco e não passam pela lista de funções. Os demais tipos estão aqui para
# que a regra continue correta se uma versão futura também os modelar como Func.
_SYNTAX_FUNCS: tuple[type[exp.Expression], ...] = (
    exp.Connector,
    exp.Not,
    exp.Paren,
    exp.Like,
    exp.ILike,
    exp.In,
    exp.Between,
    exp.Is,
    exp.Case,
    exp.If,
    exp.Cast,
    exp.Exists,
)


class SqlRejected(Exception):
    """Consulta recusada antes de qualquer acesso ao banco."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ValidatedQuery:
    """SQL regenerado e aprovado; é o único formato aceito pelos executores."""

    sql: str
    sql_template: str
    dialect: Dialect
    tables: tuple[str, ...]
    dictionary_version: str
    applied_limit: int
    original_limit: int | None
    limit_adjusted: bool
    parameters: tuple[str | int | float | bool, ...] = ()


def validate_sql(
    sql: str,
    dictionary: SqlDictionary,
    dialect: Dialect,
    parameters: tuple[str | int | float | bool, ...] = (),
) -> ValidatedQuery:
    if dialect not in SUPPORTED_DIALECTS:
        raise ValueError(f"dialeto não suportado: {dialect}")
    if not sql or not sql.strip():
        raise SqlRejected("empty", "consulta vazia")
    if len(sql) > dictionary.limits.max_sql_chars:
        raise SqlRejected(
            "too_long", f"consulta excede {dictionary.limits.max_sql_chars} caracteres"
        )

    root = _parse_single(sql, dialect)
    if not isinstance(root, (exp.Select, exp.SetOperation)):
        raise SqlRejected("not_select", f"somente SELECT/WITH é permitido, recebido {root.key}")

    try:
        _check_placeholders(root, parameters, dialect)
        _check_forbidden_nodes(root)
        cte_names = _check_ctes(root, dictionary)
        _check_identifiers(root, dictionary)
        _check_functions(root, dictionary)
        _check_star(root)
        tables = _check_tables(root, dictionary, cte_names)
        _check_sources(root)
        _check_name_collisions(root)

        qualified = _qualify(root, dictionary, dialect)
        _check_resolved_columns(qualified, dictionary)
        applied, original, adjusted = _apply_limit(qualified, dictionary.limits.max_rows)
        if sum(1 for _ in qualified.find_all(exp.Placeholder)) != len(parameters):
            raise SqlRejected("invalid_parameters", "parâmetros alterados na validação")
        sql_template = _literal_free_template(qualified, dictionary, dialect)
    except SqlRejected:
        raise
    except Exception as exc:
        # Falha fechada: qualquer erro inesperado na análise recusa a consulta.
        raise SqlRejected("validation_error", "não foi possível validar a consulta") from exc

    return ValidatedQuery(
        sql=qualified.sql(dialect=dialect, comments=False),
        sql_template=sql_template,
        dialect=dialect,
        tables=tuple(sorted(tables)),
        dictionary_version=dictionary.version,
        applied_limit=applied,
        original_limit=original,
        limit_adjusted=adjusted,
        parameters=parameters,
    )


def _literal_free_template(
    root: exp.Expression, dictionary: SqlDictionary, dialect: Dialect
) -> str:
    """Normaliza valores e nomes livres para não copiar dados recebidos à auditoria."""

    permitted_identifiers = set(dictionary.tables) | set(dictionary.allowed_functions)
    permitted_identifiers |= set(dictionary.allowed_cast_types)
    for table in dictionary.tables.values():
        permitted_identifiers.update(table.columns)
    aliases: dict[str, str] = {}

    def normalize(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Literal):
            return exp.Placeholder()
        if isinstance(node, exp.Identifier) and node.name.casefold() not in permitted_identifiers:
            key = node.name.casefold()
            if key not in aliases:
                index = len(aliases) + 1
                alias = f"audit_alias_{index}"
                while alias in permitted_identifiers:
                    index += 1
                    alias = f"audit_alias_{index}"
                aliases[key] = alias
            node.set("this", aliases[key])
        return node

    template = root.copy().transform(normalize)
    return template.sql(dialect=dialect, comments=False)


def _check_placeholders(
    root: exp.Expression,
    parameters: tuple[str | int | float | bool, ...],
    dialect: Dialect,
) -> None:
    if not isinstance(parameters, tuple) or len(parameters) > 100:
        raise SqlRejected("invalid_parameters", "conjunto de parâmetros inválido")
    if any(
        type(value) not in (str, int, float, bool)
        or (type(value) is float and not isfinite(value))
        or (type(value) is str and len(value) > 120)
        for value in parameters
    ):
        raise SqlRejected("invalid_parameters", "valor de parâmetro inválido")
    placeholders = list(root.find_all(exp.Placeholder))
    if len(placeholders) != len(parameters):
        raise SqlRejected("invalid_parameters", "quantidade de parâmetros incompatível")
    if placeholders and dialect != "sqlite":
        raise SqlRejected("invalid_parameters", "parâmetros deste dialeto ainda não validados")
    for placeholder in placeholders:
        if placeholder.this is not None or not isinstance(
            placeholder.parent,
            (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In, exp.Between),
        ):
            raise SqlRejected("invalid_parameters", "parâmetro fora de predicado de valor")


def _parse_single(sql: str, dialect: Dialect) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except SqlglotError as exc:
        raise SqlRejected("parse_error", "SQL inválido ou não suportado") from exc
    if not statements:
        raise SqlRejected("empty", "nenhuma instrução encontrada")
    if len(statements) > 1:
        raise SqlRejected("multiple_statements", "somente uma instrução é permitida")
    return statements[0]


def _check_forbidden_nodes(root: exp.Expression) -> None:
    for node in root.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SqlRejected("forbidden_construct", f"construção não permitida: {node.key}")
        if isinstance(node, exp.Select) and (node.args.get("into") or node.args.get("locks")):
            raise SqlRejected("forbidden_construct", "SELECT INTO e FOR UPDATE/SHARE são proibidos")
        if isinstance(node, exp.Join) and (node.method or "").upper() == "NATURAL":
            # As colunas de junção dependeriam do esquema físico, não do dicionário.
            raise SqlRejected("forbidden_construct", "NATURAL JOIN não é permitido")
        if isinstance(node, exp.Subquery) and not isinstance(node.this, exp.Query):
            raise SqlRejected("forbidden_construct", "subconsulta precisa ser SELECT")


def _check_ctes(root: exp.Expression, dictionary: SqlDictionary) -> set[str]:
    names: set[str] = set()
    for with_ in root.find_all(exp.With):
        if with_.args.get("recursive"):
            raise SqlRejected("recursive_cte", "WITH RECURSIVE não é permitido")
    for cte in root.find_all(exp.CTE):
        if not isinstance(cte.this, exp.Query):
            raise SqlRejected("forbidden_construct", "CTE precisa conter somente SELECT")
        name = cte.alias_or_name.casefold()
        if name in dictionary.tables:
            raise SqlRejected("cte_shadowing", f"CTE não pode reutilizar o nome da tabela {name}")
        names.add(name)
    return names


def _check_identifiers(root: exp.Expression, dictionary: SqlDictionary) -> None:
    for identifier in root.find_all(exp.Identifier):
        name = identifier.name.casefold()
        if name in dictionary.sensitive_columns:
            raise SqlRejected("sensitive_column", f"identificador sensível: {name}")
        if dictionary.is_reserved(name):
            raise SqlRejected("reserved_identifier", f"identificador interno do banco: {name}")


def _check_tables(root: exp.Expression, dictionary: SqlDictionary, ctes: set[str]) -> set[str]:
    used: set[str] = set()
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise SqlRejected("table_function", "função usada como tabela não é permitida")
        if table.args.get("db") or table.args.get("catalog"):
            raise SqlRejected("schema_qualified", "nome de tabela com esquema não é permitido")
        name = table.name.casefold()
        if name in ctes:
            continue
        if name not in dictionary.tables:
            raise SqlRejected("unknown_table", f"tabela fora do dicionário: {name}")
        used.add(name)
    if not used:
        raise SqlRejected(
            "unknown_table", "a consulta precisa ler ao menos uma tabela do dicionário"
        )
    return used


def _check_sources(root: exp.Expression) -> None:
    for clause in (*root.find_all(exp.From), *root.find_all(exp.Join)):
        if not isinstance(clause.this, (exp.Table, exp.Subquery)):
            raise SqlRejected("unsupported_source", f"origem não permitida: {clause.this.key}")


def _check_star(root: exp.Expression) -> None:
    for star in root.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise SqlRejected(
                "select_star", "liste as colunas explicitamente; só COUNT(*) aceita *"
            )


def _check_functions(root: exp.Expression, dictionary: SqlDictionary) -> None:
    for node in root.walk():
        if isinstance(node, exp.Cast):
            _check_cast(node, dictionary)
        if not isinstance(node, exp.Func) or isinstance(node, _SYNTAX_FUNCS):
            continue
        name = _function_name(node)
        if name not in dictionary.allowed_functions:
            raise SqlRejected("function_not_allowed", f"função não permitida: {name}")


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return node.name.casefold()
    return type(node).sql_names()[0].casefold()


def _check_cast(node: exp.Cast, dictionary: SqlDictionary) -> None:
    target = node.args.get("to")
    if not isinstance(target, exp.DataType) or not isinstance(target.this, exp.DataType.Type):
        raise SqlRejected("cast_not_allowed", "tipo de CAST não permitido")
    type_name = target.this.value.casefold()
    if type_name not in dictionary.allowed_cast_types:
        raise SqlRejected("cast_not_allowed", f"tipo de CAST não permitido: {type_name}")


def _qualify(root: exp.Expression, dictionary: SqlDictionary, dialect: Dialect) -> exp.Expression:
    # O esquema contém só colunas permitidas. Como o SQL executado é o qualificado, uma
    # referência ambígua não pode ser resolvida pelo banco para uma coluna fora do dicionário.
    try:
        return qualify(
            root.copy(),
            schema=dictionary.schema(),
            dialect=dialect,
            validate_qualify_columns=True,
            quote_identifiers=True,
        )
    except SqlglotError as exc:
        raise SqlRejected("unknown_column", "coluna fora do dicionário ou não resolvida") from exc


def _check_name_collisions(root: exp.Expression) -> None:
    # No PostgreSQL, uma coluna com o nome de uma tabela/alias devolve a linha inteira,
    # inclusive colunas fora do dicionário. Nomes de origem e de coluna não podem coincidir.
    sources: set[str] = set()
    for table in root.find_all(exp.Table):
        sources.update({table.name.casefold(), table.alias_or_name.casefold()})
    for aliased in (*root.find_all(exp.Subquery), *root.find_all(exp.CTE)):
        if aliased.alias:
            sources.add(aliased.alias.casefold())
    names = {column.name.casefold() for column in root.find_all(exp.Column)}
    names.update(alias.alias.casefold() for alias in root.find_all(exp.Alias))
    clash = sorted(sources & names)
    if clash:
        raise SqlRejected("ambiguous_identifier", f"nome usado como tabela e coluna: {clash[0]}")


def _check_resolved_columns(root: exp.Expression, dictionary: SqlDictionary) -> None:
    for column in root.find_all(exp.Column):
        if not column.table and not _is_order_by_alias(column):
            raise SqlRejected("unknown_column", f"coluna sem origem: {column.sql()}")
    for scope in traverse_scope(root):
        for column in scope.columns:
            source = _find_source(scope, column.table)
            if source is None:
                raise SqlRejected("unknown_column", f"coluna sem origem: {column.sql()}")
            if isinstance(source, exp.Table):
                table = dictionary.tables.get(source.name.casefold())
                if table is None or column.name.casefold() not in table.columns:
                    raise SqlRejected(
                        "unknown_column", f"coluna fora do dicionário: {column.sql()}"
                    )


def _is_order_by_alias(column: exp.Column) -> bool:
    """ORDER BY pode citar um alias da projeção; o qualify o mantém sem tabela."""

    order = column.find_ancestor(exp.Order)
    if order is None or not isinstance(order.parent, exp.Query):
        return False
    return column.name in order.parent.named_selects


def _find_source(scope, alias: str):
    current = scope
    while current is not None:
        if alias in current.sources:
            return current.sources[alias]
        current = current.parent
    return None


def _apply_limit(root: exp.Expression, max_rows: int) -> tuple[int, int | None, bool]:
    if root.args.get("offset") is not None and not _int_literal(root.args["offset"].expression):
        raise SqlRejected("invalid_limit", "OFFSET precisa ser inteiro literal")

    current = root.args.get("limit")
    original: int | None
    if current is None:
        original = None
    elif isinstance(current, exp.Limit):
        if not _int_literal(current.expression):
            raise SqlRejected("invalid_limit", "LIMIT precisa ser inteiro literal não negativo")
        original = int(current.expression.this)
    elif isinstance(current, exp.Fetch):
        options = current.args.get("limit_options")
        if options is not None and (options.args.get("percent") or options.args.get("with_ties")):
            raise SqlRejected("invalid_limit", "FETCH com PERCENT ou WITH TIES não é permitido")
        count = current.args.get("count")
        if count is not None and not _int_literal(count):
            raise SqlRejected("invalid_limit", "FETCH precisa de inteiro literal")
        original = 1 if count is None else int(count.this)
    else:
        raise SqlRejected("invalid_limit", "forma de limite não suportada")

    applied = max_rows if original is None else min(original, max_rows)
    # FETCH FIRST é normalizado para LIMIT, aceito pelos dois dialetos.
    root.set("limit", exp.Limit(expression=exp.Literal.number(applied)))
    return applied, original, applied != original


def _int_literal(node: exp.Expression | None) -> bool:
    return isinstance(node, exp.Literal) and not node.is_string and str(node.this).isdigit()
