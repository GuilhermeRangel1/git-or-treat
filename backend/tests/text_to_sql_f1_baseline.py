"""Baseline do compilador legado sobre PostgreSQL artificial e descartável.

Não exercita prontidão, sessão, publicação real, síntese ou portal.
"""

import argparse
import hashlib
import json
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path

from app.schemas.genai_plan import LogicalReadPlan
from app.services.genai_executor import _query
from app.services.gold_catalog import load_gold_catalog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


def run(address, baseline, candidates=None):
    url = make_url(address)
    if url.get_backend_name() != "postgresql" or url.database != "text_to_sql_f1_test":
        raise ValueError(
            "Use exclusivamente PostgreSQL descartável text_to_sql_f1_test."
        )
    fixture = json.loads(
        (ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_reference.json").read_text(
            encoding="utf-8"
        )
    )
    benchmark = json.loads(
        (ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    current_hash = hashlib.sha256(
        (ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_benchmark.json").read_bytes()
    ).hexdigest()
    if baseline["benchmark_sha256"] != current_hash:
        raise ValueError("Baseline desatualizado: execute novamente o planejamento.")
    cases = {c["id"]: c for c in benchmark["cases"]}
    catalog = load_gold_catalog()
    metric = next(m for m in catalog.metrics if m.metric_id == "billing.revenue")
    source = next(s for s in metric.sources if s.table == "diagnostico_receita")
    engine = create_engine(url, hide_parameters=True)
    results = []
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                # Existence is an error; this helper never drops an existing schema.
                conn.execute(text("CREATE SCHEMA gold_v2"))
                conn.execute(
                    text("""CREATE TABLE gold_v2.diagnostico_receita (
                    competencia text NOT NULL, municipio text NOT NULL,
                    classe_consumo text NOT NULL, bandeira_tarifaria text NOT NULL,
                    receita_total_reais numeric(38,2), subgrupo_tarifario text DEFAULT 'B1',
                    possui_gd text DEFAULT 'Não')""")
                )
                conn.execute(
                    text("""INSERT INTO gold_v2.diagnostico_receita
                    (competencia,municipio,classe_consumo,bandeira_tarifaria,receita_total_reais)
                    VALUES (:competencia,:municipio,:classe_consumo,:bandeira_tarifaria,
                            :receita_total_reais)"""),
                    fixture["rows"],
                )
                conn.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                for observation in baseline["results"]:
                    case = cases[observation["id"]]
                    plan_data = observation.get("observed", {}).get("plan")
                    if candidates is None and not plan_data:
                        results.append(
                            {"id": case["id"], "outcome": "not_executed_no_plan"}
                        )
                        continue
                    savepoint = conn.begin_nested()
                    try:
                        if case.get("dataset_extension"):
                            conn.execute(
                                text("""INSERT INTO gold_v2.diagnostico_receita
                                (competencia,municipio,classe_consumo,bandeira_tarifaria,receita_total_reais)
                                VALUES (:competencia,:municipio,:classe_consumo,:bandeira_tarifaria,
                                        :receita_total_reais)"""),
                                case["dataset_extension"],
                            )
                        if candidates is not None:
                            from tests.text_to_sql_f1_candidates import (
                                evaluate_candidate,
                            )

                            payload = candidates.get(case["id"])
                            if payload is None:
                                results.append(
                                    {
                                        "id": case["id"],
                                        "outcome": "not_executed_missing_candidate",
                                    }
                                )
                                continue
                            ref = case["oracle"]
                            expected = (
                                [
                                    dict(r)
                                    for r in conn.execute(
                                        text(ref["reference_sql"]), ref["parameters"]
                                    ).mappings()
                                ]
                                if ref["reference_sql"]
                                else None
                            )
                            result = evaluate_candidate(
                                payload, case, fixture, conn, expected
                            )
                            results.append({"id": case["id"], **result})
                            continue
                        plan = LogicalReadPlan.model_validate(plan_data)
                        statement = _query(plan, source, metric)
                        compiled = statement.compile(dialect=engine.dialect)
                        rows = [dict(r) for r in conn.execute(statement).mappings()]
                        ref = case["oracle"]
                        if not ref["reference_sql"]:
                            expected = None
                        else:
                            expected = [
                                dict(r)
                                for r in conn.execute(
                                    text(ref["reference_sql"]), ref["parameters"]
                                ).mappings()
                            ]
                        # Preserve every result row; never sum monthly rows to conceal shape errors.
                        normalized = []
                        for row in rows:
                            result = {"revenue": row["value"]}
                            if case["expected"]["operation"] == "monthly_series":
                                result["competencia"] = row["period"]
                            if "municipality" in row:
                                result["municipio"] = row["municipality"]
                            if "consumption_class" in row:
                                result["classe_consumo"] = row["consumption_class"]
                            normalized.append(result)
                        matches = expected is not None and normalized == expected
                        results.append(
                            {
                                "id": case["id"],
                                "outcome": "exact_reference_match"
                                if matches
                                else "divergent",
                                "first_divergence": observation.get("first_divergence")
                                or ("compiled_result" if not matches else None),
                                "sql": str(compiled),
                                "parameters": compiled.params,
                                "observed_rows": rows,
                                "reference_rows": expected,
                                "reference_sql": ref["reference_sql"],
                            }
                        )
                    except Exception as error:  # noqa: BLE001 - evaluator records each technical failure
                        results.append(
                            {
                                "id": case["id"],
                                "outcome": "technical_error",
                                "error_type": type(error).__name__,
                            }
                        )
                    finally:
                        savepoint.rollback()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
    return {
        "boundary": (
            "captured generative candidates validated and executed on synthetic PostgreSQL"
            if candidates is not None
            else "legacy compiler _query on synthetic PostgreSQL"
        )
        + "; not production admission/executor or public end-to-end",
        "planning_benchmark_sha256": baseline["benchmark_sha256"],
        "dataset_sha256": hashlib.sha256(
            json.dumps(fixture, sort_keys=True).encode()
        ).hexdigest(),
        "denominator": len(results),
        "counts": dict(Counter(r["outcome"] for r in results)),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-observations", type=Path)
    parser.add_argument("--export-contexts", action="store_true")
    args = parser.parse_args()
    if args.export_contexts:
        from tests.text_to_sql_f1_candidates import context_for_case

        fixture = json.loads(
            (ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_reference.json").read_text(
                encoding="utf-8"
            )
        )
        benchmark_path = ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_benchmark.json"
        benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        contexts = []
        for case in benchmark["cases"]:
            context = context_for_case(case, fixture)
            contexts.append(
                {
                    "id": case["id"],
                    "context_version": context.context_version,
                    "contents": context.contents,
                }
            )
        args.output.write_text(
            json.dumps(
                {
                    "benchmark_sha256": hashlib.sha256(
                        benchmark_path.read_bytes()
                    ).hexdigest(),
                    "contexts": contexts,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"{len(contexts)} synthetic contexts exported")
        return
    capture = (
        json.loads(args.candidate_observations.read_text(encoding="utf-8"))
        if args.candidate_observations
        else None
    )
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if (
        capture is not None
        and capture["benchmark_sha256"] != baseline["benchmark_sha256"]
    ):
        raise ValueError("Captura pertence a outro benchmark.")
    report = run(
        os.environ["TEST_TEXT_TO_SQL_URL"],
        baseline,
        capture["candidates"] if capture is not None else None,
    )
    args.output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            default=lambda x: format(x, ".2f") if isinstance(x, Decimal) else str(x),
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
