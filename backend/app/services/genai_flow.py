"""Preparação B9: decisão explícita de despacho, sem coordenador ou chamadas HTTP."""

from typing import Any, Literal

from app.schemas.genai_evidence import EvidenceLookupResult
from app.schemas.genai_plan import QuestionPlanStatus
from app.services.genai_client import GenAIResponseInvalid


def should_synthesize(
    *,
    planning_status: QuestionPlanStatus,
    lookup: dict[str, Any] | None = None,
    failure: Exception | None = None,
    policy: Literal["completed_lookup"],
) -> bool:
    """Política proposta opt-in: todo lookup concluído válido passa pela síntese.

    O futuro coordenador deve validar envelopes/correlação, autorizar plano e
    conferir prazo/publicação antes de despachar. Esta decisão não concede acesso
    nem ativa a política na aplicação. Cancelamento externo deve propagar.
    """
    if policy != "completed_lookup":
        raise ValueError("Política de síntese não suportada.")
    try:
        status = QuestionPlanStatus(planning_status)
    except (ValueError, TypeError):
        raise GenAIResponseInvalid from None
    if failure is not None:
        return False
    if status is not QuestionPlanStatus.PLANNED:
        if lookup is not None:
            raise GenAIResponseInvalid
        return False
    if not isinstance(lookup, dict):
        raise GenAIResponseInvalid
    try:
        EvidenceLookupResult.model_validate(lookup)
    except ValueError:
        raise GenAIResponseInvalid from None
    return True
