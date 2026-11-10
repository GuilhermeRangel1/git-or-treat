from datetime import date
from decimal import Decimal

import pytest
from app.schemas.sql_generation import SqlParameter
from app.services.genai_sql_parameters import (
    SqlParameterMismatch,
    prepare_sql_parameters,
)


def test_prepares_native_values_without_losing_decimal_precision():
    parameters = {
        "start": SqlParameter(type="date", value="2025-05-01"),
        "amount": SqlParameter(type="decimal", value="12345678901234567890.01"),
        "label": SqlParameter(type="string", value="Recife"),
    }
    result = prepare_sql_parameters(parameters, referenced_names=frozenset(parameters))
    assert result == {"start": date(2025, 5, 1),
                      "amount": Decimal("12345678901234567890.01"), "label": "Recife"}
    assert parameters["start"].value == "2025-05-01"


@pytest.mark.parametrize("references", [frozenset(), frozenset({"other"}),
                                         frozenset({"name", "extra"})])
def test_rejects_missing_unused_or_substituted_parameters(references):
    with pytest.raises(SqlParameterMismatch):
        prepare_sql_parameters({"name": SqlParameter(type="string", value="Recife")},
                               referenced_names=references)


def test_accepts_query_without_parameters():
    assert prepare_sql_parameters({}, referenced_names=frozenset()) == {}
