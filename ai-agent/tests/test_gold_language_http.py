"""Variações de linguagem na borda HTTP Gold; sem modelo remoto ou dados privados."""

import pytest

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_planning_http import HEADERS, PLAN_PATH, SYNTHESIS_PATH, _application
from .test_gold_question_filters import _setup


def _plan(question, context=(), *, dimension_values=None, extra_coverage=(), competencies=None):
    core, request = _setup(question)
    payload = request.model_dump(mode="json")
    payload["context"] = list(context)
    payload["temporal_coverage"].extend(extra_coverage)
    if competencies is not None:
        for coverage in payload["temporal_coverage"]:
            if coverage["kind"] == "monthly":
                coverage["competencies"] = list(competencies)
    if dimension_values is not None:
        payload["dimension_value_coverage"] = dimension_values
    with InProcessClient(_application(core)) as client:
        response = client.post(PLAN_PATH, json=payload, headers=HEADERS)
    assert response.status_code == 200
    return response.json()


UNKNOWN_GEOGRAPHY = "Não reconheci esse local nas referências disponíveis"


@pytest.mark.parametrize("question", [
    "Qual foi a receita faturada em Recife em jun/26?",
    "Qual foi a receita faturada em Recife em 2026?",
    "Qual foi o ticket médio da classe comercial em Olinda e como ele variou "
    "em relação a maio de 2026?",
])
def test_unrecognized_period_is_not_reported_as_unknown_location(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    message = result["response"]["message"]
    assert UNKNOWN_GEOGRAPHY not in message
    assert "período" in message or "mensal" in message


@pytest.mark.parametrize("month", ["maio de 2026", "março de 2025"])
def test_variation_against_a_single_period_asks_for_the_comparison_baseline(month):
    result = _plan(
        "Qual foi o ticket médio da classe comercial em Olinda e como ele variou "
        f"em relação a {month}?"
    )
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"]
    assert UNKNOWN_GEOGRAPHY not in message
    assert message.startswith(GRID360_GOLD_PROFILE.clarifications.comparison_baseline)


def test_variation_between_two_explicit_months_still_plans_the_comparison():
    result = _plan(
        "Como a receita em Olinda variou entre fevereiro e março de 2025?"
    )
    assert result["status"] == "planned", result
    assert result["plan"]["comparison_periods"] == ["2025-02", "2025-03"]


def test_measured_consumption_neighborhood_ranking_does_not_treat_metric_as_location():
    result = _plan(
        "Qual bairro de Lumenia teve a maior queda no consumo medido residencial entre "
        "janeiro de 2001 e abril de 2001?",
        dimension_values=[
            {"dimension_id": "geography.municipality", "values": ["Lumenia"]},
            {"dimension_id": "geography.neighborhood", "values": ["Quadra A", "Quadra B"]},
            {"dimension_id": "customer.consumption_class", "values": ["RESIDENCIAL"]},
        ],
        competencies=["2001-01", "2001-04"],
    )

    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert result["plan"]["comparison_periods"] == ["2001-01", "2001-04"]


@pytest.mark.parametrize("question,expected", [
    ("Qual foi a receita faturada em Recife em jun/26?",
     "Qual foi a receita faturada em Recife em março de 2025?"),
    ("Qual foi a receita faturada em Recife em 2026?",
     "Qual foi a receita faturada em Recife em março de 2025?"),
    ("Qual foi a energia faturada de clientes residenciais com GD em Recife em março de 2025?",
     "Qual foi o consumo de clientes residenciais com GD em Recife em março de 2025?"),
    # A troca ao lado de "versus" deixaria a comparação pela metade: sem exemplo.
    ("Qual a receita faturada versus paga em Olinda em março de 2025?", None),
    ("Qual foi a receita faturada em Recife?",
     "Qual foi a receita faturada em Recife em março de 2025?"),
])
def test_clarification_example_is_fluent_or_absent(question, expected):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    parts = result["response"]["message"].split("\n\nExemplo de pergunta: “", 1)
    example = parts[1].removesuffix("”") if len(parts) == 2 else None
    assert example == expected
    if example is not None:
        assert "  " not in example and example.endswith("?")
        assert _plan(example)["status"] == "planned"


MUNICIPALITIES = [{
    "dimension_id": "geography.municipality",
    "values": ["Recife", "Olinda", "Jaboatão dos Guararapes"],
}]
ONE_AT_A_TIME = (
    "Consulto um valor de município por vez; você citou Recife, Olinda e "
    "Jaboatão dos Guararapes. Qual quer primeiro?"
)
BOTH_BOUNDS = "Informe o mês e o ano de ambos os extremos do intervalo"


@pytest.mark.parametrize("question,expected", [
    # "entre" introduz uma lista de locais, não um intervalo de meses incompleto.
    ("Em março de 2025, qual município entre Recife, Olinda e Jaboatão dos Guararapes "
     "teve a maior receita faturada?", ONE_AT_A_TIME),
    ("Qual foi a receita faturada em março de 2025 em Recife, em Olinda e em "
     "Jaboatão dos Guararapes?", ONE_AT_A_TIME),
    # A lista de locais não vira intervalo nem some ao lado de um agrupamento.
    ("Mostre a receita por classe entre Recife, Olinda e Jaboatão dos Guararapes "
     "em março de 2025.", ONE_AT_A_TIME),
    # "Um valor de" evita errar o gênero de dimensões femininas.
    ("Qual foi a receita residencial e comercial em Recife em junho de 2026?",
     "Consulto um valor de classe de consumo por vez; você citou residencial e comercial. "
     "Qual quer primeiro?"),
    ("Qual foi a receita faturada em março de 2025 em Recife, excluindo Olinda?",
     "Este recorte pede exclusão; informe o valor que deseja incluir."),
    ("Qual foi a receita faturada em março de 2025 em Recife, exceto Olinda?",
     "Este recorte pede exclusão; informe o valor que deseja incluir."),
    ("Qual foi a receita faturada em março de 2025 em Recife, menos Olinda?",
     "Este recorte pede exclusão; informe o valor que deseja incluir."),
    ("Quais UCs com GD em Olinda tiveram queda de consumo superior a 30%?",
     "Não apresento resultados individuais por unidade consumidora (UC). "
     "Posso mostrar totais por município, bairro, classe de consumo ou geração distribuída (GD)."),
    ("Qual foi a receita faturada entre janeiro e março?",
     "De qual ano você quer consultar janeiro e março? "
     "Se forem anos diferentes, informe o ano de cada mês."),
])
def test_limit_clarifications_name_the_real_problem(question, expected):
    result = _plan(question, dimension_values=MUNICIPALITIES)
    assert result["status"] == "needs_clarification", result
    assert result["response"]["message"].split("\n\n")[0] == expected


def test_incomplete_month_interval_still_asks_for_both_bounds():
    result = _plan("Qual foi a receita faturada entre janeiro de 2025 e março?")
    assert result["status"] == "needs_clarification", result
    assert result["response"]["message"].startswith(BOTH_BOUNDS)


def test_unknown_place_after_preposition_still_asks_for_geography():
    result = _plan("Qual foi a receita faturada em Atlantis em junho de 2026?")
    assert result["status"] == "needs_clarification", result
    assert UNKNOWN_GEOGRAPHY in result["response"]["message"]


@pytest.mark.parametrize("exclusion", [
    "sem ser residencial", "que não seja residencial", "excluindo residencial",
    "sem incluir Olinda", "fora de Olinda", "fora do município de Olinda",
    "diferente de residencial", "não apenas residencial",
])
def test_exclusion_cannot_be_silently_changed_to_inclusion(exclusion):
    result = _plan(f"Receita {exclusion} em março de 2025?")
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


def test_registered_absence_of_gd_remains_an_allowed_categorical_filter():
    result = _plan("Receita residencial sem GD em março de 2025?")
    assert result["status"] == "planned", result
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "generation.distributed": ["Não"],
    }


