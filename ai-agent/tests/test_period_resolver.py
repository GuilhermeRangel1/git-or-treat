"""Resolvedor de períodos (GENAI-04, parte 04b) com competências fictícias e data injetada."""

import itertools
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.periods import (
    ClarificationReason,
    CurrentYearMode,
    GapInWindowMode,
    LastYearMode,
    PartialCoverageMode,
    PeriodCatalog,
    PeriodKind,
    PeriodNeedsClarification,
    PeriodSemantics,
    PeriodSpec,
    QuarterMode,
    RelativeAnchor,
    ResolvedWindow,
    parse_period_phrase,
    resolve,
)
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.domain_profile import CatalogGranularity
from app.schemas.read_plan import WindowKind

BATCH = "gold-csv-v1:GOLD_20310701T000000Z_0123abcd:12345678-1234-4123-8123-123456789abc"
MID_MONTH = date(2031, 5, 15)
JANUARY = date(2031, 1, 10)
DECEMBER = date(2030, 12, 20)


def _months(first: str, last: str) -> list[str]:
    year, month = map(int, first.split("-"))
    result = []
    while f"{year:04d}-{month:02d}" <= last:
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


FULL = _months("2030-01", "2031-06")


def _catalog(reference_date: date = MID_MONTH, competencias=FULL) -> PeriodCatalog:
    return PeriodCatalog.from_competencias(
        reference_date=reference_date, batch_ref=BATCH, competencias=competencias
    )


def _semantics(**overrides) -> PeriodSemantics:
    values = {
        "last_year_mode": LastYearMode.PREVIOUS_CALENDAR_YEAR,
        "relative_anchor": RelativeAnchor.REFERENCE_DATE,
        "quarter_mode": QuarterMode.CLOSED_CALENDAR_QUARTER,
        "current_year_mode": CurrentYearMode.TO_LAST_AVAILABLE_WITH_WARNING,
        "partial_coverage_mode": PartialCoverageMode.ANSWER_WITH_LIMITATION,
        "gap_in_window_mode": GapInWindowMode.ASK,
    }
    return PeriodSemantics(**{**values, **overrides})


ALL_SEMANTICS = [
    PeriodSemantics(
        last_year_mode=last_year,
        relative_anchor=anchor,
        quarter_mode=quarter,
        current_year_mode=current_year,
        partial_coverage_mode=partial,
        gap_in_window_mode=gap,
    )
    for last_year, anchor, quarter, current_year, partial, gap in itertools.product(
        LastYearMode, RelativeAnchor, QuarterMode, CurrentYearMode, PartialCoverageMode,
        GapInWindowMode,
    )
]


def _resolve(phrase: str, catalog: PeriodCatalog | None = None, **overrides):
    spec = parse_period_phrase(phrase)
    assert spec is not None, phrase
    return resolve(spec, catalog or _catalog(), _semantics(**overrides))


def _span(result) -> tuple[str, str]:
    assert isinstance(result, ResolvedWindow), result
    return result.window.start.isoformat()[:7], result.window.end.isoformat()[:7]


