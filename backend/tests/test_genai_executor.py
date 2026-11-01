from decimal import Decimal

import pytest

from app.schemas.ai import AIEvidenceReference
from app.schemas.genai_evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceResult,
)
from app.services.genai_executor import (
    MAX_EVIDENCE_BYTES,
    GoldExecutionDenied,
    _exceeds_evidence_byte_limit,
    _rounded_number,
)


def _result(extra_bytes: int = 0) -> EvidenceLookupResult:
    return EvidenceLookupResult(
        status=EvidenceLookupStatus.AVAILABLE,
        evidence=EvidenceResult(
            reference=AIEvidenceReference(
                source="gold.local",
                description="Evidência de teste",
                is_demo=False,
            ),
            records=[{"value": 1, "padding": "x" * extra_bytes}],
        ),
    )


def test_evidence_limit_counts_the_serialized_response_in_utf8_bytes():
    assert not _exceeds_evidence_byte_limit(_result())
    assert _exceeds_evidence_byte_limit(_result(MAX_EVIDENCE_BYTES + 1))


@pytest.mark.parametrize("raw,expected", [("1.005", 1.0), ("1.015", 1.02), ("-1.015", -1.02)])
def test_numeric_evidence_uses_catalog_half_even_rounding(raw, expected):
    assert _rounded_number(Decimal(raw), 2) == expected


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_measure_never_becomes_numeric_evidence(raw):
    with pytest.raises(GoldExecutionDenied):
        _rounded_number(Decimal(raw), 2)