@pytest.mark.parametrize("metric", [
    "Receita arrecadada", "Faturamento recebido", "Faturamento pago", "Valores recebidos",
])
def test_collected_or_paid_amount_is_not_answered_as_billed_revenue(metric):
    question = f"{metric} residencial em Olinda em março de 2025?"
    first = _plan(question)
    assert first["status"] == "needs_clarification", first
    assert "não comprova pagamento" in first["response"]["message"]
    result = _plan("Receita faturada", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": first["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Olinda"],
    }


@pytest.mark.parametrize("class_phrase", [
    "classe de consumo residencial", "classe de consumo: residencial",
])
def test_class_label_does_not_create_a_second_consumption_metric(class_phrase):
    result = _plan(f"Receita da {class_phrase} em Olinda em março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Olinda"],
    }


def test_explicit_consumption_metric_outside_class_label_still_requires_clarification():
    result = _plan("Receita e consumo da classe de consumo residencial em março de 2025?")
    assert result["status"] == "needs_clarification"
    assert result.get("plan") is None


@pytest.mark.parametrize("question", [
    "Qual foi o município com maior receita em março de 2025?",
    "Em qual município a receita foi maior em março de 2025?",
])
def test_municipal_ranking_is_not_mistaken_for_an_unknown_location(question):
    result = _plan(question)
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == ["geography.municipality"]
    assert result["plan"]["order"] == {"field_id": "billing.revenue", "direction": "desc"}
    assert result["plan"]["limit"] == 1
    assert result["plan"]["filters"] == []


