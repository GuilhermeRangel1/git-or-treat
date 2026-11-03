"""Continuações naturais herdam ano somente de uma competência inequívoca."""

import pytest

from app.agent.temporal import complete_contextual_period
from app.schemas.questions import ConversationTurn


@pytest.mark.parametrize("text", ["maio", "e em maio?", "Na verdade, maio.", "corrigindo: em maio"])
def test_short_month_inherits_only_explicit_year(text):
    context = [ConversationTurn(role="user", content="Qual a receita em 2026-06?")]
    assert complete_contextual_period(text, context) == "E em 2026-05?"


@pytest.mark.parametrize(
    "anchor",
    ["Qual a receita?", "Compare receita entre 2025-12 e 2026-06.", "Receita de 2025-01 a 2026-06"],
)
def test_ambiguous_or_missing_antecedent_does_not_invent_year(anchor):
    assert (
        complete_contextual_period("e em maio?", [ConversationTurn(role="user", content=anchor)])
        == "e em maio?"
    )


def test_previous_month_crosses_year_boundary():
    context = [ConversationTurn(role="user", content="Qual a receita em 2026-01?")]
    assert (
        complete_contextual_period("compare com o mês anterior", context)
        == "E compare entre 2025-12 e 2026-01."
    )


def test_new_incomplete_topic_does_not_recover_year_from_older_question():
    context = [
        ConversationTurn(role="user", content="Receita em 2026-06?"),
        ConversationTurn(role="user", content="Qual foi o consumo?"),
    ]
    assert complete_contextual_period("maio", context) == "maio"


def test_year_correction_preserves_the_single_month():
    context = [ConversationTurn(role="user", content="Receita em 2026-06?")]
    assert complete_contextual_period("corrigindo, 2025", context) == "E em 2025-06?"
