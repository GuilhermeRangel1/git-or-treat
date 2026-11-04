"""Ranking com filtros extensos respeita o contrato público sem cortar observações."""

import re

from app.schemas.internal import DimensionValueCoverage, QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan, ReadFilter

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_planning_http import HEADERS, PLAN_PATH, SYNTHESIS_PATH, _application
from .test_gold_question_filters import _setup


def test_long_ranked_rows_fit_public_response_and_keep_complete_observations():
    core, request = _setup("Quais os dez municípios com maior receita em março de 2025?")
    dimensions = {
        "geography.municipality": "municipality",
        "geography.neighborhood": "neighborhood",
        "customer.consumption_class": "consumption_class",
        "tariff.subgroup": "tariff_subgroup",
        "tariff.flag": "tariff_flag",
        "generation.distributed": "distributed_generation",
    }
    # Valores artificiais dentro dos 120 caracteres aceitos pelo catálogo.
    values = {dimension: field.upper() + "X" * 95 for dimension, field in dimensions.items()}
    cities = tuple(values["geography.municipality"] + str(index) for index in range(10))
    coverage = [
        DimensionValueCoverage(
            dimension_id=dimension,
            values=cities if dimension == "geography.municipality" else (values[dimension],),
        )
        for dimension in dimensions
    ]
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert planned["status"] == "planned", planned
        original = LogicalReadPlan.model_validate(planned["plan"])
        # A borda de síntese aceita dimensões da evidência e filtros já autorizados.
        plan = original.model_copy(update={
            "dimension_ids": tuple(dimensions),
            "filters": tuple(
                ReadFilter(dimension_id=dimension, operator="eq", values=(values[dimension],))
                for dimension in dimensions if dimension != "geography.municipality"
            ),
        })
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {
                "period": "2025-03", "value": 100 - index, "unit": "R$",
                **{
                    field: cities[index] if dimension == "geography.municipality"
                    else values[dimension]
                    for dimension, field in dimensions.items()
                },
            }
            for index in range(10)
        ]
        payload = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=coverage,
        )
        response = client.post(
            SYNTHESIS_PATH, json=payload.model_dump(mode="json"), headers=HEADERS,
        )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "answered", result
    answer = result["answer"]
    assert len(answer) <= 4000
    displayed = [line for line in answer.splitlines() if line.startswith("• ")]
    assert 0 < len(displayed) < len(cities)
    count = re.search(r"Exibidos (\d+) de (\d+) resultados", answer)
    assert count is not None
    assert (int(count[1]), int(count[2])) == (len(displayed), len(cities))
    assert "tabela" in answer and "CSV" in answer
    for index, line in enumerate(displayed):
        assert cities[index] in line
        assert f"R$ {100 - index},00" in line
        assert line.endswith(")")
        assert all(value in line for dimension, value in values.items()
                   if dimension != "geography.municipality")
