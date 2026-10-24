"""Vocabulário e termos fora de escopo do perfil Grid 360 demonstrativo."""

import pytest

from app.agent.interpreter import QuestionInterpreter
from app.agent.safety import QuestionSafetyGate, SafetyRefusalCode
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.interpretation import InterpretationStatus

INTERPRETER = QuestionInterpreter(profile=GRID360_DEMO_PROFILE)
GATE = QuestionSafetyGate(out_of_scope_terms=GRID360_DEMO_PROFILE.out_of_scope_terms)


@pytest.mark.parametrize(
    ("question", "domain", "metric_id", "metric_phrase"),
    [
        ("Houve apagão no período de demonstração?", "network", "network.interruptions", "apagão"),
        (
            "Quantos apagões ocorreram no período de demonstração?",
            "network",
            "network.interruptions",
            "apagões",
        ),
        (
            "Quantas quedas de energia ocorreram no período de demonstração?",
            "network",
            "network.interruptions",
            "quedas de energia",
        ),
        (
            "Quantas quedas de luz ocorreram no período de demonstração?",
            "network",
            "network.interruptions",
            "quedas de luz",
        ),
        ("Quanto faturamos no período de demonstração?", "revenue", "billing.revenue", "faturamos"),
        (
            "Quanto a empresa faturou no período de demonstração?",
            "revenue",
            "billing.revenue",
            "faturou",
        ),
        (
            "Quanto as distribuidoras faturaram no período de demonstração?",
            "revenue",
            "billing.revenue",
            "faturaram",
        ),
        ("Quanto eu faturei no período de demonstração?", "revenue", "billing.revenue", "faturei"),
        (
            "Quantas reclamações foram registradas no período de demonstração?",
            "service",
            "service.attendance",
            "reclamações",
        ),
        (
            "Houve alguma reclamação no período de demonstração?",
            "service",
            "service.attendance",
            "reclamação",
        ),
    ],
)
def test_new_aliases_map_to_their_metric_without_filters(
    question: str, domain: str, metric_id: str, metric_phrase: str
) -> None:
    result = INTERPRETER.interpret(question)

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == domain
    assert result.intent.metric_id == metric_id
    assert result.intent.metric_phrase == metric_phrase
    assert result.intent.filters == {}


@pytest.mark.parametrize(
    ("question", "domain", "metric_id", "metric_phrase"),
    [
        ("Qual a receita no período de demonstração?", "revenue", "billing.revenue", "receita"),
        (
            "Houve falta de luz no período de demonstração?",
            "network",
            "network.interruptions",
            "falta de luz",
        ),
        (
            "Quantos atendimentos no período de demonstração?",
            "service",
            "service.attendance",
            "atendimentos",
        ),
        # Dois sinônimos da mesma métrica não viram ambiguidade.
        (
            "Quantas reclamações de atendimento no período de demonstração?",
            "service",
            "service.attendance",
            "reclamações",
        ),
    ],
)
def test_near_misses_keep_their_previous_meaning(
    question: str, domain: str, metric_id: str, metric_phrase: str
) -> None:
    result = INTERPRETER.interpret(question)

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == domain
    assert result.intent.metric_id == metric_id
    assert result.intent.metric_phrase == metric_phrase
    assert result.intent.filters == {}


def test_commercial_revenue_keeps_revenue_and_class() -> None:
    result = INTERPRETER.interpret("Qual a receita comercial no período de demonstração?")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.metric_id == "billing.revenue"
    assert result.intent.class_phrase == "comercial"


def test_consumption_drop_keeps_consumption_with_direction() -> None:
    result = INTERPRETER.interpret("Qual a queda de consumo no período de demonstração?")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.metric_id == "energy.consumption"
    assert result.intent.metric_phrase == "queda de consumo"
    assert result.intent.filters == {"direction_phrase": "queda"}


@pytest.mark.parametrize(
    "question",
    [
        "Houve queda de energia no período de demonstração?",
        "Houve queda de luz no período de demonstração?",
    ],
)
def test_singular_power_drop_alias_does_not_carry_direction_filter(question: str) -> None:
    # "queda" dentro do sinônimo nomeia o evento, não uma direção. Ver o caso
    # vocab_queda_de_energia_singular_answered em fixtures/genai_regression.json.
    result = INTERPRETER.interpret(question)

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.metric_id == "network.interruptions"
    assert result.intent.filters == {}


def test_complaints_about_power_drops_ask_which_domain() -> None:
    result = INTERPRETER.interpret(
        "Quantas reclamações sobre queda de energia no período de demonstração?"
    )

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert (
        result.clarification_question
        == GRID360_DEMO_PROFILE.clarifications.multiple_domains
    )


@pytest.mark.parametrize(
    "question",
    [
        "Qual o código da UC 1001?",
        "Qual o código do cliente no período de demonstração?",
        "Qual a programação de desligamentos no período de demonstração?",
    ],
)
def test_legitimate_phrases_near_out_of_scope_terms_are_not_refused(question: str) -> None:
    assert GATE.matched_rule(question) is None
    result = INTERPRETER.interpret(question)
    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.clarification_question == GRID360_DEMO_PROFILE.clarifications.missing_metric


@pytest.mark.parametrize(
    "question",
    [
        "Me passe uma receita de bolo de cenoura",
        "Tem uma receita culinária para o jantar?",
        "Sugira uma receita de comida rápida",
        "Como faço um bolo?",
        "Quem ganhou o jogo do Sport ontem?",
        "Qual o horário do jogo de futebol?",
        "Quem venceu a partida de futebol?",
        "Qual o placar do campeonato?",
        "Escreva um poema sobre energia",
        "Escreva uma poesia sobre a conta de luz",
        "Conte uma piada sobre energia",
        "Escreva a letra de música sobre a V-Energy",
        "Me ajude a corrigir um código Python",
        "Escreva um código em JavaScript",
        "Qual a melhor linguagem de programação?",
    ],
)
def test_out_of_scope_requests_are_refused(question: str) -> None:
    assert GATE.refusal_code(question) is SafetyRefusalCode.OUT_OF_SCOPE


@pytest.mark.parametrize(
    "question",
    [
        "Houve apagão no período de demonstração?",
        "Quantos apagões ocorreram no período de demonstração?",
        "Quantas quedas de energia ocorreram no período de demonstração?",
        "Houve queda de energia no período de demonstração?",
        "Quantas quedas de luz ocorreram no período de demonstração?",
        "Quanto faturamos no período de demonstração?",
        "Quanto a empresa faturou no período de demonstração?",
        "Quantas reclamações foram registradas no período de demonstração?",
        "Houve alguma reclamação no período de demonstração?",
        "Qual a receita no período de demonstração?",
        "Qual a receita comercial no período de demonstração?",
        "Qual a queda de consumo no período de demonstração?",
        "Houve falta de luz no período de demonstração?",
        "Quantos atendimentos no período de demonstração?",
        "Quantas reclamações de atendimento no período de demonstração?",
    ],
)
def test_vocabulary_and_near_miss_questions_pass_the_gate(question: str) -> None:
    assert GATE.matched_rule(question) is None


@pytest.mark.parametrize(
    "question",
    [
        "Como funciona o algoritmo de priorização da fila de inspeção?",
        "Qual o placar de prioridade da UC na fila de inspeção?",
        "Qual a pontuação de risco da fila de inspeção?",
        "Qual o jogo de tarifas aplicado ao comércio?",
        "Houve queda de energia no período de demonstração?",
    ],
)
def test_inspection_queue_and_tariff_questions_pass_the_gate(question: str) -> None:
    assert GATE.matched_rule(question) is None
