"""Perguntas naturais que precisam chegar ao plano e à resposta visuais reais."""

import pytest

from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_planning_http import HEADERS, PLAN_PATH, SYNTHESIS_PATH, _application
from .test_gold_question_filters import _setup


@pytest.mark.parametrize("question,group,ordered", [
    ("Como evoluiu o consumo medido em Recife, mês a mês, de janeiro a março de 2025?", (), False),
    ("Mostre a receita por mês em Recife de janeiro a março de 2025.", (), False),
    ("Quais municípios tiveram maior consumo medido em março de 2025?",
     ("geography.municipality",), True),
    ("Mostre o consumo medido por classe em Recife em março de 2025.",
     ("customer.consumption_class",), False),
    ("Como a receita faturada de Olinda se divide entre as classes em junho de 2026?",
     ("customer.consumption_class",), False),
    ("Distribua o consumo medido entre os municípios em março de 2025.",
     ("geography.municipality",), False),
])
def test_natural_visual_question_preserves_period_groups_and_scope(question, group, ordered):
    core, request = _setup(question)
    if "2026" in question:
        payload = request.model_dump(mode="json")
        for coverage in payload["temporal_coverage"]:
            coverage["competencies"] = ["2026-06"]
        request = type(request).model_validate(payload)
    with InProcessClient(_application(core)) as client:
        result = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert result["status"] == "planned", result
        plan = result["plan"]
        assert tuple(plan["group_by_dimension_ids"]) == group
        assert (plan["order"] is not None) == ordered
        if not group:
            assert plan.get("comparison_periods") is None
            assert plan["window"]["start"] == "2025-01-01"
            assert plan["window"]["end"] == "2025-03-31"
        elif ordered:
            assert plan["order"]["direction"] == "desc"
        if "Recife" in question:
            assert any(f["values"] == ["Recife"] for f in plan["filters"])
        denied = request.model_dump(mode="json")
        denied["access_scope"]["allowed_dimension_ids"].remove("geography.municipality")
        denied["dimension_value_coverage"] = [
            item for item in denied["dimension_value_coverage"]
            if item["dimension_id"] != "geography.municipality"
        ]
        stopped = client.post(PLAN_PATH, json=denied, headers=HEADERS).json()
        assert stopped["status"] in {"refused", "needs_clarification"}, stopped
        assert stopped["plan"] is None


def test_comparison_uses_readable_numbers_and_months_without_raw_derived_periods():
    core, request = _setup("Compare o consumo medido em Recife entre janeiro e março de 2025.")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {"period": month, "value": value, "unit": "kWh"}
            for month, value in [("2025-01", 7622382), ("2025-03", 5353512)]
        ]
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
        )
        result = client.post(SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"),
                             headers=HEADERS).json()
    assert result["status"] == "answered", result
    assert "7.622.382 kWh em janeiro de 2025" in result["answer"]
    assert "5.353.512 kWh em março de 2025" in result["answer"]
    assert "-2.268.870 kWh (-29,77%)" in result["answer"]
    assert "Variação absoluta de 2025" not in result["answer"]


def test_group_summary_uses_all_authorized_rows_not_the_models_first_row():
    core, request = _setup("Distribua a receita faturada por município em março de 2025.")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {"period": "2025-03", "value": value, "unit": "R$", "municipality": city}
            for city, value in [("Olinda", 100), ("Recife", 300)]
        ]
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=request.dimension_value_coverage,
        )
        result = client.post(SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"),
                             headers=HEADERS).json()
    assert result["status"] == "answered", result
    assert "2 grupos retornados" in result["answer"]
    assert "R$ 300,00" in result["answer"]
    assert "Recife" in result["answer"]
    assert "•" not in result["answer"]


def test_group_distribution_does_not_hide_an_incomplete_date_range():
    core, request = _setup("Distribua a receita entre as classes desde março de 2025.")
    with InProcessClient(_application(core)) as client:
        result = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert result["status"] == "needs_clarification"
    assert result.get("plan") is None
