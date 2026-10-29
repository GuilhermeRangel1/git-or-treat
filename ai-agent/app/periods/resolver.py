"""Resolução pura de frases de período em janelas mensais, contra as competências do lote.

Sem relógio, I/O ou texto de mensagem: o resultado é uma janela ``bounded`` mensal ou um
motivo de esclarecimento com o intervalo disponível como dado. A janela pedida nunca é
encurtada, trocada ou deslocada em silêncio.
"""

import calendar
import re
import unicodedata
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
from app.readiness.models import Competencia
from app.schemas.domain_profile import CatalogGranularity
from app.schemas.read_plan import ReadWindow, WindowKind

_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_NUMBER_WORDS = {
    "dois": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
}
_MONTH = "(" + "|".join(_MONTHS) + ")"
_YEAR = r"([0-9]{4})"
_COUNT = r"([0-9]{1,2}|" + "|".join(_NUMBER_WORDS) + ")"

_FIXED = {
    PeriodKind.LAST_MONTH: re.compile(r"(?:o )?(?:mes passado|ultimo mes)"),
    PeriodKind.LAST_QUARTER: re.compile(r"(?:o )?ultimo trimestre"),
    PeriodKind.LAST_YEAR: re.compile(r"(?:o )?ultimo ano"),
    PeriodKind.PREVIOUS_YEAR: re.compile(r"(?:o )?ano passado"),
    PeriodKind.THIS_YEAR: re.compile(r"n?este ano"),
}
_LAST_N_MONTHS = re.compile(rf"(?:os )?ultimos {_COUNT} meses")
_MONTH_YEAR = re.compile(rf"(?:(?:em|no mes de|durante) )?{_MONTH} (?:de )?{_YEAR}")
_YEAR_ONLY = re.compile(rf"(?:(?:em|no ano de|ano de|durante) )?{_YEAR}")
# "de janeiro a março de 2030": sem ano no início, vale o ano do fim, sem inferir outro.
_RANGE = re.compile(rf"de {_MONTH}(?: de {_YEAR})? (?:a|ate) {_MONTH} de {_YEAR}")
_MONTH_ONLY = re.compile(rf"(?:(?:em|no mes de|durante) )?{_MONTH}")


class ClarificationReason(StrEnum):
    OUT_OF_RANGE = "out_of_range"
    PARTIAL_COVERAGE = "partial_coverage"
    GAP_IN_WINDOW = "gap_in_window"
    MISSING_YEAR = "missing_year"
    CURRENT_YEAR_PARTIAL = "current_year_partial"
    INVALID_RANGE = "invalid_range"


class ResolvedWindow(BaseModel):
    """Janela mensal fechada; ``missing`` só alimenta a limitação, nunca encurta a janela."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window: ReadWindow
    requested_phrase: str = Field(min_length=1, max_length=160)
    partial: bool
    missing: tuple[Competencia, ...] = ()

    @model_validator(mode="after")
    def require_monthly_bounded_window(self) -> Self:
        window = self.window
        if (
            window.kind is not WindowKind.BOUNDED
            or window.granularity is not CatalogGranularity.MONTH
            or window.start is None
            or window.end is None
            or window.start.day != 1
            or window.end.day != calendar.monthrange(window.end.year, window.end.month)[1]
        ):
            raise ValueError("janela resolvida exige meses fechados")
        if self.partial != bool(self.missing):
            raise ValueError("parcialidade e competências ausentes divergem")
        if list(self.missing) != sorted(set(self.missing)):
            raise ValueError("competências ausentes fora de ordem ou duplicadas")
        return self


class PeriodNeedsClarification(BaseModel):
    """Motivo do esclarecimento; o texto da mensagem fica com o chamador (D6 em aberto)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: ClarificationReason
    requested_phrase: str = Field(min_length=1, max_length=160)
    available_first: Competencia | None = None
    available_last: Competencia | None = None

    @model_validator(mode="after")
    def require_complete_range(self) -> Self:
        if (self.available_first is None) != (self.available_last is None):
            raise ValueError("intervalo disponível incompleto")
        return self


