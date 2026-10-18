"""Contratos públicos para perguntas e respostas do agente."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.evidence import EvidenceReference

QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
ContextText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
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

    question: QuestionText
    context: list[ConversationTurn] = Field(default_factory=list, max_length=3)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: QuestionStatus
    answer: str | None = None
    message: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
