"""Referencia de entidade exige um filtro anterior reconhecido."""
from app.agent.interpreter import QuestionInterpreter
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE as PROFILE
from app.schemas.domain_profile import DimensionValue
from app.schemas.questions import ConversationTurn


def test_selected_municipality_and_month_survive_metric_change():
    profile = PROFILE.model_copy(update={
        "period_phrases": (*PROFILE.period_phrases, "2026-06"),
        "dimensions": tuple(d.model_copy(update={"values": (DimensionValue(
            value="Recife", aliases=("Recife",)),)})
            if d.id == "geography.municipality" else d for d in PROFILE.dimensions),
    })
    interpreter = QuestionInterpreter(profile)
    question = "E o consumo medido nesse munic\u00edpio no mesmo m\u00eas?"
    result = interpreter.interpret(question, [ConversationTurn(
        role="user", content="Receita no munic\u00edpio Recife em 2026-06?",
    )])
    assert result.status == "ready", result.model_dump_json()
    assert result.intent.metric_id == "energy.consumption"
    assert result.intent.filters["geography.municipality"] == "Recife"
    assert result.intent.period_phrase == "2026-06"
    assert not result.intent.group_by_dimension_ids
    assert interpreter.interpret(question).status == "needs_clarification"
