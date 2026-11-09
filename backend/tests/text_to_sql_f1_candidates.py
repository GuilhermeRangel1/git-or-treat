"""Adaptador offline de candidatos: valida SQL e mede intenção contra o oráculo.

Usado somente pelo benchmark em banco artificial; não concede admissão em produção.
"""

from calendar import monthrange

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_semantics import review_sql_semantics

DIMENSIONS = {
    "geography.municipality": "municipality",
    "customer.consumption_class": "consumption_class",
}


def request_for_case(case, fixture):
    return QuestionPlanRequest.model_validate(
        {
            "question": case["question"],
            "context": case["context"],
            "remaining_timeout_ms": 30000,
            "batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
            "access_scope": {
                "caller_ref": "session:" + "a" * 64,
                "profile_id": "v-energy-grid-360-gold",
                "source_id": "gold.local",
                "allowed_operations": ["read"],
                "allowed_metric_ids": ["billing.revenue"],
                "allowed_dimension_ids": list(DIMENSIONS),
            },
            "temporal_coverage": [
                {
                    "metric_id": "billing.revenue",
                    "kind": "monthly",
                    "competencies": case.get("coverage", fixture["coverage"]),
                }
            ],
            "dimension_value_coverage": [
                {
                    "dimension_id": "geography.municipality",
                    "values": sorted({r["municipio"] for r in fixture["rows"]}),
                },
                {
                    "dimension_id": "customer.consumption_class",
                    "values": ["COMERCIAL", "RESIDENCIAL"],
                },
            ],
        }
    )


def context_for_case(case, fixture):
    return build_sql_generation_context(request_for_case(case, fixture))


def intent_differences(candidate, expected):
    mapping = {
        "planned": "sql_candidate",
        "refused": "unsupported",
        "needs_clarification": "needs_clarification",
    }
    differences = []
    if candidate.status != mapping[expected["status"]]:
        differences.append("status")
    if candidate.interpretation is None or expected["status"] != "planned":
        return differences
    intent = candidate.interpretation
    if intent.operation != expected["operation"]:
        differences.append("operation")
    actual_periods = [
        (p.start.strftime("%Y-%m"), p.end.strftime("%Y-%m")) for p in intent.periods
    ]
    if actual_periods != [tuple(p) for p in expected["periods"]]:
        differences.append("periods")
    if any(
        p.start.day != 1 or p.end.day != monthrange(p.end.year, p.end.month)[1]
        for p in intent.periods
    ):
        differences.append("calendar_boundaries")
    filters = {f.dimension_id: list(f.values) for f in intent.filters}
    expected_filters = expected["filters"]
    if filters != expected_filters:
        differences.append("filters")
    groups = [DIMENSIONS[k] for k in expected["group_by_dimension_ids"]]
    if expected["operation"] == "monthly_series":
        groups = ["competency"]
    if list(intent.group_by) != groups:
        differences.append("group_by")
    if expected["operation"] == "ranking" and (
        intent.ranking_limit != expected["limit"] or intent.ranking_direction != "desc"
    ):
        differences.append("ranking")
    return differences


def evaluate_candidate(payload, case, fixture, connection, reference_rows):
    candidate = SqlGenerationCandidate.model_validate(payload)
    differences = intent_differences(candidate, case["expected"])
    if candidate.status != "sql_candidate":
        return {
            "outcome": "divergent" if differences else "expected_non_query_state",
            "differences": differences,
            "observed_status": candidate.status,
        }
    reviewed = review_sql_semantics(candidate, request_for_case(case, fixture))
    rows = [
        dict(r)
        for r in connection.exec_driver_sql(
            reviewed.canonical_sql, dict(reviewed.parameter_items)
        ).mappings()
    ]
    if candidate.interpretation.operation == "comparison":
        values = {r["year"]: r["revenue"] for r in reference_rows or []}
        expected = {
            "period_0_total": values.get("2026"),
            "period_1_total": values.get("2025"),
        }
        expected["period_0_minus_period_1"] = (
            values["2026"] - values["2025"] if set(values) == {"2025", "2026"} else None
        )
        actual = [
            {meaning: row[name] for name, meaning in reviewed.measure_semantics}
            for row in rows
        ]
        numeric_match = actual == [expected]
    else:
        # Output aliases are arbitrary. Bind dimension aliases to the reviewed source columns.
        from sqlglot import exp, parse_one

        tree = parse_one(candidate.sql, read="postgres")
        aliases = {
            output.alias: output.this.name
            for output in tree.expressions
            if type(output.this) is exp.Column
        }
        measure = next(c.name for c in candidate.result_columns if c.role == "measure")
        actual = [
            {
                "revenue": row[measure],
                **{source: row[alias] for alias, source in aliases.items()},
            }
            for row in rows
        ]
        numeric_match = reference_rows is not None and actual == reference_rows
    if not numeric_match:
        differences.append("compiled_result")
    return {
        "outcome": "divergent" if differences else "exact_reference_match",
        "differences": differences,
        "first_divergence": "interpretation"
        if any(d != "compiled_result" for d in differences)
        else "compiled_result"
        if differences
        else None,
        "sql": reviewed.canonical_sql,
        "observed_rows": rows,
        "reference_rows": reference_rows,
    }
