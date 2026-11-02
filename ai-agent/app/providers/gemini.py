"""Adaptador opcional para o Gemini Developer API via SDK oficial Google Gen AI."""

from typing import Any

from pydantic import ValidationError

from app.generation.prompts import SYSTEM_INSTRUCTION, generation_contents
from app.generation.selection import parse_answer, response_model
from app.providers.protocols import (
    GeneratedAnswer,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn


class GeminiModelAdapter:
    """Gera respostas estruturadas sem executar ferramentas ou consultas ao banco."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None = None,
        timeout_ms: int = 20_000,
        client: Any | None = None,
    ) -> None:
        self._model_name = model_name
        if client is None:
            if not api_key:
                raise ValueError("Uma chave Gemini é necessária para criar o cliente.")
            try:
                from google import genai
            except ImportError:
                raise ImportError(
                    'Instale a dependência opcional com "python -m pip install -e ".[gemini]".'
                ) from None

            client = genai.Client(
                api_key=api_key,
                http_options={
                    "timeout": timeout_ms,
                    "retry_options": {"attempts": 1},
                },
            )
        self._client = client

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        contents = generation_contents(question, context, evidence)
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=contents,
                config={
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_json_schema": response_model(evidence).model_json_schema(),
                },
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if isinstance(status, str) and status.isdecimal():
                status = int(status)
            if not isinstance(status, int):
                status = getattr(exc, "code", None)
                if isinstance(status, str) and status.isdecimal():
                    status = int(status)
            if isinstance(status, int) and 400 <= status < 500 and status != 429:
                raise ModelProviderRejected("O provedor rejeitou a solicitação.") from None
            if not isinstance(exc, (ConnectionError, TimeoutError, OSError)) and not (
                status == 429 or isinstance(status, int) and status >= 500
            ):
                raise ModelProviderRejected("O provedor rejeitou a solicitação.") from None
            raise ModelProviderUnavailable(
                "O provedor de modelo está temporariamente indisponível."
            ) from None

        try:
            candidates = getattr(response, "candidates", None)
            if candidates:
                reason = getattr(candidates[0], "finish_reason", None)
                if reason is not None and getattr(reason, "value", reason) != "STOP":
                    raise ValueError("geracao incompleta")
            response_text = response.text
            if not isinstance(response_text, str) or not response_text.strip():
                raise ValueError("resposta vazia")
            return parse_answer(response_text, evidence)
        except (AttributeError, TypeError, ValueError, ValidationError):
            raise ModelProviderInvalidResponse(
                "O provedor retornou uma resposta inválida."
            ) from None
