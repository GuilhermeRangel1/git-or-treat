"""Camada SQL somente leitura do agente Text-to-SQL."""

from app.sql.audit import InMemoryAuditSink, LoggingAuditSink, QueryAuditRecord
from app.sql.dictionary import DEFAULT_DICTIONARY_PATH, SqlDictionary, load_dictionary
from app.sql.executors import (
    PostgresReadOnlyExecutor,
    QueryExecutionError,
    QueryResult,
    SqliteReadOnlyExecutor,
)
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected, ValidatedQuery, validate_sql

__all__ = [
    "DEFAULT_DICTIONARY_PATH",
    "InMemoryAuditSink",
    "LoggingAuditSink",
    "PostgresReadOnlyExecutor",
    "QueryAuditRecord",
    "QueryExecutionError",
    "QueryResult",
    "ReadOnlySqlService",
    "SqlDictionary",
    "SqlRejected",
    "SqliteReadOnlyExecutor",
    "ValidatedQuery",
    "load_dictionary",
    "validate_sql",
]
