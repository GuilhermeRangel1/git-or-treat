import pytest
from pydantic import ValidationError

from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceReference,
    EvidenceResult,
)


def test_available_result_requires_nonempty_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceLookupResult(status=EvidenceLookupStatus.AVAILABLE)

    with pytest.raises(ValidationError):
        EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=EvidenceReference(source="test", description="Evidence test"),
                records=[],
            ),
        )


def test_no_evidence_result_requires_message_and_forbids_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceLookupResult(status=EvidenceLookupStatus.NO_EVIDENCE)

    with pytest.raises(ValidationError):
        EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="No matching records.",
            evidence=EvidenceResult(
                reference=EvidenceReference(source="test", description="Evidence test"),
                records=[{"value": 1}],
            ),
        )


def test_clarification_result_preserves_message_without_data() -> None:
    result = EvidenceLookupResult(
        status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
        message="Which period do you mean?",
    )

    assert result.evidence is None
    assert result.message == "Which period do you mean?"


def test_evidence_result_rejects_more_than_100_records() -> None:
    with pytest.raises(ValidationError):
        EvidenceResult(
            reference=EvidenceReference(source="test", description="Evidence test"),
            records=[{"value": index} for index in range(101)],
        )


def test_evidence_result_rejects_missing_reference_metadata() -> None:
    with pytest.raises(ValidationError):
        EvidenceResult(
            reference=EvidenceReference(source="", description="Evidence test"),
            records=[{"value": 1}],
        )


def test_evidence_contract_has_an_explicit_internal_version() -> None:
    result = EvidenceLookupResult(
        status=EvidenceLookupStatus.NO_EVIDENCE,
        message="A consulta válida não retornou registros.",
    )

    assert result.contract_version == "v1"
    with pytest.raises(ValidationError):
        EvidenceLookupResult(
            contract_version="v2",
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="A consulta válida não retornou registros.",
        )


def test_evidence_reference_source_uses_a_safe_identifier() -> None:
    reference = EvidenceReference(
        source="synthetic_fixture:revenue_demo",
        description="Fonte demonstrativa controlada.",
    )

    assert reference.source == "synthetic_fixture:revenue_demo"
    with pytest.raises(ValidationError):
        EvidenceReference(source="SELECT * FROM gold", description="Valor inválido")
