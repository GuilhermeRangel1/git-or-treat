import asyncio
import json
import logging

import httpx
import pytest

from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
    is_gd_consumption_drop_question,
    is_periodized_accumulated_attendance_question,
)
from app.services.genai_sql_observation import (
    log_sql_context_ready,
    log_sql_context_unavailable,
    observe_sql_generation,
)
from tests.test_genai_sql_semantics import consumption_request, query
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


def run(
    request,
    *,
    status="sql_candidate",
    mutation=None,
    http_status=200,
    expired=False,
    stage_expired=False,
):
    captured = []
    clock = [0.0]

    def handler(incoming):
        body = json.loads(incoming.content)
        captured.append(body)
        assert incoming.url.path == "/api/v1/internal/sql-candidates"
        candidate = query(request).model_dump(mode="json")
        if mutation:
            candidate = mutation(candidate)
        if stage_expired:
            clock[0] = 33
        if status == "needs_clarification":
            candidate = {
                "status": status,
                "generation_contract_version": "text-to-sql-f1-v1",
                "context_version": body["context_version"],
                "scope_assessment": {"status": "in_domain"},
                "clarification": {
                    "question": "Qual período?",
                    "missing_fields": ["period"],
                },
            }
        return httpx.Response(
            http_status,
            json={"correlation_id": "b" * 32, "candidate": candidate},
            headers={"x-correlation-id": "b" * 32},
        )

    async def action():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = GenAIQuestionClient(
                http_client=http,
                base_url="http://genai",
                service_token="synthetic-service-token-0000000000",
            )
            deadline = GenAIRequestDeadline.start(
                60 if stage_expired else 10, clock=lambda: clock[0]
            )
            clock[0] = 11 if expired else 2
            result = await observe_sql_generation(
                request, client=client, deadline=deadline, correlation_id="b" * 32
            )
            assert captured[0]["remaining_timeout_ms"] == 8000
            return result

    return asyncio.run(action())


def test_generation_and_semantic_review_share_backend_context_and_budget(sql_request):
    result = run(sql_request)
    assert result.review.measure_semantics == (("revenue", "revenue_total"),)


def test_rejected_model_sql_becomes_a_sanitized_invalid_response(sql_request):
    def invalid_aggregation(candidate):
        candidate["sql"] = (
            "SELECT AVG(receita_total_reais) AS revenue "
            "FROM gold_v2.diagnostico_receita"
        )
        return candidate

    with pytest.raises(GenAIResponseInvalid):
        run(sql_request, mutation=invalid_aggregation)


def test_context_telemetry_contains_versions_and_shape_but_not_prompt_or_values(
    sql_request,
    caplog,
):
    payload = sql_request.model_dump(mode="json")
    payload["dimension_value_coverage"] = [
        {
            "dimension_id": "geography.municipality",
            "values": ["Recife"],
        }
    ]
    request = type(sql_request).model_validate(payload)
    with caplog.at_level(logging.INFO, logger="app.services.genai_sql_observation"):
        log_sql_context_ready(build_sql_generation_context(request), "b" * 32)

    message = caplog.text
    assert "genai_sql_context outcome=ready" in message
    assert "correlation_id=" + "b" * 32 in message
    assert "mapping_version=" in message
    assert "dictionary_version=" in message
    assert "billing.revenue" in message
    assert "receita_total_reais" in message
    assert "dimension_value_count=1" in message
    assert "truncation=none" in message
    assert request.question not in message
    assert "Recife" not in message
    assert request.access_scope.caller_ref not in message


