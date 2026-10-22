from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsMetadata, InspectionQueueItem, Pagination


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
