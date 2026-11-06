"""Benchmark de linguagem convencional na fronteira de planejamento Gold v2.

Os oráculos vêm da especificação v1.1 e do contrato do catálogo. Este conjunto
mede interpretação/plano, não valores numéricos nem a qualidade do Gemini.
"""

import pytest

from app.agent.comparison import comparison_records
from app.schemas.read_plan import LogicalReadPlan

from .test_gold_language_http import _plan

ONE_MONTH = ["2025-03"]
RECIFE = {"geography.municipality": ["Recife"]}
RESIDENTIAL_RECIFE = {
    "geography.municipality": ["Recife"],
    "customer.consumption_class": ["RESIDENCIAL"],
}


@pytest.mark.parametrize(
    "question,metric,unit,filters",
    [
        # Consumo residencial: termos cotidianos devem chegar à mesma medida em kWh.
        (
            "Quanto as casas consumiram em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Quanto de energia as residências consumiram em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Qual foi o consumo das unidades residenciais em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Como ficou o consumo residencial em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Qual foi a energia consumida pelos clientes residenciais em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Quanto as famílias consumiram em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Quanto de energia foi usada pelas famílias em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Quanto a classe comercial consumiu em Recife em março de 2025?",
            "energy.consumption", "kWh",
            {"geography.municipality": ["Recife"],
             "customer.consumption_class": ["COMERCIAL"]},
        ),
        (
            "Qual foi o consumo residencial em Olinda em março de 2025?",
            "energy.consumption", "kWh",
            {"geography.municipality": ["Olinda"],
             "customer.consumption_class": ["RESIDENCIAL"]},
        ),
        (
            "Quanto foi o volume consumido pelas casas em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Qual foi o volume de consumo residencial em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Qual foi o consumo medido residencial em Recife em março de 2025?",
            "energy.consumption", "kWh", RESIDENTIAL_RECIFE,
        ),
        (
            "Quanto consumiram os clientes comerciais em Recife em março de 2025?",
            "energy.consumption", "kWh",
            {"geography.municipality": ["Recife"],
             "customer.consumption_class": ["COMERCIAL"]},
        ),
        # Receita faturada: valor monetário, sem confundir com arrecadação ou energia faturada.
        (
            "Qual foi o faturamento em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        (
            "Quanto faturamos em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        (
            "Qual foi a receita faturada em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        (
            "Quanto foi faturado em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        (
            "Qual foi o valor das faturas em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        (
            "Qual foi a receita comercial em Recife em março de 2025?",
            "billing.revenue", "R$",
            {"geography.municipality": ["Recife"],
             "customer.consumption_class": ["COMERCIAL"]},
        ),
        (
            "Quanto faturaram as unidades residenciais em Recife em março de 2025?",
            "billing.revenue", "R$", RESIDENTIAL_RECIFE,
        ),
        (
            "Qual foi o total de receitas em Recife em março de 2025?",
            "billing.revenue", "R$", RECIFE,
        ),
        # Preço médio observado é distinto da tarifa regulatória.
        (
            "Quanto custou o kWh em média em Recife em março de 2025?",
            "billing.effective_tariff", "R$/kWh", RECIFE,
        ),
        (
            "Qual foi o preço médio do kWh em Recife em março de 2025?",
            "billing.effective_tariff", "R$/kWh", RECIFE,
        ),
        (
            "Qual foi o preço médio observado por kWh em Recife em março de 2025?",
            "billing.effective_tariff", "R$/kWh", RECIFE,
        ),
        (
            "Quanto custou em média cada kWh em Recife em março de 2025?",
            "billing.effective_tariff", "R$/kWh", RECIFE,
        ),
        # Chamados contam protocolos abertos, não satisfação nem tratativas.
        (
            "Quantos chamados abriram em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        (
            "Quantos chamados foram abertos em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        (
            "Quantos protocolos abriram em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        (
            "Qual foi o volume de chamados abertos em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        (
            "Quantos atendimentos foram abertos em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        (
            "Quantos protocolos de atendimento abriram em março de 2025?",
            "service.attendance", "protocolos", {},
        ),
        # Avaliação de atendimento é satisfação, não contagem de protocolos.
        (
            "Como o pessoal avaliou o atendimento em março de 2025?",
            "service.satisfaction", "pontos", {},
        ),
        (
            "Qual foi a nota média do atendimento em março de 2025?",
            "service.satisfaction", "pontos", {},
        ),
        (
            "Que nota os clientes deram ao atendimento em março de 2025?",
            "service.satisfaction", "pontos", {},
        ),
        (
            "Como avaliaram o atendimento em março de 2025?",
            "service.satisfaction", "pontos", {},
        ),
        (
            "Como os clientes avaliaram o atendimento em março de 2025?",
            "service.satisfaction", "pontos", {},
        ),
        # Frequência de eventos, DEC e FEC têm medidas diferentes.
        (
            "Quantas vezes a luz caiu no alimentador AL-01 em março de 2025?",
            "network.interruption_events", "ocorrências", {"network.feeder": ["AL-01"]},
        ),
        (
            "Quantas vezes faltou luz no alimentador AL-01 em março de 2025?",
            "network.interruption_events", "ocorrências", {"network.feeder": ["AL-01"]},
        ),
        (
            "Qual foi a contagem de interrupções no alimentador AL-01 em março de 2025?",
            "network.interruption_events", "ocorrências", {"network.feeder": ["AL-01"]},
        ),
        (
            "Qual foi o número de ocorrências de falta de energia no alimentador AL-01 "
            "em março de 2025?",
            "network.interruption_events", "ocorrências", {"network.feeder": ["AL-01"]},
        ),
        (
            "Quantas interrupções ocorreram no alimentador AL-01 em março de 2025?",
            "network.interruption_events", "ocorrências", {"network.feeder": ["AL-01"]},
        ),
        (
            "Qual foi o DEC do alimentador AL-01 em março de 2025?",
            "network.equivalent_interruption_duration", "horas por UC",
            {"network.feeder": ["AL-01"]},
        ),
        (
            "Qual foi o FEC do alimentador AL-01 em março de 2025?",
            "network.equivalent_interruption_frequency", "interrupções por UC",
            {"network.feeder": ["AL-01"]},
        ),
        # GD descreve cadastro; painel solar exige confirmação da aproximação.
        (
            "Quantas unidades com GD foram registradas em Olinda?",
            "energy.gd_units", "UCs",
            {"geography.municipality": ["Olinda"], "generation.distributed": ["Sim"]},
        ),
    ],
)
def test_conventional_questions_reach_the_expected_gold_metric_and_filters(
    question, metric, unit, filters
):
    extra_coverage = (
        [{"metric_id": "energy.gd_units", "kind": "none"}]
        if metric == "energy.gd_units" else []
    )
    result = _plan(question, competencies=ONE_MONTH, extra_coverage=extra_coverage)

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == metric
    assert plan["unit"] == unit
    assert {item["dimension_id"]: item["values"] for item in plan["filters"]} == filters
    expected_window = (None, None) if metric == "energy.gd_units" else (
        "2025-03-01", "2025-03-31"
    )
    assert (plan["window"]["start"], plan["window"]["end"]) == expected_window


