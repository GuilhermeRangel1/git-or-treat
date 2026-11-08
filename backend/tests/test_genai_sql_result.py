from decimal import Decimal

import pytest
from app.services.genai_sql_result import (
    SqlResultLimitExceeded,
    SqlResultRejected,
    materialize_sql_result,
)
from app.services.genai_sql_semantics import review_sql_semantics

from tests.test_genai_sql_semantics import attendance_candidate, consumption_query, query, ranking
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


class Cursor:
    def __init__(self, rows, columns=("revenue",)):
        self.rows = iter(rows)
        self.columns = columns
        self.closed = False
        self.reads = 0

    def keys(self):
        return self.columns

    def fetchmany(self, size):
        assert size == 1
        self.reads += 1
        row = next(self.rows, None)
        return [row] if row is not None else []

    def close(self):
        self.closed = True


@pytest.mark.parametrize("rows,status", [([], "empty"), ([(None,)], "all_measures_null"),
    ([(Decimal("0.00"),)], "available"), ([(Decimal("-50.01"),)], "available"),
    ([(Decimal("12345678901234567890.01"),)], "available")])
def test_preserves_decimal_zero_null_and_empty(sql_request, rows, status):
    cursor = Cursor(rows)
    result = materialize_sql_result(cursor, review_sql_semantics(query(sql_request), sql_request))
    assert result.rows == tuple(rows)
    assert result.status == status
    assert cursor.closed
    assert result.serialized_bytes <= 16384


@pytest.mark.parametrize("value,expected", [(12.345, Decimal("12.34")),
                                             (12.355, Decimal("12.36"))])
def test_consumption_float_is_rounded_by_catalog_half_even(sql_request, value, expected):
    candidate, request = consumption_query(sql_request)
    review = review_sql_semantics(candidate, request)
    cursor = Cursor([(value,)], columns=("consumption",))
    result = materialize_sql_result(cursor, review)
    assert result.rows == ((expected,),)
    assert cursor.closed


def test_attendance_count_integer_is_materialized_as_canonical_decimal(sql_request):
    candidate, request = attendance_candidate(sql_request)
    review = review_sql_semantics(candidate, request)
    cursor = Cursor([(6433,)], columns=("attendance",))
    result = materialize_sql_result(cursor, review)
    assert result.rows == ((Decimal("6433"),),)
    assert result.measure_semantics == (("attendance", "attendance_total"),)
    assert result.status == "available"
    assert cursor.closed


@pytest.mark.parametrize("value", [1.2, 1, True, "1.2", Decimal("NaN"),
                                  Decimal("Infinity"), Decimal("1E+1000000")])
def test_invalid_measure_closes_cursor(sql_request, value):
    cursor = Cursor([(value,)])
    with pytest.raises(SqlResultRejected):
        materialize_sql_result(cursor, review_sql_semantics(query(sql_request), sql_request))
    assert cursor.closed


def test_excess_rows_discards_entire_result(sql_request):
    cursor = Cursor([(Decimal(1),)] * 101)
    with pytest.raises(SqlResultLimitExceeded, match="linhas"):
        materialize_sql_result(cursor, review_sql_semantics(query(sql_request), sql_request))
    assert cursor.reads == 101
    assert cursor.closed


def test_excess_bytes_does_not_return_partial_groups(sql_request):
    review = review_sql_semantics(ranking(sql_request), sql_request)
    cursor = Cursor([("cidade-" + "á" * 12000, Decimal(100))], columns=("city", "revenue"))
    with pytest.raises(SqlResultLimitExceeded, match="bytes"):
        materialize_sql_result(cursor, review)
    assert cursor.closed


@pytest.mark.parametrize("columns,row", [(("wrong",), (Decimal(1),)),
    (("revenue", "revenue"), (Decimal(1), Decimal(1))),
    (("revenue",), (Decimal(1), Decimal(2)))])
def test_column_or_row_drift_is_rejected(sql_request, columns, row):
    cursor = Cursor([row], columns)
    with pytest.raises(SqlResultRejected):
        materialize_sql_result(cursor, review_sql_semantics(query(sql_request), sql_request))
    assert cursor.closed


def test_cursor_is_closed_when_driver_read_fails(sql_request):
    cursor = Cursor([])

    def fail(size):
        raise RuntimeError("synthetic read failure")

    cursor.fetchmany = fail
    with pytest.raises(RuntimeError, match="read failure"):
        materialize_sql_result(cursor, review_sql_semantics(query(sql_request), sql_request))
    assert cursor.closed


def test_dimension_null_and_text_preserve_group_identity(sql_request):
    cursor = Cursor([(None, Decimal("0.00")), ("Recife", Decimal("10.01"))],
                    columns=("city", "revenue"))
    result = materialize_sql_result(cursor, review_sql_semantics(ranking(sql_request), sql_request))
    assert result.rows == ((None, Decimal("0.00")), ("Recife", Decimal("10.01")))
    assert result.status == "available"
