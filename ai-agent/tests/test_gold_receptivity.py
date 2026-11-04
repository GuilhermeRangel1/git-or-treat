"""Paráfrases e contrastes pela borda pública de planejamento, sem modelo ou fonte remota."""

import pytest

from .test_gold_language_http import _plan


@pytest.mark.parametrize("question,metric,place,kind", [
    ("Quero saber quanto foi faturado em Recife em março de 2025.",
     "billing.revenue", "Recife", None),
    ("Me diz, em Recife, qual foi o valor faturado em mar/2025?",
     "billing.revenue", "Recife", None),
    ("Quanto foi faturado no mês 03 de 2025 em Recife?", "billing.revenue", "Recife", None),
    ("Por favor, em março de 2025, quanto faturamos em Recife?",
     "billing.revenue", "Recife", None),
    ("Quanto de energia foi consumida em Olinda em março de 2025?",
     "energy.consumption", "Olinda", None),
    ("Em março de 2025, quanto os clientes residenciais de Olinda consumiram?",
     "energy.consumption", "Olinda", "RESIDENCIAL"),
    ("Olinda: quanto consumimos em MAR. de 2025?", "energy.consumption", "Olinda", None),
    ("Quanto os clientes comerciais consumiram em Recife em março de 2025?",
     "energy.consumption", "Recife", "COMERCIAL"),
])
def test_natural_variants_preserve_the_complete_slice(question, metric, place, kind):
    result = _plan(question)
    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == metric
    assert plan["unit"] == ("R$" if metric == "billing.revenue" else "kWh")
    assert plan["window"]["start"] == "2025-03-01"
    assert plan["window"]["end"] == "2025-03-31"
    expected = {"geography.municipality": [place]}
    if kind:
        expected["customer.consumption_class"] = [kind]
    assert {f["dimension_id"]: f["values"] for f in plan["filters"]} == expected
    assert all(f["operator"] == "eq" for f in plan["filters"])
    assert plan["group_by_dimension_ids"] == []
    assert plan.get("comparison_periods") is None
    assert plan["order"] is None


@pytest.mark.parametrize("question,limit,direction", [
    ("Quais cidades tiveram mais receita em março de 2025?", 100, "desc"),
    ("Quero os três municípios que mais faturaram em março de 2025.", 3, "desc"),
    ("Top 5 cidades por receita em março de 2025", 5, "desc"),
    ("Quais os municípios com menor faturamento em março de 2025?", 100, "asc"),
    ("As duas cidades com menos receita em março de 2025", 2, "asc"),
    ("Qual município teve a maior receita em março de 2025?", 1, "desc"),
    ("Os trinta e dois municípios com mais receita em março de 2025?", 32, "desc"),
])
def test_ranking_preserves_group_order_and_requested_count(question, limit, direction):
    result = _plan(question)
    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["filters"] == []
    assert plan["group_by_dimension_ids"] == ["geography.municipality"]
    assert plan["order"] == {"field_id": "billing.revenue", "direction": direction}
    assert plan["limit"] == limit
    assert plan["window"]["start"] == "2025-03-01"


