"""Resultado explícito da interpretação determinística de uma pergunta."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisIntent


class InterpretationStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"


class ClarificationReason(StrEnum):
    """Estado interno para continuidade, independente do texto apresentado."""

    MISSING_METRIC = "missing_metric"
    MISSING_PERIOD = "missing_period"
    MISSING_YEAR = "missing_year"
    AMBIGUOUS_METRIC = "ambiguous_metric"
    AMBIGUOUS_DIMENSION = "ambiguous_dimension"
    MULTIPLE_METRICS = "multiple_metrics"
    CONFLICTING_RANKING = "conflicting_ranking"
    UNSUPPORTED_FILTER = "unsupported_filter"
    UNSUPPORTED_COMPARISON = "unsupported_comparison"
    UNIT_MISMATCH = "unit_mismatch"


class IntentInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InterpretationStatus
    intent: AnalysisIntent | None = None
    clarification_question: str | None = None
    clarification_reason: ClarificationReason | None = None
    pending_question: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is InterpretationStatus.READY:
            if (self.intent is None or self.clarification_question is not None
                    or self.clarification_reason is not None or self.pending_question is not None):
                raise ValueError(
                    "interpretação pronta exige intenção e não pode pedir esclarecimento"
                )
        elif self.intent is not None or not self.clarification_question:
            raise ValueError("esclarecimento exige pergunta e não pode expor intenção parcial")
        return self
