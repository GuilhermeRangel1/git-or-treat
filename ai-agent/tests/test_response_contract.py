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


def test_generated_answer_rejects_blank_and_oversized_text() -> None:
    for answer in ("", "   ", "x" * 4001):
        with pytest.raises(ValidationError):
            GeneratedAnswer(status="answered", answer=answer)


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
        message="Tente novamente.",
    )

    assert success.answer == "Valor demonstrativo: 42."
    assert success.message is None
    assert error.answer is None
    assert error.message == "Tente novamente."


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
