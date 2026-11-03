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
    model_serializer,
    model_validator,
)

from app.schemas.chat_visualization import ChatVisualization

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
        "invalid_continuation",
        "conversation_conflict",
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

    batch_reference: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    metric_label: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    metric_definition: Annotated[str, StringConstraints(min_length=1, max_length=500)] | None = None
    filter_labels: dict[AIIdentifier, Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(default_factory=dict, max_length=20)

    metric: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    unit: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    period: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    filters: dict[
        AIIdentifier,
        AIResponseFilterText | StrictInt | StrictFloat | StrictBool,
    ] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def require_applied_context(self) -> Self:
        if not self.filter_labels.keys() <= self.filters.keys():
            raise ValueError("rótulos exigem filtros aplicados correspondentes")
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
    visualization: ChatVisualization | None = None
    continuation_token: Annotated[str, StringConstraints(min_length=1, max_length=16000)] | None = None

    @model_serializer(mode="wrap")
    def omit_absent_continuation(self, handler):
        data = handler(self)
        if self.visualization is None:
            data.pop("visualization", None)
        if self.continuation_token is None:
            data.pop("continuation_token", None)
        return data

    @model_validator(mode="after")
    def validate_status_content(self) -> Self:
        if self.visualization is not None:
            context = self.analysis_context
            if (self.status != "answered" or context is None or not context.batch_reference
                or not context.batch_reference.startswith("gold-csv-v2:")
                or (context.metric, context.unit, context.period) != (self.visualization.metric, self.visualization.unit, self.visualization.period)
                or not self.evidence or any(e.is_demo or e.source != "gold.local" for e in self.evidence)):
                raise ValueError("visualização exige evidência Gold v2 e recorte correspondente")
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
