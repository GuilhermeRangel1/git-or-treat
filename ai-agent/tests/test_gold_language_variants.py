"""Paráfrases por domínio e proteção contra perda silenciosa de recorte."""

import pytest

from .test_gold_language_http import _plan

SHARED_NAMES = [
    {"dimension_id": "geography.municipality", "values": ["Recife", "Olinda"]},
    {"dimension_id": "geography.neighborhood", "values": ["Recife", "Casa Caiada"]},
]


@pytest.mark.parametrize("question", [
    "Quanto Recife faturou em março de 2025?",
    "Compare a receita de Recife entre janeiro e março de 2025.",
    "Qual o consumo de Recife em março de 2025?",
    "Qual a receita do município de Recife em março de 2025?",
])
def test_municipality_qualifier_or_explicit_disambiguation_keeps_slice(question):
    result = _plan(question, dimension_values=SHARED_NAMES)
    if question.startswith("Quanto Recife"):
        assert result["status"] == "needs_clarification"
        message = result["response"]["message"]
        assert "Município" in message and "Bairro" in message
        result = _plan("município", [
            {"role": "user", "content": question},
            {"role": "assistant", "content": message},
        ], dimension_values=SHARED_NAMES)
    assert result["status"] == "planned", result
    assert result["plan"]["filters"] == [{
        "dimension_id": "geography.municipality", "operator": "eq", "values": ["Recife"],
    }]


@pytest.mark.parametrize("question,dimension", [
    ("Qual a receita do bairro Recife em março de 2025?", "geography.neighborhood"),
    ("Receita no município Recife em março de 2025?", "geography.municipality"),
])
def test_explicit_dimension_wins_over_municipality_default(question, dimension):
    result = _plan(question, dimension_values=SHARED_NAMES)
    assert result["status"] == "planned", result
    assert result["plan"]["filters"] == [{
        "dimension_id": dimension, "operator": "eq", "values": ["Recife"],
    }]


@pytest.mark.parametrize("notation", ["mar/25", "03/25", "3/25", "MAR./25", "março/25"])
def test_short_year_uses_only_unambiguous_published_century(notation):
    result = _plan(f"Qual foi o consumo residencial de Recife em {notation}?",
                   dimension_values=SHARED_NAMES)
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["window"]["end"] == "2025-03-31"


@pytest.mark.parametrize("question,metric", [
    ("Quanto foi o consumo em Olinda em março de 2025?", "energy.consumption"),
    ("Me diga o consumo de Olinda em março de 2025.", "energy.consumption"),
    ("Quanto Olinda faturou em março de 2025?", "billing.revenue"),
    ("Qual foi o faturamento de Olinda em março de 2025?", "billing.revenue"),
    ("Qual o DEC do alimentador AL-01 em março de 2025?",
     "network.equivalent_interruption_duration"),
    ("Qual foi o FEC do alimentador AL-01 em março de 2025?",
     "network.equivalent_interruption_frequency"),
    ("Quantos chamados de atendimento em março de 2025?", "service.attendance"),
    ("Qual a satisfação média em março de 2025?", "service.satisfaction"),
    ("Quantos atendimentos no histórico acumulado?", "service.accumulated_attendance"),
])
def test_domain_paraphrases_keep_metric_and_period(question, metric):
    result = _plan(question, extra_coverage=[
        {"metric_id": "service.accumulated_attendance", "kind": "none"},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == metric


@pytest.mark.parametrize("reply", ["E no mês anterior?", "E no mês passado?", "no mês anterior"])
@pytest.mark.parametrize("period", ["março de 2025", "mar/25"])
def test_previous_month_reply_keeps_all_filters(reply, period):
    context = [
        {"role": "user", "content": f"Receita residencial em Olinda em {period}?"},
        {"role": "assistant", "content": "Resposta fundamentada do mês."},
    ]
    result = _plan(reply, context)
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-02-01"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Olinda"], "customer.consumption_class": ["RESIDENCIAL"],
    }


@pytest.mark.parametrize("direction,expected", [("menor", "asc"), ("maior", "desc")])
@pytest.mark.parametrize("dimension", ["município", "bairro", "classe"])
def test_rankings_never_turn_into_a_total(direction, expected, dimension):
    result = _plan(f"Qual {dimension} teve a {direction} receita faturada em março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == [{
        "município": "geography.municipality", "bairro": "geography.neighborhood",
        "classe": "customer.consumption_class",
    }[dimension]]
    assert result["plan"]["order"]["direction"] == expected
    assert result["plan"]["limit"] == 1


def test_quais_article_cardinal_ranking_preserves_dimension_direction_and_limit():
    result = _plan("Quais os três bairros com maior receita em março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert result["plan"]["order"]["direction"] == "desc"
    assert result["plan"]["limit"] == 3


@pytest.mark.parametrize("phrase", ["1º trimestre", "primeiro trimestre", "1 trimestre"])
def test_calendar_quarter_preserves_complete_months_and_filters(phrase):
    result = _plan(f"Qual foi o consumo residencial em Olinda no {phrase} de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-01-01"
    assert result["plan"]["window"]["end"] == "2025-03-31"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Olinda"], "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_comparando_with_shared_year_keeps_two_periods_and_city():
    result = _plan("Qual a receita em Olinda comparando janeiro com março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["comparison_periods"] is not None
    assert result["plan"]["filters"] == [{
        "dimension_id": "geography.municipality", "operator": "eq", "values": ["Olinda"],
    }]
