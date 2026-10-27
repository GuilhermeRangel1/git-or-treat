"""Regras do interpretador para direção, unidades, detalhes, quebras e locais."""

import pytest
from pydantic import ValidationError

from app.agent.interpreter import QuestionInterpreter
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import (
    ClarificationMessages,
    DetailRule,
    DomainProfile,
    UnitDefinition,
    UnitKind,
)
from app.schemas.interpretation import InterpretationStatus
from app.schemas.questions import ConversationTurn

INTERPRETER = QuestionInterpreter(profile=GRID360_DEMO_PROFILE)
CLARIFICATIONS = GRID360_DEMO_PROFILE.clarifications
UNKNOWN_GEOGRAPHY = CLARIFICATIONS.unknown_geography
PERIOD_DETAIL = GRID360_DEMO_PROFILE.detail_rules[0].clarification
AVERAGE_DETAIL = GRID360_DEMO_PROFILE.detail_rules[1].clarification


def _asks(question: str, context: list[ConversationTurn] | None = None) -> str:
    result = INTERPRETER.interpret(question, context)
    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION, result.intent
    assert result.intent is None
    assert result.clarification_question is not None
    return result.clarification_question


def _profile_without_new_fields() -> DomainProfile:
    """Perfil como os anteriores a esta rodada, sem unidades, detalhes nem mensagens novas."""

    data = GRID360_DEMO_PROFILE.model_dump(mode="python")
    for name in ("units", "detail_rules"):
        data.pop(name)
    for metric in data["metrics"]:
        metric.pop("accepted_unit_kinds")
    for name in ("unsupported_breakdown", "unit_mismatch"):
        data["clarifications"].pop(name)
    return DomainProfile.model_validate(data)


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


def test_unknown_place_after_a_valid_unit_still_asks_for_the_place() -> None:
    question = "Qual foi o consumo em kWh em Recife no período de demonstração?"

    assert _asks(question) == UNKNOWN_GEOGRAPHY


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
        ("Qual o consumo de 2025 no período de demonstração?", None, None),
        ("Qual o consumo de clientes residenciais no período de demonstração?", None, None),
        ("Qual o consumo de UCs no período de demonstração?", None, None),
        ("Qual o consumo da V-Energy no período de demonstração?", None, None),
        ("Qual o consumo do SIN no período de demonstração?", None, None),
    ],
)
def test_lowercase_acronyms_and_profile_words_after_de_are_not_places(
    question: str, geography: str | None, class_phrase: str | None
) -> None:
    # "de 2025" e "residenciais" não são tratados aqui; ver as limitações em
    # docs/services/ai-agent.md. Meses ficam na seção de detalhes de período.
    intent = _ready(question)

    assert intent.geography_phrase == geography
    assert intent.class_phrase == class_phrase


def test_capitalized_month_after_de_asks_for_the_period_not_the_place() -> None:
    question = "Qual o consumo de Janeiro no período de demonstração?"

    assert _asks(question) == PERIOD_DETAIL


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


# Quebra "por <dimensão>": esclarecimento provisório até existir agrupamento no plano


@pytest.mark.parametrize(
    ("question", "label"),
    [
        ("Interrupções por município no período de demonstração", "município"),
        ("Falta de luz por município no período de demonstração", "município"),
        ("Interrupções por cidade no período de demonstração", "município"),
        ("Interrupções por cidades no período de demonstração", "município"),
        ("Qual o consumo por cada município no período de demonstração?", "município"),
        ("Qual o consumo por classe no período de demonstração?", "classe de consumo"),
        ("Qual o consumo por classe de consumo no último trimestre?", "classe de consumo"),
        ("Interrupções em Olinda por classe no período de demonstração", "classe de consumo"),
        ("Consumo por município", "município"),
    ],
)
def test_breakdown_by_profile_dimension_asks_instead_of_answering_the_total(
    question: str, label: str
) -> None:
    message = _asks(question)

    assert message == CLARIFICATIONS.unsupported_breakdown.replace("{dimension}", label)
    assert "total" in message and "em Olinda" in message


def test_breakdown_follow_up_also_asks() -> None:
    previous = [
        ConversationTurn(role="user", content="Qual o consumo no período de demonstração?")
    ]

    assert _asks("E por município?", previous).startswith("Ainda não separo o resultado")


