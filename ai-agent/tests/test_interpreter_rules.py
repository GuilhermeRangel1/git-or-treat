"""Regras do interpretador para direção em sinônimos, unidades e locais sem preposição."""

import pytest

from app.agent.interpreter import QuestionInterpreter
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.interpretation import InterpretationStatus
from app.schemas.questions import ConversationTurn

INTERPRETER = QuestionInterpreter(profile=GRID360_DEMO_PROFILE)
UNKNOWN_GEOGRAPHY = GRID360_DEMO_PROFILE.clarifications.unknown_geography


def _ready(question: str):
    result = INTERPRETER.interpret(question)
    assert result.status is InterpretationStatus.READY, result.clarification_question
    assert result.intent is not None
    return result.intent


# Direção dentro de sinônimo de métrica


@pytest.mark.parametrize(
    ("question", "metric_phrase"),
    [
        ("Houve queda de energia no período de demonstração?", "queda de energia"),
        ("Houve queda de luz no período de demonstração?", "queda de luz"),
        ("Houve Queda de Energia no período de demonstração?", "Queda de Energia"),
        ("Quantas quedas de energia ocorreram no período de demonstração?", "quedas de energia"),
    ],
)
def test_direction_term_that_names_the_event_is_not_a_direction(
    question: str, metric_phrase: str
) -> None:
    intent = _ready(question)

    assert intent.metric_id == "network.interruptions"
    assert intent.metric_phrase == metric_phrase
    assert intent.filters == {}


def test_direction_that_qualifies_another_metric_alias_is_kept() -> None:
    # "queda de consumo" contém o sinônimo "consumo": a queda é direção do consumo.
    intent = _ready("Qual a queda de consumo no período de demonstração?")

    assert intent.metric_id == "energy.consumption"
    assert intent.metric_phrase == "queda de consumo"
    assert intent.filters == {"direction_phrase": "queda"}


@pytest.mark.parametrize(
    ("question", "metric_id", "direction"),
    [
        (
            "Houve aumento de queda de energia no período de demonstração?",
            "network.interruptions",
            "aumento",
        ),
        ("Houve redução de consumo no período de demonstração?", "energy.consumption", "redução"),
    ],
)
def test_direction_outside_the_metric_alias_is_kept(
    question: str, metric_id: str, direction: str
) -> None:
    intent = _ready(question)

    assert intent.metric_id == metric_id
    assert intent.filters == {"direction_phrase": direction}


def test_absorbing_aliases_are_derived_from_the_profile() -> None:
    metric = GRID360_DEMO_PROFILE.metrics[0]
    profile = GRID360_DEMO_PROFILE.model_copy(
        update={
            "metrics": (
                metric.model_copy(update={"aliases": (*metric.aliases, "aumento de receita")}),
                *GRID360_DEMO_PROFILE.metrics[1:],
            )
        }
    )

    result = QuestionInterpreter(profile=profile).interpret(
        "Qual o aumento de receita no período de demonstração?"
    )

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.filters == {"direction_phrase": "aumento"}


# Unidades de medida após "em"


@pytest.mark.parametrize(
    ("question", "metric_id"),
    [
        ("Qual foi o consumo em kWh no período de demonstração?", "energy.consumption"),
        ("Qual foi o consumo em KWH no período de demonstração?", "energy.consumption"),
        ("Qual o consumo em MWh no período de demonstração?", "energy.consumption"),
        ("Qual o consumo em quilowatt-hora no período de demonstração?", "energy.consumption"),
        ("Qual o faturamento em reais no período de demonstração?", "billing.revenue"),
        ("Qual o faturamento em R$ no período de demonstração?", "billing.revenue"),
    ],
)
def test_units_after_em_are_not_unknown_places(question: str, metric_id: str) -> None:
    intent = _ready(question)

    assert intent.metric_id == metric_id
    assert intent.geography_phrase is None
    assert intent.period_phrase == "período de demonstração"


def test_unit_and_known_place_keep_the_place_filter() -> None:
    intent = _ready("Qual o consumo em kWh em Olinda no período de demonstração?")

    assert intent.geography_phrase == "Olinda"
    assert intent.dimension_ids == ["geography.municipality"]


