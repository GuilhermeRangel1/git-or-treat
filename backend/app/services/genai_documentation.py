"""Confere resposta documental na cópia canônica do Backend antes da publicação."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_internal import (
    AccessScope,
    DocumentationReference,
    QuestionPlanResponse,
)
from app.services.genai_client import GenAIResponseInvalid

CORPUS = Path(__file__).resolve().parents[1] / "corpora/indicators.json"


def validate_documentation_response(
    envelope: QuestionPlanResponse,
    scope: AccessScope,
    *,
    path: Path = CORPUS,
) -> None:
    reference, response = envelope.documentation_reference, envelope.response
    try:
        if reference is None or response is None or path.stat().st_size > 65536:
            raise ValueError
        corpus = json.loads(path.read_text(encoding="utf-8"))
        entries = corpus["entries"]
        digest = hashlib.sha256(
            json.dumps(
                entries,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:12]
        if (
            corpus["catalogVersion"] != "gold-catalog-v2"
            or corpus["version"] != digest
            or reference.version != digest
            or "read" not in scope.allowed_operations
            or scope.source_id != "gold.local"
            or scope.profile_id != "v-energy-grid-360-gold"
        ):
            raise ValueError
        matches = [entry for entry in entries if entry["id"] == reference.id]
        if len(matches) != 1:
            raise ValueError
        entry = matches[0]
        today = datetime.now(UTC).date()
        if (
            entry["status"] != "active"
            or "assistente" not in entry["screens"]
            or entry["audience"] != "Pessoas usuárias do portal interno"
            or date_value(entry["validFrom"]) > today
            or entry["validUntil"] is not None
            and date_value(entry["validUntil"]) < today
            or not {item["metricId"] for item in entry["definitions"]}
            <= scope.allowed_metric_ids
        ):
            raise ValueError
        expected = "\n".join(
            f"{item['label']}: {item['text']}" for item in entry["definitions"]
        )
        description = (
            f"{corpus['source']} · {entry['question']} · versão {digest} "
            f"· trecho {entry['id']}."
        )
        if (
            response.answer != expected
            or response.analysis_context is not None
            or response.model_tier is not None
            or response.continuation_token is not None
            or len(response.evidence) != 1
            or response.evidence[0].source != "documentation.indicators"
            or response.evidence[0].description != description
            or response.evidence[0].is_demo
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, OSError):
        raise GenAIResponseInvalid(
            "Resposta documental não corresponde à fonte autorizada."
        ) from None


def date_value(value):
    return date.fromisoformat(value)


def document_response_is_current(response: AIQuestionResponse) -> bool:
    """Só revalida conteúdo; o consumidor continua obrigado a conferir o escopo."""
    if not any(item.source == "documentation.indicators" for item in response.evidence):
        return True
    try:
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        for entry in corpus["entries"]:
            envelope = QuestionPlanResponse(
                correlation_id="a" * 32,
                status="answered",
                response=response.model_copy(
                    update={"correlation_id": "a" * 32, "continuation_token": None}
                ),
                documentation_reference=DocumentationReference(
                    id=entry["id"], version=corpus["version"]
                ),
            )
            scope = AccessScope(
                caller_ref="history.validation",
                profile_id="v-energy-grid-360-gold",
                source_id="gold.local",
                allowed_operations={"read"},
                allowed_metric_ids={item["metricId"] for item in entry["definitions"]},
                allowed_dimension_ids=set(),
            )
            try:
                validate_documentation_response(envelope, scope)
                return True
            except GenAIResponseInvalid:
                continue
        return False
    except (ValueError, KeyError, TypeError, OSError):
        return False