@pytest.mark.parametrize(
    "question,expected_fragments",
    [
        (
            "Qual foi o volume residencial em Recife em março de 2025?",
            ("volume", "faturada", "consumo medido"),
        ),
        (
            "Qual foi o volume comercial em Recife em março de 2025?",
            ("volume", "faturada", "consumo medido"),
        ),
        (
            "Qual foi o volume faturado em Recife em março de 2025?",
            ("energia", "faturada", "kWh"),
        ),
        (
            "Qual foi o volume de energia faturada em Recife em março de 2025?",
            ("energia", "faturada", "kWh"),
        ),
        (
            "Quanto deu a conta de luz em Recife em março de 2025?",
            ("consumo", "faturado", "pago"),
        ),
        (
            "Quanto entrou de pagamento em Recife em março de 2025?",
            ("não comprova pagamento", "faturada"),
        ),
        (
            "Quanto foi arrecadado em Recife em março de 2025?",
            ("não comprova pagamento", "faturada"),
        ),
        (
            "Qual foi o volume em Recife em março de 2025?",
            ("consumo medido", "energia faturada"),
        ),
        (
            "Quanto foi a energia faturada em Recife em março de 2025?",
            ("Gold v2 publica consumo medido", "energia faturada"),
        ),
        (
            "Quantas unidades têm painel solar em Olinda?",
            ("solar", "GD"),
        ),
        (
            "Qual foi a tarifa homologada em Recife em março de 2025?",
            ("homologada", "não está disponível"),
        ),
        (
            "Quanto tempo ficou sem luz no alimentador AL-01 em março de 2025?",
            ("duração", "DEC", "individual"),
        ),
        (
            "Onde mais faltou luz em março de 2025?",
            ("ocorrências", "duração", "UCs afetadas"),
        ),
        (
            "Quantas reclamações abriram em Recife em março de 2025?",
            ("reclamações", "categoria"),
        ),
        (
            "Qual bairro teve mais ocorrências de falta de energia em março de 2025?",
            ("ocorrências", "duração", "UCs afetadas"),
        ),
        (
            "Qual foi o volume de receita em Recife em março de 2025?",
            ("volume", "energia", "valor"),
        ),
    ],
)
def test_terms_without_a_safe_equivalence_ask_a_specific_question(
    question, expected_fragments
):
    result = _plan(question, competencies=ONE_MONTH)

    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"].casefold()
    for fragment in expected_fragments:
        assert fragment.casefold() in message, (fragment, message)


