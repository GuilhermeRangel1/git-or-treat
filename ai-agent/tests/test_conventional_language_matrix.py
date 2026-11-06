"""Matriz ampliada de perguntas naturais para o planejamento Gold v2.

Os casos combinam vocabulário cotidiano, classe, município e grafias temporais.
Cada assert verifica o contrato semântico completo do plano; nenhum chama Gemini
nem consulta linhas da Gold.
"""

from calendar import monthrange

import pytest

from .test_gold_language_http import _plan

_PLACES = (
    ("em Recife", "Recife"),
    ("em Olinda", "Olinda"),
    ("em Jaboatão dos Guararapes", "Jaboatão dos Guararapes"),
)
_DIMENSION_COVERAGE = [
    {
        "dimension_id": "geography.municipality",
        "values": ["Olinda", "Recife", "Jaboatão dos Guararapes"],
    },
    {"dimension_id": "geography.neighborhood", "values": ["Casa Caiada"]},
    {"dimension_id": "network.feeder", "values": ["AL-01"]},
    {"dimension_id": "tariff.subgroup", "values": ["B1"]},
]
_EXPLICIT_MONTHS = (
    ("em março de 2025", "2025-03-01", "2025-03-31"),
    ("em 2025-03", "2025-03-01", "2025-03-31"),
    ("em mar/2025", "2025-03-01", "2025-03-31"),
    ("no mês de março de 2025", "2025-03-01", "2025-03-31"),
)

_CONSUMPTION_SUBJECTS = (
    ("as casas", "consumiram", "RESIDENCIAL"),
    ("as famílias", "consumiram", "RESIDENCIAL"),
    ("as residências", "consumiram", "RESIDENCIAL"),
    ("as unidades residenciais", "consumiram", "RESIDENCIAL"),
    ("os clientes residenciais", "consumiram", "RESIDENCIAL"),
    ("a classe residencial", "consumiu", "RESIDENCIAL"),
    ("a classe comercial", "consumiu", "COMERCIAL"),
    ("os clientes comerciais", "consumiram", "COMERCIAL"),
    ("os estabelecimentos comerciais", "consumiram", "COMERCIAL"),
    ("a classe industrial", "consumiu", "INDUSTRIAL"),
    ("os clientes industriais", "consumiram", "INDUSTRIAL"),
    ("as unidades rurais", "consumiram", "RURAL"),
    ("o poder público", "consumiu", "PODER PUBLICO"),
)
_REVENUE_SUBJECTS = (
    ("residencial", "RESIDENCIAL"),
    ("das casas", "RESIDENCIAL"),
    ("das famílias", "RESIDENCIAL"),
    ("das residências", "RESIDENCIAL"),
    ("das unidades residenciais", "RESIDENCIAL"),
    ("da classe residencial", "RESIDENCIAL"),
    ("comercial", "COMERCIAL"),
    ("da classe comercial", "COMERCIAL"),
    ("do comércio", "COMERCIAL"),
    ("dos clientes comerciais", "COMERCIAL"),
    ("dos estabelecimentos comerciais", "COMERCIAL"),
    ("industrial", "INDUSTRIAL"),
    ("da classe industrial", "INDUSTRIAL"),
    ("do setor industrial", "INDUSTRIAL"),
    ("dos clientes industriais", "INDUSTRIAL"),
    ("rural", "RURAL"),
    ("da classe rural", "RURAL"),
    ("dos clientes rurais", "RURAL"),
    ("do poder público", "PODER PUBLICO"),
    ("da classe de consumo poder público", "PODER PUBLICO"),
)


def _scenario_id(*parts: str) -> str:
    return "-".join(
        "".join(char.lower() if char.isalnum() else "-" for char in part).strip("-")
        for part in parts
    )


def _consumption_questions():
    for subject, verb, category in _CONSUMPTION_SUBJECTS:
        for place, municipality in _PLACES:
            for period, start, end in _EXPLICIT_MONTHS:
                question = f"Quanto {verb} {subject} {place} {period}?"
                yield pytest.param(
                    question,
                    category,
                    municipality,
                    start,
                    end,
                    id=_scenario_id(category, municipality, period, subject),
                )


def _revenue_questions():
    for subject, category in _REVENUE_SUBJECTS:
        for place, municipality in _PLACES:
            for period, start, end in _EXPLICIT_MONTHS:
                question = f"Qual foi o faturamento {subject} {place} {period}?"
                yield pytest.param(
                    question,
                    category,
                    municipality,
                    start,
                    end,
                    id=_scenario_id(category, municipality, period, subject),
                )


@pytest.mark.parametrize(
    "question,category,municipality,start,end", list(_consumption_questions())
)
def test_everyday_consumption_language_preserves_measure_class_city_and_month(
    question, category, municipality, start, end
):
    result = _plan(
        question, competencies=[start[:7]], dimension_values=_DIMENSION_COVERAGE
    )

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "energy.consumption"
    assert plan["unit"] == "kWh"
    assert {item["dimension_id"]: item["values"] for item in plan["filters"]} == {
        "geography.municipality": [municipality],
        "customer.consumption_class": [category],
    }
    assert (plan["window"]["start"], plan["window"]["end"]) == (start, end)


@pytest.mark.parametrize(
    "question,category,municipality,start,end", list(_revenue_questions())
)
def test_everyday_billing_language_preserves_revenue_class_city_and_month(
    question, category, municipality, start, end
):
    result = _plan(
        question, competencies=[start[:7]], dimension_values=_DIMENSION_COVERAGE
    )

    assert result["status"] == "planned", result
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["unit"] == "R$"
    assert {item["dimension_id"]: item["values"] for item in plan["filters"]} == {
        "geography.municipality": [municipality],
        "customer.consumption_class": [category],
    }
    assert (plan["window"]["start"], plan["window"]["end"]) == (start, end)


