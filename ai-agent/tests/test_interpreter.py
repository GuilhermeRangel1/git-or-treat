import pytest

from app.agent.interpreter import QuestionInterpreter
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.interpretation import InterpretationStatus
from app.schemas.questions import ConversationTurn


def test_interprets_business_synonyms_and_preserves_filter_phrases() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Quanto cresceu a receita comercial em Jaboatão entre o ano passado e este ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "revenue"
    assert result.intent.metric_phrase == "receita"
    assert result.intent.period_phrase == "ano passado e este ano"
    assert result.intent.geography_phrase == "Jaboatão"
    assert result.intent.class_phrase == "comercial"


def test_maps_everyday_power_outage_phrase_to_network_interruptions() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Houve falta de luz em Olinda no último ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "network"
    assert result.intent.metric_phrase == "falta de luz"
    assert result.intent.geography_phrase == "Olinda"


def test_plural_service_synonym_maps_to_attendance_domain() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Quantos atendimentos ocorreram no período de demonstração?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "service"
    assert result.intent.metric_phrase == "atendimentos"


def test_asks_what_account_of_light_means_instead_of_guessing() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Minha conta de luz subiu?"
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "consumo" in result.clarification_question
    assert "faturado" in result.clarification_question


def test_requests_a_period_when_a_quantitative_question_omits_it() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Compare a receita comercial em Jaboatão."
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "período" in result.clarification_question


def test_requests_a_comparison_baseline_instead_of_assuming_one() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Quanto cresceu a receita no último ano?"
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "comparação" in result.clarification_question


def test_correction_replaces_the_previous_geography_phrase() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Qual foi a receita em Olinda, não, em Jaboatão no último ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.geography_phrase == "Jaboatão"


def test_asks_when_multiple_geographies_are_not_marked_as_a_correction() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Compare a receita em Olinda e Jaboatão no último ano."
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "local" in result.clarification_question


def test_unknown_capitalized_location_is_not_silently_dropped() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Qual foi o consumo em Recife no último ano?"
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "local" in result.clarification_question


@pytest.mark.parametrize(
    ("question", "geography", "classification"),
    [
        ("Qual foi o consumo na classe residencial no último ano?", None, "residencial"),
        ("Qual foi o consumo no município de Olinda no último ano?", "Olinda", None),
    ],
)
def test_known_business_and_dimension_phrases_are_not_unknown_places(
    question: str, geography: str | None, classification: str | None
) -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(question)

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.geography_phrase == geography
    assert result.intent.class_phrase == classification


def test_preserves_direction_and_percentage_threshold_without_calculating_them() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Quais UCs tiveram queda de consumo acima de 30% em Olinda entre o ano passado e este ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.metric_phrase == "queda de consumo"
    assert result.intent.filters == {
        "direction_phrase": "queda",
        "threshold_phrase": "acima de 30%",
    }


def test_follow_up_inherits_intent_and_applies_explicit_geography_correction() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "E em Olinda, não, em Jaboatão?",
        [
            ConversationTurn(
                role="user",
                content="Qual foi o consumo no período de demonstração em Olinda?",
            ),
            ConversationTurn(role="assistant", content="A consulta não tem fixture local."),
        ],
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "consumption"
    assert result.intent.metric_phrase == "consumo"
    assert result.intent.period_phrase == "período de demonstração"
    assert result.intent.geography_phrase == "Jaboatão"


def test_follow_up_does_not_reuse_an_older_intent_after_ambiguous_latest_user_turn() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "E em Jaboatão?",
        [
            ConversationTurn(
                role="user",
                content="Qual foi o consumo no período de demonstração?",
            ),
            ConversationTurn(role="assistant", content="Resposta anterior."),
            ConversationTurn(role="user", content="Minha conta de luz subiu?"),
        ],
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None


def test_unrelated_question_does_not_inherit_previous_filters() -> None:
    result = QuestionInterpreter(profile=GRID360_DEMO_PROFILE).interpret(
        "Quais bairros tiveram maior variação?",
        [
            ConversationTurn(
                role="user",
                content="Qual foi o consumo no período de demonstração em Olinda?",
            )
        ],
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
