import pytest
from pydantic import ValidationError

from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import EvidenceReference
from app.schemas.insights import (
    InsightContextSummary,
    InsightObservation,
    ScreenInsightResponse,
    ScreenObservationValue,
    ScreenPeriod,
)
from app.schemas.questions import QuestionResponse, QuestionStatus
from app.schemas.responses import FailureCode, PublicErrorCode, map_failure


def test_generated_answer_rejects_blank_and_oversized_text() -> None:
    for answer in ("", "   ", "x" * 4001):
        with pytest.raises(ValidationError):
            GeneratedAnswer(status="answered", answer=answer)


def test_internal_failures_map_to_safe_public_codes_and_retry_policy() -> None:
    unavailable = map_failure(FailureCode.SOURCE_UNAVAILABLE)
    denied = map_failure(FailureCode.ACCESS_DENIED)
    invalid_output = map_failure(FailureCode.INVALID_MODEL_OUTPUT)

    assert unavailable.error.code is PublicErrorCode.SERVICE_UNAVAILABLE
    assert unavailable.error.retryable is True
    assert unavailable.message == "A consulta está temporariamente indisponível. Tente novamente."
    assert denied.error.code is PublicErrorCode.ACCESS_DENIED
    assert denied.error.retryable is False
    assert invalid_output.error.code is PublicErrorCode.INVALID_UPSTREAM_RESPONSE
    assert invalid_output.error.retryable is False
    assert all(map_failure(code).message for code in FailureCode)


def test_question_response_requires_content_consistent_with_status() -> None:
    with pytest.raises(ValidationError):
        QuestionResponse(status=QuestionStatus.ANSWERED)
    with pytest.raises(ValidationError):
        QuestionResponse(status=QuestionStatus.ANSWERED, answer=" ")
    with pytest.raises(ValidationError):
        QuestionResponse(status=QuestionStatus.RECOVERABLE_ERROR)
    with pytest.raises(ValidationError):
        QuestionResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            answer="resposta incompatível",
            message="erro",
        )
    with pytest.raises(ValidationError):
        QuestionResponse(status=QuestionStatus.ANSWERED, answer="42.")


def test_question_response_accepts_only_compatible_success_and_error_shapes() -> None:
    reference = EvidenceReference(
        source="synthetic:test",
        description="Evidência artificial para contrato.",
        is_demo=True,
    )
    success = QuestionResponse(
        status=QuestionStatus.ANSWERED,
        answer="Valor demonstrativo: 42.",
        evidence=[reference],
    )
    error = QuestionResponse(
        status=QuestionStatus.RECOVERABLE_ERROR,
        message=map_failure(FailureCode.MODEL_UNAVAILABLE).message,
        error=map_failure(FailureCode.MODEL_UNAVAILABLE).error,
    )

    assert success.contract_version == "v1"
    assert success.correlation_id is None
    assert success.audit_reference is None
    assert success.answer == "Valor demonstrativo: 42."
    assert success.message is None
    assert error.answer is None
    assert error.message == (
        "O serviço de resposta está temporariamente indisponível. Tente novamente."
    )
    assert error.error is not None
    assert error.error.retryable is True


def test_failed_question_response_requires_safe_error_metadata() -> None:
    with pytest.raises(ValidationError):
        QuestionResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            message="Tente novamente.",
        )


def test_public_response_version_rejects_unsupported_contracts() -> None:
    with pytest.raises(ValidationError):
        QuestionResponse(
            contract_version="v2",
            status=QuestionStatus.NEEDS_CLARIFICATION,
            message="Qual período você quer consultar?",
        )


def test_insight_response_requires_a_message_for_non_success_states() -> None:
    context = InsightContextSummary(
        metric="consumo demonstrativo",
        unit="kWh fictícios",
        period=ScreenPeriod(
            start="2025-01-01",
            end="2025-01-31",
            granularity="month",
        ),
        filters={"municipio": "Exemplo"},
    )
    observation = InsightObservation(
        values=[ScreenObservationValue(label="consumo", value=42)]
    )
    reference = EvidenceReference(
        source="synthetic:test",
        description="Contexto artificial de contrato.",
        is_demo=True,
    )

    with pytest.raises(ValidationError):
        ScreenInsightResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            context=context,
            observation=observation,
            evidence=[reference],
        )
    with pytest.raises(ValidationError):
        ScreenInsightResponse(
            status=QuestionStatus.ANSWERED,
            context=context,
            observation=observation,
            hypothesis="Hipótese de demonstração.",
        )
