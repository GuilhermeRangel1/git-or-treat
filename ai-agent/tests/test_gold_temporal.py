"""Regras puras das janelas Gold v2, sem consulta ou relógio do servidor."""

import pytest

from app.agent.interpreter import QuestionInterpreter
from app.agent.temporal import GoldTemporalWindowResolver, TemporalResolutionUnavailable
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import WindowKind

_COVERAGE = tuple(
    f"{year:04d}-{month:02d}"
    for year in range(2023, 2026)
    for month in range(1, 13)
    if (year, month) <= (2025, 4)
)


@pytest.mark.parametrize(
    ("phrase", "start", "end"),
    [
        ("último ano", "2024-05-01", "2025-04-30"),
        ("últimos 12 meses", "2024-05-01", "2025-04-30"),
        ("ano passado", "2024-01-01", "2024-12-31"),
        ("este ano", "2025-01-01", "2025-04-30"),
        ("último trimestre", "2025-02-01", "2025-04-30"),
        ("últimos três meses", "2025-02-01", "2025-04-30"),
        ("mês passado", "2025-03-01", "2025-03-31"),
    ],
)
def test_relative_phrase_uses_competencies_and_inclusive_calendar_months(phrase, start, end):
    window = GoldTemporalWindowResolver().resolve(phrase, _COVERAGE)

    assert window.kind is WindowKind.BOUNDED
    assert window.start.isoformat() == start
    assert window.end.isoformat() == end
    assert window.granularity.value == "month"


@pytest.mark.parametrize(
    ("phrase", "coverage"),
    [
        ("últimos 12 meses", ("2024-05", "2024-06", "2024-08", "2024-09")),
        ("ano passado", ("2025-01", "2025-02")),
        ("este ano", ("2025-01", "2025-03")),
        ("mês passado", ("2025-01", "2025-03")),
        ("último trimestre", ()),
    ],
)
def test_missing_coverage_or_internal_gaps_do_not_shorten_windows(phrase, coverage):
    with pytest.raises(TemporalResolutionUnavailable):
        GoldTemporalWindowResolver().resolve(phrase, coverage)


def test_accumulated_window_remains_a_phrase_without_invented_dates():
    window = GoldTemporalWindowResolver().resolve("histórico acumulado", None)

    assert window.kind is WindowKind.CATALOG_PHRASE
    assert window.phrase == "histórico acumulado"
    assert window.start is None
    assert window.end is None


def test_period_answer_after_coverage_clarification_preserves_metric_and_filters():
    interpreter = QuestionInterpreter(GRID360_GOLD_PROFILE)
    original = "Qual a receita faturada para a classe residencial no último ano?"
    clarification = GRID360_GOLD_PROFILE.clarifications.temporal_coverage_unavailable
    assert clarification is not None
    context = [
        ConversationTurn(role="user", content=original),
        ConversationTurn(role="assistant", content=clarification),
    ]

    result = interpreter.interpret("último trimestre", context)

    assert result.status.value == "ready"
    assert result.intent is not None
    assert result.intent.metric_id == "billing.revenue"
    assert result.intent.period_phrase == "último trimestre"
    assert result.intent.class_phrase == "residencial"


def test_non_period_answer_after_coverage_clarification_repeats_clarification():
    interpreter = QuestionInterpreter(GRID360_GOLD_PROFILE)
    original = "Qual a receita faturada no último ano?"
    clarification = GRID360_GOLD_PROFILE.clarifications.temporal_coverage_unavailable
    assert clarification is not None
    context = [
        ConversationTurn(role="user", content=original),
        ConversationTurn(role="assistant", content=clarification),
    ]

    result = interpreter.interpret("Recife", context)

    assert result.status.value == "needs_clarification"
    assert result.clarification_question == clarification
