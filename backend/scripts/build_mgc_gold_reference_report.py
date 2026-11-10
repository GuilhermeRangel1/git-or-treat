"""Build the checked-in MGC Gold oracle report from read-only psql output."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "docs/plans/CASOS_MELHORIA_GERAL_CHATBOT.json"
REPORT_PATH = ROOT / "docs/plans/GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json"
SQL_PATH = ROOT / "docs/plans/REFERENCIAS_GOLD_MGC_230.sql"
RANKINGS = {
    "MGC-157": "descending",
    "MGC-158": "descending",
    "MGC-166": "ascending",
    "MGC-168": "descending",
    "MGC-173": "ascending",
}
COMPARISON_RANKINGS = {
    "MGC-010": "greatest_decline_first",
    "MGC-015": "greatest_decline_first",
    "MGC-160": "greatest_increase_first",
    "MGC-165": "greatest_absolute_change_first",
    "MGC-167": "greatest_increase_first",
    "MGC-183": "greatest_decline_first",
    "MGC-195": "greatest_decline_first",
}


def read_psql_output(path: Path) -> dict[tuple[str, str, str], list[dict]]:
    results = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        case_id, metric_id, period, payload = line.split("|", 3)
        key = (case_id, metric_id, period)
        if key in results:
            raise ValueError(f"duplicate psql output key: {key}")
        results[key] = json.loads(payload)
    return results


def stable_key(row: dict, *, excluded: set[str]) -> tuple:
    return tuple(sorted((key, value) for key, value in row.items() if key not in excluded))


def period_comparison(left: dict, right: dict, left_label: str, right_label: str) -> list[dict]:
    excluded = {"valor", "numerador", "denominador", "meses_dec_validos", "meses_fec_validos"}

    def keyed(rows: list[dict]) -> dict[tuple, object]:
        output = {}
        for row in rows:
            key = stable_key(row, excluded=excluded)
            if key in output:
                raise ValueError(f"duplicate group key in period comparison: {key}")
            output[key] = row.get("valor")
        return output

    left_values, right_values = keyed(left["rows"]), keyed(right["rows"])
    compared = []
    for key in sorted(left_values.keys() | right_values.keys(), key=str):
        before, after = left_values.get(key), right_values.get(key)
        delta = Decimal(str(after)) - Decimal(str(before)) if before is not None and after is not None else None
        baseline = Decimal(str(before)) if before is not None else None
        percent = delta / baseline * 100 if delta is not None and baseline else None
        row = dict(key)
        row.update(
            {
                f"valor_{left_label}": before,
                f"valor_{right_label}": after,
                "delta": float(delta) if delta is not None else None,
                "delta_percent": float(percent) if percent is not None else None,
            }
        )
        compared.append(row)
    return compared


def add_derived_results(case: dict, query_results: dict) -> None:
    case_id = case["case_id"]
    calculations = []
    weighted = query_results.get((case_id, "network.weighted_continuity_period", "weighted_period"))
    if weighted is not None:
        if len(weighted) != 1 or weighted[0]["competencias"] != 6:
            raise ValueError(f"incomplete DEC/FEC weighted oracle for {case_id}")
        calculations.append(
            {
                "calculation_id": "weighted_continuity_period",
                "source_table": "indicadores_dec_fec",
                "period": ["2026-01", "2026-06"],
                "formula": "soma dos numeradores mensais válidos / denominador positivo e constante do alimentador; exigir as seis competências",
                "values": weighted[0],
                "certifies_coverage": False,
            }
        )

    for metric in case["metric_references"]:
        periods = metric["periods"]
        if len(periods) != 2:
            continue
        first, second = periods
        if {first["label"], second["label"]} == {"recent", "reference"}:
            before = next(period for period in periods if period["label"] == "reference")
            after = next(period for period in periods if period["label"] == "recent")
            before_label, after_label = "reference", "recent"
        else:
            before, after = first, second
            before_label, after_label = first["label"], second["label"]
        metric["period_comparison"] = period_comparison(before, after, before_label, after_label)

    if calculations:
        case["derived_calculations"] = calculations

    rankings = []
    direction = RANKINGS.get(case_id)
    if direction:
        metric = case["metric_references"][0]
        rows = metric["periods"][0]["rows"]
        rows = sorted(
            rows,
            key=lambda row: (
                row.get("valor") is None,
                row.get("valor") if direction == "ascending" else -(row.get("valor") or 0),
                tuple(str(row.get(key, "")) for key in sorted(row) if key != "valor"),
            ),
        )
        rankings.append({"metric_id": metric["metric_id"], "period": metric["periods"][0]["label"], "direction": direction, "rows": rows})

    order = COMPARISON_RANKINGS.get(case_id)
    if order:
        consumption = next((m for m in case["metric_references"] if m["metric_id"] == "energy.consumption"), None)
        if consumption and len(consumption["periods"]) == 2:
            rows = consumption["period_comparison"]
            if case_id in {"MGC-015", "MGC-195"}:
                municipalities = {}
                for row in rows:
                    municipality = row.get("municipio")
                    entry = municipalities.setdefault(municipality, {"municipio": municipality, "valor_reference": 0, "valor_recent": 0})
                    entry["valor_reference"] += row.get("valor_reference") or 0
                    entry["valor_recent"] += row.get("valor_recent") or 0
                rows = []
                for entry in municipalities.values():
                    entry["delta"] = entry["valor_recent"] - entry["valor_reference"]
                    entry["delta_percent"] = entry["delta"] / entry["valor_reference"] * 100 if entry["valor_reference"] else None
                    rows.append(entry)
                rows.sort(key=lambda row: (row["delta"], row["municipio"]))
                rankings.append({"metric_id": "energy.consumption", "periods": ["reference", "recent"], "group_by": ["municipio"], "order": order, "rows": rows})
            else:
                if order == "greatest_increase_first":
                    rows = sorted(rows, key=lambda row: (-(row["delta"] if row["delta"] is not None else float("-inf")), str(row)))
                elif order == "greatest_absolute_change_first":
                    rows = sorted(rows, key=lambda row: (-abs(row["delta"] or 0), str(row)))
                else:
                    rows = sorted(rows, key=lambda row: (row["delta"] if row["delta"] is not None else float("inf"), str(row)))
                rankings.append({"metric_id": "energy.consumption", "periods": [p["label"] for p in consumption["periods"]], "order": order, "rows": rows})
    if rankings:
        case["derived_rankings"] = rankings


def build(input_path: Path) -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    fixture_by_id = {case["id"]: case for case in fixture["cases"]}
    results = read_psql_output(input_path)
    referenced_keys = set()

    for case in report["cases"]:
        case_id = case["case_id"]
        for metric in case["metric_references"]:
            for period in metric["periods"]:
                key = (case_id, metric["metric_id"], period["label"])
                if key not in results:
                    raise ValueError(f"missing SQL result for {key}")
                period["rows"] = results[key]
                referenced_keys.add(key)
        add_derived_results(case, results)
        case["reference_status"] = (
            "independent_sql_executed"
            if any((case_id, m["metric_id"], p["label"]) in results for m in case["metric_references"] for p in m["periods"])
            else "state_only_no_sql_expected"
        )

    derived_keys = {key for key in results if key[1] == "network.weighted_continuity_period"}
    if derived_keys != {("MGC-184", "network.weighted_continuity_period", "weighted_period")}:
        raise ValueError(f"unexpected derived SQL keys: {derived_keys}")
    if referenced_keys | derived_keys != set(results):
        raise ValueError("psql output contains results not represented in the report")
    if any(case_id not in fixture_by_id for case_id, _, _ in results):
        raise ValueError("SQL output contains unknown fixture case")

    query_rows = [row for payload in results.values() for row in payload]
    report["counts"] = {
        "fixture_cases": len(report["cases"]),
        "cases_with_independent_sql_results": sum(c["reference_status"] == "independent_sql_executed" for c in report["cases"]),
        "state_only_no_sql_cases": sum(c["reference_status"] == "state_only_no_sql_expected" for c in report["cases"]),
        "metric_period_queries": len(results),
        "query_result_rows": len(query_rows),
        "empty_query_results": sum(not payload for payload in results.values()),
        "null_numeric_results": sum(1 for row in query_rows if any(row.get(key) is None for key in ("valor", "dec_ponderado_horas_por_uc", "fec_ponderado_interrupcoes_por_uc") if key in row)),
    }
    report["execution"] = "PostgreSQL transaction READ ONLY; independent aggregate SQL per metric/source; deterministic result ordering; comparison deltas and rankings derived from query results; no Gemini or F1 route calls"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("psql_output", type=Path, help="raw -A -t psql output from REFERENCIAS_GOLD_MGC_230.sql")
    args = parser.parse_args()
    report = build(args.psql_output)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