# --- parse_period_phrase ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mês passado", {"kind": PeriodKind.LAST_MONTH}),
        ("Último Mês", {"kind": PeriodKind.LAST_MONTH}),
        ("últimos 12 meses", {"kind": PeriodKind.LAST_N_MONTHS, "months": 12}),
        ("ultimos 3 meses", {"kind": PeriodKind.LAST_N_MONTHS, "months": 3}),
        ("últimos três meses", {"kind": PeriodKind.LAST_N_MONTHS, "months": 3}),
        ("último trimestre", {"kind": PeriodKind.LAST_QUARTER}),
        ("último ano", {"kind": PeriodKind.LAST_YEAR}),
        ("ano passado", {"kind": PeriodKind.PREVIOUS_YEAR}),
        ("este ano", {"kind": PeriodKind.THIS_YEAR}),
        ("agosto de 2030", {"kind": PeriodKind.MONTH, "year": 2030, "month": 8}),
        ("em MARCO de 2031", {"kind": PeriodKind.MONTH, "year": 2031, "month": 3}),
        ("2030", {"kind": PeriodKind.YEAR, "year": 2030}),
        ("em 2030", {"kind": PeriodKind.YEAR, "year": 2030}),
        ("no ano de 2030", {"kind": PeriodKind.YEAR, "year": 2030}),
        (
            "de janeiro a março de 2031",
            {"kind": PeriodKind.RANGE, "year": 2031, "month": 1, "end_year": 2031, "end_month": 3},
        ),
        (
            "de novembro de 2030 até fevereiro de 2031",
            {"kind": PeriodKind.RANGE, "year": 2030, "month": 11, "end_year": 2031, "end_month": 2},
        ),
        ("março", {"kind": PeriodKind.MONTH_WITHOUT_YEAR, "month": 3}),
        ("em agosto", {"kind": PeriodKind.MONTH_WITHOUT_YEAR, "month": 8}),
    ],
)
def test_phrase_is_structured_without_case_or_accent(text: str, expected: dict) -> None:
    spec = parse_period_phrase(text)

    assert spec is not None
    assert spec.phrase == text
    assert spec.model_dump(exclude={"phrase"}, exclude_none=True) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "Recife", "semana passada", "últimos 0 meses", "últimos 61 meses",
     "agosto de 30", "trimestre que vem", "março de 2030 em Olinda"],
)
def test_unknown_phrase_is_not_structured(text: str) -> None:
    assert parse_period_phrase(text) is None


def test_every_gold_period_phrase_is_structured() -> None:
    for phrase in GRID360_GOLD_PROFILE.period_phrases:
        assert parse_period_phrase(phrase) is not None, phrase


def test_spec_rejects_fields_of_another_kind() -> None:
    with pytest.raises(ValidationError):
        PeriodSpec(kind=PeriodKind.MONTH, phrase="agosto", month=8)
    with pytest.raises(ValidationError):
        PeriodSpec(kind=PeriodKind.LAST_MONTH, phrase="mês passado", year=2030)