@pytest.mark.parametrize(
    "question,expected_start,expected_end",
    [
        ("Qual foi o consumo residencial no último ano?", "2025-07-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos 12 meses?", "2025-07-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos 2 meses?", "2026-05-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos quatro meses?", "2026-03-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos 3 meses?", "2026-04-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos nove meses?", "2025-10-01", "2026-06-30"),
        ("Qual foi o consumo residencial nos últimos seis meses?", "2026-01-01", "2026-06-30"),
        ("Qual foi o consumo residencial há três meses?", "2026-03-01", "2026-03-31"),
        ("Qual foi o consumo residencial três meses atrás?", "2026-03-01", "2026-03-31"),
        ("Qual foi o consumo residencial há 1 mês?", "2026-05-01", "2026-05-31"),
        ("Qual foi o consumo residencial há seis meses?", "2025-12-01", "2025-12-31"),
        ("Qual foi o consumo residencial seis meses atrás?", "2025-12-01", "2025-12-31"),
        ("Qual foi o consumo residencial há 12 meses?", "2025-06-01", "2025-06-30"),
        ("Qual foi o consumo residencial no mês retrasado?", "2026-04-01", "2026-04-30"),
        ("Qual foi o consumo residencial no ano passado?", "2025-01-01", "2025-12-31"),
    ],
)
def test_relative_periods_use_june_2026_publication_anchor(question, expected_start, expected_end):
    competencies = [
        f"{year:04d}-{month:02d}"
        for year in (2025, 2026)
        for month in range(1, 13)
        if (year, month) >= (2025, 1) and (year, month) <= (2026, 6)
    ]
    result = _plan(question, competencies=competencies)

    assert result["status"] == "planned", result
    assert result["plan"]["window"]["start"] == expected_start
    assert result["plan"]["window"]["end"] == expected_end


def test_simple_house_question_asks_only_for_the_missing_period():
    result = _plan("Quanto as casas consumiram?")

    assert result["status"] == "needs_clarification", result
    message = result["response"]["message"].casefold()
    assert "período" in message
    assert "indicador" not in message and "consumo residencial" not in message


def test_user_confirmed_sectors_means_consumption_classes_for_revenue_breakdown():
    result = _plan(
        "Quanto foi o faturamento total de 2024 em janeiro, dividido por setores?",
        competencies=["2024-01"],
    )

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["group_by_dimension_ids"] == ["customer.consumption_class"]
    assert plan["window"]["start"] == "2024-01-01"
    assert plan["window"]["end"] == "2024-01-31"


def test_bare_volume_asks_whether_the_user_means_consumption_or_billed_energy():
    result = _plan("Qual bairro mais perdeu volume?")

    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"].casefold()
    assert "consumo medido" in message
    assert "energia faturada" in message


def test_explicit_consumption_context_resolves_a_volume_follow_up():
    result = _plan(
        "E o volume por bairro?",
        [{"role": "user", "content":
          "Mostre o consumo residencial medido em Recife em março de 2025."}],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "geography.municipality": ["Recife"],
        "customer.consumption_class": ["RESIDENCIAL"],
    }