def test_context_rejection_logs_only_reason_and_size_not_context_values(
    sql_request, caplog
):
    payload = sql_request.model_dump(mode="json")
    payload["dimension_value_coverage"] = [
        {
            "dimension_id": "geography.municipality",
            "values": [f"Municipio{i:04}" + "x" * 100 for i in range(700)],
        }
    ]
    oversized = type(sql_request).model_validate(payload)
    with caplog.at_level(logging.WARNING, logger="app.services.genai_sql_observation"):
        with pytest.raises(SqlContextUnavailable) as error:
            build_sql_generation_context(oversized)
        log_sql_context_unavailable(error.value, "b" * 32)

    message = caplog.text
    assert "outcome=unavailable" in message
    assert "reason=context_too_large" in message
    assert "context_bytes=" in message
    assert "Municipio" not in message
    assert sql_request.access_scope.caller_ref not in message


def test_clarification_does_not_generate_review_or_trigger_execution(sql_request):
    assert run(sql_request, status="needs_clarification").review is None


@pytest.mark.parametrize("scope_status", [None, "out_of_domain"])
def test_scope_decision_is_required_and_consistent_before_sql_review(
    sql_request, scope_status
):
    def mutate(candidate):
        if scope_status is None:
            candidate.pop("scope_assessment")
        else:
            candidate["scope_assessment"] = {"status": scope_status}
        return candidate

    with pytest.raises(GenAIResponseInvalid):
        run(sql_request, mutation=mutate)


def test_wrong_recuts_are_not_promoted_to_review(sql_request):
    def mutate(candidate):
        candidate["parameters"]["city"]["value"] = "Olinda"
        return candidate

    with pytest.raises(GenAIResponseInvalid):
        run(sql_request, mutation=mutate)


def test_provider_failure_is_not_a_clarification(sql_request):
    with pytest.raises(GenAIServiceUnavailable):
        run(sql_request, http_status=503)


@pytest.mark.parametrize(
    "question",
    [
        "Quantos chamados acumulados em janeiro de 2026?",
        "Qual o histórico acumulado de atendimento em 2026?",
        "Quantos protocolos acumulados nos últimos 12 meses?",
        "Qual o total acumulado desde janeiro?",
    ],
)
def test_accumulated_attendance_question_detects_explicit_time_window(question):
    assert is_periodized_accumulated_attendance_question(question)


def test_accumulated_attendance_with_period_is_refused_without_calling_agent(
    sql_request,
):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = "Quantos chamados no histórico acumulado em janeiro de 2026?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.accumulated_attendance"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.accumulated_attendance",
            "kind": "none",
        }
    ]
    request = type(sql_request).model_validate(payload)

    async def action():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: pytest.fail("pergunta periodizada não deve chamar o agente")
            )
        ) as http:
            client = GenAIQuestionClient(
                http_client=http,
                base_url="http://genai",
                service_token="synthetic-service-token-0000000000",
            )
            return await observe_sql_generation(
                request,
                client=client,
                deadline=GenAIRequestDeadline.start(10),
                correlation_id="b" * 32,
            )

    result = asyncio.run(action())
    assert result.model_calls == 0
    assert result.review is None
    assert result.candidate.status == "unsupported"
    assert result.candidate.unsupported_reason.code == "operation_outside_f1"


def test_expired_global_deadline_prevents_provider_call(sql_request):
    with pytest.raises(GenAITimeout):
        run(sql_request, expired=True)


def test_envelope_budget_caps_wider_global_deadline(sql_request):
    with pytest.raises(GenAITimeout):
        run(sql_request, stage_expired=True)


@pytest.mark.parametrize(
    "question",
    [
        "Qual a receita de miojo em janeiro de 2026?",
        "Como fazer uma receita de bolo?",
        "Qual foi o FATURAMENTO DE HAMBÚRGUER em janeiro de 2026?",
        "Qual a previsão do tempo em janeiro de 2026?",
    ],
)
def test_explicit_external_subject_stops_before_the_generator(sql_request, question):
    request = sql_request.model_copy(update={"question": question})

    class UnexpectedGenerator:
        async def generate_sql_candidate(self, *args, **kwargs):
            pytest.fail("Pedido externo chegou ao gerador")

    result = asyncio.run(
        observe_sql_generation(
            request,
            client=UnexpectedGenerator(),
            deadline=GenAIRequestDeadline.start(60),
            correlation_id="b" * 32,
        )
    )
    assert result.review is None
    assert result.candidate.status == "unsupported"
    assert result.candidate.sql is None
    assert result.candidate.scope_assessment.status == "out_of_domain"
    assert result.candidate.unsupported_reason.reason_code == "out_of_domain"


