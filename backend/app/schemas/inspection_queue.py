from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsMetadata, InspectionQueueItem, Pagination
from app.schemas.gold import GoldMetadata


class SignalEvidence(BaseModel):
    id: str
    label: str
    weight: float = Field(ge=0, le=1)


class EstimateEvidence(BaseModel):
    baseline_kwh: float | None = Field(ge=0)
    observed_kwh: float | None = Field(ge=0)
    horizon_months: int = Field(ge=1)
    reference: str
    unavailable_reason: str | None = None


class SuspicionDetail(InspectionQueueItem):
    rule_version: str
    signals: list[SignalEvidence]
    estimate_evidence: EstimateEvidence
    limitations: list[str]


class InspectionCandidate(InspectionQueueItem):
    signals: list[SignalEvidence]


class QueueSummary(BaseModel):
    total_units: int = Field(ge=0)
    highest_priority: float | None = Field(ge=0, le=1)
    estimated_units: int = Field(ge=0)
    unavailable_estimate_units: int = Field(ge=0)


class QueueData(BaseModel):
    items: list[InspectionCandidate]
    filter_options: dict[str, list[str]]
    summary: QueueSummary


class QueueResponse(BaseModel):
    data: QueueData
    pagination: Pagination
    metadata: AnalyticsMetadata


class SuspicionResponse(BaseModel):
    data: SuspicionDetail
    metadata: AnalyticsMetadata


class GoldInspectionVariation(BaseModel):
    p1_start: str = "2022-07"
    p1_end: str = "2023-06"
    p1_months_observed: int | None
    p1_average_kwh_per_month: float | None
    p2_start: str = "2025-07"
    p2_end: str = "2026-06"
    p2_months_observed: int | None
    p2_average_kwh_per_month: float | None
    variation_kwh: float | None
    variation_pct: float | None
    drop_over_30_pct: bool | None


class GoldInspectionEvidence(BaseModel):
    inspections_performed: int | None
    confirmed_irregular_inspections: int | None
    historical_average_kwh_per_reading: float | None
    distributed_generation_present: str | None
    cadastral_status: str | None
    call_center_contacts: int | None
    interruptions: int | None


class GoldInspectionItem(BaseModel):
    uc_id: str
    municipality: str | None
    neighborhood: str | None
    class_name: str | None
    feeder_id: str | None
    category: str | None
    reason: str | None
    potential_recoverable_energy_kwh: None = None
    recovery_unavailable_reason: str = "A Gold publicada não contém uma estimativa de energia recuperável."
    evidence: GoldInspectionEvidence
    variation: GoldInspectionVariation | None


class GoldInspectionSummary(BaseModel):
    total_units: int = Field(ge=0)
    categories: dict[str, int]
    uncategorized_units: int = Field(ge=0)
    estimated_units: int = 0
    unavailable_estimate_units: int = Field(ge=0)


class GoldInspectionQueueData(BaseModel):
    items: list[GoldInspectionItem]
    filter_options: dict[str, list[str]]
    summary: GoldInspectionSummary


class GoldInspectionQueueResponse(BaseModel):
    data: GoldInspectionQueueData
    pagination: Pagination
    metadata: GoldMetadata


class GoldSuspicionDetail(GoldInspectionItem):
    rule_version: str
    limitations: list[str]


class GoldSuspicionResponse(BaseModel):
    data: GoldSuspicionDetail
    metadata: GoldMetadata