def parse_period_phrase(text: str) -> PeriodSpec | None:
    """Estrutura a frase de período, sem diferenciar caixa e acento; desconhecida -> None."""

    normalized = _normalize(text)
    if not normalized:
        return None
    phrase = text.strip()
    for kind, pattern in _FIXED.items():
        if pattern.fullmatch(normalized):
            return PeriodSpec(kind=kind, phrase=phrase)
    if match := _LAST_N_MONTHS.fullmatch(normalized):
        count = match.group(1)
        months = int(count) if count.isdigit() else _NUMBER_WORDS[count]
        if not 1 <= months <= 60:
            return None
        return PeriodSpec(kind=PeriodKind.LAST_N_MONTHS, phrase=phrase, months=months)
    if match := _MONTH_YEAR.fullmatch(normalized):
        return PeriodSpec(
            kind=PeriodKind.MONTH,
            phrase=phrase,
            year=int(match.group(2)),
            month=_MONTHS[match.group(1)],
        )
    if match := _YEAR_ONLY.fullmatch(normalized):
        return PeriodSpec(kind=PeriodKind.YEAR, phrase=phrase, year=int(match.group(1)))
    if match := _RANGE.fullmatch(normalized):
        start_month, start_year, end_month, end_year = match.groups()
        return PeriodSpec(
            kind=PeriodKind.RANGE,
            phrase=phrase,
            year=int(start_year or end_year),
            month=_MONTHS[start_month],
            end_year=int(end_year),
            end_month=_MONTHS[end_month],
        )
    if match := _MONTH_ONLY.fullmatch(normalized):
        return PeriodSpec(
            kind=PeriodKind.MONTH_WITHOUT_YEAR, phrase=phrase, month=_MONTHS[match.group(1)]
        )
    return None


def resolve(
    spec: PeriodSpec, catalog: PeriodCatalog, semantics: PeriodSemantics
) -> ResolvedWindow | PeriodNeedsClarification:
    """Converte a frase em janela mensal ou em motivo de esclarecimento, sem exceção de dado."""

    available = [_month_index(item) for item in catalog.available]
    phrase = spec.phrase

    if spec.kind is PeriodKind.MONTH_WITHOUT_YEAR:
        return PeriodNeedsClarification(
            reason=ClarificationReason.MISSING_YEAR, requested_phrase=phrase
        )
    if spec.kind is PeriodKind.MONTH:
        index = _index(spec.year, spec.month)
        return _cover(index, index, phrase, available, semantics)
    if spec.kind is PeriodKind.YEAR:
        return _cover(_index(spec.year, 1), _index(spec.year, 12), phrase, available, semantics)
    if spec.kind is PeriodKind.RANGE:
        start, end = _index(spec.year, spec.month), _index(spec.end_year, spec.end_month)
        if start > end:
            return PeriodNeedsClarification(
                reason=ClarificationReason.INVALID_RANGE, requested_phrase=phrase
            )
        return _cover(start, end, phrase, available, semantics)

    # Mês corrente: o da data de referência ou, ancorado no lote, o seguinte à última
    # competência. As frases relativas terminam no mês anterior ao corrente.
    if semantics.relative_anchor is RelativeAnchor.REFERENCE_DATE:
        current = _index(catalog.reference_date.year, catalog.reference_date.month)
    elif available:
        current = available[-1] + 1
    else:
        return _clarify(ClarificationReason.OUT_OF_RANGE, phrase, available)
    last_closed = current - 1
    current_year = current // 12

    if spec.kind is PeriodKind.LAST_MONTH:
        return _cover(last_closed, last_closed, phrase, available, semantics)
    if spec.kind is PeriodKind.LAST_N_MONTHS:
        return _cover(last_closed - spec.months + 1, last_closed, phrase, available, semantics)
    if spec.kind is PeriodKind.LAST_QUARTER:
        if semantics.quarter_mode is QuarterMode.LAST_THREE_MONTHS:
            return _cover(last_closed - 2, last_closed, phrase, available, semantics)
        quarter_end = last_closed - (last_closed % 12 + 1) % 3
        return _cover(quarter_end - 2, quarter_end, phrase, available, semantics)
    if spec.kind is PeriodKind.LAST_YEAR:
        if semantics.last_year_mode is LastYearMode.PREVIOUS_CALENDAR_YEAR:
            year = current_year - 1
            return _cover(_index(year, 1), _index(year, 12), phrase, available, semantics)
        if not available:
            return _clarify(ClarificationReason.OUT_OF_RANGE, phrase, available)
        return _cover(available[-1] - 11, available[-1], phrase, available, semantics)
    if spec.kind is PeriodKind.PREVIOUS_YEAR:
        year = current_year - 1
        return _cover(_index(year, 1), _index(year, 12), phrase, available, semantics)

    # PeriodKind.THIS_YEAR
    year_start, year_end = _index(current_year, 1), _index(current_year, 12)
    if not available or available[-1] < year_start or available[-1] >= year_end:
        return _cover(year_start, year_end, phrase, available, semantics)
    if semantics.current_year_mode is CurrentYearMode.ASK:
        return _clarify(ClarificationReason.CURRENT_YEAR_PARTIAL, phrase, available)
    not_loaded = tuple(range(available[-1] + 1, year_end + 1))
    return _cover(year_start, available[-1], phrase, available, semantics, not_loaded)


