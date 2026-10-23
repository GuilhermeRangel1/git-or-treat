from typing import ClassVar, Protocol

from app.core.config import settings
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.synthetic import panorama_fixtures


class PanoramaRepository(Protocol):
    records: list[dict]
    incomplete_periods: frozenset[str]
    source_kind: str
    source_version: str
    source_is_demo: bool
    source_updated_at: str
    source_limitations: list[str]


class SyntheticPanoramaRepository:
    """Adaptador somente leitura dos controles sintéticos do Panorama (WEB-01)."""

    records = panorama_fixtures.PANORAMA_RECORDS
    incomplete_periods = frozenset({panorama_fixtures.INCOMPLETE_PERIOD})
    source_kind = "synthetic"
    source_version = panorama_fixtures.DATA_VERSION
    source_is_demo = True
    source_updated_at = panorama_fixtures.UPDATED_AT
    source_limitations: ClassVar[list[str]] = [panorama_fixtures.DATA_LIMITATION]


_synthetic_repository = SyntheticPanoramaRepository()


def get_panorama_repository() -> PanoramaRepository:
    """FastAPI dependency: a fonte sintética é explícita; os demais modos falham fechado."""
    if settings.ANALYTICS_SOURCE != "synthetic":
        raise AnalyticsSourceUnavailable()
    return _synthetic_repository
