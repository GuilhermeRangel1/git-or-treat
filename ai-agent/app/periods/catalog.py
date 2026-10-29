"""Contratos do catálogo de períodos: competências do lote, semântica e frase estruturada.

Nada aqui lê relógio, banco ou lote. A data de referência e as competências são injetadas pelo
chamador; a semântica de cada frase relativa é escolhida explicitamente, sem valor padrão.
"""

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.readiness.models import Competencia, GoldBatchRef


class PeriodCatalog(BaseModel):
    """Competências disponíveis na tabela da fonte escolhida e a data de referência."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_date: date
    batch_ref: GoldBatchRef
    available: tuple[Competencia, ...] = Field(max_length=1200)

    @model_validator(mode="after")
    def require_sorted_unique(self) -> Self:
        if list(self.available) != sorted(set(self.available)):
            raise ValueError("competências fora de ordem ou duplicadas")
        return self

    @classmethod
    def from_competencias(
        cls, *, reference_date: date, batch_ref: str, competencias: Iterable[str]
    ) -> Self:
        """Monta o catálogo com as competências da tabela que ``select_source`` escolheu (D7).

        Ordena a entrada; competência duplicada continua sendo erro, como em ``TableFacts``.
        """

        return cls(
            reference_date=reference_date,
            batch_ref=batch_ref,
            available=tuple(sorted(competencias)),
        )


class LastYearMode(StrEnum):
    """D1: "último ano"."""

    TRAILING_12_ENDING_LAST_AVAILABLE = "trailing_12_ending_last_available"
    PREVIOUS_CALENDAR_YEAR = "previous_calendar_year"


class RelativeAnchor(StrEnum):
    """D2: mês de que partem as frases relativas."""

    REFERENCE_DATE = "reference_date"
    LAST_AVAILABLE = "last_available"


class QuarterMode(StrEnum):
    """D4: "último trimestre"."""

    CLOSED_CALENDAR_QUARTER = "closed_calendar_quarter"
    LAST_THREE_MONTHS = "last_three_months"


class CurrentYearMode(StrEnum):
    """D3: "este ano" ainda incompleto no lote."""

    TO_LAST_AVAILABLE_WITH_WARNING = "to_last_available_with_warning"
    ASK = "ask"


class PartialCoverageMode(StrEnum):
    """D5: janela que passa da primeira ou da última competência disponível."""

    ANSWER_WITH_LIMITATION = "answer_with_limitation"
    ASK = "ask"


class GapInWindowMode(StrEnum):
    """D8: competência ausente entre a primeira e a última disponível."""

    ASK = "ask"
    ANSWER_WITH_LIMITATION = "answer_with_limitation"


class PeriodSemantics(BaseModel):
    """Escolhas de semântica pendentes com Dados; todos os campos são obrigatórios."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    last_year_mode: LastYearMode
    relative_anchor: RelativeAnchor
    quarter_mode: QuarterMode
    current_year_mode: CurrentYearMode
    partial_coverage_mode: PartialCoverageMode
    gap_in_window_mode: GapInWindowMode


class PeriodKind(StrEnum):
    LAST_MONTH = "last_month"
    LAST_N_MONTHS = "last_n_months"
    LAST_QUARTER = "last_quarter"
    LAST_YEAR = "last_year"
    PREVIOUS_YEAR = "previous_year"
    THIS_YEAR = "this_year"
    MONTH = "month"
    YEAR = "year"
    RANGE = "range"
    MONTH_WITHOUT_YEAR = "month_without_year"


_FIELDS_BY_KIND = {
    PeriodKind.LAST_MONTH: set(),
    PeriodKind.LAST_N_MONTHS: {"months"},
    PeriodKind.LAST_QUARTER: set(),
    PeriodKind.LAST_YEAR: set(),
    PeriodKind.PREVIOUS_YEAR: set(),
    PeriodKind.THIS_YEAR: set(),
    PeriodKind.MONTH: {"year", "month"},
    PeriodKind.YEAR: {"year"},
    PeriodKind.RANGE: {"year", "month", "end_year", "end_month"},
    PeriodKind.MONTH_WITHOUT_YEAR: {"month"},
}


class PeriodSpec(BaseModel):
    """Frase de período já estruturada; ``phrase`` guarda o texto como foi escrito."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: PeriodKind
    phrase: str = Field(min_length=1, max_length=160)
    months: int | None = Field(default=None, ge=1, le=60)
    year: int | None = Field(default=None, ge=1000, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1000, le=9999)
    end_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def require_fields_of_kind(self) -> Self:
        present = {
            name
            for name in ("months", "year", "month", "end_year", "end_month")
            if getattr(self, name) is not None
        }
        if present != _FIELDS_BY_KIND[self.kind]:
            raise ValueError("campos incompatíveis com o tipo de período")
        return self
