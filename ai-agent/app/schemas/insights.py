"""Contratos HTTP para insights de uma tela durante a etapa sintética."""

from datetime import date
from enum import StrEnum
from math import isfinite
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.evidence import EvidenceReference
from app.schemas.questions import QuestionStatus
from app.schemas.responses import PublicResponseMetadata

FilterValue = StrictStr | StrictInt | StrictFloat | StrictBool
InsightText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
InsightLimitation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class PeriodGranularity(StrEnum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ScreenPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    granularity: PeriodGranularity

    @model_validator(mode="after")
    def require_ordered_period(self) -> "ScreenPeriod":
        if self.start > self.end:
            raise ValueError("o início do período deve ser anterior ou igual ao fim")
        return self


class ScreenObservationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=120)]
    value: StrictInt | StrictFloat = Field(allow_inf_nan=False)

    @field_validator("label")
    @classmethod
    def require_non_blank_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("o rótulo da observação não pode ficar vazio")
        return value.strip()


class ScreenContext(BaseModel):
    """Recorte estruturado enviado pelo consumidor; valores são dados não confiáveis."""

    model_config = ConfigDict(extra="forbid")

    metric: Annotated[str, Field(min_length=1, max_length=160)]
    unit: Annotated[str, Field(min_length=1, max_length=60)]
    period: ScreenPeriod
    filters: dict[Annotated[str, Field(min_length=1, max_length=80)], FilterValue] = Field(
        min_length=1,
        max_length=20,
    )
    observations: list[ScreenObservationValue] = Field(min_length=1, max_length=20)
    reference: EvidenceReference
    limitations: list[InsightLimitation] = Field(
        min_length=1,
        max_length=20,
    )

    @field_validator("metric", "unit")
    @classmethod
    def require_non_blank_context_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("métrica e unidade não podem ficar vazias")
        return value.strip()

    @field_validator("filters")
    @classmethod
    def require_non_blank_filter_values(
        cls,
        value: dict[str, FilterValue],
    ) -> dict[str, FilterValue]:
        if len({key.casefold() for key in value}) != len(value):
            raise ValueError("nomes de filtros não podem se repetir com capitalização diferente")
        for key, item in value.items():
            if not key.strip() or (isinstance(item, str) and (not item.strip() or len(item) > 120)):
                raise ValueError("filtros devem ter nomes e valores curtos não vazios")
            if isinstance(item, float) and not isfinite(item):
                raise ValueError("valores numéricos dos filtros devem ser finitos")
        return value

    @model_validator(mode="after")
    def require_synthetic_context(self) -> "ScreenContext":
        if not self.reference.is_demo:
            raise ValueError("a etapa de insight sintético exige referência marcada como demo")
        labels = [item.label.casefold() for item in self.observations]
        if len(labels) != len(set(labels)):
            raise ValueError("os rótulos das observações devem ser únicos")
        return self


class ScreenInsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screen: ScreenContext


class InsightContextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    unit: str
    period: ScreenPeriod
    filters: dict[str, FilterValue]


class InsightObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[ScreenObservationValue]


class ScreenInsightResponse(PublicResponseMetadata):

    status: QuestionStatus
    context: InsightContextSummary
    observation: InsightObservation
    hypothesis: InsightText | None = None
    message: InsightText | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=20)
    limitations: list[InsightLimitation] = Field(default_factory=list, max_length=22)

    @model_validator(mode="after")
    def validate_generated_content(self) -> Self:
        if self.status is QuestionStatus.ANSWERED:
            if self.hypothesis is None or self.message is not None:
                raise ValueError("insight respondido exige hipótese e não permite mensagem")
            if not self.evidence:
                raise ValueError("insight respondido exige referência de evidência")
            if self.error is not None:
                raise ValueError("insight respondido não deve conter erro")
        elif self.message is None or self.hypothesis is not None:
            raise ValueError("insight não concluído exige mensagem e não permite hipótese")
        if self.status in (QuestionStatus.REFUSED, QuestionStatus.RECOVERABLE_ERROR):
            if self.error is None:
                raise ValueError("recusa ou falha exige código público e política de retry")
        elif self.error is not None:
            raise ValueError("esclarecimento e ausência de evidência não devem conter erro")
        return self