@pytest.mark.parametrize(
    "question",
    [
        # Duração e participação não são respondidas com contagem ou total.
        "Qual a duração das interrupções em horas no período de demonstração?",
        "Qual o consumo em porcentagem no período de demonstração?",
        "Qual foi o consumo em kWh em Recife no período de demonstração?",
        "Qual o consumo em março no período de demonstração?",
    ],
)
def test_unprotected_words_after_em_still_ask(question: str) -> None:
    result = INTERPRETER.interpret(question)

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.clarification_question == UNKNOWN_GEOGRAPHY


def test_correction_term_starting_with_na_is_not_a_place() -> None:
    intent = _ready(
        "Qual o consumo em Olinda, na verdade em Jaboatão, no período de demonstração?"
    )

    assert intent.geography_phrase == "Jaboatão"


# Nome próprio após "de"


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo de Recife no período de demonstração?",
        "Qual o consumo de Caruaru no período de demonstração?",
        "Qual o consumo de São Lourenço da Mata no período de demonstração?",
        "De Recife, qual o consumo no período de demonstração?",
        "Qual o consumo de Olinda e de Recife no período de demonstração?",
        "Interrupções de Recife no período de demonstração",
    ],
)
def test_unknown_proper_name_after_de_asks_for_the_place(question: str) -> None:
    result = INTERPRETER.interpret(question)

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert result.clarification_question == UNKNOWN_GEOGRAPHY


@pytest.mark.parametrize(
    ("question", "geography", "class_phrase"),
    [
        ("Qual o faturamento de Olinda no período de demonstração?", "Olinda", None),
        ("Qual o Faturamento de Olinda no período de demonstração?", "Olinda", None),
        (
            "Qual o consumo de Jaboatão dos Guararapes no período de demonstração?",
            "Jaboatão dos Guararapes",
            None,
        ),
        ("Qual o consumo de Residencial no período de demonstração?", None, "Residencial"),
        ("Qual o consumo de energia no período de demonstração?", None, None),
        ("Qual o consumo de Energia no período de demonstração?", None, None),
        ("Houve Falta de Luz no período de demonstração?", None, None),
        ("Qual o consumo de janeiro no período de demonstração?", None, None),
        ("Qual o consumo de 2025 no período de demonstração?", None, None),
        ("Qual o consumo de clientes residenciais no período de demonstração?", None, None),
        ("Qual o consumo de UCs no período de demonstração?", None, None),
        ("Qual o consumo da V-Energy no período de demonstração?", None, None),
        ("Qual o consumo do Recife no período de demonstração?", None, None),
    ],
)
def test_lowercase_acronyms_and_profile_words_after_de_are_not_places(
    question: str, geography: str | None, class_phrase: str | None
) -> None:
    # "de janeiro", "de 2025", "residenciais" e "do Recife" não são tratados aqui; ver as
    # limitações em docs/services/ai-agent.md.
    intent = _ready(question)

    assert intent.geography_phrase == geography
    assert intent.class_phrase == class_phrase


def test_capitalized_month_after_de_asks_instead_of_answering_the_whole_period() -> None:
    result = INTERPRETER.interpret("Qual o consumo de Janeiro no período de demonstração?")

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.clarification_question == UNKNOWN_GEOGRAPHY


def test_follow_up_with_unknown_proper_name_after_de_asks() -> None:
    result = INTERPRETER.interpret(
        "E de Recife?",
        [
            ConversationTurn(
                role="user", content="Qual o consumo em Olinda no período de demonstração?"
            )
        ],
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.clarification_question == UNKNOWN_GEOGRAPHY


# Quebra "por <dimensão>": ainda não representada


@pytest.mark.parametrize(
    "question",
    [
        "Interrupções por município no período de demonstração",
        "Falta de luz por município no período de demonstração",
        "Interrupções por cidade no período de demonstração",
        "Qual o consumo por classe no período de demonstração?",
    ],
)
def test_breakdown_by_dimension_is_not_yet_in_the_intent(question: str) -> None:
    # Lacuna registrada (proposta 41): sem campo de agrupamento em AnalysisIntent, a
    # quebra não pode ser representada pelo interpretador. Este teste deve mudar quando
    # o agrupamento existir.
    intent = _ready(question)

    assert intent.dimension_ids == []
    assert intent.filters == {}
