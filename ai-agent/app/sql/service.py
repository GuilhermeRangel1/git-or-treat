"""Ponto único de execução: valida, executa o SQL regenerado e audita cada tentativa."""

import time

from app.sql.audit import (
    AuditSink,
    QueryAuditRecord,
    SqlAuditContext,
    template_fingerprint,
    validate_correlation_id,
)
from app.sql.dictionary import SqlDictionary
from app.sql.executors import QueryExecutionError, QueryResult, ReadOnlyExecutor
from app.sql.validator import SqlRejected, validate_sql

_PRE_SQL_REJECTION_CODES = frozenset(
    {
        "access_denied",
        "unsupported_plan",
        "plan_out_of_catalog",
        "unsupported_window",
        "unsupported_filter",
    }
)


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

    def record_pre_sql_rejection(
        self, reason_code: str, *, correlation_id: str | None = None
    ) -> None:
        """Registra recusa anterior ao SQL sem copiar plano, filtros ou exceção."""

        if reason_code not in _PRE_SQL_REJECTION_CODES:
            raise ValueError("motivo de recusa anterior ao SQL inválido")
        validate_correlation_id(correlation_id)
        self._audit.record(
            QueryAuditRecord(
                status="rejected",
                reason_code=reason_code,
                dialect=self._executor.dialect,
                dictionary_version=self._dictionary.version,
                received_sql_chars=0,
                correlation_id=correlation_id,
            )
        )

    def run(
        self,
        sql: str,
        parameters: tuple[str | int | float | bool, ...] = (),
        *,
        audit_context: SqlAuditContext | None = None,
    ) -> QueryResult:
        """Executa uma consulta gerada; levanta SqlRejected ou QueryExecutionError após auditar."""

        if audit_context is not None and not isinstance(audit_context, SqlAuditContext):
            raise TypeError("contexto de auditoria inválido")
        base = {
            "dialect": self._executor.dialect,
            "dictionary_version": self._dictionary.version,
            "received_sql_chars": len(sql) if isinstance(sql, str) else 0,
            "plan_fingerprint": (
                audit_context.plan_fingerprint if audit_context is not None else None
            ),
            "catalog_version": audit_context.catalog_version if audit_context is not None else None,
            "correlation_id": audit_context.correlation_id if audit_context is not None else None,
        }
        try:
            if not isinstance(sql, str):
                raise SqlRejected("invalid_sql_input", "consulta precisa ser texto SQL")
            query = validate_sql(sql, self._dictionary, self._executor.dialect, parameters)
        except SqlRejected as exc:
            self._audit.record(QueryAuditRecord(status="rejected", reason_code=exc.code, **base))
            raise

        approved = {
            **base,
            "query_template": query.sql_template,
            "query_template_sha256": template_fingerprint(query.sql_template),
            "tables": query.tables,
            "original_limit": query.original_limit,
            "applied_limit": query.applied_limit,
            "limit_adjusted": query.limit_adjusted,
        }
        started = time.perf_counter()
        try:
            result = self._executor.execute(query)
        except SqlRejected as exc:
            self._audit.record(
                QueryAuditRecord(
                    status="rejected",
                    reason_code=exc.code,
                    duration_ms=_elapsed_ms(started),
                    **approved,
                )
            )
            raise
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
