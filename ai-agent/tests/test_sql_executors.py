import os
import sqlite3
from dataclasses import replace

import pytest

from app.sql.executors import (
    PostgresReadOnlyExecutor,
    QueryExecutionError,
    SqliteReadOnlyExecutor,
)
from app.sql.validator import SqlRejected, ValidatedQuery, validate_sql
from tests.sql_support import GOLD_ROWS, build_gold_sqlite, load_test_dictionary

DICTIONARY = load_test_dictionary()


@pytest.fixture
def gold_db(tmp_path):
    return build_gold_sqlite(tmp_path / "gold_teste.sqlite")


def sqlite_executor(path, max_rows=50, timeout_ms=2000) -> SqliteReadOnlyExecutor:
    return SqliteReadOnlyExecutor(
        path,
        max_rows=max_rows,
        timeout_ms=timeout_ms,
        dictionary=DICTIONARY,
        sensitive_columns=DICTIONARY.sensitive_columns,
    )


def unchecked(sql: str, dialect: str = "sqlite") -> ValidatedQuery:
    """Simula uma consulta que escapou do validador, para testar a segunda barreira."""

    return ValidatedQuery(
        sql=sql,
        sql_template=sql,
        dialect=dialect,
        tables=(),
        dictionary_version="teste",
        applied_limit=50,
        original_limit=None,
        limit_adjusted=False,
    )


def count_rows(path) -> int:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT COUNT(*) FROM gold_indicadores").fetchone()[0]
    finally:
        connection.close()


# --- SQLite ------------------------------------------------------------------------------


def test_sqlite_runs_validated_aggregate_and_matches_fixture(gold_db) -> None:
    query = validate_sql(
        "SELECT municipio, SUM(receita_total) AS receita, SUM(ucs_ativas) AS ucs "
        "FROM gold_indicadores WHERE competencia = '2025-01' GROUP BY municipio ORDER BY municipio",
        DICTIONARY,
        "sqlite",
    )

    result = sqlite_executor(gold_db).execute(query)

    expected: dict[str, list[float]] = {}
    for competencia, municipio, _, _, receita, _, ucs in GOLD_ROWS:
        if competencia == "2025-01":
            totals = expected.setdefault(municipio, [0.0, 0])
            totals[0] += receita
            totals[1] += ucs
    assert result.columns == ("municipio", "receita", "ucs")
    assert [(m, pytest.approx(r), u) for m, r, u in result.rows] == [
        (m, pytest.approx(r), u) for m, (r, u) in sorted(expected.items())
    ]
    assert result.truncated is False


def test_sqlite_direct_executor_rejects_fabricated_query_outside_dictionary(gold_db) -> None:
    forged = unchecked("SELECT segredo FROM interna_nao_listada LIMIT 1")

    with pytest.raises(SqlRejected) as info:
        sqlite_executor(gold_db).execute(forged)

    assert info.value.code == "unknown_table"


def test_sqlite_direct_executor_rejects_changed_sql_after_validation(gold_db) -> None:
    approved = validate_sql("SELECT bairro FROM gold_indicadores LIMIT 1", DICTIONARY, "sqlite")
    altered = replace(approved, sql="SELECT segredo FROM interna_nao_listada LIMIT 1")

    with pytest.raises(SqlRejected) as info:
        sqlite_executor(gold_db).execute(altered)

    assert info.value.code == "unknown_table"


def test_sqlite_direct_executor_rejects_dictionary_version_mismatch(gold_db) -> None:
    approved = validate_sql("SELECT bairro FROM gold_indicadores LIMIT 1", DICTIONARY, "sqlite")

    with pytest.raises(SqlRejected) as info:
        sqlite_executor(gold_db).execute(replace(approved, dictionary_version="versao-antiga"))

    assert info.value.code == "invalid_validated_query"


