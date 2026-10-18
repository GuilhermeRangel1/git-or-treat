"""Contratos públicos para perguntas e respostas do agente."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.evidence import EvidenceReference
from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ContextText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ResponseText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class QuestionStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    REFUSED = "refused"
    NO_EVIDENCE = "no_evidence"
    RECOVERABLE_ERROR = "recoverable_error"


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: ContextText


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    question: QuestionText
    context: list[ConversationTurn] = Field(default_factory=list, max_length=3)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: QuestionStatus
    answer: ResponseText | None = None
    message: ResponseText | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_for_status(self) -> Self:
        if self.status is QuestionStatus.ANSWERED:
            if self.answer is None or self.message is not None:
                raise ValueError("resposta concluída exige answer e não permite message")
            if not self.evidence:
                raise ValueError("resposta concluída exige ao menos uma evidência")
        elif self.message is None or self.answer is not None:
            raise ValueError("resposta não concluída exige message e não permite answer")
        return self
