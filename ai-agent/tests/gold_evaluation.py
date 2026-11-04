"""Avalia plano e síntese Gold pelo HTTP existente, com agregados artificiais."""

import json
import re
from decimal import Decimal
from pathlib import Path

from app.providers.protocols import ModelProviderUnavailable
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus, GoldEvidenceQuality
from app.schemas.internal import QuestionSynthesisRequest
from app.schemas.read_plan import LogicalReadPlan

from .conftest import FakeModelAdapter, InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_planning_http import HEADERS, PLAN_PATH, SYNTHESIS_PATH, _application
from .test_gold_question_filters import _setup

DATASET_PATH = Path(__file__).parent / "fixtures" / "gold_evaluation_numeric.json"


def evaluate_gold_case(case, *, adapter=None):
    if case.get("mode") == "provider_failure":
        adapter = FakeModelAdapter(error=ModelProviderUnavailable("artificial failure"))
    core, request = _setup(case["question"], model_adapter=adapter)
    payload = request.model_dump(mode="json")
    payload["context"] = case["context"]
    if case.get("mode") == "denied":
        payload["access_scope"]["allowed_dimension_ids"].remove("geography.municipality")
        payload["dimension_value_coverage"] = [
            row for row in payload["dimension_value_coverage"]
            if row["dimension_id"] != "geography.municipality"
        ]
    with InProcessClient(_application(core)) as client:
        planned = client.post(PLAN_PATH, json=payload, headers=HEADERS)
        body = planned.json()
        checks = {"http": planned.status_code == 200}
        if body.get("plan"):
            plan = LogicalReadPlan.model_validate(body["plan"])
            checks["interpretation"] = (
                plan.metric_id == case["metric"] and plan.unit == case["unit"]
            )
            checks["filters"] = plan.model_dump(mode="json")["filters"] == case["expected_filters"]
            checks["period"] = all(
                plan.window.model_dump(mode="json").get(key) == value
                for key, value in case["expected_window"].items()
            )
            checks["authorization"] = plan.operation == "read"
            values = [Decimal(str(value)) for value in case["inputs"]]
            value = sum(values) if case["aggregation"] == "sum" else values[0]
            lookup = _lookup(plan, batch_ref=request.batch_ref, value=float(value))
            lookup.evidence.records = [{"period": "2025-03", "value": float(value),
                                        "unit": plan.unit}]
            for item in plan.filters:
                field = {"network.feeder": "feeder", "geography.municipality": "municipality"}.get(
                    item.dimension_id
                )
                if field:
                    lookup.evidence.records[0][field] = item.values[0]
            if case.get("mode") == "observed":
                lookup.evidence.provenance = lookup.evidence.provenance.model_copy(update={
                    "quality": GoldEvidenceQuality(
                        readiness_version="gold-readiness-v2", batch_ref=request.batch_ref,
                        lot_state="partial", quality_mode="observed_uncertified",
                        observed_capability_ids=("interrupcoes.dec_fec",),
                        observed_periods=("2025-03",),
                    )
                })
            if case.get("mode") == "empty":
                lookup = EvidenceLookupResult(status=EvidenceLookupStatus.NO_EVIDENCE,
                                              message="Sem observações artificiais.")
            if case.get("mode") == "wrong_batch":
                lookup.evidence.provenance = lookup.evidence.provenance.model_copy(update={
                    "batch_ref": request.batch_ref.replace("aaaaaaaa", "bbbbbbbb"),
                })
            synthesis = QuestionSynthesisRequest(
                question=request.question, access_scope=request.access_scope,
                remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
                lookup=lookup, expected_batch_ref=request.batch_ref,
            )
            response = client.post(SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"),
                                   headers=HEADERS)
            body = response.json()
            checks["http"] &= response.status_code == 200
            if case["expected_status"] == "answered":
                fragment = re.escape(case["expected_fragment"])
                checks["numeric"] = bool(re.search(
                    rf"(?<![\d.,]){fragment}(?!\d|[.,]\d)", body.get("answer") or "",
                ))
                checks["numeric"] &= value == Decimal(str(case["expected_value"]))
                context = body.get("analysis_context") or {}
                checks["grounding"] = bool(body.get("evidence")) and (
                    context.get("batch_reference") == request.batch_ref
                    and context.get("metric") == case["metric"]
                    and context.get("unit") == case["unit"]
                    and context.get("period") == case["expected_period"]
                )
        checks["status"] = body["status"] == case["expected_status"]
        if case["expected_status"] != "answered":
            checks["privacy"] = not body.get("answer") and not body.get("evidence")
    return {"id": case["id"], "category": case["category"], "checks": checks}


def load_cases():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))["cases"]
