import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisIntent


def test_absent_phrases_and_filters_are_distinct_from_explicit_nulls() -> None:
    intent = AnalysisIntent(domain="consumption")

    assert intent.metric_phrase is None
    assert intent.period_phrase is None
    assert intent.filters == {}

    with pytest.raises(ValidationError):
        AnalysisIntent(domain="consumption", metric_phrase=None)

    with pytest.raises(ValidationError):
        AnalysisIntent(
            domain="consumption",
            filters={"municipio": None},
        )


def test_filter_values_preserve_their_input_type() -> None:
    intent = AnalysisIntent(
        domain="consumption",
        filters={"ano": 2025},
    )

    assert type(intent.filters["ano"]) is int


def test_multi_value_filters_support_the_read_plan_limit():
    values = tuple(f"Cidade {index}" for index in range(1, 6))
    intent = AnalysisIntent(
        domain="revenue",
        filters={"geography.municipality": values},
    )
    assert intent.filters["geography.municipality"] == values

    with pytest.raises(ValidationError):
        AnalysisIntent(domain="revenue", filters={"geography.municipality": ("Recife",)})
    with pytest.raises(ValidationError):
        AnalysisIntent(
            domain="revenue",
            filters={"geography.municipality": tuple(str(i) for i in range(21))},
        )


def test_logical_ids_follow_a_stable_format() -> None:
    intent = AnalysisIntent(
        domain="revenue",
        metric_id="billing.revenue",
        dimension_ids=["geography.municipality"],
        filters={"geography.municipality": "Exemplo"},
    )

    assert intent.metric_id == "billing.revenue"
    assert intent.dimension_ids == ["geography.municipality"]
    assert intent.contract_version == "v1"

    with pytest.raises(ValidationError):
        AnalysisIntent(domain="revenue", metric_id="Gold.Revenue Table")
    with pytest.raises(ValidationError):
        AnalysisIntent(domain="revenue", contract_version="v2")
