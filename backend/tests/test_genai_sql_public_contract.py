"""Compatibilidade do chat público v1 com o transporte privado SQL candidato."""

import pytest
from pydantic import ValidationError

from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.ai_question_publication import AIQuestionPublicRequest


def test_public_request_keeps_v1_envelope_and_strips_private_transport_fields():
    request = AIQuestionPublicRequest.model_validate({
        "contract_version": "v1",
        "question": "E no mês anterior?",
        "context": [{"role": "user", "content": "Faturamento de Recife em junho."}],
        "conversation_id": "12345678-1234-4123-8123-123456789abc",
        "continuation_token": "signed-continuation",
    })

    internal = request.without_publication()

    assert type(internal) is AIQuestionRequest
    assert internal.contract_version == "v1"
    assert internal.context == request.context
    assert "conversation_id" not in internal.model_dump()
    assert "continuation_token" not in internal.model_dump()
    assert "sql" not in AIQuestionRequest.model_fields
    assert "candidate" not in AIQuestionRequest.model_fields


def test_public_response_v1_rejects_private_sql_candidate_fields():
    public_fields = {
        "contract_version", "correlation_id", "status", "answer", "evidence",
    }
    assert public_fields <= AIQuestionResponse.model_fields.keys()
    assert "candidate" not in AIQuestionResponse.model_fields
    assert "sql" not in AIQuestionResponse.model_fields

    with pytest.raises(ValidationError):
        AIQuestionResponse.model_validate({
            "contract_version": "v1",
            "status": "answered",
            "answer": "O faturamento foi R$ 1,00.",
            "evidence": [{"source": "gold.local", "description": "Gold", "is_demo": False}],
            "candidate": {"generation_contract_version": "text-to-sql-f1-v1"},
        })


def _analysis(status, **fields):
    from app.schemas.sql_analysis import SqlAnalysisResponse

    return SqlAnalysisResponse.model_validate({
        "correlation_id": "a" * 32,
        "audit_reference": "b" * 32,
        "status": status,
        **fields,
    })


def test_public_analysis_keeps_legacy_refusals_and_clarifications_readable():
    legacy_refusal = _analysis("unsupported", unsupported_reason={
        "code": "metric_outside_f1", "message": "Fora do domínio."})
    assert legacy_refusal.unsupported_reason.reason_code is None
    legacy_question = _analysis("needs_clarification", clarification={
        "question": "Qual período?", "missing_fields": ["period"]})
    assert legacy_question.clarification.reason_code is None
    assert legacy_question.clarification.options == ()


def test_public_analysis_carries_reason_code_and_options_without_quantitative_data():
    refusal = _analysis("unsupported", unsupported_reason={
        "code": "metric_outside_f1", "message": "Fora do domínio.",
        "reason_code": "out_of_domain"})
    assert refusal.model_dump(mode="json")["unsupported_reason"]["reason_code"] == "out_of_domain"
    question = _analysis("needs_clarification", clarification={
        "question": "Junho de qual ano?", "missing_fields": ["period"],
        "reason_code": "missing_context",
        "options": [{"label": "2025", "question": "Qual a receita em junho de 2025?"}]})
    body = question.model_dump(mode="json")
    assert body["clarification"]["options"][0]["label"] == "2025"
    assert body["evidence"] is None and body["presentation"] is None


@pytest.mark.parametrize("reason", ["because", "ambiguous_subject", "missing_context"])
def test_public_refusal_rejects_unknown_or_clarification_reason(reason):
    with pytest.raises(ValidationError):
        _analysis("unsupported", unsupported_reason={
            "code": "metric_outside_f1", "message": "x", "reason_code": reason})


@pytest.mark.parametrize("reason", ["because", "out_of_domain", "security_restriction"])
def test_public_clarification_rejects_unknown_or_refusal_reason(reason):
    with pytest.raises(ValidationError):
        _analysis("needs_clarification", clarification={
            "question": "x", "missing_fields": ["context"], "reason_code": reason})