@pytest.mark.parametrize(
    "question",
    [
        "Qual foi a receita em janeiro de 2026?",
        "Qual foi a receita de Recife em 2026?",
        "Qual foi a receita residencial?",
    ],
)
def test_energy_revenue_still_reaches_the_generator(sql_request, question):
    request = sql_request.model_copy(update={"question": question})
    assert run(request).review is not None


def test_mixed_consumption_and_revenue_is_refused_without_partial_sql(sql_request):
    request = consumption_request(sql_request).model_copy(
        update={
            "question": "Compare o consumo medido e o faturamento em junho de 2026.",
        }
    )

    class UnexpectedGenerator:
        async def generate_sql_candidate(self, *args, **kwargs):
            pytest.fail("Pergunta multi-métrica não pode chamar o gerador F1")

    result = asyncio.run(
        observe_sql_generation(
            request,
            client=UnexpectedGenerator(),
            deadline=GenAIRequestDeadline.start(60),
            correlation_id="b" * 32,
        )
    )
    assert result.review is None
    assert result.candidate.status == "unsupported"
    assert result.candidate.sql is None
    assert result.candidate.unsupported_reason.code == "operation_outside_f1"
    assert result.model_calls == 0


def test_gd_consumption_drop_reaches_generator_only_with_approved_metric_scope(
    sql_request,
):
    payload = consumption_request(sql_request).model_dump(mode="json")
    payload["question"] = "Quantas UCs com GD tiveram queda de consumo superior a 30%?"
    payload["access_scope"]["allowed_dimension_ids"].append("generation.distributed")
    payload["access_scope"]["allowed_metric_ids"].append("energy.gd_consumption_drop")
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.gd_consumption_drop",
            "kind": "none",
        }
    ]
    payload["dimension_value_coverage"].append(
        {
            "dimension_id": "generation.distributed",
            "values": ["Não", "Sim"],
        }
    )
    request = type(sql_request).model_validate(payload)
    assert is_gd_consumption_drop_question(request.question)

    class CalledGenerator:
        called = False

        async def generate_sql_candidate(self, *args, **kwargs):
            self.called = True
            raise RuntimeError("fim do teste após confirmar admissão ao gerador")

    client = CalledGenerator()
    with pytest.raises(RuntimeError, match="fim do teste"):
        asyncio.run(
            observe_sql_generation(
                request,
                client=client,
                deadline=GenAIRequestDeadline.start(60),
                correlation_id="b" * 32,
            )
        )

    assert client.called


def test_periodized_accumulated_satisfaction_is_refused_before_model_call(sql_request):
    payload = sql_request.model_dump(mode="json")
    payload["question"] = (
        "Qual foi a nota média de satisfação no histórico acumulado em 2025?"
    )
    payload["access_scope"]["allowed_metric_ids"] = ["service.accumulated_satisfaction"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.accumulated_satisfaction",
            "kind": "none",
        }
    ]
    request = type(sql_request).model_validate(payload)

    class UnexpectedGenerator:
        async def generate_sql_candidate(self, *args, **kwargs):
            pytest.fail("Histórico sem janela não deve responder a pedido anual")

    result = asyncio.run(
        observe_sql_generation(
            request,
            client=UnexpectedGenerator(),
            deadline=GenAIRequestDeadline.start(60),
            correlation_id="b" * 32,
        )
    )

    assert result.candidate.status == "unsupported"
    assert result.candidate.unsupported_reason.code == "operation_outside_f1"
    assert result.model_calls == 0
