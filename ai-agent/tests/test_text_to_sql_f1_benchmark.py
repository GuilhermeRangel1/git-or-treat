"""Cross-check manual SQL against Decimal calculation under counterfactual bases."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from .test_text_to_sql_f1_reference import (
    DATA,
    connection,  # noqa: F401, F811
)
from .text_to_sql_f1_baseline import compare_plan
from .text_to_sql_f1_oracle import reference_rows

CASES = [c for c in DATA["cases"] if c["reference_sql"]]
MUTATIONS = [
    {
        "competencia": "2026-06",
        "municipio": "Recife",
        "classe_consumo": "RESIDENCIAL",
        "bandeira_tarifaria": "CONTRA_EXTRA_GRAIN",
        "receita_total_reais": "17.23",
    },
    {
        "competencia": "2026-06",
        "municipio": "Olinda",
        "classe_consumo": "COMERCIAL",
        "bandeira_tarifaria": "CONTRA_OTHER_CITY",
        "receita_total_reais": "99999.99",
    },
    {
        "competencia": "2026-07",
        "municipio": "Recife",
        "classe_consumo": "COMERCIAL",
        "bandeira_tarifaria": "CONTRA_OUTSIDE",
        "receita_total_reais": "88888.88",
    },
    {
        "competencia": "2025-06",
        "municipio": "Recife",
        "classe_consumo": "COMERCIAL",
        "bandeira_tarifaria": "CONTRA_BASELINE",
        "receita_total_reais": "-33.33",
    },
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_decimal_oracle_agrees_with_frozen_literal_reference(case):
    assert reference_rows(case["id"], DATA["rows"]) == case["expected_rows"]


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda r: r["bandeira_tarifaria"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_manual_sql_matches_independent_calculation_on_counterfactual(
    connection,  # noqa: F811
    case,
    mutation,
):
    savepoint = connection.begin_nested()
    try:
        connection.execute(
            text("""INSERT INTO gold_v2.diagnostico_receita
            (competencia, municipio, classe_consumo, bandeira_tarifaria, receita_total_reais)
            VALUES (:competencia, :municipio, :classe_consumo,
                    :bandeira_tarifaria, :receita_total_reais)"""),
            mutation,
        )
        actual = [
            {k: format(v, ".2f") if isinstance(v, Decimal) else v for k, v in row.items()}
            for row in connection.execute(
                text(case["reference_sql"]), case["parameters"]
            ).mappings()
        ]
        assert actual == reference_rows(case["id"], DATA["rows"] + [mutation])
    finally:
        savepoint.rollback()


def test_evaluator_detects_lost_filter_and_does_not_invent_execution_success():
    benchmark = json.loads(
        (Path(__file__).parent / "fixtures/text_to_sql_f1_benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    expected = benchmark["cases"][0]["expected"]
    plan = {
        "metric_id": "billing.revenue",
        "unit": "R$",
        "group_by_dimension_ids": [],
        "order": None,
        "filters": [],
        "window": {"start": "2026-06-01", "end": "2026-06-30"},
    }
    differences, unmeasured = compare_plan(expected, {"status": "planned", "plan": plan})
    assert differences == ["filters"]
    assert "numbers" in unmeasured
    assert "aggregation_shape" in unmeasured
    # An unrelated huge city must not alter Recife's total.
    assert reference_rows("F1-01", DATA["rows"]) == reference_rows(
        "F1-01", DATA["rows"] + [MUTATIONS[1]]
    )
    assert reference_rows("F1-01", DATA["rows"]) != reference_rows(
        "F1-01", DATA["rows"] + [MUTATIONS[0]]
    )


def test_evaluator_rejects_comparison_of_months_for_an_interval_total():
    benchmark = json.loads(
        (Path(__file__).parent / "fixtures/text_to_sql_f1_benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    expected = next(c["expected"] for c in benchmark["cases"] if c["id"] == "F1-03-V0")
    observed = {
        "status": "planned",
        "plan": {
            "metric_id": "billing.revenue",
            "unit": "R$",
            "group_by_dimension_ids": [],
            "order": None,
            "filters": [{"dimension_id": "geography.municipality", "values": ["Recife"]}],
            "window": {"start": "2026-01-01", "end": "2026-06-30"},
            "comparison_periods": ["2026-01", "2026-06"],
        },
    }
    assert "operation" in compare_plan(expected, deepcopy(observed))[0]


def test_freeze_and_split_prevent_silent_oracle_changes():
    import hashlib

    root = Path(__file__).resolve().parents[2]
    lock = json.loads(
        (root / "ai-agent/tests/fixtures/text_to_sql_f1_freeze.json").read_text(encoding="utf-8")
    )
    for relative, expected_hash in lock["files"].items():
        contents = (root / relative).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(contents).hexdigest() == expected_hash
    benchmark = json.loads(
        (root / "ai-agent/tests/fixtures/text_to_sql_f1_benchmark.json").read_text(encoding="utf-8")
    )
    reserve = json.loads(
        (root / "ai-agent/tests/fixtures/text_to_sql_f1_authorial_reserve.json").read_text(
            encoding="utf-8"
        )
    )
    assert len({c["id"] for c in benchmark["cases"]}) == len(benchmark["cases"])
    assert not {c["question"] for c in benchmark["cases"]} & {
        c["question"] for c in reserve["cases"]
    }
    assert all(c["split"] == "development" for c in benchmark["cases"])
    assert len(reserve["cases"]) == 8


def test_missing_comparison_group_is_not_replaced_by_zero(connection):  # noqa: F811
    case = next(c for c in DATA["cases"] if c["id"] == "F1-04")
    rows = [
        dict(r)
        for r in connection.execute(
            text(case["reference_sql"]), {"municipality": "Olinda"}
        ).mappings()
    ]
    assert rows == [{"year": "2026", "revenue": Decimal("480.00")}]
    assert not any(row["year"] == "2025" for row in rows)
    # A difference requires two observed windows; absence cannot become zero.
    assert len(rows) != 2
