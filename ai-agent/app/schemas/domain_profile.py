"""Contrato tipado para vocabulário e catálogo de um domínio analítico."""

import unicodedata
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.analysis import LogicalIdentifier
from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

CatalogText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
CatalogValue = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
CatalogPhrase = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class CatalogOperation(StrEnum):
    READ = "read"


class FilterValueType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"


class FilterOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"


class CatalogSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL = "personal"


class EvidenceFieldRole(StrEnum):
    MEASURE = "measure"
    UNIT = "unit"
    PERIOD = "period"
    DIMENSION = "dimension"


class EvidenceFieldDefinition(BaseModel):
    """Campo que pode atravessar a fronteira de evidências para esta métrica."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,79}$")]
    role: EvidenceFieldRole
    value_type: FilterValueType
    sensitivity: CatalogSensitivity
    dimension_id: LogicalIdentifier | None = None

    @model_validator(mode="after")
    def require_dimension_mapping(self) -> Self:
        if self.role is EvidenceFieldRole.DIMENSION:
            if self.sensitivity is not CatalogSensitivity.PERSONAL and self.dimension_id is None:
                raise ValueError("dimensão de evidência exige ID lógico")
        elif self.dimension_id is not None:
            raise ValueError("ID de dimensão exige campo de dimensão")
        if self.role is EvidenceFieldRole.PERIOD and self.value_type is not FilterValueType.DATE:
            raise ValueError("período de evidência exige tipo date")
        return self


class DimensionRole(StrEnum):
    GEOGRAPHY = "geography"
    CLASSIFICATION = "classification"
    OTHER = "other"


class CatalogGranularity(StrEnum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class CatalogPeriodWindow(BaseModel):
    """Janela fixa associada a uma frase aprovada do catálogo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phrase: CatalogPhrase
    start: date
    end: date
    granularity: CatalogGranularity

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.start > self.end:
            raise ValueError("janela de catálogo invertida")
        return self


class DomainDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: LogicalIdentifier
    label: CatalogText
    example_questions: tuple[CatalogText, ...] = Field(default=(), max_length=20)


class DimensionValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: CatalogValue
    aliases: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=20)


class DimensionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: LogicalIdentifier
    label: CatalogText
    role: DimensionRole
    aliases: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=30)
    value_type: FilterValueType
    operators: tuple[FilterOperator, ...] = Field(min_length=1)
    sensitivity: CatalogSensitivity
    values: tuple[DimensionValue, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def validate_dimension_aliases(self) -> Self:
        aliases = [_normalize(alias) for alias in self.aliases]
        if len(aliases) != len(set(aliases)):
            raise ValueError("alias de dimensão duplicado")
        value_aliases = [_normalize(alias) for value in self.values for alias in value.aliases]
        if len(value_aliases) != len(set(value_aliases)):
            raise ValueError("alias de valor da dimensão duplicado ou ambíguo")
        compatible_operators = {
            FilterValueType.STRING: {
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.CONTAINS,
            },
            FilterValueType.INTEGER: {
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.LT,
                FilterOperator.LTE,
            },
            FilterValueType.NUMBER: {
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.LT,
                FilterOperator.LTE,
            },
            FilterValueType.BOOLEAN: {FilterOperator.EQ, FilterOperator.NE},
            FilterValueType.DATE: {
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.LT,
                FilterOperator.LTE,
            },
        }
        if not set(self.operators) <= compatible_operators[self.value_type]:
            raise ValueError("operador incompatível com tipo de filtro da dimensão")
        return self


class MetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: LogicalIdentifier
    domain_id: LogicalIdentifier
    aliases: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=40)
    unit: CatalogText
    granularities: tuple[CatalogGranularity, ...] = Field(min_length=1)
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=30)
    sensitivity: CatalogSensitivity
    evidence_fields: tuple[EvidenceFieldDefinition, ...] = Field(default=(), max_length=30)
    limitation_texts: tuple[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)],
        ...,
    ] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def validate_metric_aliases(self) -> Self:
        aliases = [_normalize(alias) for alias in self.aliases]
        if len(aliases) != len(set(aliases)):
            raise ValueError("alias de métrica duplicado")
        if len(self.dimension_ids) != len(set(self.dimension_ids)):
            raise ValueError("dimensão permitida duplicada na métrica")
        if len({field.name for field in self.evidence_fields}) != len(self.evidence_fields):
            raise ValueError("campo de evidência duplicado na métrica")
        if sum(field.role is EvidenceFieldRole.MEASURE for field in self.evidence_fields) > 1:
            raise ValueError("métrica aceita somente um campo de medida")
        if sum(field.role is EvidenceFieldRole.PERIOD for field in self.evidence_fields) > 1:
            raise ValueError("métrica aceita somente um campo de período")
        evidence_dimension_ids = [
            field.dimension_id for field in self.evidence_fields if field.dimension_id is not None
        ]
        if len(evidence_dimension_ids) != len(set(evidence_dimension_ids)):
            raise ValueError("dimensão de evidência duplicada na métrica")
        if any(
            field.dimension_id not in self.dimension_ids
            for field in self.evidence_fields
            if field.dimension_id is not None
        ):
            raise ValueError("campo de evidência referencia dimensão fora da métrica")
        return self


class AmbiguityRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phrases: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=20)
    clarification: CatalogText


