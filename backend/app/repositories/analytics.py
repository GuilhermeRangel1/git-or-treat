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


@dataclass(frozen=True)
class RevenueCoverage:
    """Explicit monthly coverage for each independent revenue measure."""

    billed_amount: frozenset[str]
    billed_energy_kwh: frozenset[str]
    paid_amount: frozenset[str]
    measured_energy_kwh: frozenset[str]


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
    revenue_coverage: RevenueCoverage


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
    revenue_coverage: RevenueCoverage = RevenueCoverage(
        billed_amount=frozenset(fixtures.REVENUE_BILLED_AMOUNT_COVERAGE),
        billed_energy_kwh=frozenset(fixtures.REVENUE_BILLED_ENERGY_COVERAGE),
        paid_amount=frozenset(fixtures.REVENUE_PAID_AMOUNT_COVERAGE),
        measured_energy_kwh=frozenset(fixtures.REVENUE_MEASURED_ENERGY_COVERAGE),
    )


_synthetic_repository = SyntheticAnalyticsRepository()


def get_analytics_repository() -> AnalyticsRepository:
    """FastAPI dependency: synthetic is explicit; all other allowed modes fail closed."""
    if settings.ANALYTICS_SOURCE != "synthetic":
        raise AnalyticsSourceUnavailable()
    return _synthetic_repository
