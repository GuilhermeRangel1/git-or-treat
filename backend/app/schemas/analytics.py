from math import isfinite
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator


AnalyticsStatus = Literal["available", "empty", "partial", "unavailable"]
T = TypeVar("T")


class AnalyticsPeriod(BaseModel):
    start: str
    end: str
    granularity: Literal["month"] = "month"


class AnalyticsFilters(BaseModel):
    municipio: Optional[str] = None
    bairro: Optional[str] = None
    classe: Optional[str] = None
    alimentador: Optional[str] = None


class AnalyticsSource(BaseModel):
    kind: str
    version: str
    is_demo: bool
    updated_at: str


class AnalyticsMetadata(BaseModel):
    contract_version: str = "1.0.0"
    status: AnalyticsStatus
    period: AnalyticsPeriod
    filters: AnalyticsFilters = Field(default_factory=AnalyticsFilters)
    source: AnalyticsSource
    limitations: list[str] = Field(default_factory=list)


class Metric(BaseModel):
    id: str
    label: str
    value: float | int | None
    unit: str
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_value_and_status(self):
        if self.value is not None and (isinstance(self.value, bool) or not isfinite(float(self.value))):
            raise ValueError("Metric values must be finite JSON numbers or null")
        if self.status == "available" and self.value is None:
            raise ValueError("Available metrics require a numeric value")
        if self.status in {"empty", "unavailable"} and self.value is not None:
            raise ValueError("Empty and unavailable metrics require a null value")
        return self


class KPIData(BaseModel):
    metrics: list[Metric]


class KPIResponse(BaseModel):
    data: KPIData
    metadata: AnalyticsMetadata


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AnalyticsListData(BaseModel, Generic[T]):
    items: list[T]


class AnalyticsListResponse(BaseModel, Generic[T]):
    data: AnalyticsListData[T]
    pagination: Pagination
    metadata: AnalyticsMetadata


class RevenuePeriod(BaseModel):
    competencia: str
    billed_amount: float | None
    paid_amount: float | None
    measured_energy_kwh: float | None
    billed_energy_kwh: float | None


class RevenueComparison(BaseModel):
    billed_amount_change_brl: float | None
    billed_energy_change_kwh: float | None
    measured_energy_change_kwh: float | None
    billed_amount_change_percent: float | None


class RevenueDecomposition(BaseModel):
    method: str
    reference_version: str
    price_effect_brl: float | None
    volume_effect_brl: float | None
    interaction_effect_brl: float | None
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)


class RevenueData(BaseModel):
    currency_unit: Literal["BRL"] = "BRL"
    energy_unit: Literal["kWh"] = "kWh"
    total_billed_amount: float | None
    total_paid_amount: float | None
    total_measured_energy_kwh: float | None
    total_billed_energy_kwh: float | None
    observed_price_brl_per_kwh: float | None
    series: list[RevenuePeriod]
    comparison: RevenueComparison
    price_volume: RevenueDecomposition


class RevenueResponse(BaseModel):
    data: RevenueData
    metadata: AnalyticsMetadata


class UCListItem(BaseModel):
    uc_id: str
    municipio: str
    bairro: str
    classe: str
    alimentador: str
    status: str


class UCProfile(BaseModel):
    uc_id: str
    customer_reference: str | None
    customer_name: str | None
    municipio: str
    bairro: str
    classe: str
    alimentador: str
    status: str


class UCDetailData(BaseModel):
    profile: UCProfile
    consumption: list["ConsumptionReading"]
    invoices: list["InvoiceDetail"]
    meters: list["MeterDetail"]
    distributed_generation: list["GenerationDetail"]
    interruptions: list["InterruptionDetail"]
    calls: list["CallDetail"]
    section_status: dict[str, AnalyticsStatus]


class UCDetailResponse(BaseModel):
    data: UCDetailData
    metadata: AnalyticsMetadata


class ConsumptionReading(BaseModel):
    competencia: str
    measured_energy_kwh: float | None
    status: Literal["available", "missing"]


class InvoiceDetail(BaseModel):
    currency_unit: Literal["BRL"] = "BRL"
    invoice_id: str
    competencia: str
    billed_amount: float
    paid_amount: float | None
    billed_energy_kwh: float
    due_date: str | None
    payment_date: str | None
    payment_status: Literal["paid", "partial", "unpaid", "unknown"]


class MeterDetail(BaseModel):
    meter_id: str
    installed_at: str
    removed_at: str | None


class GenerationDetail(BaseModel):
    capacity_kw: float
    status: str


class InterruptionDetail(BaseModel):
    event_id: str
    feeder_id: str
    competencia: str
    duration_hours: float


class CallDetail(BaseModel):
    call_id: str
    opened_at: str
    category: str


UCDetailData.model_rebuild()


class InspectionQueueItem(BaseModel):
    uc_id: str
    municipality: str
    neighborhood: str
    class_name: str
    feeder_id: str
    priority: float
    reason: str
    potential_recoverable_energy_kwh: float | None
    indicators: list[str]


class ContinuityItem(BaseModel):
    feeder_id: str
    municipalities: list[str]
    territory_status: Literal["single_municipality", "multi_municipal"]
    dec_hours_per_uc: float | None
    fec_interruptions_per_uc: float | None
    interruption_count: int
    denominator_uc_count: int | None
    covered_uc_count: int
    coverage_ratio: float | None
    served_uc_count: int
    coverage_status: AnalyticsStatus
    status: AnalyticsStatus
    limitations: list[str] = Field(default_factory=list)


class ContinuityData(BaseModel):
    items: list[ContinuityItem]


class ContinuityResponse(BaseModel):
    data: ContinuityData
    metadata: AnalyticsMetadata


class AnalyticsErrorDetail(BaseModel):
    field: str
    message: str


class AnalyticsErrorBody(BaseModel):
    code: str
    message: str
    details: list[AnalyticsErrorDetail] = Field(default_factory=list)


class AnalyticsErrorResponse(BaseModel):
    error: AnalyticsErrorBody