@pytest.mark.parametrize("dimension,label", [
    ("geography.municipality", "município"), ("customer.consumption_class", "classe de consumo"),
])
def test_supported_grouping_is_not_mistaken_for_a_missing_filter_value(dimension, label):
    result = _plan(f"Receita por {label} em março de 2025?")
    assert result["status"] == "planned", result
    assert result["plan"]["group_by_dimension_ids"] == [dimension]
    assert result["plan"]["filters"] == []
    assert result["plan"].get("order") is None


@pytest.mark.parametrize("question", [
    "Receita por município inventado em março de 2025?",
    "Qual município inventado teve a maior receita em março de 2025?",
    "Receita por município e classe em março de 2025?",
    "Receita da classe de consumo inventada em março de 2025?",
])
def test_unknown_or_multiple_grouping_references_do_not_disappear(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


@pytest.mark.parametrize("period", [
    "no mês de março de 2025", "na competência março de 2025",
    "em 03/2025", "em 3/2025", "em março/2025", "em mar/2025", "em mar. 2025",
])
def test_explicit_month_notation_preserves_the_authorized_slice(period):
    result = _plan(f"Receita residencial em Olinda {period}?")
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["window"]["end"] == "2025-03-31"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Olinda"],
    }


@pytest.mark.parametrize("question,comparison", [
    ("Receita janeiro a março de 2025?", None),
    ("Receita em janeiro a março de 2025?", None),
    ("Qual a variação da receita de janeiro para março de 2025?", ["2025-01", "2025-03"]),
    ("Compare receita de janeiro versus março de 2025?", ["2025-01", "2025-03"]),
])
def test_equivalent_range_and_comparison_links_keep_their_distinct_plans(question, comparison):
    result = _plan(question)
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-01-01"
    assert result["plan"]["window"]["end"] == "2025-03-31"
    assert result["plan"].get("comparison_periods") == comparison


@pytest.mark.parametrize("question", [
    "Preço  médio  por  kWh  em  março  de  2025?",
    "Consumo\tresidencial no bairro Casa\nCaiada em março de 2025?",
])
def test_whitespace_does_not_lose_metric_or_registered_filter(question):
    result = _plan(question)
    assert result["status"] == "planned", result
    if question.startswith("Preço"):
        assert result["plan"]["metric_id"] == "billing.effective_tariff"
    else:
        assert result["plan"]["metric_id"] == "energy.consumption"
        assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
            "customer.consumption_class": ["RESIDENCIAL"],
            "geography.neighborhood": ["Casa Caiada"],
        }


