"""Responder ao esclarecimento não exige reescrever a pergunta."""

from app.agent.interpreter import QuestionInterpreter
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.domain_profile import DimensionValue
from app.schemas.questions import ConversationTurn


def test_short_dimension_answer_resolves_shared_name_without_changing_period_or_metric():
    dimensions = tuple(
        dimension.model_copy(
            update={"values": (DimensionValue(value="RECIFE", aliases=("Recife",)),)}
        )
        if dimension.id in {"geography.municipality", "geography.neighborhood"}
        else dimension
        for dimension in GRID360_GOLD_PROFILE.dimensions
    )
    interpreter = QuestionInterpreter(
        GRID360_GOLD_PROFILE.model_copy(update={"dimensions": dimensions})
    )
    original = "Quanto Recife faturou no último ano?"
    first = interpreter.interpret(original)
    assert first.intent is None
    response = interpreter.interpret(
        "município",
        [
            ConversationTurn(role="user", content=original),
            ConversationTurn(role="assistant", content=first.clarification_question),
        ],
    )
    assert response.intent is not None
    assert response.intent.metric_id == "billing.revenue"
    assert response.intent.filters == {"geography.municipality": "RECIFE"}
    assert response.intent.period_phrase == "último ano"
