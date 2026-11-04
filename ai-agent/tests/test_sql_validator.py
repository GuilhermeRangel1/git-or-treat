from dataclasses import replace

import pytest
import sqlglot
from sqlglot import exp

from app.sql.validator import SqlRejected, validate_sql
from tests.sql_support import load_test_dictionary

DICTIONARY = load_test_dictionary()
DIALECTS = ["sqlite", "postgres"]
MAX_ROWS = DICTIONARY.limits.max_rows


def rejected_code(sql: str, dialect: str) -> str:
    with pytest.raises(SqlRejected) as info:
        validate_sql(sql, DICTIONARY, dialect)
    return info.value.code


VALID_QUERIES = [
    "SELECT municipio, SUM(receita_total) AS receita FROM gold_indicadores "
    "GROUP BY municipio ORDER BY receita DESC LIMIT 10",
    "WITH mensal AS (SELECT competencia, SUM(energia_consumida_kwh) AS kwh "
    "FROM gold_indicadores GROUP BY competencia) SELECT competencia, kwh FROM mensal LIMIT 5",
    "SELECT bairro FROM gold_indicadores WHERE receita_total > "
    "(SELECT AVG(receita_total) FROM gold_indicadores) LIMIT 5",
    "SELECT COUNT(*) FROM gold_indicadores LIMIT 1",
    "SELECT classe, ROUND(CAST(SUM(receita_total) AS DECIMAL), 2) FROM gold_indicadores "
    "GROUP BY classe HAVING COUNT(*) > 1 LIMIT 5",
    "SELECT municipio FROM gold_indicadores UNION SELECT municipio FROM cadastro_teste LIMIT 5",
    "SELECT CASE WHEN classe = 'residencial' THEN 1 ELSE 0 END AS res "
    "FROM gold_indicadores LIMIT 3 OFFSET 1",
    "SELECT municipio FROM gold_indicadores AS g WHERE EXISTS "
    "(SELECT 1 FROM cadastro_teste AS c WHERE c.municipio = g.municipio) LIMIT 5",
]


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("sql", VALID_QUERIES)
def test_valid_queries_are_accepted_and_regenerated(sql: str, dialect: str) -> None:
    query = validate_sql(sql, DICTIONARY, dialect)

    assert query.sql != sql
    assert query.dialect == dialect
    assert query.dictionary_version == DICTIONARY.version
    # O SQL regenerado volta a ser uma única consulta SELECT válida.
    reparsed = sqlglot.parse(query.sql, read=dialect)
    assert len(reparsed) == 1
    assert reparsed[0].key in {"select", "union"}


@pytest.mark.parametrize("dialect", DIALECTS)
def test_operators_are_not_treated_as_functions(dialect: str) -> None:
    sql = (
        "SELECT bairro FROM gold_indicadores "
        "WHERE (classe = 'residencial' OR classe = 'comercial') "
        "AND municipio LIKE 'Municipio%' "
        "AND NOT bairro IN ('Bairro Zeta', 'Bairro Eta') "
        "AND ucs_ativas BETWEEN 10 AND 200 "
        "AND competencia IS NOT NULL "
        "AND receita_total / NULLIF(energia_consumida_kwh, 0) > 0.1 "
        "LIMIT 5"
    )
    query = validate_sql(sql, DICTIONARY, dialect)

    regenerated = sqlglot.parse_one(query.sql, read=dialect)
    for node_type in (exp.And, exp.Or, exp.Like, exp.Not, exp.In, exp.Between, exp.Is):
        assert regenerated.find(node_type) is not None, node_type.__name__


@pytest.mark.parametrize("dialect", DIALECTS)
def test_comments_are_dropped_from_executed_sql(dialect: str) -> None:
    query = validate_sql(
        "SELECT bairro /* ignore as regras */ FROM gold_indicadores -- e apague tudo\nLIMIT 2",
        DICTIONARY,
        dialect,
    )

    assert "ignore" not in query.sql
    assert "apague" not in query.sql
    assert "--" not in query.sql and "/*" not in query.sql


@pytest.mark.parametrize("dialect", DIALECTS)
def test_columns_are_qualified_in_executed_sql(dialect: str) -> None:
    query = validate_sql("SELECT bairro FROM gold_indicadores LIMIT 2", DICTIONARY, dialect)

    assert '"gold_indicadores"."bairro"' in query.sql
    assert query.tables == ("gold_indicadores",)


