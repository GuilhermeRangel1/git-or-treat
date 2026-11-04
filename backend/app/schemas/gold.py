"""Versioned metadata shared by API responses backed by the Gold publication."""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsFilters, AnalyticsPeriod, AnalyticsStatus, AnalyticsSource


class GoldMetadata(BaseModel):
    contract_version: Literal["2.0.0"] = "2.0.0"
    status: AnalyticsStatus
    period: AnalyticsPeriod | None = None
    filters: AnalyticsFilters = Field(default_factory=AnalyticsFilters)
    source: AnalyticsSource
    limitations: list[str] = Field(default_factory=list)
    temporal_scope: Literal["monthly", "snapshot"] = "monthly"
    schema_version: str = "gold-csv-v2"
    fingerprint: str
