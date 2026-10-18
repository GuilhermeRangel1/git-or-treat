"""Contratos públicos para perguntas e respostas do agente."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from app.schemas.evidence import EvidenceReference
from app.schemas.responses import PublicResponseMetadata
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
QueryContextText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
ResponseFilterKey = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9._:-]{0,79}$"),
]
ResponseFilterText = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
ResponseLimitation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
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


class AppliedQueryContext(BaseModel):
    """Recorte normalizado que a fonte confirma ter aplicado; ausente enquanto não informado."""

    model_config = ConfigDict(extra="forbid")

    metric: QueryContextText | None = None
    unit: QueryContextText | None = None
    period: QueryContextText | None = None
    filters: dict[
        ResponseFilterKey,
        ResponseFilterText | StrictInt | StrictFloat | StrictBool,
    ] = Field(
        default_factory=dict,
        max_length=20,
    )

    @model_validator(mode="after")
    def require_applied_context(self) -> Self:
        if self.metric is None and self.unit is None and self.period is None and not self.filters:
            raise ValueError("recorte aplicado vazio deve ser omitido")
        return self


class QuestionResponse(PublicResponseMetadata):

    status: QuestionStatus
    answer: ResponseText | None = None
    message: ResponseText | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=20)
    limitations: list[ResponseLimitation] = Field(default_factory=list, max_length=20)
    analysis_context: AppliedQueryContext | None = Field(
        default=None,
        description=(
            "Recorte que a fonte confirma ter aplicado; nulo enquanto a fonte não o fornecer."
        ),
    )

    @model_validator(mode="after")
    def validate_content_for_status(self) -> Self:
        if self.status is QuestionStatus.ANSWERED:
            if self.answer is None or self.message is not None:
                raise ValueError("resposta concluída exige answer e não permite message")
            if not self.evidence:
                raise ValueError("resposta concluída exige ao menos uma evidência")
            if self.error is not None:
                raise ValueError("resposta concluída não deve conter erro")
        elif self.message is None or self.answer is not None:
            raise ValueError("resposta não concluída exige message e não permite answer")
        if self.status in (QuestionStatus.REFUSED, QuestionStatus.RECOVERABLE_ERROR):
            if self.error is None:
                raise ValueError("recusa ou falha exige código público e política de retry")
        elif self.error is not None:
            raise ValueError("esclarecimento e ausência de evidência não devem conter erro")
        return self
