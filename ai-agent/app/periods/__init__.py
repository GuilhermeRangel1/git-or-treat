"""Catálogo de períodos em tempo de execução (GENAI-04, parte 04b); ainda fora do fluxo."""

from app.periods.catalog import (
    CurrentYearMode,
    GapInWindowMode,
    LastYearMode,
    PartialCoverageMode,
    PeriodCatalog,
    PeriodKind,
    PeriodSemantics,
    PeriodSpec,
    QuarterMode,
    RelativeAnchor,
)
from app.periods.resolver import (
    ClarificationReason,
    PeriodNeedsClarification,
    ResolvedWindow,
    parse_period_phrase,
    resolve,
)

__all__ = [
    "ClarificationReason",
    "CurrentYearMode",
    "GapInWindowMode",
    "LastYearMode",
    "PartialCoverageMode",
    "PeriodCatalog",
    "PeriodKind",
    "PeriodNeedsClarification",
    "PeriodSemantics",
    "PeriodSpec",
    "QuarterMode",
    "RelativeAnchor",
    "ResolvedWindow",
    "parse_period_phrase",
    "resolve",
]
