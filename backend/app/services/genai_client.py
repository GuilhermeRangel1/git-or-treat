"""Cliente interno do serviço GenAI para o contrato conversacional v1."""

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.schemas.ai import (
    AIQuestionErrorResponse,
    AIQuestionRequest,
    AIQuestionResponse,
)
from app.schemas.ai_insight import AIInsightRequest, AIInsightResponse
from app.schemas.genai_internal import (
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionSynthesisRequest,
)


class GenAIServiceUnavailable(Exception):
    """A integração não está configurada ou o serviço não pôde ser alcançado."""

    def __init__(self, message: str = "", *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class GenAITimeout(Exception):
    """O serviço GenAI excedeu o prazo configurado pelo Backend."""


class GenAIResponseInvalid(Exception):
    """O serviço GenAI devolveu status, JSON ou contrato inesperado."""


async def _post_genai_json(
    *,
    http_client: httpx.AsyncClient,
    base_url: str | None,
    service_token: str | None,
    path: str,
    payload: BaseModel | dict[str, Any],
    correlation_id: str,
) -> Any:
    """Executa o transporte privado comum e valida o envelope HTTP/JSON básico."""
    if base_url is None or service_token is None:
        raise GenAIServiceUnavailable

    request_payload = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    headers = {
        "Authorization": f"Bearer {service_token}",
        "X-Correlation-ID": correlation_id,
    }

    try:
        response = await http_client.post(
            f"{base_url}{path}",
            json=request_payload,
            headers=headers,
        )
    except httpx.TimeoutException as exc:
        raise GenAITimeout from exc
    except httpx.RequestError as exc:
        raise GenAIServiceUnavailable from exc

    if response.status_code == 503:
        try:
            body = response.json()
        except ValueError:
            body = None
        # Proxies podem retornar HTML ou JSON genérico durante indisponibilidade.
        # Um envelope que declara o contrato, porém, precisa ser válido e correlacionado.
        if isinstance(body, dict) and (
            "contract_version" in body or body.get("status") == "error"
        ):
            try:
                error = AIQuestionErrorResponse.model_validate(body)
            except ValueError as exc:
                raise GenAIResponseInvalid from exc
            if (
                error.correlation_id != correlation_id
                or response.headers.get("x-correlation-id") != correlation_id
                or error.error.code != "service_unavailable"
            ):
                raise GenAIResponseInvalid
            raise GenAIServiceUnavailable(retryable=error.error.retryable)
        raise GenAIServiceUnavailable

    if response.status_code != 200:
        raise GenAIResponseInvalid

    try:
        result = response.json()
    except ValueError as exc:
        raise GenAIResponseInvalid from exc

    if response.headers.get("x-correlation-id") != correlation_id:
        raise GenAIResponseInvalid
    return result


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
        response_payload = await _post_genai_json(
            http_client=self._http_client,
            base_url=self._base_url,
            service_token=self._service_token,
            path="/api/v1/questions",
            payload=payload,
            correlation_id=correlation_id,
        )

        try:
            result = AIQuestionResponse.model_validate(response_payload)
        except (ValueError, ValidationError) as exc:
            raise GenAIResponseInvalid from exc

        if result.correlation_id != correlation_id:
            raise GenAIResponseInvalid
        return result

    async def plan(
        self, payload: QuestionPlanRequest, *, correlation_id: str
    ) -> QuestionPlanResponse:
        """Planeja com metadados confiáveis; não usa a rota demonstrativa como fallback."""
        response_payload = await _post_genai_json(
            http_client=self._http_client,
            base_url=self._base_url,
            service_token=self._service_token,
            path="/api/v1/internal/question-plans",
            payload=payload,
            correlation_id=correlation_id,
        )
        try:
            result = QuestionPlanResponse.model_validate(response_payload)
        except ValueError as exc:
            raise GenAIResponseInvalid from exc
        if result.correlation_id != correlation_id:
            raise GenAIResponseInvalid
        return result

    async def evaluate_readiness(self, engine, **kwargs):
        """Reusa o observador Backend e a operação interna de prontidão."""
        from app.services.gold_readiness import evaluate_domain_readiness
        if self._base_url is None or self._service_token is None:
            raise GenAIServiceUnavailable
        return await evaluate_domain_readiness(
            engine, http_client=self._http_client, base_url=self._base_url,
            service_token=self._service_token, **kwargs,
        )

    async def synthesize(
        self, payload: QuestionSynthesisRequest, *, correlation_id: str
    ) -> AIQuestionResponse:
        """Entrega lookup concluído ao mesmo núcleo; falha não ativa outra fonte."""
        response_payload = await _post_genai_json(
            http_client=self._http_client,
            base_url=self._base_url,
            service_token=self._service_token,
            path="/api/v1/internal/question-syntheses",
            payload=payload,
            correlation_id=correlation_id,
        )
        try:
            result = AIQuestionResponse.model_validate(response_payload)
        except ValueError as exc:
            raise GenAIResponseInvalid from exc
        if result.correlation_id != correlation_id:
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
        response_payload = await _post_genai_json(
            http_client=self._http_client,
            base_url=self._base_url,
            service_token=self._service_token,
            path="/api/v1/insights",
            payload=payload,
            correlation_id=correlation_id,
        )

        try:
            result = AIInsightResponse.model_validate(response_payload)
        except (ValueError, ValidationError) as exc:
            raise GenAIResponseInvalid from exc

        if result.correlation_id != correlation_id:
            raise GenAIResponseInvalid
        return result
