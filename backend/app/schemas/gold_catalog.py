"""Contrato físico interno do catálogo Gold v2; não é entrada do modelo ou do portal."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.genai_plan import LogicalIdentifier

ColumnType = Literal["string", "bigint", "double", "decimal"]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Rounding(CatalogModel):
    decimals: int = Field(ge=0, le=6)
    mode: Literal["half_even"]


class CatalogSource(CatalogModel):
    capability_id: LogicalIdentifier
    table: str
    temporal_column: str | None
    temporal_transform: Literal["identity", "utc_month"]
    grain: tuple[str, ...] = Field(min_length=1)
    measure_column: str | None
    numerator_column: str | None
    denominator_column: str | None
    nullable_columns: tuple[str, ...]
    dimension_columns: dict[LogicalIdentifier, str]
    decimal_shapes: dict[str, tuple[int, int]]


class CatalogMetric(CatalogModel):
    metric_id: LogicalIdentifier
    label: str = Field(min_length=1, max_length=300)
    definition: str = Field(min_length=1, max_length=300)
    dimension_operators: dict[LogicalIdentifier, tuple[Literal["eq", "in"], ...]]
    capability_id: LogicalIdentifier
    required_capability_ids: tuple[LogicalIdentifier, ...] = Field(min_length=1)
    accumulated_period_phrases: tuple[str, ...]
    granularities: tuple[Literal["month", "year"], ...] = Field(min_length=1)
    max_window_days: int | None = Field(ge=1)
    aggregation: Literal[
        "sum", "ratio_of_sums", "key_grain_read", "count_non_null", "average_non_null"
    ]
    unit: str
    unit_kind: Literal["currency", "energy", "count", "time", "score"]
    measure_type: ColumnType | None
    numerator_type: ColumnType | None
    denominator_type: ColumnType | None
    rounding: Rounding
    null_rule: Literal[
        "sum_ignores_null_all_null_is_absent",
        "ratio_absent_on_null_or_zero_denominator",
        "read_null_is_absent",
        "count_requires_certified_zero",
        "average_ignores_null_all_null_is_absent",
    ]
    required_dimension_ids: tuple[LogicalIdentifier, ...]
    sources: tuple[CatalogSource, ...] = Field(min_length=1)


class UnavailableCapability(CatalogModel):
    capability_id: LogicalIdentifier
    reasons: tuple[str, ...] = Field(min_length=1)
    note: str


class GoldCatalog(CatalogModel):
    mapping_version: Literal["gold-catalog-v2"]
    physical_schema: Literal["gold_v2"]
    profile_id: Literal["v-energy-grid-360-gold"]
    dictionary_version: Literal["gold-csv-v2"]
    readiness_version: Literal["gold-readiness-v2"]
    metrics: tuple[CatalogMetric, ...] = Field(min_length=1)
    unavailable: tuple[UnavailableCapability, ...]
    open_points: tuple[str, ...]
