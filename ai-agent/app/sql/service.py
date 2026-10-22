"""Ponto único de execução: valida, executa o SQL regenerado e audita cada tentativa."""

import time

from app.sql.audit import AuditSink, QueryAuditRecord, fingerprint
from app.sql.dictionary import SqlDictionary
from app.sql.executors import QueryExecutionError, QueryResult, ReadOnlyExecutor
from app.sql.validator import SqlRejected, validate_sql


class ReadOnlySqlService:
    def __init__(
        self,
        dictionary: SqlDictionary,
        executor: ReadOnlyExecutor,
        audit: AuditSink,
    ) -> None:
        self._dictionary = dictionary
        self._executor = executor
        self._audit = audit

    def run(
        self, sql: str, parameters: tuple[str | int | float | bool, ...] = ()
    ) -> QueryResult:
        """Executa uma consulta gerada; levanta SqlRejected ou QueryExecutionError após auditar."""

        base = {
            "dialect": self._executor.dialect,
            "dictionary_version": self._dictionary.version,
            "received_sql_sha256": fingerprint(sql),
            "received_sql_chars": len(sql),
        }
        try:
            query = validate_sql(sql, self._dictionary, self._executor.dialect, parameters)
        except SqlRejected as exc:
            self._audit.record(QueryAuditRecord(status="rejected", reason_code=exc.code, **base))
            raise

        approved = {
            **base,
            "executed_sql": query.sql,
            "tables": query.tables,
            "original_limit": query.original_limit,
            "applied_limit": query.applied_limit,
            "limit_adjusted": query.limit_adjusted,
        }
        started = time.perf_counter()
        try:
            result = self._executor.execute(query)
        except QueryExecutionError as exc:
            self._audit.record(
                QueryAuditRecord(
                    status="failed",
                    reason_code=exc.kind,
                    error_type=exc.error_type,
                    duration_ms=_elapsed_ms(started),
                    **approved,
                )
            )
            raise

        self._audit.record(
            QueryAuditRecord(
                status="accepted",
                row_count=result.row_count,
                truncated=result.truncated,
                duration_ms=_elapsed_ms(started),
                **approved,
            )
        )
        return result


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
