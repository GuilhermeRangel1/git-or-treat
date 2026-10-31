from app.schemas.ai import AIEvidenceReference
from app.schemas.genai_evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceResult,
)
from app.services.genai_executor import MAX_EVIDENCE_BYTES, _exceeds_evidence_byte_limit


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
