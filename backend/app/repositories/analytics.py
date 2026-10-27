from dataclasses import dataclass
from typing import Callable, ClassVar, Protocol

from app.core.config import settings
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_analytics_db
from app.synthetic import fixtures


class AnalyticsSourceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class MonthlyCoverage:
    """Inclusive source coverage, independent of observed events and UC snapshots."""

    start: str
    end: str


@dataclass(frozen=True)
class UCCoverage:
    """Coverage declaration for one UC source, independent of its rows."""

    uc_ids: frozenset[str]
    start: str | None = None
    end: str | None = None
    snapshot_at: str | None = None


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
    uc_monthly_coverage: dict[str, UCCoverage]
    uc_snapshot_coverage: dict[str, UCCoverage]


_SYNTHETIC_UC_COVERAGE_IDS = frozenset({"UC-1001", "UC-1002", "UC-1003", "UC-1004"})
_SYNTHETIC_UC_PROFILE_IDS = frozenset(unit["uc_id"] for unit in fixtures.UNITS)


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
    source_limitations: ClassVar[list[str]] = [fixtures.DATA_LIMITATION]
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
    uc_monthly_coverage: ClassVar[dict[str, UCCoverage]] = {
        measure: UCCoverage(_SYNTHETIC_UC_COVERAGE_IDS, "2025-01", "2025-02")
        for measure in (
            "measured_energy_kwh",
            "billed_amount",
            "billed_energy_kwh",
            "paid_amount",
            "interruptions",
            "calls",
        )
    }
    uc_snapshot_coverage: ClassVar[dict[str, UCCoverage]] = {
        "profile": UCCoverage(
            _SYNTHETIC_UC_PROFILE_IDS, snapshot_at=fixtures.UPDATED_AT[:10]
        ),
        "meters": UCCoverage(
            _SYNTHETIC_UC_COVERAGE_IDS, snapshot_at=fixtures.UPDATED_AT[:10]
        ),
        "distributed_generation": UCCoverage(
            _SYNTHETIC_UC_COVERAGE_IDS, snapshot_at=fixtures.UPDATED_AT[:10]
        ),
    }

    def __init__(self):
        self.units = [dict(row) for row in fixtures.UNITS]
        self.invoices = [dict(row) for row in fixtures.INVOICES]
        self.readings = [dict(row) for row in fixtures.READINGS]
        self.meters = [dict(row) for row in fixtures.METERS]
        self.generation = [dict(row) for row in fixtures.GENERATION]
        self.interruptions = [dict(row) for row in fixtures.INTERRUPTIONS]
        self.calls = [dict(row) for row in fixtures.CALLS]
        self.feeders = [dict(row) for row in fixtures.FEEDERS]
        self.suspicions = [dict(row) for row in fixtures.SUSPICIONS]
        self.source_limitations = list(type(self).source_limitations)
        self.uc_monthly_coverage = dict(type(self).uc_monthly_coverage)
        self.uc_snapshot_coverage = dict(type(self).uc_snapshot_coverage)


_synthetic_repository = SyntheticAnalyticsRepository()


def get_analytics_repository(db: Session | None = Depends(get_analytics_db)) -> AnalyticsRepository:
    """FastAPI dependency: synthetic is explicit; all other allowed modes fail closed."""
    if settings.ANALYTICS_SOURCE == "gold":
        from app.repositories.gold import GoldAnalyticsRepository
        return GoldAnalyticsRepository(db)
    if settings.ANALYTICS_SOURCE != "synthetic":
        raise AnalyticsSourceUnavailable()
    return _synthetic_repository


def get_analytics_repository_provider(db: Session | None = Depends(get_analytics_db)) -> Callable[[], AnalyticsRepository]:
    """Resolve analytics lazily, only when a new order needs queue evidence."""
    return lambda: get_analytics_repository(db)