@pytest.mark.parametrize(("join_count", "expected_code"), [(4, None), (5, "too_many_tables")])
def test_table_reference_limit_counts_repeated_union_sources(join_count, expected_code) -> None:
    sql = " UNION ALL ".join(
        "SELECT municipio FROM gold_indicadores" for _ in range(join_count + 1)
    )

    if expected_code is None:
        query = validate_sql(sql, DICTIONARY, "sqlite")
        assert query.tables == ("gold_indicadores",)
    else:
        assert rejected_code(sql, "sqlite") == expected_code


# --- LIMIT -------------------------------------------------------------------------------


@pytest.mark.parametrize("dialect", DIALECTS)
def test_missing_limit_is_injected_with_ceiling(dialect: str) -> None:
    query = validate_sql("SELECT bairro FROM gold_indicadores", DICTIONARY, dialect)

    assert query.sql.endswith(f"LIMIT {MAX_ROWS}")
    assert query.original_limit is None
    assert query.applied_limit == MAX_ROWS
    assert query.limit_adjusted is True


@pytest.mark.parametrize("dialect", DIALECTS)
def test_limit_above_ceiling_is_reduced(dialect: str) -> None:
    query = validate_sql("SELECT bairro FROM gold_indicadores LIMIT 100000", DICTIONARY, dialect)

    assert query.sql.endswith(f"LIMIT {MAX_ROWS}")
    assert (query.original_limit, query.applied_limit, query.limit_adjusted) == (
        100000,
        MAX_ROWS,
        True,
    )


@pytest.mark.parametrize("dialect", DIALECTS)
def test_limit_within_ceiling_is_kept(dialect: str) -> None:
    query = validate_sql("SELECT bairro FROM gold_indicadores LIMIT 7", DICTIONARY, dialect)

    assert query.sql.endswith("LIMIT 7")
    assert query.limit_adjusted is False


@pytest.mark.parametrize("dialect", DIALECTS)
def test_limit_only_in_subquery_still_gets_outer_ceiling(dialect: str) -> None:
    query = validate_sql(
        "SELECT s.bairro FROM (SELECT bairro FROM gold_indicadores LIMIT 3) AS s",
        DICTIONARY,
        dialect,
    )

    assert query.sql.endswith(f"LIMIT {MAX_ROWS}")
    assert "LIMIT 3" in query.sql
    assert query.limit_adjusted is True


@pytest.mark.parametrize("dialect", DIALECTS)
def test_union_limit_applies_to_whole_query(dialect: str) -> None:
    query = validate_sql(
        "SELECT municipio FROM gold_indicadores UNION ALL SELECT municipio FROM cadastro_teste",
        DICTIONARY,
        dialect,
    )

    assert query.sql.endswith(f"LIMIT {MAX_ROWS}")


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    ("fetch", "expected"),
    [
        ("FETCH FIRST 5 ROWS ONLY", 5),
        ("FETCH FIRST ROW ONLY", 1),
        ("FETCH FIRST 900 ROWS ONLY", 50),
    ],
)
def test_fetch_first_is_normalized_to_limit(dialect: str, fetch: str, expected: int) -> None:
    query = validate_sql(f"SELECT bairro FROM gold_indicadores {fetch}", DICTIONARY, dialect)

    assert "FETCH" not in query.sql
    assert query.sql.endswith(f"LIMIT {expected}")
    assert query.applied_limit == expected


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    "tail",
    [
        "LIMIT -1",
        "LIMIT ALL",
        "LIMIT 1 + 1",
        "LIMIT (SELECT COUNT(*) FROM gold_indicadores)",
        "LIMIT '10'",
        "LIMIT 5 OFFSET (SELECT 1)",
        "FETCH FIRST 10 PERCENT ROWS ONLY",
        "FETCH FIRST 10 ROWS WITH TIES",
    ],
)
def test_non_literal_or_ambiguous_limits_are_rejected(dialect: str, tail: str) -> None:
    sql = f"SELECT bairro FROM gold_indicadores ORDER BY bairro {tail}"

    # No SQLite, LIMIT ALL é lido como uma coluna chamada ALL e cai na regra de colunas.
    assert rejected_code(sql, dialect) in {
        "invalid_limit",
        "parse_error",
        "forbidden_construct",
        "unknown_column",
    }


# --- Ataques -------------------------------------------------------------------------------