def _month_shift(year: int, month: int, offset: int) -> tuple[int, int]:
    absolute = year * 12 + month - 1 + offset
    return absolute // 12, absolute % 12 + 1


def _month_window(year: int, month: int) -> tuple[str, str]:
    return (
        f"{year:04d}-{month:02d}-01",
        f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}",
    )


def _relative_month_cases():
    anchor = (2026, 6)
    number_words = (
        "um", "dois", "três", "quatro", "cinco", "seis",
        "sete", "oito", "nove", "dez", "onze", "doze",
    )
    for count, word in enumerate(number_words, start=1):
        for phrase in (
            f"há {count} {'mês' if count == 1 else 'meses'}",
            f"há {word} {'mês' if count == 1 else 'meses'}",
            f"{count} {'mês' if count == 1 else 'meses'} atrás",
            f"{word} {'mês' if count == 1 else 'meses'} atrás",
        ):
            year, month = _month_shift(*anchor, -count)
            start, end = _month_window(year, month)
            yield pytest.param(
                f"Qual foi o consumo residencial {phrase}?", start, end,
                id=_scenario_id("mês-relativo", phrase),
            )

        if count > 1:
            for phrase in (f"últimos {count} meses", f"últimos {word} meses"):
                year, month = _month_shift(*anchor, -(count - 1))
                start, _ = _month_window(year, month)
                _, end = _month_window(*anchor)
                yield pytest.param(
                    f"Qual foi o consumo residencial nos {phrase}?", start, end,
                    id=_scenario_id("janela-relativa", phrase),
                )


@pytest.mark.parametrize("question,start,end", list(_relative_month_cases()))
def test_relative_month_language_resolves_each_number_and_spelling_from_june_2026(
    question, start, end
):
    competencies = [
        f"{year:04d}-{month:02d}"
        for year in (2025, 2026)
        for month in range(1, 13)
        if (year, month) >= (2025, 1) and (year, month) <= (2026, 6)
    ]
    result = _plan(question, competencies=competencies)

    assert result["status"] == "planned", result
    assert (result["plan"]["window"]["start"], result["plan"]["window"]["end"]) == (
        start,
        end,
    )


@pytest.mark.parametrize(
    "question,expected_metric,expected_unit,fragments",
    [
        ("Quanto deu a conta de luz em Recife em março de 2025?", None, None,
         ("consumo", "faturado", "pago")),
        ("Quanto custou minha conta de energia em Recife em março de 2025?", None, None,
         ("consumo", "faturado", "pago")),
        ("Quanto entrou de pagamento em Recife em março de 2025?", None, None,
         ("não comprova pagamento", "faturada")),
        ("Quanto recebemos dos clientes em março de 2025?", None, None,
         ("não comprova pagamento", "faturada")),
        ("Qual foi a arrecadação em Recife em março de 2025?", None, None,
         ("não comprova pagamento", "faturada")),
        ("Quantas casas têm painel solar em Olinda?", None, None, ("solar", "GD")),
        ("Quantos clientes instalaram energia solar em Recife?", None, None,
         ("solar", "GD")),
        ("Quanto tempo os moradores ficaram sem luz no alimentador AL-01 em março de 2025?",
         None, None, ("duração", "DEC", "individual")),
        ("Quantas vezes caiu a energia no alimentador AL-01 em março de 2025?",
         "network.interruption_events", "ocorrências", ()),
        ("Quantos apagões ocorreram no alimentador AL-01 em março de 2025?",
         "network.interruption_events", "ocorrências", ()),
        ("Quantos chamados abriram em março de 2025?",
         "service.attendance", "protocolos", ()),
        ("Quantas solicitações de atendimento foram abertas em março de 2025?",
         "service.attendance", "protocolos", ()),
        ("Qual foi a nota dos clientes para o atendimento em março de 2025?",
         "service.satisfaction", "pontos", ()),
        ("O que os clientes acharam do atendimento em março de 2025?",
         "service.satisfaction", "pontos", ()),
        ("Quantas reclamações de falta de luz foram registradas em março de 2025?",
         None, None, ("reclamações", "categoria")),
        ("Qual foi a tarifa regulada em Recife em março de 2025?", None, None,
         ("homologada", "não está disponível")),
        ("Qual foi o faturamento em Recife em março de 2025?", "billing.revenue", "R$", ()),
        ("Quanto custou o kWh em média em Recife em março de 2025?",
         "billing.effective_tariff", "R$/kWh", ()),
        ("Quanto as casas consumiram em Recife em março de 2025?",
         "energy.consumption", "kWh", ()),
        ("Qual foi o volume em Recife em março de 2025?", None, None,
         ("consumo medido", "energia faturada")),
    ],
)
def test_simple_business_questions_return_a_supported_measure_or_a_specific_limit(
    question, expected_metric, expected_unit, fragments
):
    extra_coverage = (
        [{"metric_id": "energy.gd_units", "kind": "none"}]
        if "com GD" in question else []
    )
    result = _plan(question, competencies=["2025-03"], extra_coverage=extra_coverage)

    if expected_metric is not None:
        assert result["status"] == "planned", result
        assert result["plan"]["metric_id"] == expected_metric
        assert result["plan"]["unit"] == expected_unit
        return

    assert result["status"] == "needs_clarification", result
    assert result.get("plan") is None
    message = result["response"]["message"].casefold()
    for fragment in fragments:
        assert fragment.casefold() in message, (fragment, message)
