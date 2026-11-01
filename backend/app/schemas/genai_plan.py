"""Contrato de leitura v1 validado pelo Backend, independente do pacote GenAI.

A compatibilidade dos schemas dos dois serviços é verificada por vetores JSON
compartilhados; nenhum import atravessa a fronteira de implantação.
"""

import hashlib
import json
from datetime import date
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
    SerializerFunctionWrapHandler,
    model_serializer,
    StringConstraints,
    model_validator,
)

ContractVersion = Literal["v1"]
LogicalIdentifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$", max_length=120),
]
FilterScalar = StrictStr | StrictInt | StrictFloat | StrictBool
PlanFingerprint = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]


class QuestionPlanStatus(StrEnum):
    PLANNED = "planned"
    NEEDS_CLARIFICATION = "needs_clarification"
    REFUSED = "refused"
    RECOVERABLE_ERROR = "recoverable_error"


class WindowKind(StrEnum):
    CATALOG_PHRASE = "catalog_phrase"
    BOUNDED = "bounded"


class FilterOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"


class ReadWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WindowKind
    phrase: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
        | None
    ) = None
    start: date | None = None
    end: date | None = None
    granularity: Literal["day", "month", "quarter", "year"] | None = None

    @model_validator(mode="after")
    def require_complete_window(self) -> Self:
        if self.kind is WindowKind.CATALOG_PHRASE:
            if self.phrase is None or self.start is not None or self.end is not None:
                raise ValueError("janela por frase exige frase e não aceita datas parciais")
        elif (
            self.phrase is not None
            or self.start is None
            or self.end is None
            or self.granularity is None
            or self.start > self.end
        ):
            raise ValueError("janela delimitada exige datas ordenadas e granularidade")
        return self


class ReadFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension_id: LogicalIdentifier
    operator: FilterOperator
    values: tuple[FilterScalar, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_operator_arity(self) -> Self:
        if self.operator is FilterOperator.IN:
            if len(self.values) < 2:
                raise ValueError("operador in exige ao menos dois valores")
        elif len(self.values) != 1:
            raise ValueError("operador escalar exige exatamente um valor")
        if any(
            isinstance(value, str) and (not value.strip() or len(value) > 120)
            for value in self.values
        ):
            raise ValueError("valor textual de filtro inválido")
        return self


class ReadOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: LogicalIdentifier
    direction: Literal["asc", "desc"]


class LogicalReadPlan(BaseModel):
    """Plano validado estruturalmente; fingerprint não concede autorização SQL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: ContractVersion = "v1"
    catalog_version: ContractVersion
    operation: Literal["read"]
    profile_id: LogicalIdentifier
    source_id: LogicalIdentifier
    domain_id: LogicalIdentifier
    metric_id: LogicalIdentifier
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    group_by_dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    window: ReadWindow
    comparison_periods: tuple[
        Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")],
        Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")],
    ] | None = None
    filters: tuple[ReadFilter, ...] = Field(default=(), max_length=20)
    order: ReadOrder | None = None
    limit: int = Field(ge=1, le=100, strict=True)

    @model_serializer(mode="wrap")
    def omit_absent_comparison(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        payload = handler(self)
        if self.comparison_periods is None:
            payload.pop("comparison_periods", None)
        return payload

    def fingerprint(self) -> str:
        """SHA-256 B3: defaults/nulos presentes e listas na ordem recebida."""
        payload = self.model_dump(mode="json")
        if self.comparison_periods is None:
            payload.pop("comparison_periods", None)
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def require_consistent_dimensions(self) -> Self:
        if self.comparison_periods is not None:
            baseline, target = self.comparison_periods
            if (
                baseline >= target or baseline.startswith("0000")
                or self.window.kind is not WindowKind.BOUNDED
                or self.window.granularity != "month"
                or self.window.start is None or self.window.end is None
                or self.window.start.isoformat() != baseline + "-01"
                or self.window.end.strftime("%Y-%m") != target
            ):
                raise ValueError("comparação exige dois meses distintos e ordenados na janela")
        if len(self.dimension_ids) != len(set(self.dimension_ids)):
            raise ValueError("dimensão repetida no plano")
        if len(self.group_by_dimension_ids) != len(set(self.group_by_dimension_ids)):
            raise ValueError("dimensão repetida no agrupamento")
        if not set(self.group_by_dimension_ids) <= set(self.dimension_ids):
            raise ValueError("agrupamento exige dimensão declarada no plano")
        filter_ids = [item.dimension_id for item in self.filters]
        if len(filter_ids) != len(set(filter_ids)):
            raise ValueError("filtro repetido no plano")
        if not set(filter_ids) <= set(self.dimension_ids):
            raise ValueError("filtro exige dimensão declarada no plano")
        if self.order is not None and self.order.field_id not in {
            self.metric_id,
            *self.dimension_ids,
        }:
            raise ValueError("ordenação exige métrica ou dimensão declarada")
        return self
