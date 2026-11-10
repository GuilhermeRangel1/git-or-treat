"""Structural checks for the new, Gold v2-backed chatbot evaluation fixture.

These checks validate fixture integrity. Route, Gold, SQL-oracle and live Gemini
acceptance are covered by opt-in integration tests in
``test_genai_sql_live_gold_route.py``.
"""

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_SET_PATH = (
    REPOSITORY_ROOT / "docs" / "plans" / "CASOS_MELHORIA_GERAL_CHATBOT.json"
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = BACKEND_ROOT / "app" / "catalogs" / "gold_v2.json"
GOLD_ORACLE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "plans"
    / "GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json"
)
EXPECTED_CATEGORY_COUNTS = {
    "individual": 170,
    "ranking_comparison": 20,
    "colloquial": 10,
    "continuity": 10,
    "compound": 10,
    "safety": 10,
}
GROUP_DIMENSIONS = {
    "municipality": "geography.municipality",
    "consumption_class": "customer.consumption_class",
    "inspection_priority": "inspection.priority",
    "feeder": "network.feeder",
}


def _normalized_question(question: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", question.casefold())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def _load_inputs() -> tuple[dict, dict]:
    case_set = json.loads(CASE_SET_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return case_set, catalog


def test_case_set_has_exact_size_categories_and_unique_questions():
    case_set, _ = _load_inputs()
    cases = case_set["cases"]

    assert len(cases) == 230
    assert Counter(case["category"] for case in cases) == EXPECTED_CATEGORY_COUNTS
    assert [case["id"] for case in cases] == [
        f"MGC-{index:03d}" for index in range(1, 231)
    ]
    assert len({_normalized_question(case["question"]) for case in cases}) == 230
    assert case_set["old_596_case_set"] == "not_reused"


def test_released_gold_controls_are_part_of_the_updated_chatbot_battery():
    case_set, catalog = _load_inputs()
    extension_path = (
        BACKEND_ROOT
        / "tests"
        / "fixtures"
        / "genai_gold_released_controls_c05_c09.json"
    )
    extension = json.loads(extension_path.read_text(encoding="utf-8"))
    assert case_set["extensions"] == [{
        "id": "genai-gold-released-controls-c05-c09",
        "fixture": "../../backend/tests/fixtures/genai_gold_released_controls_c05_c09.json",
        "case_count": 6,
        "scope": "Route-validation fixture linked to the core MGC cases: CTL-001/002 to MGC-211/212, CTL-003/004 to MGC-221/222, and CTL-005/006 to existing GD cases MGC-004/005; these are test harness references, not extra cases.",
    }]
    assert len(extension["cases"]) == 6
    assert [case["id"] for case in extension["cases"]] == [
        "CTL-001", "CTL-002", "CTL-003", "CTL-004", "CTL-005", "CTL-006",
    ]
    assert [case["case_id"] for case in extension["cases"]] == [
        "MGC-211", "MGC-212", "MGC-221", "MGC-222", "MGC-004", "MGC-005",
    ]
    core_cases = {case["id"]: case for case in case_set["cases"]}
    metrics = {item["metric_id"]: item for item in catalog["metrics"]}
    expected_metric = {
        "C05": "customer.units_by_class",
        "C06": "inspection.units_by_priority",
        "C07": "inspection.units_by_priority",
        "C08": "energy.gd_units",
        "C09": "energy.gd_consumption_drop",
    }
    for case in extension["cases"]:
        metric = metrics[case["metric_id"]]
        assert case["metric_id"] in core_cases[case["case_id"]]["expected"]["metric_ids"]
        assert case["control"] in expected_metric
        assert case["metric_id"] == expected_metric[case["control"]]
        assert case["operation"] == "snapshot_total"
        assert case["unit"] == metric["unit"] == "UCs"
        assert any(
            source["table"] == case["source_table"].split(".")[-1]
            for source in metric["sources"]
        )
        assert "COUNT(" in case["reference_sql"]
        if case["control"] in {"C05", "C06", "C07"}:
            assert "COUNT(DISTINCT id_uc)" in case["reference_sql"]
    assert extension["cases"][3]["expected"].startswith("Contagem zero válida")


def test_each_gold_catalog_metric_has_ten_individual_cases():
    case_set, catalog = _load_inputs()
    counts = Counter(
        metric_id
        for case in case_set["cases"]
        if case["category"] == "individual"
        for metric_id in case["expected"].get("metric_ids", [])
    )
    catalog_metrics = {item["metric_id"] for item in catalog["metrics"]}
    assert set(counts) == catalog_metrics
    assert all(counts[metric_id] >= 10 for metric_id in catalog_metrics), counts


def test_case_capabilities_match_gold_v2_metric_contracts():
    case_set, catalog = _load_inputs()
    metrics = {metric["metric_id"]: metric for metric in catalog["metrics"]}

    for case in case_set["cases"]:
        expected = case["expected"]
        assert case["semantic_review"]["status"] == (
            "reviewed_against_f1_v12_gold_v2"
        ), case["id"]
        metric_ids = expected.get("metric_ids", [])
        unknown_metrics = set(metric_ids) - metrics.keys()
        assert not unknown_metrics, (case["id"], unknown_metrics)

        required_capabilities = sorted(
            {
                capability
                for metric_id in metric_ids
                for capability in metrics[metric_id].get(
                    "required_capability_ids", []
                )
            }
        )
        assert sorted(expected.get("required_capabilities", [])) == (
            required_capabilities
        ), case["id"]

        filter_dimensions = set(expected.get("filters", {}))
        group_dimensions = {
            GROUP_DIMENSIONS.get(dimension, dimension)
            for dimension in expected.get("group_by", [])
            if dimension != "competency"
        }
        for metric_id, candidates in expected.get("source_candidates", {}).items():
            assert metric_id in metrics, (case["id"], metric_id)
            metric = metrics[metric_id]
            sources = metric.get("sources", [])
            allowed_tables = {source["table"] for source in sources}
            assert set(candidates) <= allowed_tables, (case["id"], metric_id)

        for metric_id, reference in expected.get("gold_reference", {}).items():
            assert metric_id in metrics, (case["id"], metric_id)
            metric = metrics[metric_id]
            assert reference["unit"] == metric["unit"], case["id"]
            assert reference["aggregation"] == metric["aggregation"], (
                case["id"]
            )
            source = next(
                (
                    source
                    for source in metric.get("sources", [])
                    if source["table"] == reference["source_table"]
                ),
                None,
            )
            assert source is not None, (case["id"], metric_id)
            selected_dimensions = set(source.get("dimension_columns", {}))
            required_dimensions = filter_dimensions | {
                GROUP_DIMENSIONS.get(dimension, dimension)
                for dimension in expected.get("group_by", [])
                if dimension != "competency"
            }
            assert required_dimensions <= selected_dimensions, (
                case["id"],
                metric_id,
                reference["source_table"],
                required_dimensions - selected_dimensions,
            )

        for metric_id in metric_ids:
            metric = metrics[metric_id]
            dimensions = set(metric.get("dimension_operators", {}))
            assert filter_dimensions <= dimensions, (case["id"], metric_id)
            assert group_dimensions <= dimensions, (case["id"], metric_id)
            assert expected.get("units", {}).get(metric_id, metric["unit"]) == (
                metric["unit"]
            ), (case["id"], metric_id)
            if "competency" in expected.get("group_by", []):
                assert metric.get("granularities"), (case["id"], metric_id)


def test_cases_reflect_the_current_f1_operation_contract():
    case_set, _ = _load_inputs()
    cases = {case["id"]: case for case in case_set["cases"]}

    for case in case_set["cases"]:
        expected = case["expected"]
        metric_ids = set(expected.get("metric_ids", []))
        if (
            case["category"] == "individual"
            and expected.get("operation") in {"total", "average"}
            and metric_ids & {"service.attendance", "service.satisfaction"}
        ):
            assert re.fullmatch(r"\d{4}-\d{2}", expected["period"]), (
                case["id"],
                expected["period"],
            )

    continuity = cases["MGC-006"]
    assert continuity["expected"]["operation"] == "weighted_continuity"
    assert continuity["expected"]["group_by"] == []
    assert continuity["expected"]["filters"] == {
        "network.feeder": "ALM-ABR-001"
    }
    assert "ALM-ABR-001" in continuity["question"]
    assert continuity["expected"]["status"] == (
        "conditional_on_authorization_and_readiness_no_certified_result"
    )
    formula = continuity["expected"]["calculation_reference"]
    assert formula["denominator_column"] == "total_ucs_alimentador"
    assert formula["denominator_rule"] == "count_once_per_feeder"
    assert formula["required_complete_months"] == 6
    assert set(formula["numerator_columns"].values()) == {
        "duracao_total_interrupcoes_horas",
        "frequencia_total_interrupcoes",
    }
    route_observation = continuity["route_observation"]
    assert route_observation["profile"] == "admin"
    assert route_observation["pre_fix"]["combined_dec_fec"]["status"] == (
        "needs_clarification"
    )
    assert route_observation["post_fix"]["combined_dec_fec"]["status"] == "answered"
    assert route_observation["post_fix"]["independent_reference_reconciled"] is True
    assert route_observation["post_fix"]["authorization_and_readiness_preserved"] is True
    assert route_observation["acceptance"] == (
        "passed_expected_weighted_window_behavior_with_uncertified_notice"
    )
    assert route_observation["credential_recorded"] is False

    mandatory = cases["MGC-015"]["expected"]
    assert mandatory["status"] == "compare_and_disclose_unavailable_decomposition"
    assert mandatory["full_acceptance_pending"] is True
    assert any("decomposição" in note.casefold() for note in mandatory["notes"])
    values = mandatory["reference_values"]
    assert values["population"]["municipalities_with_both_complete_windows"] == 14
    assert [row["municipality"] for row in values["ranking_top_3"]] == [
        "JABOATÃO DOS GUARARAPES",
        "RECIFE",
        "OLINDA",
    ]
    assert len(values["top_3_by_class_deltas"]) == 15
    assert values["price_volume_decomposition"]["matching_window_rows"] == 0
    assert mandatory["diagnostic_acceptance"].endswith(
        "without_causal_attribution"
    )

    zero_denominator = cases["MGC-041"]["expected"]
    assert zero_denominator["status"] == (
        "answered_as_unavailable_when_denominator_is_zero"
    )
    assert zero_denominator["reference_values"]["qtd_ucs_com_leitura"] == 0
    assert zero_denominator["reference_values"]["expected_value"] is None

    for case_id, metric_id in {
        "MGC-203": "service.attendance",
        "MGC-204": "service.satisfaction",
    }.items():
        case = cases[case_id]
        expected = case["expected"]
        assert metric_id in expected["metric_ids"]
        assert expected["status"] == "unsupported_no_SQL"
        assert expected["sql_must_be_absent"] is True
        assert any("mensal" in note.casefold() for note in expected["notes"])

    multi_feeder = cases["MGC-210"]["expected"]
    assert multi_feeder["metric_ids"] == [
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    ]
    assert multi_feeder["group_by"] == ["feeder"]
    assert multi_feeder["status"] == "unsupported_no_SQL"
    assert multi_feeder["sql_must_be_absent"] is True


def test_individual_cases_cover_more_than_city_class_and_month_variants():
    case_set, _ = _load_inputs()
    individual = [
        case for case in case_set["cases"] if case["category"] == "individual"
    ]
    dimensions = {
        dimension
        for case in individual
        for dimension in case["expected"].get("filters", {})
    }
    assert {
        "geography.neighborhood",
        "tariff.subgroup",
        "tariff.flag",
        "generation.distributed",
    } <= dimensions

    for case in individual:
        assert case["turns"] == [case["question"]], case["id"]


def test_negative_cases_require_no_sql_and_percentage_ranking_is_not_admitted():
    case_set, _ = _load_inputs()
    cases = {case["id"]: case for case in case_set["cases"]}
    no_sql_statuses = {
        "unsupported_out_of_domain",
        "unsupported_no_SQL",
        "needs_clarification_without_SQL",
        "blocked_no_temporal_coverage_without_SQL",
        "unsupported_without_SQL",
        "unsupported_join_without_SQL",
        "denied_sensitive_data_without_SQL",
    }
    for case in case_set["cases"]:
        if case["expected"]["status"] in no_sql_statuses:
            assert case["expected"].get("sql_must_be_absent") is True, case["id"]

    percent_ranking = cases["MGC-162"]["expected"]
    assert percent_ranking["status"] == "unsupported_no_SQL"
    assert percent_ranking["sql_must_be_absent"] is True
    assert percent_ranking["ranking"]["measure"] == "period_percent_delta"


def test_colloquial_cases_encode_the_intended_analytical_operation():
    case_set, _ = _load_inputs()
    cases = {case["id"]: case for case in case_set["cases"]}
    expected_operations = {
        "MGC-175": "total",
        "MGC-176": "total",
        "MGC-177": "snapshot_total",
        "MGC-178": "ratio_of_sums",
        "MGC-179": "ratio_of_sums",
        "MGC-180": "ratio_of_sums",
        "MGC-181": "total",
        "MGC-182": "average",
        "MGC-183": "ranking",
        "MGC-184": "weighted_continuity",
    }
    assert {
        case_id: cases[case_id]["expected"]["operation"]
        for case_id in expected_operations
    } == expected_operations
    assert cases["MGC-183"]["expected"]["ranking"]["measure"] == (
        "absolute_delta"
    )
    assert cases["MGC-184"]["expected"]["calculation_reference"][
        "denominator_rule"
    ] == "count_once_per_feeder"


def test_diagnostic_and_holdout_splits_keep_semantic_families_together():
    case_set, _ = _load_inputs()
    cases = case_set["cases"]
    assert case_set["split_plan"]["status"] == "frozen_family_disjoint"
    assert case_set["split_plan"]["counts"]["diagnostic"] == 186
    assert case_set["split_plan"]["counts"]["holdout"] == 44

    category_holdout_counts = Counter(
        case["category"] for case in cases if case["split"] == "holdout"
    )
    assert category_holdout_counts == {
        "individual": 31,
        "ranking_comparison": 5,
        "colloquial": 2,
        "continuity": 2,
        "compound": 2,
        "safety": 2,
    }

    split_by_family = {}
    for case in cases:
        assert case["split"] in {"diagnostic", "holdout"}, case["id"]
        family_id = case["family_id"]
        previous = split_by_family.setdefault(family_id, case["split"])
        assert previous == case["split"], (family_id, case["id"])

    by_id = {case["id"]: case for case in cases}
    for first, second in [
        ("MGC-001", "MGC-175"),
        ("MGC-006", "MGC-184"),
        ("MGC-007", "MGC-182"),
        ("MGC-010", "MGC-183"),
        ("MGC-012", "MGC-185"),
        ("MGC-008", "MGC-181"),
    ]:
        assert by_id[first]["family_id"] == by_id[second]["family_id"]
        assert by_id[first]["split"] == by_id[second]["split"]


def test_independent_gold_oracles_cover_numeric_cases_and_derived_results():
    case_set, _ = _load_inputs()
    report = json.loads(GOLD_ORACLE_PATH.read_text(encoding="utf-8"))
    fixture_cases = {case["id"]: case for case in case_set["cases"]}
    report_cases = {case["case_id"]: case for case in report["cases"]}

    assert set(report_cases) == set(fixture_cases)
    assert report["snapshot"] == "GOLD_20261103T173853Z_76c37784"
    assert report["counts"] == {
        "fixture_cases": 230,
        "cases_with_independent_sql_results": 219,
        "state_only_no_sql_cases": 11,
        "metric_period_queries": 257,
        "query_result_rows": 2001,
        "empty_query_results": 0,
        "null_numeric_results": 1,
    }

    for case_id, case in fixture_cases.items():
        reported = report_cases[case_id]
        if case["expected"].get("sql_must_be_absent"):
            assert reported["reference_status"] == "state_only_no_sql_expected", (
                case_id
            )
            assert reported["metric_references"] == [], case_id
        else:
            assert reported["reference_status"] == "independent_sql_executed", (
                case_id
            )
            for metric in reported["metric_references"]:
                for period in metric["periods"]:
                    assert period["rows"], (case_id, metric["metric_id"])

    expected_top3 = fixture_cases["MGC-015"]["expected"]["reference_values"][
        "ranking_top_3"
    ]
    observed_top3 = report_cases["MGC-015"]["derived_rankings"][0]["rows"][:3]
    assert [row["municipio"] for row in observed_top3] == [
        row["municipality"] for row in expected_top3
    ]
    assert [row["delta"] for row in observed_top3] == [
        row["consumption_delta_kwh"] for row in expected_top3
    ]
    assert len(report_cases["MGC-015"]["derived_rankings"][0]["rows"]) == 14
    revenue_rows = report_cases["MGC-015"]["metric_references"][1][
        "period_comparison"
    ]
    class_deltas = fixture_cases["MGC-015"]["expected"]["reference_values"][
        "top_3_by_class_deltas"
    ]
    actual_class_deltas = {
        (row["municipio"], row["classe_consumo"]): row["delta"]
        for row in revenue_rows
    }
    for row in class_deltas:
        assert math.isclose(
            actual_class_deltas[(row["municipality"], row["class"])],
            row["revenue_delta_brl"],
            abs_tol=0.000001,
        )
    for expected in expected_top3:
        revenue_delta = sum(
            value
            for (municipality, _), value in actual_class_deltas.items()
            if municipality == expected["municipality"]
        )
        assert math.isclose(
            revenue_delta,
            expected["revenue_delta_brl"],
            abs_tol=0.000001,
        )

    weighted_values = report_cases["MGC-184"]["derived_calculations"][0][
        "values"
    ]
    assert weighted_values["competencias"] == 6
    assert weighted_values["denominador_min"] == weighted_values[
        "denominador_max"
    ] == fixture_cases["MGC-006"]["expected"]["reference_values"][
        "denominator"
    ]
    assert weighted_values["dec_ponderado_horas_por_uc"] == (
        fixture_cases["MGC-006"]["expected"]["reference_values"]["dec_value"]
    )
    assert weighted_values["fec_ponderado_interrupcoes_por_uc"] == (
        fixture_cases["MGC-006"]["expected"]["reference_values"]["fec_value"]
    )
