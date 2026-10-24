"""Cliente interno do serviço GenAI para o contrato conversacional v1."""

from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas.ai import AIQuestionRequest, AIQuestionResponse
from app.schemas.ai_insight import AIInsightRequest, AIInsightResponse


class GenAIServiceUnavailable(Exception):
    """A integração não está configurada ou o serviço não pôde ser alcançado."""


class GenAITimeout(Exception):
    """O serviço GenAI excedeu o prazo configurado pelo Backend."""


class GenAIResponseInvalid(Exception):
    """O serviço GenAI devolveu status, JSON ou contrato inesperado."""


class GenAIQuestionClient:
    """Encaminha somente o contrato de pergunta para o endpoint privado da GenAI."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str | None,
        service_token: str | None,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/") if base_url else None
        self._service_token = service_token

    async def ask(
        self,
        payload: AIQuestionRequest | dict[str, Any],
        *,
        correlation_id: str,
    ) -> AIQuestionResponse:
        if self._base_url is None or self._service_token is None:
            raise GenAIServiceUnavailable

        request_payload = (
            payload.model_dump(mode="json")
            if isinstance(payload, AIQuestionRequest)
            else payload
        )
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "X-Correlation-ID": correlation_id,
        }

        try:
            response = await self._http_client.post(
                f"{self._base_url}/api/v1/questions",
                json=request_payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise GenAITimeout from exc
        except httpx.RequestError as exc:
            raise GenAIServiceUnavailable from exc

        if response.status_code != 200:
            raise GenAIResponseInvalid

        try:
            result = AIQuestionResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise GenAIResponseInvalid from exc

        if (
            result.correlation_id != correlation_id
            or response.headers.get("x-correlation-id") != correlation_id
        ):
            raise GenAIResponseInvalid
        return result


class GenAIInsightClient:
    """Encaminha o contrato de insight já publicado pelo serviço GenAI."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str | None,
        service_token: str | None,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/") if base_url else None
        self._service_token = service_token

    async def generate(
        self,
        payload: AIInsightRequest | dict[str, Any],
        *,
        correlation_id: str,
    ) -> AIInsightResponse:
        if self._base_url is None or self._service_token is None:
            raise GenAIServiceUnavailable

        request_payload = (
            payload.model_dump(mode="json")
            if isinstance(payload, AIInsightRequest)
            else payload
        )
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "X-Correlation-ID": correlation_id,
        }

        try:
            response = await self._http_client.post(
                f"{self._base_url}/api/v1/insights",
                json=request_payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise GenAITimeout from exc
        except httpx.RequestError as exc:
            raise GenAIServiceUnavailable from exc

        if response.status_code != 200:
            raise GenAIResponseInvalid

        try:
            result = AIInsightResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise GenAIResponseInvalid from exc

        if (
            result.correlation_id != correlation_id
            or response.headers.get("x-correlation-id") != correlation_id
        ):
            raise GenAIResponseInvalid
        return result
