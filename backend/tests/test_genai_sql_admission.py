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
from app.services.genai_sql_observation import (
    assert_current_sql_request_context,
    prepare_sql_candidate,
)
from app.services.genai_sql_structure import SqlStructureRejected
from app.services.gold_catalog import GoldCatalogIncompatible
from tests.test_genai_sql_comparison import comparison
from tests.test_genai_sql_semantics import (
    accumulated_attendance_query,
    consumption_query,
    continuity_candidate,
    neighborhood_revenue_query,
    query,
    satisfaction_candidate,
)
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


class Environment:
    """Substitui apenas fronteiras I/O; revisão e contratos são os de produção."""

    def __init__(self, request):
        self.request = request
        self.analytic_engine = object()
        self.readiness_engine = object()
        self.batch_ref = request.batch_ref
        self.scope = request.access_scope
        self.now = [0.0]
        self.deadline = GenAIRequestDeadline.start(20, clock=lambda: self.now[0])
        body = request.model_dump(mode="json")
        self.fields = {key: body[key] for key in (
            "batch_ref", "temporal_coverage", "dimension_value_coverage")}
        self.report = {"readiness_version": "gold-readiness-v2", "batch_ref": self.batch_ref,
                       "lot_state": "ready", "capabilities": {
                           "faturamento.receita": {"status": "available"},
                           "faturamento.receita_bairro": {"status": "available"},
                           "atendimento.uc_acumulado": {"status": "available"},
                           "atendimento.mensal": {"status": "available"},
                           "consumo.variacao_uc": {"status": "available"},
                           "consumo.mensal_uc": {"status": "available"}}}
        self.events = []
        self.source_coverage_failure = False
        self.on_readiness = lambda: None
        self.on_publication_check = lambda: None

    def planning_fields(self, engine, scope):
        assert engine is self.analytic_engine
        self.events.append("metadata")
        assert scope == self.request.access_scope
        return copy.deepcopy(self.fields)

    def assert_current(self, engine):
        self.events.append("publication")
        self.on_publication_check()

    def assert_sql_source_coverage(self, engine, **kwargs):
        assert engine is self.analytic_engine
        self.events.append(("source_coverage", kwargs))
        if self.source_coverage_failure:
            raise GoldCatalogIncompatible("synthetic source coverage failure")

    async def evaluate_readiness(self, engine, **kwargs):
        assert engine is self.readiness_engine
        self.events.append(("readiness", kwargs))
        self.on_readiness()
        return GoldReadinessReport.model_validate(self.report)

    def kwargs(self):
        return {"engine": self.analytic_engine, "readiness_engine": self.readiness_engine, "publication": self, "client": self,
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


def test_satisfaction_admission_requires_monthly_customer_service_readiness(sql_request):
    candidate, request = satisfaction_candidate(sql_request)
    env = Environment(request)
    admitted = env.admit(candidate)
    assert admitted.requested_periods == ("2026-06",)
    assert candidate.interpretation.metric_id == "service.satisfaction"
    assert "atendimento.mensal" in env.report["capabilities"]
    env.report["capabilities"]["atendimento.mensal"] = {
        "status": "unavailable", "reasons": ["control_pending"],
    }
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_comparison_checks_readiness_for_both_windows(sql_request):
    request, candidate = comparison(sql_request)
    env = Environment(request)
    admitted = env.admit(candidate)
    assert admitted.requested_periods == ("2025-06", "2026-06")
    request_args = next(item[1] for item in env.events
                        if isinstance(item, tuple) and item[0] == "readiness")
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


@pytest.mark.parametrize("reason", ["coverage_incomplete", "control_pending"])
def test_continuity_only_allows_observed_feeder_month_after_c11_passes(sql_request, reason):
    candidate, request = continuity_candidate(sql_request)
    env = Environment(request)
    env.report["lot_state"] = "partial"
    env.report["capabilities"] = {
        "interrupcoes.dec_fec": {"status": "unavailable", "reasons": [reason]},
    }
    if reason == "coverage_incomplete":
        admitted = env.admit(candidate)
        assert admitted.quality_mode == "observed_uncertified"
        assert admitted.requested_periods == ("2026-06",)
    else:
        with pytest.raises(SqlAdmissionDenied):
            env.admit(candidate)


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


def test_consumption_uses_legacy_revenue_controls_and_exact_source_month(sql_request):
    candidate, request = consumption_query(sql_request)
    env = Environment(request)

    admitted = env.admit(candidate)

    coverage = next(item[1] for item in env.events
                    if isinstance(item, tuple) and item[0] == "source_coverage")
    assert coverage["table_name"] == "diagnostico_receita"
    assert coverage["periods"] == ("2026-06",)
    assert coverage["metric_ids"] == frozenset({"energy.consumption"})
    readiness = next(item[1] for item in env.events
                     if isinstance(item, tuple) and item[0] == "readiness")
    assert readiness["requested_periods"] == ("2026-06",)
    assert admitted.requested_periods == ("2026-06",)


def test_neighborhood_revenue_requires_its_own_controls_and_exact_source(sql_request):
    candidate, request = neighborhood_revenue_query(sql_request)
    env = Environment(request)
    admitted = env.admit(candidate)
    coverage = next(item[1] for item in env.events
                    if isinstance(item, tuple) and item[0] == "source_coverage")
    assert coverage["table_name"] == "consumo_receita_bairro"
    assert coverage["source_capability_id"] == "faturamento.receita_bairro"
    readiness = next(item[1] for item in env.events
                     if isinstance(item, tuple) and item[0] == "readiness")
    assert readiness["requested_periods"] == ("2026-06",)
    assert admitted.requested_periods == ("2026-06",)
    env.report["capabilities"]["faturamento.receita_bairro"] = {
        "status": "unavailable", "reasons": ["control_pending"],
    }
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_accumulated_attendance_admission_uses_c14_without_fabricated_period(sql_request):
    candidate, request = accumulated_attendance_query(sql_request)
    env = Environment(request)
    admitted = env.admit(candidate)
    readiness = next(item[1] for item in env.events
                     if isinstance(item, tuple) and item[0] == "readiness")
    assert readiness["requested_periods"] == ()
    assert admitted.requested_periods == ()
    assert not any(isinstance(item, tuple) and item[0] == "source_coverage"
                   for item in env.events)
    env.report["capabilities"]["atendimento.uc_acumulado"] = {
        "status": "unavailable", "reasons": ["control_pending"],
    }
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_consumption_is_denied_when_legacy_revenue_capability_is_not_available(sql_request):
    candidate, request = consumption_query(sql_request)
    env = Environment(request)
    env.report["capabilities"]["faturamento.receita"] = {
        "status": "unavailable", "reasons": ["control_pending"]}
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)
    assert any(item[0] == "source_coverage" for item in env.events
               if isinstance(item, tuple))


