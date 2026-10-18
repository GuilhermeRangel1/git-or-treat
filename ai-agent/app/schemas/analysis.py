"""Tipos de intenção analítica independentes das fixtures de demonstração."""

from enum import StrEnum
from typing import Annotated

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

from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

AnalysisFilterValue = StrictStr | StrictInt | StrictFloat | StrictBool
LogicalIdentifier = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
        max_length=120,
    ),
]
AnalysisFilterKey = LogicalIdentifier


class AnalysisDomain(StrEnum):
    """Áreas de negócio usadas pelo interpretador, sem presumir o esquema Gold."""

    REVENUE = "revenue"
    CONSUMPTION = "consumption"
    NETWORK = "network"
    SERVICE = "service"


class AnalysisIntent(BaseModel):
    """Interpretação inicial da pergunta em termos de linguagem do usuário."""

    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    domain: AnalysisDomain
    metric_id: LogicalIdentifier | None = None
    dimension_ids: list[LogicalIdentifier] = Field(default_factory=list, max_length=10)
    metric_phrase: str | None = Field(default=None, min_length=1, max_length=160)
    period_phrase: str | None = Field(default=None, min_length=1, max_length=160)
    geography_phrase: str | None = Field(default=None, min_length=1, max_length=160)
    class_phrase: str | None = Field(default=None, min_length=1, max_length=120)
    filters: dict[AnalysisFilterKey, AnalysisFilterValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, values: object) -> object:
        if isinstance(values, dict):
            nullable_fields = (
                "metric_id",
                "metric_phrase",
                "period_phrase",
                "geography_phrase",
                "class_phrase",
            )
            explicit_nulls = [
                name for name in nullable_fields if name in values and values[name] is None
            ]
            if explicit_nulls:
                raise ValueError(
                    "campos não informados devem ser omitidos, não enviados como null"
                )
        return values
