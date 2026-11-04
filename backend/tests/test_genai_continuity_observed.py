from datetime import date

import pytest

from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.gold_readiness import CapabilityReadiness, GoldReadinessReport
from app.schemas.genai_plan import LogicalReadPlan
from app.services.genai_coordination import (
    OBSERVED_CONTINUITY_WARNING,
    _apply_observed_continuity_warning,
    _observed_continuity_quality,
)


BATCH = (
    "gold-csv-v2:GOLD_20260601T000000Z_12345678:"
    "12345678-1234-4234-8234-123456789012"
)


def _plan(metric="network.equivalent_interruption_duration"):
    return LogicalReadPlan.model_validate({
        "catalog_version": "v1", "operation": "read",
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "domain_id": "continuity", "metric_id": metric, "unit": "horas por UC",
        "window": {"kind": "bounded", "start": date(2026, 6, 1),
                   "end": date(2026, 6, 30), "granularity": "month"},
        "dimension_ids": ["network.feeder"],
        "filters": [{"dimension_id": "network.feeder", "operator": "eq", "values": ["AL-01"]}],
        "limit": 10,
    })


def _report(reason="coverage_incomplete"):
    return GoldReadinessReport(
        readiness_version="gold-readiness-v2", batch_ref=BATCH, lot_state="partial",
        capabilities={"interrupcoes.dec_fec": CapabilityReadiness(
            status="unavailable", reasons=(reason,),
        )},
    )


def test_only_dec_fec_with_exclusively_uncertified_coverage_enters_observed_mode():
    quality = _observed_continuity_quality(_report(), _plan(), BATCH)

    assert quality is not None
    assert quality.quality_mode == "observed_uncertified"
    assert quality.available_capability_ids == ()
    assert quality.observed_capability_ids == ("interrupcoes.dec_fec",)
    assert quality.observed_periods == ("2026-06",)


@pytest.mark.parametrize("reason", ["control_failed", "table_empty", "coverage_missing"])
def test_other_readiness_failures_remain_blocked(reason):
    assert _observed_continuity_quality(_report(reason), _plan(), BATCH) is None


def test_other_metrics_and_multi_feeder_queries_remain_blocked():
    assert _observed_continuity_quality(
        _report(), _plan("billing.revenue"), BATCH,
    ) is None
    data = _plan().model_dump(mode="python")
    data["filters"] = [{
        "dimension_id": "network.feeder", "operator": "in", "values": ["AL-01", "AL-02"],
    }]
    multi_feeder = LogicalReadPlan.model_validate(data)
    assert _observed_continuity_quality(_report(), multi_feeder, BATCH) is None


def test_public_answer_always_receives_deterministic_observed_warning():
    from app.schemas.genai_evidence import GoldEvidenceQuality

    quality = GoldEvidenceQuality(
        readiness_version="gold-readiness-v2", batch_ref=BATCH, lot_state="partial",
        quality_mode="observed_uncertified", available_capability_ids=(),
        observed_capability_ids=("interrupcoes.dec_fec",), observed_periods=("2026-06",),
    )
    response = AIQuestionResponse(
        status="answered", answer="O DEC observado foi 0,12 horas por UC.",
        evidence=[{"source": "gold.local", "description": "Evidência Gold v2", "is_demo": False}],
    )

    published = _apply_observed_continuity_warning(response, quality)

    assert OBSERVED_CONTINUITY_WARNING in published.answer
    assert OBSERVED_CONTINUITY_WARNING in published.limitations


def test_audit_records_observed_mode_scope_and_limitation_without_values():
    event = BackendAuditEvent(
        correlation_id="a" * 32,
        stage="response",
        code="completed",
        outcome="success",
        duration_ms=12,
        batch_ref=BATCH,
        quality_mode="observed_uncertified",
        observed_capability_ids=("interrupcoes.dec_fec",),
        observed_periods=("2026-06",),
        quality_limitation=OBSERVED_CONTINUITY_WARNING,
    )

    payload = event.model_dump(mode="json")

    assert payload["quality_mode"] == "observed_uncertified"
    assert payload["observed_periods"] == ["2026-06"]
    assert payload["quality_limitation"] == OBSERVED_CONTINUITY_WARNING
    assert "value" not in payload