@pytest.mark.parametrize(
    ("question", "geography", "class_phrase"),
    [
        ("Qual o consumo, por favor, no período de demonstração?", None, None),
        ("Qual o consumo por favor em Olinda no período de demonstração?", "Olinda", None),
        ("Houve falta de luz por causa da chuva no período de demonstração?", None, None),
        # Valor logo depois da dimensão é filtro, não quebra.
        ("Qual o consumo por classe residencial no período de demonstração?", None, "residencial"),
        (
            "Qual o consumo por município de Olinda no período de demonstração?",
            "Olinda",
            None,
        ),
    ],
)
def test_por_that_is_not_a_breakdown_is_not_affected(
    question: str, geography: str | None, class_phrase: str | None
) -> None:
    intent = _ready(question)

    assert intent.geography_phrase == geography
    assert intent.class_phrase == class_phrase


def test_por_que_keeps_the_comparison_rule() -> None:
    # "por que" não é quebra; "caiu" pede a base da comparação como antes.
    question = "Por que o consumo caiu no último trimestre?"

    assert _asks(question) == CLARIFICATIONS.comparison_baseline


def test_por_uc_with_identifier_is_not_a_breakdown() -> None:
    # "UC" não é dimensão do perfil; o filtro por UC continua fora do perfil demonstrativo.
    result = INTERPRETER.interpret("Qual o consumo por UC 123456 no período de demonstração?")

    assert result.clarification_question != CLARIFICATIONS.unsupported_breakdown


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo por mês no período de demonstração?",
        "Qual o consumo por ano no último ano?",
        "Qual o faturamento mês a mês no período de demonstração?",
    ],
)
def test_breakdown_by_period_granularity_asks_for_the_period(question: str) -> None:
    # Série por período não é dimensão do perfil: pede um período disponível.
    assert _asks(question) == PERIOD_DETAIL


def test_profile_without_breakdown_message_keeps_the_previous_behavior() -> None:
    interpreter = QuestionInterpreter(profile=_profile_without_new_fields())

    result = interpreter.interpret("Interrupções por município no período de demonstração")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.dimension_ids == []


# Locais com artigo, minúsculas e meses


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo no Recife no período de demonstração?",
        "Qual o consumo do Recife no período de demonstração?",
        "Qual o consumo da Região Metropolitana no período de demonstração?",
        "Qual o consumo na cidade de Recife no período de demonstração?",
        "Qual o consumo em recife no período de demonstração?",
        "Qual o consumo no recife no período de demonstração?",
        "Qual o consumo dos Prazeres no período de demonstração?",
    ],
)
def test_unknown_place_with_article_or_lowercase_asks_for_the_place(question: str) -> None:
    assert _asks(question) == UNKNOWN_GEOGRAPHY


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo na cidade de Olinda no período de demonstração?",
        "Qual o consumo em olinda no período de demonstração?",
        "Qual o consumo de olinda no período de demonstração?",
        "Qual o consumo do município de Olinda no período de demonstração?",
    ],
)
def test_known_place_with_article_or_lowercase_is_filtered(question: str) -> None:
    intent = _ready(question)

    assert intent.geography_phrase.casefold() == "olinda"
    assert intent.dimension_ids == ["geography.municipality"]


def test_lowercase_unknown_place_after_de_is_not_detectable() -> None:
    # Limite documentado: sem lista de locais, "de recife" em minúsculas parece "de energia".
    intent = _ready("Qual o consumo de recife no período de demonstração?")

    assert intent.geography_phrase is None


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo de Janeiro?",
        "Qual o consumo de janeiro no período de demonstração?",
        "Qual o consumo em março?",
        "Qual o consumo em Março no período de demonstração?",
        "Qual o consumo de março de 2026?",
        "Qual o faturamento no mês de Dezembro?",
        "Qual o consumo nos últimos seis meses?",
    ],
)
def test_month_is_a_period_detail_not_a_place(question: str) -> None:
    assert _asks(question) == PERIOD_DETAIL


def test_month_in_a_follow_up_is_a_period_detail() -> None:
    previous = [
        ConversationTurn(role="user", content="Qual o consumo no período de demonstração?")
    ]

    assert _asks("E em março?", previous) == PERIOD_DETAIL


def test_month_inside_a_catalog_period_phrase_is_accepted() -> None:
    # Perfis com meses no catálogo (como o do ensaio SQL) não disparam a regra.
    profile = GRID360_DEMO_PROFILE.model_copy(
        update={"period_phrases": (*GRID360_DEMO_PROFILE.period_phrases, "março de 2025")}
    )

    result = QuestionInterpreter(profile=profile).interpret("Qual o consumo em março de 2025?")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.period_phrase == "março de 2025"


