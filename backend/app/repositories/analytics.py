from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.synthetic import fixtures


class AnalyticsSourceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class MonthlyCoverage:
    """Inclusive source coverage, independent of observed events and UC snapshots."""

    start: str
    end: str


class AnalyticsRepository(Protocol):
    units: list[dict]
    invoices: list[dict]
    readings: list[dict]
    meters: list[dict]
    generation: list[dict]
    interruptions: list[dict]
    calls: list[dict]
    feeders: list[dict]
    suspicions: list[dict]
    source_kind: str
    source_version: str
    source_is_demo: bool
    source_updated_at: str
    source_limitations: list[str]
    continuity_coverage: MonthlyCoverage | None


class SyntheticAnalyticsRepository:
    """Read-only in-memory adapter. All aggregates derive from these records."""

    units = fixtures.UNITS
    invoices = fixtures.INVOICES
    readings = fixtures.READINGS
    meters = fixtures.METERS
    generation = fixtures.GENERATION
    interruptions = fixtures.INTERRUPTIONS
    calls = fixtures.CALLS
    feeders = fixtures.FEEDERS
    suspicions = fixtures.SUSPICIONS
    source_kind = "synthetic"
    source_version = fixtures.DATA_VERSION
    source_is_demo = True
    source_updated_at = fixtures.UPDATED_AT
    source_limitations = [fixtures.DATA_LIMITATION]
    continuity_coverage: MonthlyCoverage | None = MonthlyCoverage(
        start=fixtures.CONTINUITY_COVERAGE_START,
        end=fixtures.CONTINUITY_COVERAGE_END,
    )


_synthetic_repository = SyntheticAnalyticsRepository()


def get_analytics_repository() -> AnalyticsRepository:
    """FastAPI dependency: synthetic is explicit; all other allowed modes fail closed."""
    if settings.ANALYTICS_SOURCE != "synthetic":
        raise AnalyticsSourceUnavailable()
    return _synthetic_repository
