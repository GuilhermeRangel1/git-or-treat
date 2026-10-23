from typing import Annotated, Any, Literal, Self

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

AIContractVersion = Literal["v1"]
AIQuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
AIContextText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
AIResponseText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
AIResponseLimitation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
AIResponseFilterText = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2438),
]
AIIdentifier = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
        min_length=1,
        max_length=120,
    ),
]
AICorrelationId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{32}$", min_length=32, max_length=32),
]


class AIQueryRequest(BaseModel):
    intent: str
    target_table: str
    filters: dict[str, Any] = Field(default_factory=dict)


class AIQueryResponse(BaseModel):
    status: str
    intent: str
    table: str
    records: list[dict[str, Any]]
    evidence: str


class AIConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: AIContextText


class AIQuestionRequest(BaseModel):
    """Contrato v1 entre o portal/backend e o serviço GenAI para o chat."""

    model_config = ConfigDict(extra="forbid")

    contract_version: AIContractVersion = "v1"
    question: AIQuestionText
    context: list[AIConversationTurn] = Field(default_factory=list, max_length=3)


class AIQuestionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "invalid_request",
        "out_of_scope",
        "policy_refusal",
        "security_violation",
        "access_denied",
        "service_unavailable",
        "limit_exceeded",
        "invalid_upstream_response",
        "ungrounded_response",
        "invalid_context",
        "internal_error",
    ]
    retryable: StrictBool


class AIQuestionErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: AIContractVersion = "v1"
    status: Literal["error"] = "error"
    correlation_id: AICorrelationId
    message: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    error: AIQuestionError


class AIEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: AIIdentifier
    description: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    is_demo: StrictBool = False


class AIAnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    period: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    filters: dict[
        AIIdentifier,
        AIResponseFilterText | StrictInt | StrictFloat | StrictBool,
    ] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def require_applied_context(self) -> Self:
        if self.metric is None and self.unit is None and self.period is None and not self.filters:
            raise ValueError("recorte aplicado vazio deve ser omitido")
        return self


class AIQuestionResponse(BaseModel):
    """Envelope v1 da resposta conversacional, alinhado ao serviço GenAI."""

    model_config = ConfigDict(extra="forbid")

    contract_version: AIContractVersion = "v1"
    correlation_id: AICorrelationId | None = None
    audit_reference: str | None = None
    error: AIQuestionError | None = None
    status: Literal[
        "answered",
        "needs_clarification",
        "refused",
        "no_evidence",
        "recoverable_error",
    ]
    model_tier: Literal["light", "strong"] | None = None
    answer: AIResponseText | None = None
    message: AIResponseText | None = None
    evidence: list[AIEvidenceReference] = Field(default_factory=list, max_length=20)
    limitations: list[AIResponseLimitation] = Field(default_factory=list, max_length=20)
    analysis_context: AIAnalysisContext | None = None

    @model_validator(mode="after")
    def validate_status_content(self) -> Self:
        if self.status == "answered":
            if self.answer is None or self.message is not None or not self.evidence:
                raise ValueError("resposta concluída exige answer e evidência, sem message")
            if self.error is not None:
                raise ValueError("resposta concluída não deve conter erro")
        elif self.message is None or self.answer is not None:
            raise ValueError("resposta não concluída exige message, sem answer")

        if self.status in {"refused", "recoverable_error"}:
            if self.error is None:
                raise ValueError("recusa ou falha exige erro público")
        elif self.error is not None:
            raise ValueError("resposta informativa não deve conter erro")
        return self
