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
