from app.agent.interpreter import QuestionInterpreter
from app.schemas.interpretation import InterpretationStatus


def test_interprets_business_synonyms_and_preserves_filter_phrases() -> None:
    result = QuestionInterpreter().interpret(
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
    result = QuestionInterpreter().interpret("Houve falta de luz em Olinda no último ano?")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "network"
    assert result.intent.metric_phrase == "falta de luz"
    assert result.intent.geography_phrase == "Olinda"


def test_plural_service_synonym_maps_to_attendance_domain() -> None:
    result = QuestionInterpreter().interpret(
        "Quantos atendimentos ocorreram no período de demonstração?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "service"
    assert result.intent.metric_phrase == "atendimentos"


def test_asks_what_account_of_light_means_instead_of_guessing() -> None:
    result = QuestionInterpreter().interpret("Minha conta de luz subiu?")

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "consumo" in result.clarification_question
    assert "faturado" in result.clarification_question


def test_requests_a_period_when_a_quantitative_question_omits_it() -> None:
    result = QuestionInterpreter().interpret("Compare a receita comercial em Jaboatão.")

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "período" in result.clarification_question


def test_requests_a_comparison_baseline_instead_of_assuming_one() -> None:
    result = QuestionInterpreter().interpret("Quanto cresceu a receita no último ano?")

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "comparação" in result.clarification_question


def test_correction_replaces_the_previous_geography_phrase() -> None:
    result = QuestionInterpreter().interpret(
        "Qual foi a receita em Olinda, não, em Jaboatão no último ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.geography_phrase == "Jaboatão"


def test_asks_when_multiple_geographies_are_not_marked_as_a_correction() -> None:
    result = QuestionInterpreter().interpret(
        "Compare a receita em Olinda e Jaboatão no último ano."
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "local" in result.clarification_question


def test_unknown_capitalized_location_is_not_silently_dropped() -> None:
    result = QuestionInterpreter().interpret(
        "Qual foi o consumo em Recife no último ano?"
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert "local" in result.clarification_question


def test_preserves_direction_and_percentage_threshold_without_calculating_them() -> None:
    result = QuestionInterpreter().interpret(
        "Quais UCs tiveram queda de consumo acima de 30% em Olinda entre o ano passado e este ano?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.metric_phrase == "queda de consumo"
    assert result.intent.filters == {
        "direction_phrase": "queda",
        "threshold_phrase": "acima de 30%",
    }