# Unidade compatível com a métrica


@pytest.mark.parametrize(
    ("question", "unit"),
    [
        ("Qual o faturamento em kWh no período de demonstração?", "kWh"),
        ("Qual o consumo em R$ no período de demonstração?", "R$"),
        ("Qual o consumo em reais no período de demonstração?", "reais"),
        ("Quantas interrupções em kWh no período de demonstração?", "kWh"),
        ("Qual o consumo em kW no período de demonstração?", "kW"),
        ("Qual a duração das interrupções em horas no período de demonstração?", "horas"),
        ("Qual o consumo em porcentagem no período de demonstração?", "porcentagem"),
        ("Qual o faturamento em Olinda em kWh no período de demonstração?", "kWh"),
    ],
)
def test_unit_incompatible_with_the_metric_asks(question: str, unit: str) -> None:
    assert _asks(question) == CLARIFICATIONS.unit_mismatch.replace("{unit}", unit)


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo em kWh no período de demonstração?",
        "Qual o consumo em quilowatts-hora no período de demonstração?",
        "Qual o faturamento em R$ no período de demonstração?",
        "Quantas interrupções em quantidade no período de demonstração?",
        # Fora de "em <unidade>", a palavra não é tratada como unidade pedida.
        "Qual o consumo real no período de demonstração?",
    ],
)
def test_compatible_or_non_unit_words_are_answered(question: str) -> None:
    _ready(question)


def test_profile_without_units_does_not_check_unit_kinds() -> None:
    interpreter = QuestionInterpreter(profile=_profile_without_new_fields())

    result = interpreter.interpret("Qual o faturamento em kWh no período de demonstração?")

    # Sem unidades no perfil, "kWh" volta a ser palavra desconhecida após "em".
    assert result.clarification_question == UNKNOWN_GEOGRAPHY


def test_interpreter_reads_units_only_from_the_profile() -> None:
    import app.agent.interpreter as module

    assert not hasattr(module, "_UNIT_PHRASES")
    profile = GRID360_DEMO_PROFILE.model_copy(
        update={
            "units": (
                *GRID360_DEMO_PROFILE.units,
                UnitDefinition(id="energy.tep", kind=UnitKind.ENERGY, aliases=("tep",)),
            )
        }
    )

    result = QuestionInterpreter(profile=profile).interpret(
        "Qual o consumo em tep no período de demonstração?"
    )

    assert result.status is InterpretationStatus.READY


# Detalhe de estatística


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo em média no período de demonstração?",
        "Qual o consumo médio no período de demonstração?",
        "Qual a média de interrupções no último trimestre?",
    ],
)
def test_average_asks_for_the_statistic_not_the_place(question: str) -> None:
    assert _asks(question) == AVERAGE_DETAIL


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo no total no período de demonstração?",
        "Qual o total de interrupções no período de demonstração?",
        "Quantos chamados ao todo no período de demonstração?",
    ],
)
def test_total_is_already_answered(question: str) -> None:
    _ready(question)


# Schema do perfil


def test_profile_without_new_fields_is_still_valid() -> None:
    profile = _profile_without_new_fields()

    assert profile.units == ()
    assert profile.detail_rules == ()
    assert profile.clarifications.unsupported_breakdown is None
    assert all(metric.accepted_unit_kinds == () for metric in profile.metrics)


def test_clarification_messages_keep_old_required_fields_only() -> None:
    data = GRID360_DEMO_PROFILE.clarifications.model_dump()
    data.pop("unsupported_breakdown")
    data.pop("unit_mismatch")

    assert ClarificationMessages.model_validate(data).unit_mismatch is None


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (
            {"units": (UnitDefinition(id="x.a", kind=UnitKind.COUNT, aliases=("consumo",)),)},
            "alias de unidade conflita",
        ),
        (
            {
                "units": (
                    UnitDefinition(id="x.a", kind=UnitKind.COUNT, aliases=("kwh",)),
                    UnitDefinition(id="x.b", kind=UnitKind.ENERGY, aliases=("KWh",)),
                )
            },
            "alias de unidade ambíguo",
        ),
        (
            {"detail_rules": (DetailRule(phrases=("total",)), DetailRule(phrases=("Total",)))},
            "frase de detalhe duplicada",
        ),
    ],
)
def test_profile_rejects_conflicting_units_and_details(update: dict, message: str) -> None:
    data = {**GRID360_DEMO_PROFILE.model_dump(mode="python"), **update}

    with pytest.raises(ValidationError, match=message):
        DomainProfile.model_validate(data)
