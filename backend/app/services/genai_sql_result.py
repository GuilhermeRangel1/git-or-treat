"""Materialização limitada de resultado SQL F1; não executa nem autoriza SQL."""

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from app.services.genai_sql_semantics import SqlSemanticReview

MAX_SQL_RESULT_ROWS = 100
MAX_SQL_RESULT_BYTES = 16_384


class SqlResultRejected(ValueError):
    """Resultado incompatível, sem SQL, valores ou detalhes do driver no erro."""


class SqlResultLimitExceeded(SqlResultRejected):
    """Resultado descartado integralmente porque ultrapassou o limite."""


class SqlResultCursor(Protocol):
    def keys(self) -> Sequence[str]: ...
    def fetchmany(self, size: int) -> Sequence[Sequence[object]]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class SqlMaterializedResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[str | Decimal | None, ...], ...]
    measure_semantics: tuple[tuple[str, str], ...]
    status: Literal["empty", "all_measures_null", "available"]
    serialized_bytes: int


def _value(value: object, *, measure: bool):
    if value is None:
        return None
    if measure:
        if (type(value) is not Decimal or not value.is_finite()
                or abs(value.adjusted()) > 100 or abs(value.as_tuple().exponent) > 100):
            raise SqlResultRejected("Medida SQL exige Decimal finito dentro do limite F1.")
        return value
    if type(value) is not str:
        raise SqlResultRejected("Dimensão SQL exige texto ou nulo.")
    if len(value) > MAX_SQL_RESULT_BYTES:
        raise SqlResultLimitExceeded("Dimensão SQL excede o limite de bytes.")
    return value


def _encoded(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
                          default=lambda item: format(item, "f")).encode("utf-8")
    except (ValueError, UnicodeError, TypeError):
        raise SqlResultRejected("Resultado SQL não serializável no contrato F1.") from None


def sql_result_digest(result: SqlMaterializedResult) -> str:
    payload = {"columns": result.columns, "measure_semantics": result.measure_semantics,
               "rows": result.rows, "status": result.status}
    return hashlib.sha256(_encoded(payload)).hexdigest()


def materialize_sql_result(
    cursor: SqlResultCursor, review: SqlSemanticReview,
    *, check_active: Callable[[], None] | None = None,
) -> SqlMaterializedResult:
    """Lê incrementalmente e fecha o cursor em sucesso ou falha.

    O chamador deve permanecer no snapshot de execução até esta função terminar.
    Nenhuma linha é devolvida quando há excesso; não existe truncamento silencioso.
    """
    try:
        columns = tuple(cursor.keys())
        if columns != review.output_names or len(set(columns)) != len(columns):
            raise SqlResultRejected("Colunas SQL divergem da revisão admitida.")
        measures = {name for name, _ in review.measure_semantics}
        if not measures or not measures <= set(columns):
            raise SqlResultRejected("Linhagem de medidas SQL incompatível.")
        header = {"columns": columns, "measure_semantics": review.measure_semantics,
                  "rows": [], "status": "all_measures_null"}
        size = len(_encoded(header))
        rows = []
        while True:
            if check_active is not None:
                check_active()
            batch = cursor.fetchmany(1)
            if not batch:
                break
            if len(batch) != 1 or len(rows) >= MAX_SQL_RESULT_ROWS:
                raise SqlResultLimitExceeded("Resultado SQL excede o limite de linhas.")
            raw = batch[0]
            if isinstance(raw, Mapping) or len(raw) != len(columns):
                raise SqlResultRejected("Linha SQL diverge das colunas declaradas.")
            row = tuple(_value(value, measure=name in measures)
                        for name, value in zip(columns, raw, strict=True))
            size += len(_encoded(row)) + bool(rows)
            if size > MAX_SQL_RESULT_BYTES:
                raise SqlResultLimitExceeded("Resultado SQL excede o limite de bytes.")
            rows.append(row)
        if size > MAX_SQL_RESULT_BYTES:
            raise SqlResultLimitExceeded("Resultado SQL excede o limite de bytes.")
        has_measure = any(row[index] is not None for row in rows
                          for index, name in enumerate(columns) if name in measures)
        status = "empty" if not rows else "available" if has_measure else "all_measures_null"
        if check_active is not None:
            check_active()
        header.update(rows=rows, status=status)
        return SqlMaterializedResult(columns, tuple(rows), review.measure_semantics,
                                     status, len(_encoded(header)))
    finally:
        cursor.close()