def test_sqlite_executor_caps_rows_and_flags_truncation(gold_db) -> None:
    query = validate_sql("SELECT bairro FROM gold_indicadores", DICTIONARY, "sqlite")

    result = sqlite_executor(gold_db, max_rows=3).execute(query)

    assert result.row_count == 3
    assert result.truncated is True


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM gold_indicadores",
        "UPDATE gold_indicadores SET receita_total = 0",
        "INSERT INTO gold_indicadores (competencia) VALUES ('x')",
        "DROP TABLE gold_indicadores",
        "CREATE TABLE x (a INT)",
        "PRAGMA query_only = OFF",
        "ATTACH DATABASE ':memory:' AS outro",
    ],
)
def test_sqlite_executor_blocks_writes_even_if_validation_is_bypassed(
    gold_db, sql: str, monkeypatch
) -> None:
    # Falha injetada somente no teste: prova a barreira do banco independentemente da AST.
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    with pytest.raises(QueryExecutionError) as info:
        sqlite_executor(gold_db).execute(unchecked(sql))

    assert info.value.kind == "database_error"
    assert count_rows(gold_db) == len(GOLD_ROWS)


def test_sqlite_executor_rejects_multiple_statements(gold_db, monkeypatch) -> None:
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    with pytest.raises(QueryExecutionError):
        sqlite_executor(gold_db).execute(
            unchecked("SELECT bairro FROM gold_indicadores; DELETE FROM gold_indicadores")
        )

    assert count_rows(gold_db) == len(GOLD_ROWS)


def test_sqlite_authorizer_denies_sensitive_columns(gold_db, monkeypatch) -> None:
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    with pytest.raises(QueryExecutionError):
        sqlite_executor(gold_db).execute(unchecked("SELECT cpf_cnpj FROM cadastro_teste"))


def test_sqlite_executor_times_out(gold_db, monkeypatch) -> None:
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    # Produto cartesiano de 8^10 linhas: sem recursão, só lento.
    tables = ", ".join(f"gold_indicadores AS t{i}" for i in range(10))
    slow = unchecked(f"SELECT COUNT(*) FROM {tables}")

    with pytest.raises(QueryExecutionError) as info:
        sqlite_executor(gold_db, timeout_ms=50).execute(slow)

    assert info.value.kind == "timeout"


def test_sqlite_authorizer_denies_recursive_cte(gold_db, monkeypatch) -> None:
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    recursive = unchecked(
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r LIMIT 3) "
        "SELECT COUNT(*) FROM r"
    )

    with pytest.raises(QueryExecutionError) as info:
        sqlite_executor(gold_db).execute(recursive)

    assert info.value.kind == "database_error"


def test_sqlite_executor_refuses_raw_strings_and_other_dialects(gold_db) -> None:
    executor = sqlite_executor(gold_db)

    with pytest.raises(TypeError):
        executor.execute("SELECT bairro FROM gold_indicadores")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        executor.execute(unchecked("SELECT 1", dialect="postgres"))


def test_sqlite_executor_requires_existing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        sqlite_executor(tmp_path / "nao_existe.sqlite")
    assert not (tmp_path / "nao_existe.sqlite").exists()


# --- PostgreSQL com conexão falsa ------------------------------------------------------


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.description = [("municipio",), ("receita",)]

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def execute(self, sql, params=None, prepare=None) -> None:
        self.connection.calls.append((sql, params, prepare))
        if self.connection.error and sql == self.connection.target_sql:
            raise self.connection.error

    def fetchmany(self, size: int):
        self.connection.fetch_sizes.append(size)
        return self.connection.rows[:size]


class FakeConnection:
    def __init__(self, rows=None, error: Exception | None = None, target_sql: str = "") -> None:
        self.rows = rows or []
        self.error = error
        self.target_sql = target_sql
        self.calls: list[tuple] = []
        self.fetch_sizes: list[int] = []
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class CanceledError(Exception):
    sqlstate = "57014"


def pg_query() -> ValidatedQuery:
    return validate_sql(
        "SELECT municipio, SUM(receita_total) AS receita FROM gold_indicadores GROUP BY municipio",
        DICTIONARY,
        "postgres",
    )


