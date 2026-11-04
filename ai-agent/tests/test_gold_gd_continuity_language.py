import pytest

from .test_gold_language_http import _plan


@pytest.mark.parametrize("question,metric", [
    ("Preço observado em Recife em março de 2025?", "billing.effective_tariff"),
    ("Ticket médio das unidades faturadas em Olinda em março de 2025?", "billing.average_ticket"),
    ("Compare o DEC do alimentador AL-01 entre fevereiro e março de 2025",
     "network.equivalent_interruption_duration"),
    ("Compare o FEC do alimentador AL-01 entre fevereiro e março de 2025",
     "network.equivalent_interruption_frequency"),
    ("Compare o consumo das unidades com e sem GD em Recife em março de 2025",
     "energy.consumption"),
    ("Compare o consumo das unidades com GD e sem GD em Recife em março de 2025",
     "energy.consumption"),
])
def test_domain_questions_preserve_requested_metric(question, metric):
    result = _plan(question)
    assert result["status"] == "planned", result["response"]["message"]
    assert result["plan"]["metric_id"] == metric
    if metric.startswith("network."):
        assert result["plan"]["comparison_periods"] == ["2025-02", "2025-03"]
        assert result["plan"]["filters"][0]["values"] == ["AL-01"]
    if "sem GD" in question:
        assert result["plan"].get("comparison_periods") is None
        assert result["plan"]["group_by_dimension_ids"] == ["generation.distributed"]


@pytest.mark.parametrize("question", [
    "Qual município tem mais unidades com GD?",
    "Qual município tem mais unidades com geração distribuída?",
    "Qual município tem mais UCs com geração distribuída?",
])
def test_total_gd_count_plans_ranking_without_drop_criterion(question):
    result = _plan(question, extra_coverage=[
        {"metric_id": "energy.gd_units", "kind": "none"},
    ])
    assert result["status"] == "planned", result["response"]["message"]
    assert result["plan"]["metric_id"] == "energy.gd_units"
    assert result["plan"]["group_by_dimension_ids"] == ["geography.municipality"]


def test_natural_gd_drop_question_does_not_treat_threshold_as_unknown_location():
    result = _plan(
        "Quantas UCs com GD em Olinda reduziram o consumo em mais de 30%?",
        extra_coverage=[{"metric_id": "energy.gd_consumption_drop", "kind": "none"}],
    )
    assert result["status"] == "planned", result
    assert result["plan"]["metric_id"] == "energy.gd_consumption_drop"
    assert {item["dimension_id"]: item["values"] for item in result["plan"]["filters"]} == {
        "generation.distributed": ["Sim"],
        "geography.municipality": ["Olinda"],
    }


def test_explicit_ticket_and_revenue_remain_two_indicators():
    result = _plan("Qual foi o ticket médio e a receita faturada em Olinda em março de 2025?")
    assert result["status"] == "needs_clarification"
    assert "indicador" in result["response"]["message"]


@pytest.mark.parametrize("question", [
    "Quantas unidades com energia solar tiveram queda de consumo?",
    "Quantas UCs com GD tiveram queda de consumo?",
])
def test_unqualified_unit_count_never_becomes_total_consumption(question):
    result = _plan(question, extra_coverage=[
        {"metric_id": "energy.gd_consumption_drop", "kind": "none"},
    ])
    assert result["status"] == "needs_clarification"
    assert "30%" in result["response"]["message"] or "solar" in result["response"]["message"]
    assert result["plan"] is None
    assert "Exemplo de pergunta: “Quantas UCs com GD" in result["response"]["message"]


@pytest.mark.parametrize("previous", [
    "DEC no alimentador AL-01 em março de 2025?",
    "Compare o DEC no alimentador AL-01 entre fevereiro e março de 2025",
    "Compare duração equivalente de interrupção (DEC) no alimentador AL-01 "
    "entre 2025-02 e 2025-03?",
])
@pytest.mark.parametrize("reference", ["nesse", "desse"])
def test_feeder_reference_survives_metric_change(previous, reference):
    result = _plan(f"Quantas interrupções ocorreram {reference} alimentador em março de 2025?", [
        {"role": "user", "content": previous},
    ])
    assert result["status"] == "planned", result["response"]["message"]
    assert result["plan"]["filters"][0]["values"] == ["AL-01"]


def test_fec_follow_up_keeps_feeder_and_same_month():
    result = _plan("E o FEC desse alimentador no mesmo mês?", [
        {"role": "user", "content": "Duração equivalente de interrupção (DEC) "
         "no alimentador AL-01 em 2025-03?"},
    ])
    assert result["status"] == "planned", result["response"]["message"]
    assert result["plan"]["metric_id"] == "network.equivalent_interruption_frequency"
    assert result["plan"]["window"]["start"] == "2025-03-01"
    assert result["plan"]["filters"][0]["values"] == ["AL-01"]


def test_unsupported_feeder_ranking_asks_for_a_specific_feeder():
    result = _plan("Qual alimentador teve o maior DEC em junho de 2026?")
    assert result["status"] == "needs_clarification", result
    assert result["plan"] is None
    assert result["response"]["message"].startswith(
        "Ainda não consigo comparar alimentadores para esse indicador."
    )
    assert "Informe o código de um alimentador" in result["response"]["message"]


def test_solar_confirmation_preserves_municipality_then_requests_drop_criterion():
    original = "Quantas unidades com energia solar em Olinda tiveram queda de consumo?"
    first = _plan(original, extra_coverage=[
        {"metric_id": "energy.gd_consumption_drop", "kind": "none"},
    ])
    assert first["status"] == "needs_clarification"
    second = _plan("Sim", [
        {"role": "user", "content": original},
        {"role": "assistant", "content": first["response"]["message"]},
    ], extra_coverage=[{"metric_id": "energy.gd_consumption_drop", "kind": "none"}])
    assert second["status"] == "needs_clarification", second
    assert "30%" in second["response"]["message"]
    third = _plan("Sim", [
        {"role": "user", "content": second["pending_question"]},
        {"role": "assistant", "content": second["response"]["message"]},
    ], extra_coverage=[{"metric_id": "energy.gd_consumption_drop", "kind": "none"}])
    assert third["status"] == "planned", third
    assert third["plan"]["metric_id"] == "energy.gd_consumption_drop"
    assert any(f["values"] == ["Olinda"] for f in third["plan"]["filters"])