def test_commercial_follow_up_changes_class_and_preserves_metric_period_and_city():
    result = _plan(
        "E no comercial?",
        [
            {"role": "user", "content":
             "Quanto as casas consumiram em Recife em março de 2025?"},
            {"role": "assistant", "content":
             "O consumo medido residencial de Recife em março de 2025 foi consultado."},
        ],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "energy.consumption"
    assert plan["window"]["start"] == "2025-03-01"
    assert plan["window"]["end"] == "2025-03-31"
    assert {item["dimension_id"]: item["values"] for item in plan["filters"]} == {
        "geography.municipality": ["Recife"],
        "customer.consumption_class": ["COMERCIAL"],
    }


def test_residential_volume_can_mean_measured_consumption_only_after_explicit_context():
    result = _plan(
        "E o volume residencial por bairro?",
        [{"role": "user", "content":
          "Mostre o consumo residencial medido em Recife em março de 2025."}],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["group_by_dimension_ids"] == ["geography.neighborhood"]
    assert result["plan"]["window"]["start"] == "2025-03-01"


def test_billed_energy_context_is_not_replaced_by_measured_consumption():
    result = _plan(
        "E o volume por bairro?",
        [{"role": "user", "content":
          "Quero energia faturada em kWh por bairro em março de 2025."}],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"].casefold()
    assert "energia faturada" in message and "consumo medido" in message


@pytest.mark.parametrize(
    "question,comparison_periods,metric,group,order",
    [
        (
            "Qual bairro teve a maior queda de consumo entre fevereiro e março de 2025?",
            ["2025-02", "2025-03"], "energy.consumption",
            "geography.neighborhood", "asc",
        ),
        (
            "Qual bairro mais perdeu consumo medido entre fevereiro e março de 2025?",
            ["2025-02", "2025-03"], "energy.consumption",
            "geography.neighborhood", "asc",
        ),
        (
            "Qual município teve o maior crescimento de receita entre fevereiro e março de 2025?",
            ["2025-02", "2025-03"], "billing.revenue",
            "geography.municipality", "desc",
        ),
        (
            "Qual foi o município com maior faturamento em março de 2025?",
            None, "billing.revenue", "geography.municipality", "desc",
        ),
    ],
)
def test_rankings_preserve_the_requested_group_metric_direction_and_periods(
    question, comparison_periods, metric, group, order
):
    result = _plan(question, competencies=["2025-02", "2025-03"])

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == metric
    assert plan["group_by_dimension_ids"] == [group]
    assert plan["order"] == {"field_id": metric, "direction": order}
    assert plan.get("comparison_periods") == comparison_periods
    assert plan["limit"] == (100 if comparison_periods is not None else 1)


@pytest.mark.parametrize(
    "question,expected_metric,expected_direction,rows,expected_group",
    [
        (
            "Qual bairro teve a maior queda de consumo entre fevereiro e março de 2025?",
            "energy.consumption", "asc",
            [("A", "2025-02", 100), ("A", "2025-03", 80),
             ("B", "2025-02", 100), ("B", "2025-03", 90)],
            "A",
        ),
        (
            "Qual município teve o maior crescimento de receita entre fevereiro e março de 2025?",
            "billing.revenue", "desc",
            [("A", "2025-02", 50), ("A", "2025-03", 60),
             ("B", "2025-02", 10), ("B", "2025-03", 40)],
            "B",
        ),
    ],
)
def test_comparison_ranking_selects_the_largest_requested_absolute_change(
    question, expected_metric, expected_direction, rows, expected_group
):
    result = _plan(question, competencies=["2025-02", "2025-03"])
    assert result["status"] == "planned", result
    plan = LogicalReadPlan.model_validate(result["plan"])
    assert plan.metric_id == expected_metric
    assert plan.order.direction.value == expected_direction

    records = [
        {
            "observation_id": str(index),
            "value": value,
            "unit": plan.unit,
            "period": period,
            "dimensions": {plan.group_by_dimension_ids[0]: group},
        }
        for index, (group, period, value) in enumerate(rows)
    ]
    selected = comparison_records(plan, records)

    assert all(row["dimensions"][plan.group_by_dimension_ids[0]] == expected_group
               for row in selected)


@pytest.mark.parametrize("question", [
    "Qual bairro mais perdeu volume residencial no último ano?",
    "Qual bairro mais perdeu volume faturado no último ano?",
])
def test_case_volume_ranking_reports_missing_billed_kwh_instead_of_ranking_consumption(question):
    result = _plan(question, competencies=[
        f"{year:04d}-{month:02d}"
        for year in (2024, 2025, 2026)
        for month in range(1, 13)
        if (year, month) >= (2024, 1) and (year, month) <= (2026, 6)
    ])

    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"].casefold()
    assert "energia faturada" in message and "consumo medido" in message


def test_follow_up_switches_to_commercial_class_and_keeps_measure_period_and_city():
    result = _plan(
        "E no comercial?",
        [{"role": "user", "content":
          "Quanto as casas consumiram em Recife em março de 2025?"}],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "geography.municipality": ["Recife"],
        "customer.consumption_class": ["COMERCIAL"],
    }


def test_single_metric_can_be_followed_by_a_new_geography_without_repeating_the_period():
    result = _plan(
        "E em Olinda?",
        [{"role": "user", "content":
          "Quanto de energia as casas consumiram em Recife em março de 2025?"}],
        competencies=ONE_MONTH,
    )

    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.consumption"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "geography.municipality": ["Olinda"],
        "customer.consumption_class": ["RESIDENCIAL"],
    }