@pytest.mark.parametrize("question", [
    "Quanto foi faturado em Reciffe em março de 2025?",
    "Quero os 101 municípios que mais faturaram em março de 2025.",
    "Quero os 0 municípios que mais faturaram em março de 2025.",
    "Os cento e um municípios com mais receita em março de 2025?",
    "Qual município inventado teve maior receita em março de 2025?",
    "Quanto de energia foi consumida exceto residencial em março de 2025?",
    "Quanto foi faturado e pago em Recife em março de 2025?",
    "Quanto foi faturado em Recife no mês 13 de 2025?",
    "Quanto foi faturado em Recife em 12 de março de 2025?",
    "Quais cidades tiveram mais receita e consumo em março de 2025?",
])
def test_receptivity_does_not_discard_unknown_conflicting_or_unsupported_parts(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


def test_ranked_follow_up_keeps_count_and_class_but_changes_city_scope_only_explicitly():
    first = "Quero os três municípios com mais receita residencial em março de 2025."
    result = _plan("Só comercial.", [{"role": "user", "content": first}])
    assert result["status"] == "planned", result
    assert result["plan"]["limit"] == 3
    assert result["plan"]["group_by_dimension_ids"] == ["geography.municipality"]
    assert result["plan"]["filters"] == [{
        "dimension_id": "customer.consumption_class", "operator": "eq", "values": ["COMERCIAL"],
    }]


@pytest.mark.parametrize("answer", ["2025", "faturado, 2025"])
def test_short_year_answer_preserves_the_two_months_and_location(answer):
    first = "A receita em Recife caiu de janeiro para março?"
    result = _plan(answer, [
        {"role": "user", "content": first},
        {"role": "assistant", "content": "Qual ano você quer comparar?"},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]
    assert result["plan"]["filters"] == [{
        "dimension_id": "geography.municipality", "operator": "eq", "values": ["Recife"],
    }]


def test_business_choice_and_year_can_be_answered_together():
    result = _plan("faturado, 2025", [
        {"role": "user", "content": "A grana que entrou em Recife caiu de janeiro para março?"},
        {"role": "assistant", "content": "Você quer faturado ou recebido, e de qual ano?"},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]
    assert result["plan"]["filters"][0]["values"] == ["Recife"]


def test_confirmation_asks_only_the_missing_year_and_preserves_the_comparison():
    first = _plan("A grana que entrou em Recife caiu de janeiro para março?")
    second = _plan("Sim", [
        {"role": "user", "content": first["pending_question"]},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert second["status"] == "needs_clarification"
    assert second["response"]["message"].startswith(
        "De qual ano você quer comparar janeiro e março?"
    )
    assert "Exemplo de pergunta" not in second["response"]["message"]
    result = _plan("2025", [
        {"role": "user", "content": second["pending_question"]},
        {"role": "assistant", "content": second["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]
    assert result["plan"]["filters"] == [{
        "dimension_id": "geography.municipality", "operator": "eq", "values": ["Recife"],
    }]


def test_missing_period_follow_up_does_not_depend_on_assistant_message_wording():
    result = _plan("março de 2025", [
        {"role": "user", "content": "Qual o consumo residencial em Recife?"},
        {"role": "assistant", "content": "Para qual competência?"},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Recife"], "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_polite_new_question_discards_previous_unresolved_business_intent():
    result = _plan("Me mostra o consumo em Olinda em março de 2025.", [
        {"role": "user", "content": "Receita paga em Recife em janeiro de 2025?"},
        {"role": "assistant", "content": "Você quer receita faturada?"},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["filters"][0]["values"] == ["Olinda"]


def test_typo_is_only_suggested_and_confirmed_by_a_new_plan():
    result = _plan("Quanto foi faturado em Reciffe em março de 2025?")
    assert result["status"] == "needs_clarification", result
    message = result["response"]["message"]
    example = message.split("\n\nExemplo de pergunta: “")[1].removesuffix("”")
    assert "Recife" in example and "Reciffe" not in example
    accepted = _plan(example)
    assert accepted["plan"]["filters"][0]["values"] == ["Recife"]


NEIGHBORHOODS = [
    {"dimension_id": "geography.municipality", "values": ["Recife", "Olinda"]},
    {"dimension_id": "geography.neighborhood", "values": ["BAIRO", "LUMENIA"]},
]


def test_dimension_name_is_not_suggested_as_a_similar_neighborhood():
    result = _plan(
        "Qual bairro de Recife teve a maior queda de consumo entre fevereiro e março de 2025?",
        dimension_values=NEIGHBORHOODS,
    )
    assert result["status"] == "needs_clarification", result
    assert "BAIRO" not in result["response"]["message"]


def test_typo_beside_a_dimension_name_is_still_suggested():
    result = _plan(
        "Qual foi a receita faturada no bairro LUMENIA em Reciffe em março de 2025?",
        dimension_values=NEIGHBORHOODS,
    )
    assert result["status"] == "needs_clarification", result
    example = result["response"]["message"].split("\n\nExemplo de pergunta: “")[1]
    assert example.removesuffix("”") == (
        "Qual foi a receita faturada no bairro LUMENIA em Recife em março de 2025?"
    )


@pytest.mark.parametrize("question,limit", [
    ("Quais classes tiveram mais receita em março de 2025?", 100),
    ("Top 3 classes com maior receita faturada em 2025-03?", 3),
])
def test_plural_class_ranking_never_becomes_an_ungrouped_total(question, limit):
    result = _plan(question)
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["group_by_dimension_ids"] == ["customer.consumption_class"]
    assert result["plan"]["limit"] == limit
    assert result["plan"]["order"]["direction"] == "desc"


def test_received_calls_are_not_mistaken_for_collected_revenue():
    result = _plan("Quantos chamados recebemos em março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "service.attendance"


@pytest.mark.parametrize("ids", [("missing.metric",), ("billing.revenue", "billing.revenue")])
def test_clarification_alternatives_must_be_unique_catalog_metrics(ids):
    from pydantic import ValidationError

    from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
    from app.schemas.domain_profile import DomainProfile

    data = GRID360_GOLD_PROFILE.model_dump()
    data["ambiguities"][1]["alternative_metric_ids"] = ids
    with pytest.raises(ValidationError):
        DomainProfile.model_validate(data)


@pytest.mark.parametrize("question", [
    "O que significa DEC?", "Qual a diferença entre DEC e FEC?",
    "Como é calculado o consumo médio por UC?",
])
def test_definition_requests_point_to_approved_help_instead_of_asking_for_a_month(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification"
    assert "Entenda os indicadores" in result["response"]["message"]
    assert result.get("plan") is None


@pytest.mark.parametrize("answer,metric", [
    ("o primeiro", "billing.revenue"), ("o segundo", "energy.consumption"),
    ("consumo medido", "energy.consumption"),
])
def test_indicator_choice_uses_displayed_order_and_keeps_shared_filters(answer, metric):
    question = "Qual a receita e o consumo residencial em Recife em março de 2025?"
    first = _plan(question)
    assert first["status"] == "needs_clarification"
    message = first["response"]["message"]
    assert "1) Receita faturada" in message and "2) Consumo medido" in message
    follow = _plan(answer, [
        {"role": "user", "content": question}, {"role": "assistant", "content": message},
    ])
    assert follow["status"] == "planned", follow
    assert follow["plan"]["metric_id"] == metric
    assert follow["plan"]["window"]["start"] == "2025-03-01"
    assert {f["dimension_id"]: f["values"] for f in follow["plan"]["filters"]} == {
        "geography.municipality": ["Recife"], "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_an_ordinal_without_a_previous_choice_cannot_create_a_query():
    assert _plan("o segundo")["status"] == "needs_clarification"


def test_confirmation_only_accepts_one_explicit_catalog_alternative():
    question = "Qual a receita paga em Recife em março de 2025?"
    first = _plan(question)
    result = _plan("sim", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["filters"][0]["values"] == ["Recife"]


def test_confirmation_without_unique_alternative_remains_a_clarification():
    result = _plan("sim", [
        {"role": "user", "content": "Conta de luz em Recife em março de 2025?"},
        {"role": "assistant", "content": "Você quer valor faturado ou consumo?"},
    ])
    assert result["status"] == "needs_clarification"
    assert result.get("plan") is None


def test_reworded_coverage_clarification_keeps_the_typed_pending_period():
    first = "Qual a receita residencial em Recife no último ano?"
    result = _plan("fevereiro de 2025", [
        {"role": "user", "content": first},
        {"role": "assistant", "content": "Esta janela não está disponível. Escolha outro mês."},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-02-01"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Recife"], "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_confirmation_of_gd_is_explicit_and_preserves_the_original_query():
    question = "Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%?"
    extra = [{"metric_id": "energy.gd_consumption_drop", "kind": "none"}]
    first = _plan(question, extra_coverage=extra)
    result = _plan("sim", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": first["response"]["message"]},
    ], extra_coverage=extra)
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.gd_consumption_drop"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Olinda"], "generation.distributed": ["Sim"],
    }


def test_two_rankings_are_not_silently_reduced_to_the_last_direction():
    question = "Quais cidades tiveram mais receita em março de 2025 e quais tiveram menos?"
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    assert "maiores" in result["response"]["message"]
    follow = _plan("maiores", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": result["response"]["message"]},
    ])
    assert follow["status"] == "planned", follow
    assert follow["plan"]["group_by_dimension_ids"] == ["geography.municipality"]
    assert follow["plan"]["order"]["direction"] == "desc"


def test_multiple_clarifications_keep_a_compact_pending_question():
    question = "A grana que entrou em Recife caiu de janeiro para março?"
    first = _plan(question)
    assert first["pending_question"] == question
    second = _plan("faturado", [
        {"role": "user", "content": first["pending_question"]},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert second["status"] == "needs_clarification", second
    assert "Recife" in second["pending_question"]
    result = _plan("2025", [
        {"role": "user", "content": second["pending_question"]},
        {"role": "assistant", "content": second["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]
    assert result["plan"]["filters"][0]["values"] == ["Recife"]


def test_an_unclear_choice_preserves_the_options_instead_of_losing_the_slice():
    question = "Qual a receita e o consumo residencial em Recife em março de 2025?"
    first = _plan(question)
    second = _plan("talvez", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert second["status"] == "needs_clarification"
    assert "1) Receita faturada" in second["response"]["message"]
    assert second["pending_question"] == question


@pytest.mark.parametrize("question", [
    "Receita em um município inventado em março de 2025?",
    "Consumo em Recife e Atlantis em março de 2025?",
    "Receita acima de R$ 100 em março de 2025?",
])
def test_an_example_never_replaces_an_unresolved_filter_with_a_total(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert "Exemplo de pergunta" not in result["response"]["message"]
    assert result.get("plan") is None


def test_pending_follow_up_preserves_the_previous_executed_slice():
    original = "Receita faturada em Recife em março de 2025?"
    pending = _plan("E quanto recebemos?", [
        {"role": "user", "content": original},
        {"role": "assistant", "content": "Resultado consultado."},
    ])
    assert pending["status"] == "needs_clarification", pending
    assert "Recife" in pending["pending_question"]
    result = _plan("receita faturada", [
        {"role": "user", "content": pending["pending_question"]},
        {"role": "assistant", "content": pending["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["filters"][0]["values"] == ["Recife"]


def test_repeated_coverage_clarifications_preserve_class_and_municipality():
    first = _plan("Qual a receita residencial em Recife no último ano?")
    assert first["pending_question"]
    second = _plan("E em abril de 2025?", [
        {"role": "user", "content": first["pending_question"]},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert second["pending_question"]
    result = _plan("março de 2025", [
        {"role": "user", "content": second["pending_question"]},
        {"role": "assistant", "content": second["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"], "geography.municipality": ["Recife"],
    }


@pytest.mark.parametrize("answer", ["sim", "com GD"])
def test_ambiguous_follow_up_applies_the_known_municipality_override(answer):
    pending = _plan("E em Olinda com solar?", [
        {"role": "user", "content": "Receita faturada em Recife em março de 2025?"},
        {"role": "assistant", "content": "Resultado de março consultado."},
    ])
    assert pending["status"] == "needs_clarification"
    assert "Recife" not in pending["pending_question"]
    result = _plan(answer, [
        {"role": "user", "content": pending["pending_question"]},
        {"role": "assistant", "content": pending["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {f["dimension_id"]: f["values"] for f in result["plan"]["filters"]} == {
        "geography.municipality": ["Olinda"], "generation.distributed": ["Sim"],
    }


def test_grouped_comparison_draft_never_invents_a_top_limit():
    pending = _plan(
        "Qual bairro mais perdeu volume residencial entre janeiro de 2025 e abril de 2025?"
    )
    assert pending["status"] == "needs_clarification"
    assert "Top" not in pending["pending_question"]
    assert "entre e entre" not in pending["response"]["message"]
    result = _plan("Compare janeiro de 2025 e março de 2025", [
        {"role": "user", "content": pending["pending_question"]},
        {"role": "assistant", "content": pending["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert result["plan"]["limit"] == 100
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]


def test_backend_grouped_comparison_anchor_preserves_the_next_period_change():
    anchor = "Compare Qual bairro teve menor consumo medido entre 2025-01 e 2025-02?"
    result = _plan("Compare fevereiro de 2025 e março de 2025", [
        {"role": "user", "content": anchor},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert result["plan"]["order"] == {"field_id": "energy.consumption", "direction": "asc"}
    assert result["plan"]["comparison_periods"] == ["2025-02", "2025-03"]
    assert result["plan"]["limit"] == 100