def _cover(
    start: int,
    end: int,
    phrase: str,
    available: list[int],
    semantics: PeriodSemantics,
    not_loaded: tuple[int, ...] = (),
) -> ResolvedWindow | PeriodNeedsClarification:
    """Confere a janela pedida contra as competências; ``not_loaded`` vem de "este ano"."""

    loaded = set(available)
    requested = range(start, end + 1)
    if not any(index in loaded for index in requested):
        return _clarify(ClarificationReason.OUT_OF_RANGE, phrase, available)
    missing = [index for index in requested if index not in loaded]
    outside = [index for index in missing if not available[0] <= index <= available[-1]]
    if outside and semantics.partial_coverage_mode is PartialCoverageMode.ASK:
        return _clarify(ClarificationReason.PARTIAL_COVERAGE, phrase, available)
    if len(outside) < len(missing) and semantics.gap_in_window_mode is GapInWindowMode.ASK:
        return _clarify(ClarificationReason.GAP_IN_WINDOW, phrase, available)
    absent = tuple(_competencia(index) for index in sorted({*missing, *not_loaded}))
    start_year, start_month = _year_month(start)
    end_year, end_month = _year_month(end)
    return ResolvedWindow(
        window=ReadWindow(
            kind=WindowKind.BOUNDED,
            start=date(start_year, start_month, 1),
            end=date(end_year, end_month, calendar.monthrange(end_year, end_month)[1]),
            granularity=CatalogGranularity.MONTH,
        ),
        requested_phrase=phrase,
        partial=bool(absent),
        missing=absent,
    )


def _clarify(
    reason: ClarificationReason, phrase: str, available: list[int]
) -> PeriodNeedsClarification:
    return PeriodNeedsClarification(
        reason=reason,
        requested_phrase=phrase,
        available_first=_competencia(available[0]) if available else None,
        available_last=_competencia(available[-1]) if available else None,
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", without_accents).strip()


def _index(year: int, month: int) -> int:
    return year * 12 + month - 1


def _year_month(index: int) -> tuple[int, int]:
    return index // 12, index % 12 + 1


def _month_index(competencia: str) -> int:
    year, month = competencia.split("-")
    return _index(int(year), int(month))


def _competencia(index: int) -> str:
    year, month = _year_month(index)
    return f"{year:04d}-{month:02d}"
