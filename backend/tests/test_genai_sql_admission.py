import asyncio
import copy
from dataclasses import replace

import pytest
from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.gold_readiness import GoldReadinessReport
from app.schemas.sql_generation import SqlGenerationResponse
from app.services.genai_client import GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_admission import (
    SqlAdmissionDenied,
    admit_sql_candidate,
    revalidate_sql_admission,
)
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_observation import prepare_sql_candidate
from app.services.genai_sql_structure import SqlStructureRejected

from tests.test_genai_sql_comparison import comparison
from tests.test_genai_sql_semantics import query
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


class Environment:
    """Substitui apenas fronteiras I/O; revisão e contratos são os de produção."""

    def __init__(self, request):
        self.request = request
        self.batch_ref = request.batch_ref
        self.scope = request.access_scope
        self.now = [0.0]
        self.deadline = GenAIRequestDeadline.start(20, clock=lambda: self.now[0])
        body = request.model_dump(mode="json")
        self.fields = {key: body[key] for key in (
            "batch_ref", "temporal_coverage", "dimension_value_coverage")}
        self.report = {"readiness_version": "gold-readiness-v2", "batch_ref": self.batch_ref,
                       "lot_state": "ready", "capabilities": {
                           "faturamento.receita": {"status": "available"}}}
        self.events = []
        self.on_readiness = lambda: None
        self.on_publication_check = lambda: None

    def planning_fields(self, engine, scope):
        self.events.append("metadata")
        assert scope == self.request.access_scope
        return copy.deepcopy(self.fields)

    def assert_current(self, engine):
        self.events.append("publication")
        self.on_publication_check()

    async def evaluate_readiness(self, engine, **kwargs):
        self.events.append(("readiness", kwargs))
        self.on_readiness()
        return GoldReadinessReport.model_validate(self.report)

    def kwargs(self):
        return {"engine": object(), "publication": self, "client": self,
                "resolve_scope": lambda: self.scope, "approved_controls": frozenset({"control"}),
                "deadline": self.deadline, "correlation_id": "b" * 32}

    def admit(self, candidate):
        return asyncio.run(admit_sql_candidate(candidate, self.request, **self.kwargs()))

    def revalidate(self, admitted, candidate, **changes):
        kwargs = self.kwargs()
        kwargs.update(changes)
        return asyncio.run(revalidate_sql_admission(admitted, candidate, self.request, **kwargs))


def test_admission_binds_context_canonical_query_and_readiness(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    assert admitted.context_version == candidate.context_version
    assert len(admitted.digest) == len(admitted.candidate_digest) == 64
    assert admitted.requested_periods == ("2026-06",)
    assert env.events[-1] == "publication"
    env.now[0] = 2
    assert env.revalidate(admitted, candidate) == admitted
    assert len([item for item in env.events if item == "metadata"]) == 2


def test_comparison_checks_readiness_for_both_windows(sql_request):
    request, candidate = comparison(sql_request)
    env = Environment(request)
    admitted = env.admit(candidate)
    assert admitted.requested_periods == ("2025-06", "2026-06")
    request_args = next(item[1] for item in env.events if isinstance(item, tuple))
    assert request_args["requested_periods"] == admitted.requested_periods
    assert request_args["expected_batch_ref"] == request.batch_ref


@pytest.mark.parametrize("state", ["mixed", "stale", "empty", "invalid", "unavailable"])
def test_denies_non_current_lot(sql_request, state):
    env = Environment(sql_request)
    env.report["lot_state"] = state
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))


def test_partial_lot_can_admit_only_available_revenue(sql_request):
    env = Environment(sql_request)
    env.report["lot_state"] = "partial"
    assert env.admit(query(sql_request))
    env.report["capabilities"]["faturamento.receita"] = {
        "status": "unavailable", "reasons": ["coverage_incomplete"]}
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))


def test_metadata_change_invalidates_original_context(sql_request):
    env = Environment(sql_request)
    env.fields["dimension_value_coverage"] = [{
        "dimension_id": "geography.municipality", "values": ["Recife"]}]
    with pytest.raises(SqlStructureRejected, match="Contexto"):
        env.admit(query(sql_request))
    assert env.events == ["metadata"]


