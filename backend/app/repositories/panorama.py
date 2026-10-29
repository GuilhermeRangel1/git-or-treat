from typing import ClassVar, Protocol

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.synthetic import panorama_fixtures
from app.models.gold_load import TABLES
from app.repositories.gold_context import GoldContext


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


class GoldPanoramaRepository:
    """SQL aggregates for the financial subset supported by the Gold export."""

    source_kind = "gold"
    source_version = "2.0.0"
    source_is_demo = False

    def __init__(self, context: GoldContext):
        self.context = context
        self.connection = context.connection
        self.table = TABLES["diagnostico_receita"]
        self.source_updated_at = context.imported_at.isoformat()
        self.source_limitations = [
            "Receita paga, energia faturada e UCs ativas não estão disponíveis nesta fonte Gold.",
            "A série usa pares UC/mês presentes simultaneamente em faturas e leituras; não há declaração de fechamento mensal.",
        ]

    def options(self) -> tuple[list[str], list[str], list[str]]:
        table = self.table
        rows = self.connection.execute(select(
            table.c.competencia, table.c.municipio, table.c.classe_consumo,
        ).distinct()).all()
        return (
            sorted({row.competencia for row in rows}),
            sorted({row.municipio for row in rows}),
            sorted({row.classe_consumo for row in rows}),
        )

    def aggregate(self, competencia: str, municipio: str | None = None, classe: str | None = None):
        table = self.table
        conditions = [table.c.competencia == competencia]
        if municipio is not None:
            conditions.append(table.c.municipio == municipio)
        if classe is not None:
            conditions.append(table.c.classe_consumo == classe)
        statement = select(
            func.sum(table.c.receita_total_reais).label("revenue"),
            func.sum(table.c.consumo_total_kwh).label("energy"),
            func.sum(table.c.qtd_ucs_distintas_faturadas_no_mes).label("billed_ucs"),
            func.count().label("row_count"),
            func.count(table.c.receita_total_reais).label("revenue_values"),
            func.count(table.c.consumo_total_kwh).label("energy_values"),
            func.count(table.c.qtd_ucs_distintas_faturadas_no_mes).label("billed_uc_values"),
        ).where(*conditions)
        row = self.connection.execute(statement).mappings().one()
        return dict(row)

    def series(self, through: str, municipio: str | None = None, classe: str | None = None):
        table = self.table
        conditions = [table.c.competencia <= through]
        if municipio is not None:
            conditions.append(table.c.municipio == municipio)
        if classe is not None:
            conditions.append(table.c.classe_consumo == classe)
        statement = select(
            table.c.competencia,
            func.sum(table.c.receita_total_reais).label("revenue"),
            func.sum(table.c.consumo_total_kwh).label("energy"),
            func.count().label("row_count"),
            func.count(table.c.receita_total_reais).label("revenue_values"),
            func.count(table.c.consumo_total_kwh).label("energy_values"),
        ).where(*conditions).group_by(table.c.competencia).order_by(table.c.competencia)
        return [dict(row) for row in self.connection.execute(statement).mappings()]


def get_panorama_repository() -> PanoramaRepository:
    """FastAPI dependency: a fonte sintética é explícita; os demais modos falham fechado."""
    if settings.ANALYTICS_SOURCE != "synthetic":
        raise AnalyticsSourceUnavailable()
    return _synthetic_repository
