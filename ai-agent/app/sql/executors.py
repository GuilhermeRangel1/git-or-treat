"""Executores somente leitura para SQL já aprovado pelo validador.

Os executores são uma segunda barreira, independente do validador: abrem o banco em modo de
leitura, impõem timeout e teto de linhas e nunca recebem texto SQL cru.
"""

import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.sql.dictionary import SqlDictionary
from app.sql.validator import SqlRejected, ValidatedQuery, validate_sql

_PROGRESS_STEPS = 1_000

# Ações que o autorizador do SQLite permite durante a compilação de um SELECT.
_SQLITE_ALLOWED_ACTIONS = frozenset(
    {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
)

_PG_QUERY_CANCELED = "57014"


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    truncated: bool

    @property
    def row_count(self) -> int:
        return len(self.rows)


class QueryExecutionError(Exception):
    """Falha ao executar uma consulta aprovada; a mensagem não inclui dados do banco."""

    def __init__(self, kind: str, error_type: str) -> None:
        super().__init__(f"{kind}: {error_type}")
        self.kind = kind
        self.error_type = error_type


class ReadOnlyExecutor(Protocol):
    dialect: str

    def execute(self, query: ValidatedQuery) -> QueryResult: ...


class SqliteReadOnlyExecutor:
    """Abre o arquivo com mode=ro e query_only, com autorizador e interrupção por tempo."""

    dialect = "sqlite"

    def __init__(
        self,
        database_path: Path | str,
        max_rows: int,
        timeout_ms: int,
        dictionary: SqlDictionary,
        sensitive_columns: frozenset[str] = frozenset(),
    ) -> None:
        path = Path(database_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        self._uri = f"{path.as_uri()}?mode=ro"
        self._max_rows = max_rows
        self._timeout_ms = timeout_ms
        self._dictionary = dictionary
        self._sensitive = frozenset(
            c.casefold() for c in dictionary.sensitive_columns | sensitive_columns
        )

    def execute(self, query: ValidatedQuery) -> QueryResult:
        _require_validated_query(query, self.dialect, self._dictionary)
        connection = sqlite3.connect(self._uri, uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.set_authorizer(self._authorize)
            deadline = time.monotonic() + self._timeout_ms / 1000
            connection.set_progress_handler(
                lambda: int(time.monotonic() > deadline), _PROGRESS_STEPS
            )
            try:
                cursor = connection.execute(query.sql, query.parameters)
                rows = cursor.fetchmany(self._max_rows + 1)
            except sqlite3.Error as exc:
                if time.monotonic() > deadline:
                    raise QueryExecutionError("timeout", type(exc).__name__) from exc
                raise QueryExecutionError("database_error", type(exc).__name__) from exc
            columns = tuple(d[0] for d in cursor.description or ())
        finally:
            connection.close()
        return _result(columns, rows, self._max_rows)

    def _authorize(
        self, action: int, arg1: str | None, arg2: str | None, database: str | None,
        _origin: str | None,
    ) -> int:
        if action not in _SQLITE_ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ:
            table = self._dictionary.tables.get((arg1 or "").casefold())
            column = (arg2 or "").casefold()
            # COUNT(*) sobre uma CTE materializada não referencia tabela física.
            # As leituras físicas da CTE recebem database="main" e são verificadas abaixo.
            if database is None and not column:
                return sqlite3.SQLITE_OK
            if (
                database != "main"
                or table is None
                or column in self._sensitive
                or (column and column not in table.columns)
            ):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


class PostgresReadOnlyExecutor:
    """Executa em transação READ ONLY com statement_timeout local, sempre desfeita ao final.

    A credencial do DSN também deve ser de um papel somente leitura: a transação read-only é
    defesa em profundidade, não substitui a permissão no banco.
    """

    dialect = "postgres"

    def __init__(
        self, connect: Callable[[], Any], max_rows: int, timeout_ms: int, dictionary: SqlDictionary
    ) -> None:
        self._connect = connect
        self._max_rows = max_rows
        self._timeout_ms = timeout_ms
        self._dictionary = dictionary

    @classmethod
    def from_dsn(
        cls, dsn: str, max_rows: int, timeout_ms: int, dictionary: SqlDictionary
    ) -> "PostgresReadOnlyExecutor":
        import psycopg  # extra opcional "postgres"

        connect_timeout = max(1, timeout_ms // 1000)
        return cls(
            lambda: psycopg.connect(dsn, autocommit=False, connect_timeout=connect_timeout),
            max_rows=max_rows,
            timeout_ms=timeout_ms,
            dictionary=dictionary,
        )

    def execute(self, query: ValidatedQuery) -> QueryResult:
        _require_validated_query(query, self.dialect, self._dictionary)
        try:
            connection = self._connect()
        except Exception as exc:
            raise QueryExecutionError("connection_error", type(exc).__name__) from exc
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(self._timeout_ms),),
                )
                # prepare=True usa o protocolo estendido, que não aceita várias instruções.
                cursor.execute(query.sql, query.parameters or None, prepare=True)
                rows = cursor.fetchmany(self._max_rows + 1)
                columns = tuple(d[0] for d in cursor.description or ())
        except QueryExecutionError:
            raise
        except Exception as exc:
            kind = (
                "timeout"
                if getattr(exc, "sqlstate", None) == _PG_QUERY_CANCELED
                else "database_error"
            )
            raise QueryExecutionError(kind, type(exc).__name__) from exc
        finally:
            try:
                connection.rollback()
            finally:
                connection.close()
        return _result(columns, rows, self._max_rows)


def _require_validated_query(
    query: ValidatedQuery, dialect: str, dictionary: SqlDictionary
) -> None:
    if not isinstance(query, ValidatedQuery):
        raise TypeError("o executor aceita somente ValidatedQuery")
    if query.dialect != dialect:
        raise ValueError(f"consulta validada para {query.dialect}, executor {dialect}")
    approved = validate_sql(query.sql, dictionary, dialect, query.parameters)
    if (
        query.sql != approved.sql
        or query.tables != approved.tables
        or query.dictionary_version != dictionary.version
        or query.applied_limit != approved.applied_limit
    ):
        raise SqlRejected("invalid_validated_query", "consulta não corresponde à validação atual")


def _result(columns: tuple[str, ...], rows: Sequence[Sequence[Any]], max_rows: int) -> QueryResult:
    truncated = len(rows) > max_rows
    return QueryResult(
        columns=columns,
        rows=tuple(tuple(row) for row in rows[:max_rows]),
        truncated=truncated,
    )