ATTACKS = {
    # Escrita e DDL
    "drop": ("DROP TABLE gold_indicadores", {"not_select"}),
    "delete": ("DELETE FROM gold_indicadores", {"not_select"}),
    "update": ("UPDATE gold_indicadores SET receita_total = 0", {"not_select"}),
    "insert": ("INSERT INTO gold_indicadores (bairro) VALUES ('x')", {"not_select"}),
    "insert_select": (
        "INSERT INTO gold_indicadores SELECT * FROM gold_indicadores",
        {"not_select"},
    ),
    "truncate": ("TRUNCATE TABLE gold_indicadores", {"not_select"}),
    "create": ("CREATE TABLE x AS SELECT bairro FROM gold_indicadores", {"not_select"}),
    "alter": ("ALTER TABLE gold_indicadores ADD COLUMN x INT", {"not_select"}),
    "grant": ("GRANT ALL ON gold_indicadores TO public", {"not_select"}),
    "vacuum": ("VACUUM", {"not_select"}),
    "set_role": ("SET ROLE postgres", {"not_select"}),
    "begin": ("BEGIN", {"not_select"}),
    "select_into": (
        "SELECT bairro INTO copia FROM gold_indicadores LIMIT 1",
        {"forbidden_construct"},
    ),
    "for_update": (
        "SELECT bairro FROM gold_indicadores LIMIT 1 FOR UPDATE",
        {"forbidden_construct"},
    ),
    # Múltiplas instruções
    "stacked_drop": (
        "SELECT bairro FROM gold_indicadores LIMIT 1; DROP TABLE gold_indicadores",
        {"multiple_statements"},
    ),
    "stacked_select": (
        "SELECT bairro FROM gold_indicadores LIMIT 1; SELECT bairro FROM gold_indicadores LIMIT 1",
        {"multiple_statements"},
    ),
    "stacked_after_comment": (
        "SELECT bairro FROM gold_indicadores LIMIT 1 /* x */; DELETE FROM gold_indicadores",
        {"multiple_statements"},
    ),
    # CTE
    "cte_delete": (
        "WITH x AS (DELETE FROM gold_indicadores RETURNING bairro) SELECT bairro FROM x LIMIT 1",
        {"forbidden_construct"},
    ),
    "cte_update": (
        "WITH x AS (UPDATE gold_indicadores SET bairro = 'y' RETURNING bairro) "
        "SELECT bairro FROM x LIMIT 1",
        {"forbidden_construct"},
    ),
    "cte_recursive": (
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r LIMIT 1",
        {"recursive_cte"},
    ),
    "cte_shadowing_real_table": (
        "WITH gold_indicadores AS (SELECT 1 AS bairro) SELECT bairro FROM gold_indicadores LIMIT 1",
        {"cte_shadowing"},
    ),
    "cte_named_sensitive": (
        "WITH cpf_cnpj AS (SELECT bairro FROM gold_indicadores) "
        "SELECT bairro FROM cpf_cnpj LIMIT 1",
        {"sensitive_column"},
    ),
    "cte_named_catalog": (
        "WITH pg_user AS (SELECT bairro FROM gold_indicadores) SELECT bairro FROM pg_user LIMIT 1",
        {"reserved_identifier"},
    ),
    # Catálogo e tabelas fora do dicionário
    "union_pg_user": (
        "SELECT bairro FROM gold_indicadores UNION SELECT usename FROM pg_user LIMIT 5",
        {"reserved_identifier"},
    ),
    "union_pg_shadow": (
        "SELECT bairro FROM gold_indicadores UNION SELECT passwd FROM pg_shadow LIMIT 5",
        {"reserved_identifier"},
    ),
    "sqlite_master": ("SELECT sql FROM sqlite_master LIMIT 5", {"reserved_identifier"}),
    "schema_qualified": (
        "SELECT bairro FROM public.gold_indicadores LIMIT 1",
        {"schema_qualified"},
    ),
    "catalog_qualified": (
        "SELECT table_name FROM information_schema.tables LIMIT 1",
        {"reserved_identifier"},
    ),
    "pg_catalog_table": (
        "SELECT relname FROM pg_catalog.pg_class LIMIT 1",
        {"reserved_identifier"},
    ),
    "unknown_table": ("SELECT segredo FROM interna_nao_listada LIMIT 1", {"unknown_table"}),
    "comma_join_unknown_table": (
        "SELECT g.bairro FROM gold_indicadores AS g, interna_nao_listada AS i LIMIT 1",
        {"join_not_approved"},
    ),
    "subquery_unknown_table": (
        "SELECT bairro FROM gold_indicadores WHERE bairro IN "
        "(SELECT segredo FROM interna_nao_listada) LIMIT 1",
        {"unknown_table"},
    ),
    "no_table": ("SELECT 1 LIMIT 1", {"unknown_table"}),
    # Fontes não tabulares
    "lateral": (
        "SELECT g.bairro, l.n FROM gold_indicadores AS g, "
        "LATERAL (SELECT COUNT(*) AS n FROM cadastro_teste) AS l LIMIT 1",
        {"join_not_approved"},
    ),
    "generate_series_table": (
        "SELECT g FROM generate_series(1, 1000000000) AS g LIMIT 1",
        {"function_not_allowed", "table_function"},
    ),
    "values_source": ("SELECT x FROM (VALUES (1)) AS v(x) LIMIT 1", {"forbidden_construct"}),
    # Funções perigosas
    "pg_sleep": ("SELECT pg_sleep(10) FROM gold_indicadores LIMIT 1", {"function_not_allowed"}),
    "pg_sleep_in_where": (
        "SELECT bairro FROM gold_indicadores WHERE pg_sleep(10) IS NULL LIMIT 1",
        {"function_not_allowed"},
    ),
    "pg_sleep_qualified": (
        "SELECT pg_catalog.pg_sleep(1) FROM gold_indicadores LIMIT 1",
        {"reserved_identifier", "forbidden_construct"},
    ),
    "pg_read_file": (
        "SELECT pg_read_file('/etc/passwd') FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "current_user": ("SELECT current_user FROM gold_indicadores LIMIT 1", {"function_not_allowed"}),
    "current_user_alone": ("SELECT current_user", {"function_not_allowed"}),
    "session_user": ("SELECT session_user FROM gold_indicadores LIMIT 1", None),
    "version": ("SELECT version() FROM gold_indicadores LIMIT 1", {"function_not_allowed"}),
    "current_database": (
        "SELECT current_database() FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "dblink": (
        "SELECT dblink('host=x', 'DROP TABLE t') FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "load_extension": (
        "SELECT load_extension('evil') FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "randomblob": (
        "SELECT randomblob(1000000000) FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "set_config": (
        "SELECT set_config('statement_timeout', '0', false) FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "lo_import": (
        "SELECT lo_import('/etc/passwd') FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "cast_regclass": (
        "SELECT CAST(bairro AS regclass) FROM gold_indicadores LIMIT 1",
        {"cast_not_allowed"},
    ),
    "placeholder": ("SELECT bairro FROM gold_indicadores WHERE bairro = ? LIMIT 1", None),
    # Colunas sensíveis e desconhecidas
    "sensitive_direct": ("SELECT cpf_cnpj FROM cadastro_teste LIMIT 1", {"sensitive_column"}),
    "sensitive_quoted_upper": (
        'SELECT "CPF_CNPJ" FROM cadastro_teste LIMIT 1',
        {"sensitive_column"},
    ),
    "sensitive_mixed_case": (
        "SELECT Nome_Titular FROM cadastro_teste LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_qualified": (
        "SELECT c.cpf_cnpj FROM cadastro_teste AS c LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_in_where": (
        "SELECT uc_id FROM cadastro_teste WHERE cpf_cnpj LIKE '0%' LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_in_order": (
        "SELECT uc_id FROM cadastro_teste ORDER BY nome_titular LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_in_subquery": (
        "SELECT bairro FROM gold_indicadores WHERE EXISTS "
        "(SELECT 1 FROM cadastro_teste WHERE cpf_cnpj = '0') LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_in_function": (
        "SELECT COUNT(DISTINCT cpf_cnpj) FROM cadastro_teste LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_as_alias": (
        "SELECT uc_id AS nome_titular FROM cadastro_teste LIMIT 1",
        {"sensitive_column"},
    ),
    "sensitive_in_union": (
        "SELECT bairro FROM gold_indicadores UNION SELECT nome_titular FROM cadastro_teste LIMIT 5",
        {"sensitive_column"},
    ),
    "unlisted_physical_column": (
        "SELECT segredo FROM gold_indicadores LIMIT 1",
        {"unknown_column"},
    ),
    "unlisted_qualified_column": (
        "SELECT c.endereco_ficticio FROM cadastro_teste AS c LIMIT 1",
        {"unknown_column"},
    ),
    # No PostgreSQL, o alias da tabela usado como coluna devolve a linha inteira.
    "whole_row_alias": ("SELECT c FROM cadastro_teste AS c LIMIT 1", {"ambiguous_identifier"}),
    "whole_row_table_name": (
        "SELECT cadastro_teste FROM cadastro_teste LIMIT 1",
        {"ambiguous_identifier"},
    ),
    "whole_row_in_function": (
        "SELECT COUNT(c) FROM cadastro_teste AS c LIMIT 1",
        {"ambiguous_identifier"},
    ),
    "whole_row_in_order": (
        "SELECT uc_id FROM cadastro_teste AS c ORDER BY c LIMIT 1",
        {"ambiguous_identifier"},
    ),
    "whole_row_in_where": (
        "SELECT uc_id FROM cadastro_teste AS c WHERE c IS NOT NULL LIMIT 1",
        {"ambiguous_identifier"},
    ),
    "whole_row_subquery_alias": (
        "SELECT s FROM (SELECT uc_id FROM cadastro_teste) AS s LIMIT 1",
        {"ambiguous_identifier"},
    ),
    "unapproved_join": (
        "SELECT g.municipio FROM gold_indicadores AS g "
        "JOIN cadastro_teste AS c ON c.municipio = g.municipio LIMIT 5",
        {"join_not_approved"},
    ),
    "natural_join": (
        "SELECT g.bairro FROM gold_indicadores AS g NATURAL JOIN cadastro_teste AS c LIMIT 1",
        {"forbidden_construct"},
    ),
    "using_unlisted_column": (
        "SELECT g.bairro FROM gold_indicadores AS g JOIN cadastro_teste AS c USING (segredo) "
        "LIMIT 1",
        {"join_not_approved"},
    ),
    "window_function_not_listed": (
        "SELECT ROW_NUMBER() OVER (ORDER BY bairro) FROM gold_indicadores LIMIT 1",
        {"function_not_allowed"},
    ),
    "select_star": ("SELECT * FROM cadastro_teste LIMIT 1", {"select_star"}),
    "table_star": ("SELECT c.* FROM cadastro_teste AS c LIMIT 1", {"select_star"}),
    "star_in_cte": (
        "WITH x AS (SELECT * FROM cadastro_teste) SELECT uc_id FROM x LIMIT 1",
        {"select_star"},
    ),
    # Entradas malformadas
    "empty": ("   ", {"empty"}),
    "only_semicolon": (";", {"empty", "parse_error"}),
    "garbage": ("SELEC bairro FRM gold_indicadores", {"parse_error", "not_select"}),
    "too_long": (
        "SELECT bairro FROM gold_indicadores WHERE bairro = '" + "a" * 3000 + "'",
        {"too_long"},
    ),
}


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_attacks_are_rejected(name: str, dialect: str) -> None:
    sql, expected_codes = ATTACKS[name]

    code = rejected_code(sql, dialect)

    if expected_codes is not None:
        assert code in expected_codes, f"{name}: {code}"


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT current_user FROM gold_indicadores LIMIT 1",
        "SELECT CURRENT_USER() FROM gold_indicadores LIMIT 1",
        "SELECT version() FROM gold_indicadores LIMIT 1",
        "SELECT pg_sleep(1) FROM gold_indicadores LIMIT 1",
        "SELECT pg_read_file('/etc/passwd') FROM gold_indicadores LIMIT 1",
    ],
)
def test_dangerous_functions_are_rejected_even_without_reserved_prefix_rule(
    sql: str, dialect: str
) -> None:
    # Remove a regra de prefixo reservado para provar que a lista de funções também recusa.
    dictionary = replace(DICTIONARY, reserved_prefixes=())

    with pytest.raises(SqlRejected) as info:
        validate_sql(sql, dictionary, dialect)

    assert info.value.code == "function_not_allowed"


def test_correlated_reference_is_pinned_to_authorized_table() -> None:
    # cadastro_teste tem municipio liberado; a referência sem qualificação dentro do EXISTS
    # precisa sair qualificada para que o banco não a resolva para outra coluna física.
    query = validate_sql(
        "SELECT bairro FROM gold_indicadores WHERE EXISTS "
        "(SELECT 1 FROM cadastro_teste WHERE uc_id = 'UC-0001' AND municipio = 'x') LIMIT 1",
        DICTIONARY,
        "postgres",
    )

    assert '"cadastro_teste"."municipio"' in query.sql
    assert '"cadastro_teste"."uc_id"' in query.sql


def test_unsupported_dialect_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        validate_sql("SELECT bairro FROM gold_indicadores", DICTIONARY, "mysql")  # type: ignore[arg-type]
