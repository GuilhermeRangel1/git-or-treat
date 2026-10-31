"""Matriz de despacho B9; falhas nunca viram ausência legítima."""

import pytest

from app.repositories.gold_publication import GoldPublicationChanged, GoldPublicationInvalid
from app.schemas.genai_plan import QuestionPlanStatus
from app.services.genai_client import GenAIResponseInvalid, GenAITimeout
from app.services.genai_flow import should_synthesize

AVAILABLE = {
    "status": "available",
    "evidence": {
        "reference": {"source": "synthetic.fixture", "description": "Fixture", "is_demo": True},
        "records": [{"value": 0}],
    },
}


@pytest.mark.parametrize(
    "lookup",
    [
        AVAILABLE,
        {"status": "no_evidence", "message": "Sem evidência."},
        {"status": "needs_clarification", "message": "Especifique o recorte."},
    ],
)
def test_completed_lookup_including_zero_absence_or_clarification_is_synthesized(lookup):
    assert should_synthesize(planning_status="planned", lookup=lookup, policy="completed_lookup")


@pytest.mark.parametrize("status", [s for s in QuestionPlanStatus if s != "planned"])
def test_planning_response_is_returned_without_synthesis(status):
    assert not should_synthesize(planning_status=status, policy="completed_lookup")
    with pytest.raises(GenAIResponseInvalid):
        should_synthesize(planning_status=status, lookup=AVAILABLE, policy="completed_lookup")


@pytest.mark.parametrize(
    "failure", [GenAITimeout(), GoldPublicationChanged(), GoldPublicationInvalid(), RuntimeError()]
)
def test_execution_failure_prevents_synthesis_even_with_leftover_result(failure):
    assert not should_synthesize(
        planning_status="planned", lookup=AVAILABLE, failure=failure, policy="completed_lookup"
    )


@pytest.mark.parametrize(
    "lookup",
    [
        None,
        {},
        {"status": "error", "message": "Falha não é ausência."},
        {"status": "no_evidence"},
        {"status": "no_evidence", "message": "Sem dados", "evidence": AVAILABLE["evidence"]},
        {"status": "available", "evidence": {**AVAILABLE["evidence"], "records": []}},
        {**AVAILABLE, "unexpected": True},
        {**AVAILABLE, "contract_version": "v2"},
    ],
)
def test_invalid_or_incomplete_lookup_is_not_sent_to_synthesis(lookup):
    with pytest.raises(GenAIResponseInvalid):
        should_synthesize(planning_status="planned", lookup=lookup, policy="completed_lookup")


def test_policy_is_explicit_and_unknown_state_is_rejected():
    with pytest.raises(TypeError):
        should_synthesize(planning_status="planned", lookup=AVAILABLE)
    with pytest.raises(ValueError):
        should_synthesize(planning_status="planned", lookup=AVAILABLE, policy="unknown")
    with pytest.raises(GenAIResponseInvalid):
        should_synthesize(planning_status="answered", lookup=AVAILABLE, policy="completed_lookup")
