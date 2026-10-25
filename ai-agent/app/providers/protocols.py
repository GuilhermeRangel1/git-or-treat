"""Interfaces independentes de fornecedor para a geração de respostas."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StringConstraints

from app.schemas.domain_profile import FilterOperator
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import FilterScalar

GeneratedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class ObservationClaim(BaseModel):
    """Medida citada por ID; cálculos derivados precisam de outra observação."""

    model_config = ConfigDict(extra="forbid")

    observation_id: Annotated[str, StringConstraints(pattern=r"^row_[1-9][0-9]{0,2}$")]
    value: StrictInt | StrictFloat = Field(allow_inf_nan=False)
    decimal_places: Annotated[int, Field(strict=True, ge=0, le=6)] | None = None


class QuantitativeClaim(ObservationClaim):
    """Contexto explícito disponível apenas na evidência autorizada."""

    metric: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=200)
    filters: dict[str, FilterScalar | list[FilterScalar]] = Field(max_length=20)
    filter_operators: dict[str, FilterOperator] = Field(default_factory=dict, max_length=20)
    dimensions: dict[str, FilterScalar] = Field(default_factory=dict, max_length=10)


class BoundQuantitativeClaim(ObservationClaim):
    """Vincula contexto sem enviar seu conteúdo ao provedor de insight."""

    context_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "needs_clarification", "refused"]
    answer: GeneratedText
    observation_ids: tuple[
        Annotated[str, StringConstraints(pattern=r"^row_[1-9][0-9]{0,2}$")], ...
    ] = Field(default=(), max_length=10)
    claims: tuple[QuantitativeClaim | BoundQuantitativeClaim, ...] = Field(
        default=(), max_length=10
    )


class ModelProviderUnavailable(Exception):
    """Sinaliza indisponibilidade temporária do provedor de linguagem."""


class ModelProviderRejected(Exception):
    """Erro definitivo do provedor; não aciona fallback ou nova tentativa."""


class ModelProviderInvalidResponse(Exception):
    """Saída incompatível com o contrato; não aciona fallback."""


class ModelAdapter(Protocol):
    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer: ...
