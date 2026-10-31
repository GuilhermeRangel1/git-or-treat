from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.schemas.analytics import (
    AnalyticsMetadata,
    AnalyticsPeriod,
    AnalyticsStatus,
    CallDetail,
    GenerationDetail,
    InterruptionDetail,
    InvoiceDetail,
    MeterDetail,
    Pagination,
)


class UCCoveredMeasure(BaseModel):
    value: Decimal | None
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_value_and_status(self):
        if self.status == "available" and self.value is None:
            raise ValueError("Available UC measures require a value")
        if self.status in {"empty", "unavailable"} and self.value is not None:
            raise ValueError("Empty or unavailable UC measures require a null value")
        if self.value is not None and not self.value.is_finite():
            raise ValueError("UC measure values must be finite")
        return self

    @field_serializer("value", when_used="json")
    def serialize_value(self, value: Decimal | None):
        return float(value) if value is not None else None


class UCMeasureChange(BaseModel):
    delta: Decimal | None
    percent_change: Decimal | None
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_value_and_status(self):
        if self.status == "available" and self.delta is None:
            raise ValueError("Available UC changes require a delta")
        if self.status in {"empty", "unavailable"} and self.delta is not None:
            raise ValueError("Empty or unavailable UC changes require a null delta")
        if self.delta is not None and not self.delta.is_finite():
            raise ValueError("UC deltas must be finite")
        if self.percent_change is not None and not self.percent_change.is_finite():
            raise ValueError("UC percent changes must be finite")
        return self

    @field_serializer("delta", "percent_change", when_used="json")
    def serialize_change(self, value: Decimal | None):
        return float(value) if value is not None else None


class UCSnapshot(BaseModel):
    competencia: str
    measured_energy_kwh: UCCoveredMeasure
    billed_energy_kwh: UCCoveredMeasure
    billed_amount: UCCoveredMeasure
    paid_amount: UCCoveredMeasure


class UCComparison(BaseModel):
    initial: UCSnapshot
    final: UCSnapshot
    measured_energy_kwh: UCMeasureChange
    billed_energy_kwh: UCMeasureChange
    billed_amount: UCMeasureChange
    paid_amount: UCMeasureChange


class UCCountMeasure(BaseModel):
    count: int | None
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_count_and_status(self):
        if self.status in {"available", "partial"} and self.count is None:
            raise ValueError("Available or partial counts require a value")
        if self.status in {"empty", "unavailable"} and self.count is not None:
            raise ValueError("Empty or unavailable counts require a null value")
        return self


class UCMeterMeasure(BaseModel):
    item: MeterDetail | None
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_item_and_status(self):
        if self.status == "available" and self.item is None:
            raise ValueError("Available meter status requires an item")
        if self.status in {"empty", "unavailable"} and self.item is not None:
            raise ValueError("Empty or unavailable meter status requires a null item")
        return self


class UCGenerationSection(BaseModel):
    items: list[GenerationDetail]
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_items_and_status(self):
        if self.status == "available" and not self.items:
            raise ValueError("Available generation status requires at least one item")
        if self.status in {"empty", "unavailable"} and self.items:
            raise ValueError("Empty or unavailable generation status requires no items")
        return self


class UCProfile(BaseModel):
    uc_id: str
    customer_reference: str | None
    customer_name: str | None
    municipio: str
    bairro: str
    classe: str
    alimentador: str
    status: str


class UCGoldGeneration(BaseModel):
    capacity_kwp: float | None = Field(ge=0)
    connection_date: str | None
    modality: str | None


class UCOverviewData(BaseModel):
    profile: UCProfile
    period: AnalyticsPeriod
    comparison: UCComparison
    open_invoices: UCCountMeasure
    current_meter: UCMeterMeasure
    distributed_generation: UCGenerationSection
    gold_generation: UCGoldGeneration | None = None
    section_status: dict[str, AnalyticsStatus]


class UCOverviewResponse(BaseModel):
    data: UCOverviewData
    metadata: AnalyticsMetadata


class UCConsumptionHistoryItem(BaseModel):
    competencia: str
    measured_energy_kwh: Decimal | None
    billed_amount: Decimal | None = None
    status: Literal["available", "partial", "unavailable"]

    @model_validator(mode="after")
    def validate_energy(self):
        if (
            self.measured_energy_kwh is not None
            and not self.measured_energy_kwh.is_finite()
        ):
            raise ValueError("Consumption values must be finite")
        if self.status == "available" and self.measured_energy_kwh is None:
            raise ValueError("Available consumption rows require a value")
        if (
            self.status in {"partial", "unavailable"}
            and self.measured_energy_kwh is not None
        ):
            raise ValueError(
                "Partial or unavailable consumption rows must not claim a complete value"
            )
        return self

    @field_serializer("measured_energy_kwh", "billed_amount", when_used="json")
    def serialize_energy(self, value: Decimal | None):
        return float(value) if value is not None else None


class UCInvoiceHistoryItem(InvoiceDetail):
    billed_amount: float | None
    billed_energy_kwh: float | None


class UCMeterHistoryItem(MeterDetail):
    installed_at: str | None


class UCGenerationHistoryItem(GenerationDetail):
    pass


class UCInterruptionHistoryItem(InterruptionDetail):
    duration_hours: float | None


class UCCallHistoryItem(CallDetail):
    pass


UCHistoryItem = (
    UCConsumptionHistoryItem
    | UCInvoiceHistoryItem
    | UCMeterHistoryItem
    | UCGenerationHistoryItem
    | UCInterruptionHistoryItem
    | UCCallHistoryItem
)


class UCHistoryData(BaseModel):
    items: list[UCHistoryItem]


class UCHistoryResponse(BaseModel):
    data: UCHistoryData
    pagination: Pagination
    metadata: AnalyticsMetadata


UCHistorySection = Literal[
    "consumption",
    "invoices",
    "meters",
    "distributed_generation",
    "interruptions",
    "calls",
]