def test_consumption_is_denied_when_monthly_control_capability_is_not_available(sql_request):
    candidate, request = consumption_query(sql_request)
    env = Environment(request)
    env.report["capabilities"]["consumo.mensal_uc"] = {
        "status": "unavailable", "reasons": ["control_pending"]}
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_consumption_is_denied_when_monthly_capability_is_missing(sql_request):
    candidate, request = consumption_query(sql_request)
    env = Environment(request)
    del env.report["capabilities"]["consumo.mensal_uc"]
    with pytest.raises(SqlAdmissionDenied):
        env.admit(candidate)


def test_consumption_source_missing_month_is_denied_before_readiness(sql_request):
    candidate, request = consumption_query(sql_request)
    env = Environment(request)
    env.report["capabilities"]["consumo.mensal_uc"] = {"status": "available"}
    env.source_coverage_failure = True
    with pytest.raises(SqlAdmissionDenied, match="Cobertura ou fonte"):
        env.admit(candidate)
    assert not any(item[0] == "readiness" for item in env.events
                   if isinstance(item, tuple))


def test_observed_dec_fec_readiness_cannot_authorize_billing_sql(sql_request):
    env = Environment(sql_request)
    env.report["lot_state"] = "partial"
    env.report["capabilities"] = {
        "faturamento.receita": {
            "status": "unavailable", "reasons": ["coverage_incomplete"]},
        "interrupcoes.dec_fec": {
            "status": "unavailable", "reasons": ["coverage_incomplete"]},
    }

    with pytest.raises(SqlAdmissionDenied):
        env.admit(query(sql_request))

    assert not any(item[0] == "publication" for item in env.events)


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


@pytest.mark.parametrize("metric_id", [
    "energy.consumption",
    "service.attendance",
    "network.equivalent_interruption_duration",
    "network.equivalent_interruption_frequency",
])
def test_out_of_scope_semantic_intent_is_observed_without_admission_or_sql(
    sql_request, metric_id,
):
    env = Environment(sql_request)

    async def generate(payload, *, correlation_id):
        env.events.append("generation")
        return SqlGenerationResponse.model_validate({
            "correlation_id": correlation_id,
            "candidate": {
                "generation_contract_version": "text-to-sql-f1-v1",
                "status": "unsupported",
                "context_version": payload.context_version,
                "unsupported_reason": {
                    "code": "metric_outside_f1",
                    "message": "Consumo medido ainda não está disponível na F1.",
                },
                "semantic_intent": {
                    "metric_id": metric_id,
                    "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
                    "filters": [],
                },
            },
        })

    env.generate_sql_candidate = generate
    result = asyncio.run(prepare_sql_candidate(sql_request, **env.kwargs()))

    assert result.candidate.semantic_intent.metric_id == metric_id
    assert result.candidate.sql is None
    assert result.admission is None
    assert env.events == ["publication", "generation"]


def test_generation_context_is_rejected_after_current_session_scope_changes(sql_request):
    env = Environment(sql_request)
    env.scope = env.scope.model_copy(update={"caller_ref": "session:" + "b" * 64})

    with pytest.raises(SqlAdmissionDenied, match="antes da geração"):
        assert_current_sql_request_context(
            sql_request, resolve_scope=lambda: env.scope, publication=env,
        )

    assert env.events == []


def test_generation_context_is_rejected_after_publication_changes(sql_request):
    env = Environment(sql_request)
    env.batch_ref = "gold-csv-v2:GOLD_20000101T000000Z_bbbbbbbb:12345678-1234-4123-8123-123456789abc"

    with pytest.raises(SqlAdmissionDenied, match="antes da geração"):
        assert_current_sql_request_context(
            sql_request, resolve_scope=lambda: env.scope, publication=env,
        )

    assert env.events == []


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
