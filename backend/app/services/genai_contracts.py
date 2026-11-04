"""Validação B11 de respostas internas, ainda sem cliente das futuras rotas."""

from typing import Any, TypeVar

from pydantic import BaseModel

from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_internal import QuestionPlanResponse
from app.services.genai_client import GenAIResponseInvalid

T = TypeVar("T", bound=BaseModel)


def _validate_response(
    schema: type[T], payload: dict[str, Any], correlation_id: str, header_correlation_id: str | None
) -> T:
    try:
        response = schema.model_validate(payload)
    except ValueError:
        raise GenAIResponseInvalid from None
    if header_correlation_id != correlation_id or response.correlation_id != correlation_id:
        raise GenAIResponseInvalid
    return response


def validate_plan_response(
    payload: dict[str, Any], *, correlation_id: str, header_correlation_id: str | None
) -> QuestionPlanResponse:
    return _validate_response(QuestionPlanResponse, payload, correlation_id, header_correlation_id)


def validate_synthesis_response(
    payload: dict[str, Any], *, correlation_id: str, header_correlation_id: str | None
) -> AIQuestionResponse:
    return _validate_response(AIQuestionResponse, payload, correlation_id, header_correlation_id)
