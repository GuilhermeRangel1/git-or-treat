"""Contrastes da revisão de consistência pela borda HTTP, com catálogo artificial."""

import pytest

from app.agent.documentation import conceptual_question

from .test_gold_language_http import _plan


@pytest.mark.parametrize("exclusion", [
    "sem contar", "sem contar com", "sem contar os clientes de", "tirando",
    "retirando", "desconsiderando", "com exceção de", "desconsiderando as UCs de",
    "tirando a receita de",
])
def test_excluded_municipality_never_becomes_an_inclusion(exclusion):
    result = _plan(f"Qual foi a receita em março de 2025 {exclusion} Recife?")
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    assert "exclusão" in result["response"]["message"]


@pytest.mark.parametrize("connector", ["mudou em comparação com", "em relação a"])
def test_target_month_before_its_baseline_keeps_the_requested_change(connector):
    result = _plan(
        f"Qual foi o consumo de Recife em março de 2025 {connector} fevereiro de 2025?"
    )
    assert result["status"] == "planned", result
    assert result["plan"]["comparison_periods"] == ["2025-02", "2025-03"]
    assert result["plan"]["filters"][0]["values"] == ["Recife"]


def test_geographical_difference_groups_only_the_two_requested_locations():
    question = "Qual a diferença de faturamento entre Recife e Olinda em março de 2025?"
    assert not conceptual_question(question)
    result = _plan(question)
    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["group_by_dimension_ids"] == ["geography.municipality"]
    assert plan["filters"] == [{
        "dimension_id": "geography.municipality",
        "operator": "in",
        "values": ["Recife", "Olinda"],
    }]

@pytest.mark.parametrize("question", [
    "Como se calcula o DEC?", "Como é calculada a receita faturada?",
    "Qual a diferença entre faturamento e arrecadação?",
])
def test_supported_definition_questions_remain_conceptual(question):
    assert conceptual_question(question)


def test_colloquial_outage_question_offers_specific_indicators():
    result = _plan("Quantas vezes faltou luz no alimentador AL-01 em março de 2025?")
    assert result["status"] == "needs_clarification"
    message = result["response"]["message"]
    assert "DEC" in message and "FEC" in message and "alimentador" in message


def test_valid_negative_gd_category_is_still_an_authorized_filter():
    result = _plan("Qual a receita residencial em Olinda em março de 2025 sem GD?")
    assert result["status"] == "planned", result
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "generation.distributed": ["Não"],
        "geography.municipality": ["Olinda"],
    }