def test_revoked_scope_denies_before_observation(sql_request):
    env = Environment(sql_request)
    env.scope = env.scope.model_copy(update={"allowed_metric_ids": frozenset()})
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))
    assert env.events == []


def test_scope_revoked_during_readiness_is_denied(sql_request):
    env = Environment(sql_request)
    env.on_readiness = lambda: setattr(env, "scope", env.scope.model_copy(
        update={"allowed_metric_ids": frozenset()}))
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))


def test_candidate_mutation_during_await_is_denied(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    env.on_readiness = candidate.parameters.clear
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_revalidation_rejects_sql_or_artifact_mutation(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(admitted, candidate.model_copy(update={"sql": candidate.sql + " "}))
    tampered = replace(admitted, review=replace(admitted.review, canonical_sql="DELETE FROM x"))
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(tampered, candidate)


def test_changed_control_policy_invalidates_artifact(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(admitted, candidate, approved_controls=frozenset())


def test_expired_artifact_cannot_be_renewed_by_new_deadline(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    env.now[0] = 21
    new_deadline = GenAIRequestDeadline.start(60, clock=lambda: env.now[0])
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(admitted, candidate, deadline=new_deadline)


def test_deadline_expired_during_readiness_discards_result(sql_request):
    env = Environment(sql_request)
    env.on_readiness = lambda: env.now.__setitem__(0, 21)
    with pytest.raises(GenAITimeout):
        env.admit(query(sql_request))


def test_policy_version_change_requires_new_admission(sql_request, monkeypatch):
    import app.services.genai_sql_admission as module

    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    monkeypatch.setattr(module, "SQL_ADMISSION_POLICY_VERSION", "next-policy")
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(admitted, candidate)


def test_missing_revenue_capability_is_denied(sql_request):
    env = Environment(sql_request)
    env.report["capabilities"] = {}
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))


def test_report_from_different_publication_is_denied(sql_request):
    env = Environment(sql_request)
    env.report["batch_ref"] = env.batch_ref.replace("12345678", "22345678")
    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))


def test_publication_change_after_readiness_discards_admission(sql_request):
    env = Environment(sql_request)

    def changed():
        raise RuntimeError("synthetic publication change")

    env.on_publication_check = changed
    with pytest.raises(RuntimeError, match="publication change"):
        env.admit(query(sql_request))


@pytest.mark.parametrize("clarification", [False, True])
def test_preparation_composes_generation_and_admission_without_executor(sql_request, clarification):
    env = Environment(sql_request)

    async def generate(payload, *, correlation_id):
        env.events.append("generation")
        candidate = query(sql_request).model_dump(mode="json")
        if clarification:
            candidate = {"generation_contract_version": "text-to-sql-f1-v1",
                         "status": "needs_clarification", "context_version": payload.context_version,
                         "clarification": {"question": "Qual mês?", "missing_fields": ["period"]}}
        return SqlGenerationResponse.model_validate({
            "correlation_id": correlation_id, "candidate": candidate})

    env.generate_sql_candidate = generate
    result = asyncio.run(prepare_sql_candidate(sql_request, **env.kwargs()))
    assert env.events[:2] == ["publication", "generation"]
    if clarification:
        assert result.admission is None
        assert env.events == ["publication", "generation"]
    else:
        assert result.admission.requested_periods == ("2026-06",)
        assert "metadata" in env.events
        assert env.events[-1] == "publication"


def test_old_admission_is_not_transferable_to_another_authorized_caller(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    payload = sql_request.model_dump(mode="json")
    payload["access_scope"]["caller_ref"] = "session:" + "c" * 64
    env.request = QuestionPlanRequest.model_validate(payload)
    env.scope = env.request.access_scope
    new_candidate = candidate.model_copy(update={
        "context_version": build_sql_generation_context(env.request).context_version})
    with pytest.raises(SqlAdmissionDenied):
        env.revalidate(admitted, new_candidate)


def test_modified_parameter_is_rejected_before_new_observation(sql_request):
    env = Environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    env.events.clear()
    parameters = dict(candidate.parameters)
    parameters["city"] = type(parameters["city"])(type="string", value="Olinda")
    with pytest.raises(SqlStructureRejected):
        env.revalidate(admitted, candidate.model_copy(update={"parameters": parameters}))
    assert env.events == []
