"""Envelopes internos de planejar e sintetizar (GENAI-01, parte A1), sem rota nem núcleo.

As entradas válidas são os exemplos de docs/contracts/genai-query-execution.md; os demais
casos alteram cópias desses exemplos. Nenhum valor vem do lote.
"""

import copy

import pytest
from pydantic import ValidationError

from app.schemas.access import AccessContext
from app.schemas.internal import (
    AccessScope,
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionPlanStatus,
    QuestionSynthesisRequest,
)
from app.schemas.read_plan import LogicalReadPlan
from app.schemas.responses import FailureCode, map_failure

from .test_internal_contract_examples import (
    CORRELATION_ID,
    _json_example,
    _lookup_example,
    _plan_example,
)


def _plan_request() -> dict:
    return _json_example("Requisição (proposta: `QuestionPlanRequest`)")


def _planned() -> dict:
    return _plan_example()


def _clarification() -> dict:
    return _json_example("Válido — esclarecimento (planejar)")


def _synthesis() -> dict:
    request = _plan_request()
    planned = _planned()
    return {
        **request,
        "plan": planned["plan"],
        "plan_fingerprint": planned["plan_fingerprint"],
        "lookup": _lookup_example(),
    }


def _response_for(status: QuestionPlanStatus) -> dict:
    response = {
        "contract_version": "v1",
        "correlation_id": CORRELATION_ID,
        "status": status.value,
        "message": "Mensagem sintética.",
    }
    if status is QuestionPlanStatus.REFUSED:
        response["error"] = map_failure(FailureCode.SECURITY_VIOLATION).error.model_dump()
    elif status is QuestionPlanStatus.RECOVERABLE_ERROR:
        response["error"] = map_failure(FailureCode.INVALID_SOURCE_RESPONSE).error.model_dump()
    return response


def _not_planned(status: QuestionPlanStatus) -> dict:
    return {
        "contract_version": "v1",
        "correlation_id": CORRELATION_ID,
        "status": status.value,
        "plan": None,
        "plan_fingerprint": None,
        "response": _response_for(status),
    }


def _tampered_plan() -> dict:
    """Mesmo plano com o filtro trocado; o fingerprint antigo deixa de valer."""

    plan = copy.deepcopy(_planned()["plan"])
    plan["filters"][0]["values"] = ["Olinda"]
    return plan


NOT_PLANNED = [status for status in QuestionPlanStatus if status is not QuestionPlanStatus.PLANNED]
ENVELOPES = {
    "plan_request": (QuestionPlanRequest, _plan_request),
    "planned": (QuestionPlanResponse, _planned),
    "clarification": (QuestionPlanResponse, _clarification),
    "synthesis": (QuestionSynthesisRequest, _synthesis),
}


# (1) Exemplos do contrato


@pytest.mark.parametrize("name", ENVELOPES)
def test_contract_example_is_a_valid_envelope(name: str) -> None:
    model, build = ENVELOPES[name]

    model.model_validate(build())


def test_planned_example_carries_the_plan_fingerprint() -> None:
    envelope = QuestionPlanResponse.model_validate(_planned())

    assert envelope.status is QuestionPlanStatus.PLANNED
    assert envelope.plan_fingerprint == envelope.plan.fingerprint()


# (2) Campos extras e versão


@pytest.mark.parametrize("name", ENVELOPES)
def test_extra_field_is_rejected(name: str) -> None:
    model, build = ENVELOPES[name]

    with pytest.raises(ValidationError):
        model.model_validate({**build(), "batch_ref": "qualquer"})


@pytest.mark.parametrize("name", ["plan_request", "synthesis"])
def test_extra_field_in_access_scope_is_rejected(name: str) -> None:
    model, build = ENVELOPES[name]
    envelope = build()
    envelope["access_scope"] = {**envelope["access_scope"], "role": "admin"}

    with pytest.raises(ValidationError):
        model.model_validate(envelope)


@pytest.mark.parametrize("name", ENVELOPES)
def test_incompatible_contract_version_is_rejected(name: str) -> None:
    model, build = ENVELOPES[name]

    with pytest.raises(ValidationError):
        model.model_validate({**build(), "contract_version": "v2"})


