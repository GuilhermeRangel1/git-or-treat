"""Semântica de conjuntos na fronteira pública da validação de afirmações."""

import pytest

from app.agent.grounding import has_unsupported_claims
from app.providers.protocols import GeneratedAnswer


def check_filters(values, expected, *, operator="in", claim_operator="in"):
    generated = GeneratedAnswer.model_validate({
        "status": "answered", "answer": "Observação selecionada.",
        "observation_ids": ["row_1"],
        "claims": [{
            "observation_id": "row_1", "value": 90, "metric": "energy.consumption",
            "unit": "kWh", "period": "2025-01", "filters": {"region": values},
            "filter_operators": {"region": claim_operator},
        }],
    })
    return has_unsupported_claims(
        generated, {"row_1": {"value": 90, "unit": "kWh"}},
        metric="energy.consumption", period="2025-01", filters={"region": expected},
        filter_operators={"region": operator},
    )


def test_in_filter_accepts_same_values_in_reverse_order():
    assert not check_filters(["Olinda", "Recife"], ["Recife", "Olinda"])


@pytest.mark.parametrize("values,expected", [
    (["Olinda", "Recife", "Olinda"], ["Recife", "Olinda"]),
    ([False, 2, "Recife"], ["Recife", 2, False]),
    ([1.5, 2.5], [2.5, 1.5]),
])
def test_in_compares_membership_without_sorting_or_coercion(values, expected):
    assert not check_filters(values, expected)


@pytest.mark.parametrize("values,expected", [
    (["Olinda"], ["Olinda", "Recife"]),
    (["Olinda", "Recife", "Paulista"], ["Olinda", "Recife"]),
    (["Olinda", "Paulista"], ["Olinda", "Recife"]),
    (["1", 2], [1, 2]),
    ([True, 2], [1, 2]),
    ([1.0, 2], [1, 2]),
    ("Recife", ["Olinda", "Recife"]),
])
def test_in_rejects_changed_members_types_or_shape(values, expected):
    assert check_filters(values, expected)


def test_non_in_filter_keeps_order_sensitive_comparison():
    assert check_filters(["Olinda", "Recife"], ["Recife", "Olinda"],
                         operator="eq", claim_operator="eq")


def test_in_still_rejects_wrong_operator_even_with_identical_members():
    assert check_filters(["Olinda", "Recife"], ["Recife", "Olinda"], claim_operator="ne")


def test_non_in_scalar_preserves_type_and_exact_match():
    assert not check_filters("Recife", "Recife", operator="eq", claim_operator="eq")
    assert check_filters(True, 1, operator="eq", claim_operator="eq")
