"""Contratos locais do proxy de insight entre Panorama, Backend e GenAI."""

from datetime import date
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

AIInsightFilterValue = StrictStr | StrictInt | StrictFloat | StrictBool
AIInsightStatus = Literal[
    "answered",
    "needs_clarification",
    "refused",
    "no_evidence",
    "recoverable_error",
]
AIInsightErrorCode = Literal[
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
AIInsightText = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
AIInsightLimitation = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class PanoramaInsightFilters(BaseModel):
    """Filtros permitidos para gerar o recorte a partir da fonte do servidor."""

    model_config = ConfigDict(extra="forbid")

    periodo: Annotated[StrictStr, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    comparacao: Literal["anterior", "ano_anterior", "nenhuma"]
    municipio: Annotated[StrictStr, StringConstraints(min_length=1, max_length=100)]
    classe: Annotated[StrictStr, StringConstraints(min_length=1, max_length=100)]


class PanoramaInsightRequest(BaseModel):
    """Pedido público: filtros e versão exibida; nunca recebe métricas do navegador."""

    model_config = ConfigDict(extra="forbid")

    filters: PanoramaInsightFilters
    loteVersao: Annotated[
        StrictStr,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ]


class AIInsightPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    granularity: Literal["day", "month", "quarter", "year"]

    @model_validator(mode="after")
    def require_ordered_period(self) -> Self:
        if self.start > self.end:
            raise ValueError("o início do período deve ser anterior ou igual ao fim")
        return self


class AIInsightObservationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[
        StrictStr,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ]
    value: StrictInt | StrictFloat = Field(allow_inf_nan=False)


class AIInsightReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[
        StrictStr,
        StringConstraints(
            pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$", max_length=120
        ),
    ]
    description: Annotated[StrictStr, StringConstraints(min_length=1, max_length=500)]
    is_demo: StrictBool


class AIInsightScreenContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Annotated[
        StrictStr,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
    ]
    unit: Annotated[
        StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
    ]
    period: AIInsightPeriod
    filters: dict[
        Annotated[StrictStr, StringConstraints(min_length=1, max_length=80)],
        AIInsightFilterValue,
    ] = Field(min_length=1, max_length=20)
    observations: list[AIInsightObservationValue] = Field(min_length=1, max_length=20)
    reference: AIInsightReference
    limitations: list[AIInsightLimitation] = Field(min_length=1, max_length=20)


class AIInsightRequest(BaseModel):
    """Payload v1 já suportado pelo endpoint POST /api/v1/insights da GenAI."""

    model_config = ConfigDict(extra="forbid")

    screen: AIInsightScreenContext


class AIInsightError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: AIInsightErrorCode
    retryable: StrictBool


class AIInsightContextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: StrictStr
    unit: StrictStr
    period: AIInsightPeriod
    filters: dict[StrictStr, AIInsightFilterValue] = Field(max_length=20)


class AIInsightObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[AIInsightObservationValue] = Field(max_length=20)


class AIInsightEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[
        StrictStr,
        StringConstraints(
            pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$", max_length=120
        ),
    ]
    description: Annotated[StrictStr, StringConstraints(min_length=1, max_length=500)]
    is_demo: StrictBool


class AIInsightResponse(BaseModel):
    """Resposta do contrato v1 da GenAI, validada antes de chegar ao portal."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["v1"]
    correlation_id: (
        Annotated[
            StrictStr,
            StringConstraints(pattern=r"^[a-f0-9]{32}$", min_length=32, max_length=32),
        ]
        | None
    )
    audit_reference: StrictStr | None
    error: AIInsightError | None
    status: AIInsightStatus
    context: AIInsightContextSummary
    observation: AIInsightObservation
    hypothesis: AIInsightText | None
    message: AIInsightText | None
    evidence: list[AIInsightEvidence] = Field(default_factory=list, max_length=20)
    limitations: list[AIInsightLimitation] = Field(default_factory=list, max_length=22)

    @model_validator(mode="after")
    def validate_generated_content(self) -> Self:
        if self.status == "answered":
            if self.hypothesis is None or self.message is not None or not self.evidence:
                raise ValueError(
                    "insight respondido exige hipótese e evidência, sem mensagem"
                )
            if self.error is not None:
                raise ValueError("insight respondido não deve conter erro")
        elif self.message is None or self.hypothesis is not None:
            raise ValueError("insight não concluído exige mensagem, sem hipótese")

        if self.status in {"refused", "recoverable_error"}:
            if self.error is None:
                raise ValueError("recusa ou falha exige erro público")
        elif self.error is not None:
            raise ValueError(
                "esclarecimento e ausência de evidência não devem conter erro"
            )
        return self


class PanoramaInsightMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr
    definicao: StrictStr
    formula: StrictStr


class PanoramaInsightSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: StrictStr
    loteVersao: StrictStr
    dataAtualizacao: StrictStr
    isDemo: StrictBool
    limitacoes: list[AIInsightLimitation] = Field(default_factory=list, max_length=20)


class PanoramaInsightContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: Literal["municipio", "classe"]
    segmento: Annotated[StrictStr, StringConstraints(min_length=1, max_length=120)]
    variacaoAbsoluta: StrictInt | StrictFloat = Field(allow_inf_nan=False)
    participacaoPercentual: StrictFloat | None = Field(
        default=None, allow_inf_nan=False
    )


class PanoramaInsightAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direcao: Literal["alta", "queda", "estavel", "indisponivel"]
    variacaoPercentual: StrictFloat | None = Field(
        default=None, allow_inf_nan=False
    )
    principalContribuicao: PanoramaInsightContribution | None = None
    compensacao: PanoramaInsightContribution | None = None


class PanoramaInsightEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight: AIInsightResponse
    metric: PanoramaInsightMetric
    source: PanoramaInsightSource
    analysis: PanoramaInsightAnalysis