def test_postgres_direct_executor_rejects_fabricated_query_before_connecting() -> None:
    connections = 0

    def connect():
        nonlocal connections
        connections += 1
        raise AssertionError("não deve conectar")

    executor = PostgresReadOnlyExecutor(connect, max_rows=5, timeout_ms=1000, dictionary=DICTIONARY)

    with pytest.raises(SqlRejected) as info:
        executor.execute(unchecked("SELECT segredo FROM interna_nao_listada LIMIT 1", "postgres"))

    assert info.value.code == "unknown_table"
    assert connections == 0


def test_postgres_uses_read_only_transaction_timeout_and_rollback() -> None:
    connection = FakeConnection(rows=[("A", 1.0), ("B", 2.0)])
    executor = PostgresReadOnlyExecutor(
        lambda: connection, max_rows=10, timeout_ms=1500, dictionary=DICTIONARY
    )
    query = pg_query()

    result = executor.execute(query)

    statements = [call[0] for call in connection.calls]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert "statement_timeout" in statements[1]
    assert connection.calls[1][1] == ("1500",)
    assert connection.calls[2] == (query.sql, None, True)
    assert connection.fetch_sizes == [11]
    assert connection.rolled_back and connection.closed
    assert result.rows == (("A", 1.0), ("B", 2.0))
    assert result.truncated is False


def test_postgres_caps_rows() -> None:
    connection = FakeConnection(rows=[("A", float(i)) for i in range(20)])
    executor = PostgresReadOnlyExecutor(
        lambda: connection, max_rows=5, timeout_ms=1000, dictionary=DICTIONARY
    )

    result = executor.execute(pg_query())

    assert result.row_count == 5
    assert result.truncated is True


def test_postgres_timeout_is_reported_and_rolled_back() -> None:
    query = pg_query()
    connection = FakeConnection(error=CanceledError("canceling statement"), target_sql=query.sql)
    executor = PostgresReadOnlyExecutor(
        lambda: connection, max_rows=5, timeout_ms=1000, dictionary=DICTIONARY
    )

    with pytest.raises(QueryExecutionError) as info:
        executor.execute(query)

    assert info.value.kind == "timeout"
    assert "canceling" not in str(info.value)
    assert connection.rolled_back and connection.closed


def test_postgres_database_error_hides_message() -> None:
    query = pg_query()
    connection = FakeConnection(
        error=RuntimeError("valor sensível 000.000.000-00"), target_sql=query.sql
    )
    executor = PostgresReadOnlyExecutor(
        lambda: connection, max_rows=5, timeout_ms=1000, dictionary=DICTIONARY
    )

    with pytest.raises(QueryExecutionError) as info:
        executor.execute(query)

    assert info.value.kind == "database_error"
    assert "000.000" not in str(info.value)
    assert connection.rolled_back


def test_postgres_connection_failure() -> None:
    def refuse():
        raise OSError("sem rede")

    executor = PostgresReadOnlyExecutor(refuse, max_rows=5, timeout_ms=1000, dictionary=DICTIONARY)

    with pytest.raises(QueryExecutionError) as info:
        executor.execute(pg_query())

    assert info.value.kind == "connection_error"


@pytest.mark.skipif(
    not os.environ.get("GENAI_TEST_POSTGRES_DSN"),
    reason="defina GENAI_TEST_POSTGRES_DSN para testar contra um PostgreSQL real",
)
def test_postgres_real_server_refuses_write_in_read_only_transaction(monkeypatch) -> None:
    monkeypatch.setattr("app.sql.executors._require_validated_query", lambda *_: None)
    executor = PostgresReadOnlyExecutor.from_dsn(
        os.environ["GENAI_TEST_POSTGRES_DSN"], max_rows=5, timeout_ms=1000, dictionary=DICTIONARY
    )

    with pytest.raises(QueryExecutionError):
        executor.execute(unchecked("CREATE TEMP TABLE agente_ia_teste (a int)", "postgres"))
    with pytest.raises(QueryExecutionError) as info:
        executor.execute(unchecked("SELECT pg_sleep(5)", "postgres"))
    assert info.value.kind == "timeout"