@pytest.mark.parametrize("name", ["plan_request", "synthesis"])
def test_context_accepts_three_turns_and_rejects_four(name: str) -> None:
    model, build = ENVELOPES[name]
    turn = {"role": "user", "content": "Pergunta anterior sintética."}

    model.model_validate({**build(), "context": [turn] * 3})
    with pytest.raises(ValidationError):
        model.model_validate({**build(), "context": [turn] * 4})


# (3) Estado ↔ campos da resposta de planejar


@pytest.mark.parametrize("missing", ["plan", "plan_fingerprint"])
def test_planned_requires_plan_and_fingerprint(missing: str) -> None:
    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate({**_planned(), missing: None})


def test_planned_rejects_response() -> None:
    envelope = {
        **_planned(),
        "response": _response_for(QuestionPlanStatus.NEEDS_CLARIFICATION),
    }

    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate(envelope)


@pytest.mark.parametrize("status", NOT_PLANNED)
def test_other_states_require_response(status: QuestionPlanStatus) -> None:
    QuestionPlanResponse.model_validate(_not_planned(status))
    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate({**_not_planned(status), "response": None})


@pytest.mark.parametrize("status", NOT_PLANNED)
@pytest.mark.parametrize("field", ["plan", "plan_fingerprint"])
def test_other_states_reject_plan_and_fingerprint(status: QuestionPlanStatus, field: str) -> None:
    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate({**_not_planned(status), field: _planned()[field]})


@pytest.mark.parametrize("status", NOT_PLANNED)
def test_response_status_must_match_the_planning_state(status: QuestionPlanStatus) -> None:
    other = next(item for item in NOT_PLANNED if item is not status)
    envelope = {**_not_planned(status), "response": _response_for(other)}

    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate(envelope)


def test_response_correlation_must_match_the_envelope() -> None:
    envelope = _clarification()
    envelope["response"]["correlation_id"] = "f" * 32

    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate(envelope)


# (4) Fingerprint


def test_planned_rejects_fingerprint_of_another_plan() -> None:
    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate({**_planned(), "plan_fingerprint": "0" * 64})


def test_planned_rejects_tampered_plan_with_old_fingerprint() -> None:
    with pytest.raises(ValidationError):
        QuestionPlanResponse.model_validate({**_planned(), "plan": _tampered_plan()})


def test_synthesis_rejects_tampered_plan_with_old_fingerprint() -> None:
    with pytest.raises(ValidationError):
        QuestionSynthesisRequest.model_validate({**_synthesis(), "plan": _tampered_plan()})


def test_synthesis_rejects_fingerprint_of_another_plan() -> None:
    tampered = LogicalReadPlan.model_validate(_tampered_plan())

    with pytest.raises(ValidationError):
        QuestionSynthesisRequest.model_validate(
            {**_synthesis(), "plan_fingerprint": tampered.fingerprint()}
        )


@pytest.mark.parametrize(
    ("model", "build"), [(QuestionPlanResponse, _planned), (QuestionSynthesisRequest, _synthesis)]
)
def test_round_trip_preserves_the_fingerprint(model, build) -> None:
    original = model.model_validate(build())

    restored = model.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.plan.fingerprint() == original.plan_fingerprint
    assert model.model_validate(restored.model_dump(mode="json")) == original


# (5) Escopo


def test_access_scope_has_no_correlation() -> None:
    scope = _plan_request()["access_scope"]

    assert "correlation_id" not in AccessScope.model_fields
    with pytest.raises(ValidationError):
        AccessScope.model_validate({**scope, "correlation_id": CORRELATION_ID})


def test_access_scope_becomes_the_core_access_context() -> None:
    scope = _plan_request()["access_scope"]

    context = AccessScope.model_validate(scope).to_context(CORRELATION_ID)

    assert context == AccessContext.model_validate({**scope, "correlation_id": CORRELATION_ID})


def test_access_scope_rejects_invalid_correlation() -> None:
    scope = AccessScope.model_validate(_plan_request()["access_scope"])

    with pytest.raises(ValidationError):
        scope.to_context("não-é-correlação")