@pytest.mark.parametrize("question", [
    "Receita de 2025-13 a 2025-03?", "Receita de 13/2025 a 03/2025?",
    "Receita de 31/03/2025 a 03/2025?", "Receita de janeiro de 2025 até março?",
    "Receita em 31/03/2025?", "Receita em 03/99?",
    "Receita de 03/99 a 03/2025?", "Receita de 2025-123 a 2025-03?",
    "Receita em 10 março de 2025?", "Receita em 31.03.2025?",
])
def test_invalid_or_daily_dates_cannot_be_shortened_to_a_recognized_month(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


@pytest.mark.parametrize("question", ["Em março de 2025?", "março de 2025", "Só em março de 2025?"])
def test_period_only_follow_up_keeps_the_previous_metric_and_filters(question):
    result = _plan(question, [
        {"role": "user", "content": "Receita residencial em Olinda em janeiro de 2025?"},
        {"role": "assistant", "content": "Resultado da consulta."},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "billing.revenue"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Olinda"],
    }


def test_follow_up_cannot_drop_comparison_when_switching_to_consumption():
    result = _plan("E o consumo?", [
        {"role": "user", "content": "Compare receita residencial em Olinda "
         "de janeiro e março de 2025."},
        {"role": "assistant", "content": "Resultado da comparação."},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["comparison_periods"] == ["2025-01", "2025-03"]
    assert result["plan"]["window"]["end"] == "2025-03-31"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Olinda"],
    }


def test_metric_switch_cannot_silently_remove_a_previous_grouped_comparison():
    result = _plan("E a receita?", [
        {"role": "user", "content": "Qual bairro de Olinda mais perdeu consumo medido residencial "
         "entre janeiro de 2025 e março de 2025?"},
        {"role": "assistant", "content": "Resultado da comparação."},
    ])
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


@pytest.mark.parametrize("question", ["Em março de 2025?", "Só em março de 2025?"])
def test_period_alone_without_user_context_cannot_invent_a_metric(question):
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


@pytest.mark.parametrize("constraint", [
    "superior a 1000", "inferior a 1000", "maior ou igual a 1000", "igual a 1000",
    "> 1000", ">=1000", "< R$ 1000", "!= 1000",
])
def test_unimplemented_value_constraint_cannot_be_dropped(constraint):
    result = _plan(f"Receita {constraint} em março de 2025?")
    assert result["status"] in {"needs_clarification", "refused"}, result
    assert result.get("plan") is None


def test_lost_revenue_ranking_cannot_be_answered_as_lowest_monthly_total():
    result = _plan("Qual município mais perdeu receita em março de 2025?")
    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None


@pytest.mark.parametrize("question,value,unit,expected", [
    ("Qual foi o ticket médio em Olinda em março de 2025?", 260.78,
     "R$ por UC faturada no mês",
     "Para ticket médio por UC faturada no mês, o resultado foi de "
     "260,78 R$ por UC faturada no mês em março de 2025."),
    ("Qual foi a tarifa média efetiva em Olinda em março de 2025?", 0.7557, "R$/kWh",
     "Para preço médio observado por kWh, o resultado foi de 0,7557 R$/kWh em março de 2025."),
    ("Qual foi o consumo em Olinda em março de 2025?", 1364362.0, "kWh",
     "Para consumo medido, o resultado foi de 1.364.362 kWh em março de 2025."),
    ("Qual foi a receita em Olinda em março de 2025?", -189630.15, "R$",
     "Para receita faturada, o resultado foi de -R$ 189.630,15 em março de 2025."),
])
def test_synthesized_answer_uses_pt_br_numbers_and_keeps_acronyms(question, value, unit, expected):
    core, request = _setup(question)
    with InProcessClient(_application(core)) as client:
        result = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert result["status"] == "planned", result
        plan = LogicalReadPlan.model_validate(result["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [{"period": "2025-03", "value": value, "unit": unit}]
        synthesis = QuestionSynthesisRequest(
            question=question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=request.dimension_value_coverage,
        )
        response = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert response["status"] == "answered", response
    assert response["answer"] == expected


def test_comparison_keeps_sign_before_currency_and_percent_without_space():
    question = "Compare a receita em Recife entre janeiro e março de 2025."
    core, request = _setup(question)
    with InProcessClient(_application(core)) as client:
        result = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert result["status"] == "planned", result
        plan = LogicalReadPlan.model_validate(result["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {"period": "2025-01", "value": 2000, "unit": "R$"},
            {"period": "2025-03", "value": 979.5, "unit": "R$"},
        ]
        synthesis = QuestionSynthesisRequest(
            question=question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
        )
        response = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert response["status"] == "answered", response
    assert response["answer"] == (
        "Receita faturada: R$ 2.000,00 em janeiro de 2025; R$ 979,50 em março de 2025. "
        "Variação absoluta: -R$ 1.020,50 (-51,02%)."
    )


@pytest.mark.parametrize("follow_up", [False, True])
def test_language_normalization_survives_plan_revalidation_and_synthesis(follow_up):
    question = "Receita da classe de consumo residencial em Olinda em 03/2025?"
    context = []
    if follow_up:
        question = "E o consumo?"
        context = [
            {"role": "user", "content": "Compare receita residencial em Olinda "
             "de janeiro para março de 2025."},
            {"role": "assistant", "content": "Resultado da comparação."},
        ]
    core, request = _setup(question)
    payload = request.model_dump(mode="json")
    payload["context"] = context
    with InProcessClient(_application(core)) as client:
        result = client.post(PLAN_PATH, json=payload, headers=HEADERS).json()
        assert result["status"] == "planned", result
        plan = LogicalReadPlan.model_validate(result["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = (
            [{"period": "2025-01", "value": 80, "unit": "kWh"},
             {"period": "2025-03", "value": 100, "unit": "kWh"}]
            if follow_up else [{"period": "2025-03", "value": 120, "unit": "R$"}]
        )
        synthesis = QuestionSynthesisRequest(
            question=question, context=context, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=request.dimension_value_coverage,
        )
        response = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert response["status"] == "answered", response
    assert "março de 2025" in response["answer"]
    if follow_up:
        assert "janeiro de 2025" in response["answer"]
        assert "Variação absoluta: 20 kWh (25%)." in response["answer"]
    else:
        assert "R$ 120,00" in response["answer"]


@pytest.mark.parametrize("qualified", [True, False])
def test_child_place_reference_qualifies_a_parent_name_shared_with_other_neighborhoods(qualified):
    place = "no bairro Casa Caiada de Recife" if qualified else "Recife"
    result = _plan(
        f"Receita da classe de consumo residencial {place} em março de 2025?",
        dimension_values=[
            {"dimension_id": "geography.municipality", "values": ["Olinda", "Recife"]},
            {"dimension_id": "geography.neighborhood", "values": ["Casa Caiada", "Recife"]},
        ],
    )
    if qualified:
        assert result["status"] == "planned", result
        assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
            "customer.consumption_class": ["RESIDENCIAL"],
            "geography.municipality": ["Recife"],
            "geography.neighborhood": ["Casa Caiada"],
        }
    else:
        assert result["status"] == "needs_clarification", result
        assert result.get("plan") is None


@pytest.mark.parametrize("question,metric,neighborhood", [
    ("Qual foi a receita faturada em Recife em junho de 2026?", "billing.revenue", False),
    ("Qual foi o consumo de energia em Recife em junho de 2026?", "energy.consumption", False),
    ("Qual foi a receita residencial no bairro Brasília Teimosa, em Recife, em junho de 2026?",
     "billing.revenue", True),
])
def test_exact_browser_questions_resolve_municipality_shared_with_neighborhood(
    question, metric, neighborhood,
):
    core, request = _setup(question)
    payload = request.model_dump(mode="json")
    for coverage in payload["temporal_coverage"]:
        coverage["competencies"] = ["2026-06"]
    payload["dimension_value_coverage"] = [
        {"dimension_id": "geography.municipality", "values": ["Recife", "Olinda"]},
        {"dimension_id": "geography.neighborhood", "values": ["Recife", "Brasília Teimosa"]},
    ]
    with InProcessClient(_application(core)) as client:
        result = client.post(PLAN_PATH, json=payload, headers=HEADERS).json()
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == metric
    assert result["plan"]["window"]["start"] == "2026-06-01"
    filters = {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]}
    assert filters == ({"geography.municipality": ["Recife"],
                        "geography.neighborhood": ["Brasília Teimosa"],
                        "customer.consumption_class": ["RESIDENCIAL"]}
                       if neighborhood else {"geography.municipality": ["Recife"]})


def test_explicit_neighborhood_overrides_municipal_default_for_same_name():
    result = _plan("Receita no bairro Recife em março de 2025?", dimension_values=[
        {"dimension_id": "geography.municipality", "values": ["Recife"]},
        {"dimension_id": "geography.neighborhood", "values": ["Recife"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["filters"] == [{"dimension_id": "geography.neighborhood",
                                         "operator": "eq", "values": ["Recife"]}]


@pytest.mark.parametrize("with_context", [False, True])
def test_new_case_question_does_not_inherit_an_unresolved_solar_indicator(with_context):
    solar = "Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%?"
    solar_result = _plan(solar)
    assert solar_result["status"] == "needs_clarification"
    message = solar_result["response"]["message"]
    assert "Gold" not in message and "GD" in message and "solar" in message
    context = [{"role":"user", "content":solar},
               {"role":"assistant", "content":message}] if with_context else []
    question = "Qual bairro mais perdeu volume residencial no último ano?"
    result = _plan(question, context)
    assert result["status"] == "needs_clarification", result
    assert "Gold v2 não publica essa medida" in result["response"]["message"]
    assert "consumo medido é outro indicador" in result["response"]["message"]
    assert result == _plan(question)


def test_full_revenue_growth_question_after_solar_asks_only_for_missing_period():
    solar = "Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%?"
    result = _plan("Quanto cresceu a receita comercial em Jaboatão dos Guararapes?", [
        {"role":"user", "content":solar},
        {"role":"assistant", "content":_plan(solar)["response"]["message"]},
    ], dimension_values=[
        {"dimension_id":"geography.municipality", "values":["Olinda", "Jaboatão dos Guararapes"]},
    ])
    assert result["status"] == "needs_clarification", result
    assert result["response"]["message"].split("\n\nExemplo de pergunta:")[0] == (
        "Qual período você quer consultar ou comparar?"
    )


@pytest.mark.parametrize("question", [
    "Qual foi a receita em Olinda?",
    "Quanto foi o consumo em Recife?",
])
def test_new_complete_question_does_not_inherit_period_or_class(question):
    previous = "Receita residencial em Olinda no último trimestre?"
    result = _plan(question, [
        {"role": "user", "content": previous},
        {"role": "assistant", "content": "Resultado do trimestre residencial."},
    ])
    assert result == _plan(question)
    assert result["status"] == "needs_clarification"
    assert "Qual período" in result["response"]["message"]


def test_explicit_follow_up_still_preserves_period_and_class():
    result = _plan("E em Recife?", [
        {"role": "user", "content": "Receita residencial em Olinda em março de 2025?"},
        {"role": "assistant", "content": "Resultado residencial de março."},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "customer.consumption_class": ["RESIDENCIAL"],
        "geography.municipality": ["Recife"],
    }


@pytest.mark.parametrize("question", [
    "Receita e consumo em março de 2025?",
    "Qual foi a receita?",
    "Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%?",
])
def test_clarification_has_a_complete_example_that_is_accepted_in_the_same_scope(question):
    extra = [{"metric_id":"energy.gd_consumption_drop", "kind":"none"}]
    result = _plan(question, extra_coverage=extra)
    assert result["status"] == "needs_clarification", result
    message = result["response"]["message"]
    example = message.split("\n\nExemplo de pergunta: “", 1)[1].removesuffix("”")
    follow_up = _plan(example, [
        {"role":"user", "content":question}, {"role":"assistant", "content":message},
    ], extra_coverage=extra)
    assert follow_up["status"] == "planned", follow_up
    if "bairro" in question:
        assert follow_up["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
        assert follow_up["plan"]["comparison_periods"] == ["2025-02", "2025-03"]
        assert {item["dimension_id"] for item in follow_up["plan"]["filters"]} == {
            "customer.consumption_class",
        }
    if "solar" in question:
        assert "GD" in example and "solar" not in example
        assert follow_up["plan"]["metric_id"] == "energy.gd_consumption_drop"


def test_billed_residential_volume_clarification_does_not_silently_suggest_measured_kwh():
    question = "Qual bairro mais perdeu volume residencial no último ano?"
    result = _plan(question)
    assert result["status"] == "needs_clarification", result
    message = result["response"]["message"]
    assert "Gold v2 não publica essa medida" in message
    assert "consumo medido é outro indicador" in message
    assert "Exemplo de pergunta:" not in message


def test_example_uses_published_months_and_does_not_break_a_short_period_reply():
    question = "Receita residencial em Olinda"
    message = _plan(question)["response"]["message"]
    assert "março de 2025" in message
    result = _plan("março de 2025", [
        {"role":"user", "content":question}, {"role":"assistant", "content":message},
    ])
    assert result["status"] == "planned", result
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "geography.municipality":["Olinda"], "customer.consumption_class":["RESIDENCIAL"],
    }


@pytest.mark.parametrize("available", [True, False])
def test_examples_respect_read_scope_and_are_omitted_without_published_periods(available):
    core, request = _setup("Qual indicador?")
    payload = request.model_dump(mode="json")
    payload["access_scope"]["allowed_metric_ids"] = ["energy.consumption"]
    payload["temporal_coverage"] = [coverage for coverage in payload["temporal_coverage"]
                                    if coverage["metric_id"] == "energy.consumption"]
    if not available:
        payload["temporal_coverage"][0]["competencies"] = []
    with InProcessClient(_application(core)) as client:
        result = client.post(PLAN_PATH, json=payload, headers=HEADERS).json()
        message = result["response"]["message"]
        if not available:
            assert "Exemplo de pergunta:" not in message
            return
        example = message.split("\n\nExemplo de pergunta: “", 1)[1].removesuffix("”")
        payload["question"] = example
        planned = client.post(PLAN_PATH, json=payload, headers=HEADERS).json()
    assert planned["status"] == "planned", planned
    assert planned["plan"]["metric_id"] == "energy.consumption"


@pytest.mark.parametrize("question", [
    "Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%?",
])
def test_solar_example_replaces_the_qualifier_without_repeating_com(question):
    coverage = [{"metric_id": "energy.gd_consumption_drop", "kind": "none"}]
    result = _plan(question, extra_coverage=coverage)
    assert result["status"] == "needs_clarification"
    message = result["response"]["message"]
    example = message.split("Exemplo de pergunta: “", 1)[1].removesuffix("”")
    assert "com com" not in example
    assert "UCs com GD em Olinda" in example
    assert _plan(example, extra_coverage=coverage)["status"] == "planned"


def test_gd_synthesis_preserves_initial_acronym_and_published_windows():
    question = "Quantas UCs com GD em Olinda tiveram queda de consumo acima de 30%?"
    core, request = _setup(question)
    payload = request.model_dump(mode="json")
    payload["temporal_coverage"].append({"metric_id": "energy.gd_consumption_drop", "kind": "none"})
    with InProcessClient(_application(core)) as client:
        result = client.post(PLAN_PATH, json=payload, headers=HEADERS).json()
        assert result["status"] == "planned", result
        plan = LogicalReadPlan.model_validate(result["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [{"period": plan.window.phrase, "value": 12, "unit": "UCs"}]
        synthesis = QuestionSynthesisRequest(
            question=question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=request.dimension_value_coverage,
        )
        response = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert response["status"] == "answered", response
    assert "Para UCs elegíveis com GD" in response["answer"]
    assert "12 UCs" in response["answer"]
    assert response["analysis_context"]["period"] == plan.window.phrase


@pytest.mark.parametrize("reply", [
    "Compare janeiro de 2025 e março de 2025",
    "entre janeiro de 2025 e março de 2025",
])
def test_comparison_baseline_reply_retains_metric_and_filters(reply):
    question = "Como a receita residencial em Olinda variou em março de 2025?"
    pending = _plan(question)
    assert pending["status"] == "needs_clarification"
    result = _plan(reply, [
        {"role": "user", "content": question},
        {"role": "assistant", "content": pending["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["comparison_periods"] == ["2025-01", "2025-03"]
    assert {f["dimension_id"]: f["values"] for f in plan["filters"]} == {
        "geography.municipality": ["Olinda"],
        "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_new_question_after_comparison_clarification_does_not_inherit_metric():
    question = "Como a receita residencial em Olinda variou em março de 2025?"
    pending = _plan(question)
    result = _plan("Qual foi o consumo em Recife em janeiro de 2025?", [
        {"role": "user", "content": question},
        {"role": "assistant", "content": pending["response"]["message"]},
    ])
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"].get("comparison_periods") is None
    assert result["plan"]["filters"] == [{
        "dimension_id": "geography.municipality", "operator": "eq", "values": ["Recife"],
    }]
