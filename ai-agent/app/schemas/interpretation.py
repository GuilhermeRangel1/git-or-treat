"""Resultado explícito da interpretação determinística de uma pergunta."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.scenarios import AnalysisIntent


class InterpretationStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"


class IntentInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InterpretationStatus
    intent: AnalysisIntent | None = None
    clarification_question: str | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is InterpretationStatus.READY:
            if self.intent is None or self.clarification_question is not None:
                raise ValueError(
                    "interpretação pronta exige intenção e não pode pedir esclarecimento"
                )
        elif self.intent is not None or not self.clarification_question:
            raise ValueError("esclarecimento exige pergunta e não pode expor intenção parcial")
        return self
