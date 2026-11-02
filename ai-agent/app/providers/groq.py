"""Adaptador opcional para o Groq pela API compatível com OpenAI, via httpx."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr, ValidationError

from app.generation.prompts import SYSTEM_INSTRUCTION, generation_contents
from app.generation.selection import parse_answer, response_model
from app.providers.protocols import (
    GeneratedAnswer,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.questions import ConversationTurn

if TYPE_CHECKING:
    from app.schemas.evidence import EvidenceResult

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

# O JSON mode do Groq não recebe esquema; ele segue no prompt de sistema.
SYSTEM_PROMPT = (
    f"{SYSTEM_INSTRUCTION}\n"
    "Responda com um único objeto JSON, sem texto fora dele, que siga este esquema JSON:\n"
    f"{json.dumps(GeneratedAnswer.model_json_schema(), ensure_ascii=False)}"
)


class GroqModelAdapter:
    """Gera respostas estruturadas sem executar ferramentas ou consultas ao banco."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: SecretStr,
        timeout_ms: int = 20_000,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.get_secret_value().strip():
            raise ValueError("Uma chave Groq é necessária para chamar o provedor.")
        self._model_name = model_name
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_ms / 1000)
        self._client = client
        self._transport = transport

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        contents = generation_contents(question, context, evidence)
        system_prompt = (
            f"{SYSTEM_INSTRUCTION}\n"
            "Responda com um único objeto JSON, sem texto fora dele, que siga este esquema JSON:\n"
            f"{json.dumps(response_model(evidence).model_json_schema(), ensure_ascii=False)}"
        )
        payload = {
            "model": self._model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": contents},
            ],
        }
        try:
            response = await self._post(payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                raise ModelProviderUnavailable(
                    "O provedor de modelo está temporariamente indisponível."
                ) from None
            raise ModelProviderRejected("O provedor rejeitou a solicitação.") from None
        except httpx.TransportError:
            # Inclui timeouts e falhas de rede.
            raise ModelProviderUnavailable(
                "O provedor de modelo está temporariamente indisponível."
            ) from None
        except httpx.HTTPError:
            raise ModelProviderRejected("O provedor rejeitou a solicitação.") from None

        try:
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise ValueError("geracao incompleta")
            response_text = choice["message"]["content"]
            if not isinstance(response_text, str) or not response_text.strip():
                raise ValueError("resposta vazia")
            return parse_answer(response_text, evidence)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise ModelProviderInvalidResponse(
                "O provedor retornou uma resposta inválida."
            ) from None

    async def _post(self, payload: dict[str, object]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        if self._client is not None:
            return await self._client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            return await client.post(GROQ_CHAT_COMPLETIONS_URL, json=payload, headers=headers)
