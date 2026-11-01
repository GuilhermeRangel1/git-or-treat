from decimal import Decimal
from datetime import date, timedelta

import pytest

from app.schemas.ai import AIEvidenceReference
from app.schemas.genai_evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceResult,
)
from app.services.genai_executor import (
    MAX_EVIDENCE_BYTES,
    GoldExecutionDenied,
    _exceeds_evidence_byte_limit,
    _rounded_number,
)
from app.schemas.genai_internal import AccessScope
from app.schemas.genai_plan import LogicalReadPlan
from app.services.genai_client import GenAIResponseInvalid
from app.services.genai_planning import _admit_plan


@pytest.mark.parametrize('days,allowed', [(1830, True), (1831, False)])
def test_backend_reapplies_the_gold_profile_window_boundary(days, allowed):
    plan = LogicalReadPlan.model_validate({
        'catalog_version': 'v1', 'operation': 'read',
        'profile_id': 'v-energy-grid-360-gold', 'source_id': 'gold.local',
        'domain_id': 'revenue', 'metric_id': 'billing.revenue', 'unit': 'R$',
        'window': {'kind': 'bounded', 'start': date(2000, 1, 1),
                   'end': date(2000, 1, 1) + timedelta(days=days), 'granularity': 'month'},
        'limit': 100,
    })
    scope = AccessScope(caller_ref='test.window', profile_id=plan.profile_id,
                        source_id=plan.source_id, allowed_operations={'read'},
                        allowed_metric_ids={'billing.revenue'}, allowed_dimension_ids=set())
    if allowed:
        assert _admit_plan(plan, scope).table == 'diagnostico_receita'
    else:
        with pytest.raises(GenAIResponseInvalid):
            _admit_plan(plan, scope)


def _result(extra_bytes: int = 0) -> EvidenceLookupResult:
    return EvidenceLookupResult(
        status=EvidenceLookupStatus.AVAILABLE,
        evidence=EvidenceResult(
            reference=AIEvidenceReference(
                source="gold.local",
                description="Evidência de teste",
                is_demo=False,
            ),
            records=[{"value": 1, "padding": "x" * extra_bytes}],
        ),
    )


def test_evidence_limit_counts_the_serialized_response_in_utf8_bytes():
    assert not _exceeds_evidence_byte_limit(_result())
    assert _exceeds_evidence_byte_limit(_result(MAX_EVIDENCE_BYTES + 1))


@pytest.mark.parametrize("raw,expected", [("1.005", 1.0), ("1.015", 1.02), ("-1.015", -1.02)])
def test_numeric_evidence_uses_catalog_half_even_rounding(raw, expected):
    assert _rounded_number(Decimal(raw), 2) == expected


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_measure_never_becomes_numeric_evidence(raw):
    with pytest.raises(GoldExecutionDenied):
        _rounded_number(Decimal(raw), 2)
