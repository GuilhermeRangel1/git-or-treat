"""Backend admite apenas texto/citação literais de documentação vigente e autorizada."""
# ruff: noqa: F811

import asyncio
import json

import pytest

from app.schemas.ai import AIQuestionRequest
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.services.genai_client import GenAIResponseInvalid
from app.services.genai_coordination import answer_gold_question
from app.services.genai_documentation import CORPUS, validate_documentation_response
from tests.test_ai_history_store import storage  # noqa: F401
from tests.test_genai_planning_metadata import gold_v2_database  # noqa: F401


def scope():
    return AccessScope(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_operations={"read"},
        allowed_metric_ids={"billing.revenue"},
        allowed_dimension_ids=set(),
    )


def envelope():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    item = next(entry for entry in corpus["entries"] if entry["id"] == "revenue")
    return QuestionPlanResponse.model_validate(
        {
            "correlation_id": "a" * 32,
            "status": "answered",
            "documentation_reference": {"id": "revenue", "version": corpus["version"]},
            "response": {
                "correlation_id": "a" * 32,
                "status": "answered",
                "answer": "\n".join(
                    f"{x['label']}: {x['text']}" for x in item["definitions"]
                ),
                "evidence": [
                    {
                        "source": "documentation.indicators",
                        "is_demo": False,
                        "description": f"{corpus['source']} · {item['question']} · versão {corpus['version']} · trecho revenue.",
                    }
                ],
            },
        }
    )


@pytest.mark.parametrize("mutation", ["text", "citation", "version", "scope"])
def test_forged_or_unauthorized_document_response_is_not_admitted(mutation):
    response, identity = envelope(), scope()
    if mutation == "text":
        response.response.answer += " Receita de R$ 123."
    elif mutation == "citation":
        response.response.evidence[0].description = "Citação inventada."
    elif mutation == "version":
        response.documentation_reference = response.documentation_reference.model_copy(
            update={"version": "0" * 12}
        )
    else:
        identity = identity.model_copy(update={"allowed_metric_ids": frozenset()})
    with pytest.raises(GenAIResponseInvalid):
        validate_documentation_response(response, identity)


def test_gold_coordinator_serves_document_with_audit_and_without_sql_executor(
    gold_v2_database,
):
    class Client:
        async def plan(self, payload, **_):
            assert payload.access_scope == scope()
            return envelope()

    class Audit:
        def record(self, event, **_):
            return "audit-test-reference"

    result = asyncio.run(
        answer_gold_question(
            gold_v2_database,
            Client(),
            AIQuestionRequest(question="O que significa receita faturada?"),
            resolve_scope=scope,
            correlation_id="a" * 32,
            audit_store=Audit(),
        )
    )
    assert result.status == "answered" and result.answer == envelope().response.answer
    assert result.audit_reference == "audit-test-reference"
    assert result.analysis_context is None and result.continuation_token is None


def test_history_does_not_serve_removed_document_or_cached_old_citation(
    storage, tmp_path, monkeypatch
):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.services import genai_documentation as documentation

    _, owner, _ = storage
    conversation = owner.create(str(uuid4()))["id"]
    request_id = str(uuid4())
    _, _, attempt = owner.reserve(conversation, request_id, "payload", "scope")
    owner.finish(
        conversation,
        request_id,
        attempt,
        "O que significa receita?",
        envelope().response,
    )
    assert owner.detail(conversation, "scope")["exchanges"][0]["state"] == "completed"
    path = tmp_path / "removed.json"
    path.write_text(
        '{"entries": [], "version": "000000000000", "catalogVersion": "gold-catalog-v2"}'
    )
    monkeypatch.setattr(documentation, "CORPUS", path)
    item = owner.detail(conversation, "scope")["exchanges"][0]
    assert item["state"] == "unavailable" and item["response"] is None
    with pytest.raises(HTTPException) as exc:
        owner.reserve(conversation, request_id, "payload", "scope")
    assert exc.value.status_code == 409


def test_revocation_after_document_validation_does_not_serve_definition(
    gold_v2_database,
):
    class Client:
        async def plan(self, payload, **_):
            return envelope()

    class Audit:
        def record(self, event, **_):
            return "test-audit"

    calls = 0

    def resolve():
        nonlocal calls
        calls += 1
        return (
            scope()
            if calls < 3
            else scope().model_copy(update={"allowed_metric_ids": frozenset()})
        )

    result = asyncio.run(
        answer_gold_question(
            gold_v2_database,
            Client(),
            AIQuestionRequest(question="O que significa receita?"),
            resolve_scope=resolve,
            correlation_id="a" * 32,
            audit_store=Audit(),
        )
    )
    assert result.status == "refused" and not result.evidence and result.answer is None
