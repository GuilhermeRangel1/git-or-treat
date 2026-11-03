"""Contexto curto assinado: somente recorte, sem respostas, linhas ou histórico."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.ai import AIConversationTurn, AIQuestionText
from app.schemas.genai_internal import AccessScope
from app.schemas.genai_plan import LogicalReadPlan, WindowKind
from app.services.gold_catalog import load_gold_catalog

TTL_SECONDS = 1800
MAX_TOKEN_LENGTH = 16000
DIMENSIONS = {
    "geography.municipality": "município",
    "geography.neighborhood": "bairro",
    "customer.consumption_class": "classe",
    "network.feeder": "alimentador",
}
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ContinuationState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1] = 1
    kind: Literal["executed", "pending"] = "executed"
    expires: int = Field(strict=True, gt=0)
    session: Digest
    conversation: str = Field(min_length=1, max_length=36)
    scope: Digest
    catalog: Digest
    batch: str = Field(min_length=1, max_length=200)
    question: AIQuestionText
    response_digest: Digest


class InvalidContinuation(ValueError):
    """Referência expirada, adulterada ou pertencente a outro contexto."""


def canonical_question(plan: LogicalReadPlan) -> str | None:
    """Só representa planos que podem ser expressos integralmente no núcleo atual."""
    metric = next(
        (m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id), None
    )
    if metric is None or len(plan.group_by_dimension_ids) > 1:
        return None
    question = f"Qual foi {metric.label.lower()}"
    if plan.group_by_dimension_ids:
        dimension = DIMENSIONS.get(plan.group_by_dimension_ids[0])
        if dimension is None:
            return None
        if plan.order is not None:
            direction = "maior" if plan.order.direction == "desc" else "menor"
            question = f"Qual {dimension} teve {direction} {metric.label.lower()}"
            if plan.limit > 1 and plan.comparison_periods is None:
                plural = {"município": "municípios", "bairro": "bairros",
                          "classe": "classes", "alimentador": "alimentadores"}[dimension]
                question = f"Top {plan.limit} {plural} com {direction} {metric.label.lower()}"
        else:
            question += f" por {dimension}"
    elif plan.order is not None:
        return None
    for item in plan.filters:
        dimension = DIMENSIONS.get(item.dimension_id)
        if dimension is None or item.operator.value != "eq" or len(item.values) != 1:
            return None
        value = item.values[0]
        if not isinstance(value, str):
            return None
        prefix = "no" if dimension in {"município", "bairro", "alimentador"} else "na"
        question += f" {prefix} {dimension} {value}"
    if plan.comparison_periods is not None:
        question = "Compare " + question.removeprefix("Qual foi ")
        question += (
            f" entre {plan.comparison_periods[0]} e {plan.comparison_periods[1]}"
        )
    elif plan.window.kind is WindowKind.BOUNDED:
        start = plan.window.start.strftime("%Y-%m")
        end = plan.window.end.strftime("%Y-%m")
        question += f" em {start}" if start == end else f" de {start} a {end}"
    else:
        question += f" no {plan.window.phrase}"
    question += "?"
    return question if len(question) <= 1000 else None


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _scope_digest(scope: AccessScope) -> str:
    return _digest(
        {
            key: sorted(value) if isinstance(value, frozenset) else value
            for key, value in scope.model_dump().items()
        }
    )


def _catalog_digest() -> str:
    return _digest(load_gold_catalog().model_dump(mode="json"))


def _key(secret: str) -> bytes:
    return hmac.digest(secret.encode(), b"grid360:genai:continuation:v1", "sha256")


def issue_continuation(
    plan: LogicalReadPlan,
    scope: AccessScope,
    batch_ref: str,
    *,
    session: str,
    conversation: str,
    secret: str,
    response_text: str = "",
) -> str | None:
    question = canonical_question(plan)
    if question is None or not session or not conversation:
        return None
    return issue_context_continuation(question, scope, batch_ref, session=session,
        conversation=conversation, secret=secret, response_text=response_text)


def issue_context_continuation(
    question, scope, batch_ref, *, session, conversation, secret, response_text="", kind="executed",
):
    """Renova uma âncora capturada pelo servidor, nunca um texto fornecido como autoridade pelo cliente."""
    payload = ContinuationState(
        kind=kind,
        expires=int(time.time()) + TTL_SECONDS,
        session=_digest(session),
        conversation=conversation,
        scope=_scope_digest(scope),
        catalog=_catalog_digest(),
        batch=batch_ref,
        question=question,
        response_digest=_digest(response_text[:1000]),
    )
    serialized = payload.model_dump_json(exclude={"kind"} if kind == "executed" else set())
    data = base64.urlsafe_b64encode(serialized.encode()).decode()
    token = data + "." + hmac.digest(_key(secret), data.encode(), "sha256").hex()
    return token if len(token) <= MAX_TOKEN_LENGTH else None


def restore_continuation(
    token: str,
    scope: AccessScope,
    *,
    session: str,
    conversation: str,
    secret: str,
    context: Sequence[AIConversationTurn],
) -> tuple[str, list[AIConversationTurn]]:
    try:
        if len(token) > MAX_TOKEN_LENGTH:
            raise ValueError
        data, signature = token.split(".")
        expected = hmac.digest(_key(secret), data.encode(), "sha256").hex()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = ContinuationState.model_validate_json(
            base64.b64decode(data, altchars=b"-_", validate=True),
        )
        if (
            payload.expires <= time.time()
            or payload.session != _digest(session)
            or payload.conversation != conversation
            or payload.scope != _scope_digest(scope)
            or payload.catalog != _catalog_digest()
        ):
            raise ValueError
        anchor = AIConversationTurn(role="user", content=payload.question)
        if payload.kind == "pending" and (
            not context or context[-1].role == "assistant"
            and _digest(context[-1].content) == payload.response_digest
        ):
            # O estado vem da assinatura; o texto não é um marcador a interpretar.
            return payload.batch, [anchor, AIConversationTurn(
                role="assistant", content="Há um esclarecimento pendente para esta pergunta.",
            )]
        if (
            context
            and context[-1].role == "assistant"
            and _digest(context[-1].content) == payload.response_digest
        ):
            return payload.batch, [anchor]
        # O contexto recente permite responder esclarecimentos. É replanejado e
        # nunca concede permissão; a âncora vem apenas de uma consulta concluída.
        return payload.batch, [anchor, *context[-2:]]
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise InvalidContinuation from None