# --- frases relativas ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reference_date", "phrase", "overrides", "expected"),
    [
        # Meio do mês: o mês corrente (maio/2031) ainda não fechou.
        (MID_MONTH, "mês passado", {}, ("2031-04", "2031-04")),
        (MID_MONTH, "último mês", {}, ("2031-04", "2031-04")),
        (MID_MONTH, "últimos 3 meses", {}, ("2031-02", "2031-04")),
        (MID_MONTH, "últimos 12 meses", {}, ("2030-05", "2031-04")),
        (MID_MONTH, "último trimestre", {}, ("2031-01", "2031-03")),
        (
            MID_MONTH,
            "último trimestre",
            {"quarter_mode": QuarterMode.LAST_THREE_MONTHS},
            ("2031-02", "2031-04"),
        ),
        (MID_MONTH, "ano passado", {}, ("2030-01", "2030-12")),
        (MID_MONTH, "último ano", {}, ("2030-01", "2030-12")),
        (
            MID_MONTH,
            "último ano",
            {"last_year_mode": LastYearMode.TRAILING_12_ENDING_LAST_AVAILABLE},
            ("2030-07", "2031-06"),
        ),
        # Janeiro: o mês fechado anterior é dezembro do ano anterior.
        (JANUARY, "mês passado", {}, ("2030-12", "2030-12")),
        (JANUARY, "últimos 3 meses", {}, ("2030-10", "2030-12")),
        (JANUARY, "últimos 12 meses", {}, ("2030-01", "2030-12")),
        (JANUARY, "último trimestre", {}, ("2030-10", "2030-12")),
        (
            JANUARY,
            "último trimestre",
            {"quarter_mode": QuarterMode.LAST_THREE_MONTHS},
            ("2030-10", "2030-12"),
        ),
        (JANUARY, "ano passado", {}, ("2030-01", "2030-12")),
        (JANUARY, "este ano", {}, ("2031-01", "2031-06")),
        # Dezembro: o trimestre fechado é o terceiro; o quarto ainda não terminou.
        (DECEMBER, "mês passado", {}, ("2030-11", "2030-11")),
        (DECEMBER, "último trimestre", {}, ("2030-07", "2030-09")),
        (
            DECEMBER,
            "último trimestre",
            {"quarter_mode": QuarterMode.LAST_THREE_MONTHS},
            ("2030-09", "2030-11"),
        ),
        (DECEMBER, "este ano", {}, ("2030-01", "2030-12")),
        # Âncora no lote: o mês corrente é o seguinte à última competência (2031-06).
        (MID_MONTH, "mês passado", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2031-06", "2031-06")),
        (DECEMBER, "mês passado", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2031-06", "2031-06")),
        (MID_MONTH, "últimos 12 meses", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2030-07", "2031-06")),
        (MID_MONTH, "último trimestre", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2031-04", "2031-06")),
        (MID_MONTH, "ano passado", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2030-01", "2030-12")),
        (MID_MONTH, "último ano", {"relative_anchor": RelativeAnchor.LAST_AVAILABLE},
         ("2030-01", "2030-12")),
    ],
)
def test_relative_phrase_resolves_to_closed_months(
    reference_date: date, phrase: str, overrides: dict, expected: tuple[str, str]
) -> None:
    result = _resolve(phrase, _catalog(reference_date), **overrides)

    assert _span(result) == expected
    assert result.window.kind is WindowKind.BOUNDED
    assert result.window.granularity is CatalogGranularity.MONTH
    assert result.requested_phrase == phrase


def test_anchor_on_reference_date_and_on_last_available_differ() -> None:
    catalog = _catalog(DECEMBER, _months("2030-01", "2031-03"))

    by_date = _resolve("último trimestre", catalog)
    by_lot = _resolve("último trimestre", catalog, relative_anchor=RelativeAnchor.LAST_AVAILABLE)

    assert _span(by_date) == ("2030-07", "2030-09")
    assert _span(by_lot) == ("2031-01", "2031-03")


def test_quarter_modes_differ_when_last_closed_month_is_not_a_quarter_end() -> None:
    catalog = _catalog(competencias=_months("2030-01", "2031-05"))
    anchor = {"relative_anchor": RelativeAnchor.LAST_AVAILABLE}

    closed = _resolve("último trimestre", catalog, **anchor)
    trailing = _resolve(
        "último trimestre", catalog, quarter_mode=QuarterMode.LAST_THREE_MONTHS, **anchor
    )

    assert _span(closed) == ("2031-01", "2031-03")
    assert _span(trailing) == ("2031-03", "2031-05")


def test_last_year_modes_differ() -> None:
    catalog = _catalog(JANUARY, _months("2029-01", "2030-09"))

    calendar_year = _resolve("último ano", catalog)
    trailing = _resolve(
        "último ano", catalog, last_year_mode=LastYearMode.TRAILING_12_ENDING_LAST_AVAILABLE
    )

    assert _span(calendar_year) == ("2030-01", "2030-12")
    assert calendar_year.missing == ("2030-10", "2030-11", "2030-12")
    assert _span(trailing) == ("2029-10", "2030-09")
    assert not trailing.partial


def test_relative_window_partly_before_the_lot_keeps_its_start() -> None:
    result = _resolve("últimos 12 meses", _catalog(DECEMBER))

    assert _span(result) == ("2029-12", "2030-11")
    assert result.partial
    assert result.missing == ("2029-12",)


def test_relative_window_after_the_lot_asks_instead_of_moving() -> None:
    result = _resolve("mês passado", _catalog(date(2031, 9, 3)))

    assert isinstance(result, PeriodNeedsClarification)
    assert result.reason is ClarificationReason.OUT_OF_RANGE
    assert (result.available_first, result.available_last) == ("2030-01", "2031-06")


# --- ano corrente ----------------------------------------------------------------------


def test_current_year_to_last_available_warns_with_months_not_loaded() -> None:
    result = _resolve("este ano", _catalog(date(2031, 7, 2)))

    assert _span(result) == ("2031-01", "2031-06")
    assert result.partial
    assert result.missing == tuple(_months("2031-07", "2031-12"))


def test_current_year_ask_returns_the_available_range() -> None:
    result = _resolve(
        "este ano", _catalog(date(2031, 7, 2)), current_year_mode=CurrentYearMode.ASK
    )

    assert result == PeriodNeedsClarification(
        reason=ClarificationReason.CURRENT_YEAR_PARTIAL,
        requested_phrase="este ano",
        available_first="2030-01",
        available_last="2031-06",
    )


@pytest.mark.parametrize("mode", list(CurrentYearMode))
def test_current_year_complete_in_the_lot_is_not_partial(mode: CurrentYearMode) -> None:
    result = _resolve("este ano", _catalog(DECEMBER), current_year_mode=mode)

    assert _span(result) == ("2030-01", "2030-12")
    assert not result.partial


def test_current_year_without_any_loaded_month_is_out_of_range() -> None:
    result = _resolve("este ano", _catalog(date(2032, 2, 1)))

    assert isinstance(result, PeriodNeedsClarification)
    assert result.reason is ClarificationReason.OUT_OF_RANGE


# --- frases explícitas -----------------------------------------------------------------


def test_isolated_month_and_year() -> None:
    assert _span(_resolve("agosto de 2030")) == ("2030-08", "2030-08")
    assert _span(_resolve("em 2030")) == ("2030-01", "2030-12")


@pytest.mark.parametrize("phrase", ["março de 2029", "agosto de 2032", "2029", "2032"])
def test_explicit_period_outside_the_lot_asks(phrase: str) -> None:
    result = _resolve(phrase)

    assert result == PeriodNeedsClarification(
        reason=ClarificationReason.OUT_OF_RANGE,
        requested_phrase=phrase,
        available_first="2030-01",
        available_last="2031-06",
    )


def test_range_across_year_end() -> None:
    result = _resolve("de novembro de 2030 a fevereiro de 2031")

    assert result.window.start == date(2030, 11, 1)
    assert result.window.end == date(2031, 2, 28)
    assert not result.partial


@pytest.mark.parametrize(
    "phrase", ["de março de 2031 a janeiro de 2031", "de novembro a fevereiro de 2031"]
)
def test_inverted_range_is_invalid_and_no_year_is_inferred(phrase: str) -> None:
    result = _resolve(phrase)

    assert result == PeriodNeedsClarification(
        reason=ClarificationReason.INVALID_RANGE, requested_phrase=phrase
    )


@pytest.mark.parametrize("phrase", ["março", "em agosto"])
def test_month_without_year_asks_for_the_year(phrase: str) -> None:
    result = _resolve(phrase)

    assert result == PeriodNeedsClarification(
        reason=ClarificationReason.MISSING_YEAR, requested_phrase=phrase
    )


@pytest.mark.parametrize(
    ("phrase", "last_day"), [("fevereiro de 2032", 29), ("fevereiro de 2031", 28)]
)
def test_february_ends_on_its_last_day(phrase: str, last_day: int) -> None:
    result = _resolve(phrase, _catalog(competencias=["2031-02", "2032-02"]))

    assert result.window.end.day == last_day


# --- cobertura parcial e lacunas -------------------------------------------------------


@pytest.mark.parametrize("mode", list(PartialCoverageMode))
def test_partial_coverage_follows_its_mode(mode: PartialCoverageMode) -> None:
    result = _resolve("2031", partial_coverage_mode=mode)

    if mode is PartialCoverageMode.ASK:
        assert isinstance(result, PeriodNeedsClarification)
        assert result.reason is ClarificationReason.PARTIAL_COVERAGE
        assert (result.available_first, result.available_last) == ("2030-01", "2031-06")
    else:
        assert _span(result) == ("2031-01", "2031-12")
        assert result.missing == tuple(_months("2031-07", "2031-12"))


@pytest.mark.parametrize("mode", list(GapInWindowMode))
def test_gap_in_window_follows_its_mode(mode: GapInWindowMode) -> None:
    with_gap = [item for item in FULL if item != "2030-06"]

    result = _resolve(
        "de abril a agosto de 2030", _catalog(competencias=with_gap), gap_in_window_mode=mode
    )

    if mode is GapInWindowMode.ASK:
        assert isinstance(result, PeriodNeedsClarification)
        assert result.reason is ClarificationReason.GAP_IN_WINDOW
    else:
        assert _span(result) == ("2030-04", "2030-08")
        assert result.missing == ("2030-06",)


def test_partial_coverage_is_reported_before_a_gap_when_both_ask() -> None:
    with_gap = [item for item in FULL if item != "2030-06"]

    result = _resolve(
        "de dezembro de 2029 a julho de 2030",
        _catalog(competencias=with_gap),
        partial_coverage_mode=PartialCoverageMode.ASK,
    )

    assert result.reason is ClarificationReason.PARTIAL_COVERAGE


def test_explicit_window_is_never_shortened_or_moved() -> None:
    with_gap = [item for item in _months("2030-03", "2031-04") if item != "2030-09"]
    catalog = _catalog(competencias=with_gap)
    requested = {
        "agosto de 2030": ("2030-08", "2030-08"),
        "2030": ("2030-01", "2030-12"),
        "de julho a outubro de 2030": ("2030-07", "2030-10"),
        "de dezembro de 2030 a junho de 2031": ("2030-12", "2031-06"),
    }
    for semantics in ALL_SEMANTICS:
        for phrase, span in requested.items():
            result = resolve(parse_period_phrase(phrase), catalog, semantics)
            if isinstance(result, ResolvedWindow):
                assert _span(result) == span, (phrase, semantics)


# --- catálogo vazio, validação e determinismo ------------------------------------------


def test_empty_lot_always_asks_and_never_raises() -> None:
    catalog = _catalog(competencias=[])
    phrases = [
        "mês passado", "últimos 12 meses", "último trimestre", "último ano", "ano passado",
        "este ano", "agosto de 2030", "2030", "de janeiro a março de 2031",
    ]
    for semantics in ALL_SEMANTICS:
        for phrase in phrases:
            result = resolve(parse_period_phrase(phrase), catalog, semantics)
            assert result == PeriodNeedsClarification(
                reason=ClarificationReason.OUT_OF_RANGE, requested_phrase=phrase
            ), (phrase, semantics)


def test_catalog_validates_competencias() -> None:
    assert _catalog(competencias=["2031-02", "2030-01"]).available == ("2030-01", "2031-02")
    for invalid in (["2030-13"], ["2030-1"], ["2030-01", "2030-01"]):
        with pytest.raises(ValidationError):
            _catalog(competencias=invalid)
    with pytest.raises(ValidationError):
        PeriodCatalog(reference_date=MID_MONTH, batch_ref=BATCH, available=("2031-02", "2030-01"))
    with pytest.raises(ValidationError):
        PeriodCatalog(reference_date=MID_MONTH, batch_ref="lote", available=())


def test_semantics_has_no_default() -> None:
    with pytest.raises(ValidationError):
        PeriodSemantics()
    values = _semantics().model_dump()
    for field in values:
        with pytest.raises(ValidationError):
            PeriodSemantics(**{key: value for key, value in values.items() if key != field})


def test_same_input_resolves_to_the_same_window() -> None:
    first = _resolve("últimos 12 meses", _catalog(DECEMBER))
    second = _resolve("últimos 12 meses", _catalog(DECEMBER))

    assert first == second
    assert first.window.model_dump_json() == second.window.model_dump_json()


def test_module_does_not_read_the_clock() -> None:
    package = Path(__file__).resolve().parents[1] / "app" / "periods"
    forbidden = ("date.today", "datetime.now", "datetime.utcnow", "time.time", "today()")
    for source in package.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert not any(item in text for item in forbidden), source.name
