"""Contratos de metadados do histórico; identidade é resolvida pelo servidor."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.ai import AIQuestionResponse, AIQuestionText
from app.schemas.ai_question_publication import AIExpectedPublication

ConversationTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ConversationRename(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ConversationTitle
    expected_revision: int = Field(strict=True, ge=1)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: ConversationTitle
    revision: int = Field(strict=True, ge=1)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    message_count: int = Field(strict=True, ge=0)


class ConversationListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConversationSummary] = Field(max_length=50)
    has_more: bool


class ConversationExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    state: Literal["pending", "completed", "interrupted", "unavailable"]
    question: AIQuestionText | None
    response: AIQuestionResponse | None


class ConversationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationSummary
    exchanges: list[ConversationExchange] = Field(max_length=200)
    historical: Literal[True]


class ConversationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    question: AIQuestionText
    expected_publication: AIExpectedPublication | None = None
    refresh_context: bool = Field(default=False, strict=True)