class ClarificationMessages(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_metric: CatalogText
    multiple_domains: CatalogText
    multiple_metrics: CatalogText
    unknown_geography: CatalogText
    multiple_geographies: CatalogText
    multiple_classes: CatalogText
    missing_period: CatalogText
    comparison_baseline: CatalogText
    multiple_periods: CatalogText


class DomainProfile(BaseModel):
    """Perfil imutável fornecido à interpretação e à composição da fonte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: LogicalIdentifier
    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    domains: tuple[DomainDefinition, ...] = Field(min_length=1, max_length=50)
    metrics: tuple[MetricDefinition, ...] = Field(min_length=1, max_length=200)
    dimensions: tuple[DimensionDefinition, ...] = Field(min_length=1, max_length=100)
    period_phrases: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=100)
    period_windows: tuple[CatalogPeriodWindow, ...] = Field(default=(), max_length=100)
    default_period_phrase: CatalogPhrase | None = None
    default_period_context_phrases: tuple[CatalogPhrase, ...] = Field(
        default=(),
        max_length=50,
        description="Contextos que autorizam aplicar o período padrão sem uma janela explícita.",
    )
    comparison_period_phrases: tuple[CatalogPhrase, ...] = Field(
        default=(),
        max_length=30,
        description=(
            "Frases reconhecidas como janela de comparação; a primeira é a forma canônica "
            "e as demais são aliases."
        ),
    )
    non_location_phrases: tuple[CatalogPhrase, ...] = Field(default=(), max_length=50)
    comparison_terms: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=30)
    correction_terms: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=30)
    follow_up_starters: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=30)
    direction_terms: tuple[CatalogPhrase, ...] = Field(min_length=1, max_length=30)
    out_of_scope_terms: tuple[CatalogPhrase, ...] = Field(default=(), max_length=30)
    ambiguities: tuple[AmbiguityRule, ...] = Field(default=(), max_length=50)
    clarifications: ClarificationMessages
    operations: tuple[CatalogOperation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog_references_and_aliases(self) -> Self:
        domain_ids = [domain.id for domain in self.domains]
        metric_ids = [metric.id for metric in self.metrics]
        dimension_ids = [dimension.id for dimension in self.dimensions]
        _require_unique(domain_ids, "ID de domínio duplicado")
        _require_unique(metric_ids, "ID de métrica duplicado")
        _require_unique(dimension_ids, "ID de dimensão duplicado")

        domain_set = set(domain_ids)
        dimension_set = set(dimension_ids)
        for metric in self.metrics:
            if metric.domain_id not in domain_set:
                raise ValueError("métrica referencia domínio inexistente")
            unknown_dimensions = set(metric.dimension_ids) - dimension_set
            if unknown_dimensions:
                raise ValueError("métrica referencia dimensão inexistente")

        metric_aliases = [_normalize(alias) for metric in self.metrics for alias in metric.aliases]
        if len(metric_aliases) != len(set(metric_aliases)):
            raise ValueError("alias de métrica ambíguo entre métricas")

        ambiguity_phrases = [
            _normalize(phrase) for rule in self.ambiguities for phrase in rule.phrases
        ]
        if len(ambiguity_phrases) != len(set(ambiguity_phrases)):
            raise ValueError("frase de ambiguidade duplicada")
        if set(metric_aliases) & set(ambiguity_phrases):
            raise ValueError("frase de ambiguidade conflita com alias de métrica")
        denied_terms = [_normalize(item) for item in self.out_of_scope_terms]
        _require_unique(denied_terms, "termo fora do escopo duplicado")
        if set(metric_aliases) & set(denied_terms):
            raise ValueError("termo fora do escopo conflita com alias de métrica")

        dimension_aliases = [
            _normalize(alias) for dimension in self.dimensions for alias in dimension.aliases
        ]
        if len(dimension_aliases) != len(set(dimension_aliases)):
            raise ValueError("alias de dimensão ambíguo entre dimensões")
        if CatalogOperation.READ not in self.operations:
            raise ValueError("catálogo analítico precisa permitir leitura")
        _require_unique(list(self.operations), "operação duplicada")
        normalized_period_phrases = [_normalize(item) for item in self.period_phrases]
        _require_unique(normalized_period_phrases, "período duplicado")
        period_phrases = set(normalized_period_phrases)
        normalized_windows = [_normalize(item.phrase) for item in self.period_windows]
        _require_unique(normalized_windows, "janela de período duplicada")
        if any(phrase not in period_phrases for phrase in normalized_windows):
            raise ValueError("janela exige frase no catálogo de períodos")
        if self.default_period_phrase is not None and (
            _normalize(self.default_period_phrase) not in period_phrases
        ):
            raise ValueError("período padrão precisa estar no catálogo de períodos")
        if self.default_period_context_phrases and self.default_period_phrase is None:
            raise ValueError("contexto de período padrão exige um período padrão")
        _require_unique(
            [_normalize(item) for item in self.default_period_context_phrases],
            "contexto de período padrão duplicado",
        )
        if any(_normalize(item) not in period_phrases for item in self.comparison_period_phrases):
            raise ValueError("período de comparação precisa estar no catálogo de períodos")
        _require_unique(
            [_normalize(item) for item in self.comparison_period_phrases],
            "período de comparação duplicado",
        )
        _require_unique(
            [_normalize(item) for item in self.non_location_phrases],
            "frase não geográfica duplicada",
        )
        return self


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _require_unique(values: list[str], message: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(message)
