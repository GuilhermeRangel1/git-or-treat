"""Cliente interno do serviço GenAI para o contrato conversacional v1."""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from time import monotonic
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


logger = logging.getLogger(__name__)


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

        if getattr(result, "visualization", None) is not None:
            raise GenAIResponseInvalid
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
        if result.response is not None and result.response.visualization is not None:
            raise GenAIResponseInvalid
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
        if getattr(result, "visualization", None) is not None:
            raise GenAIResponseInvalid
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
        cache_ttl_seconds: float = 120,
        cache_max_entries: int = 64,
        cache_max_bytes: int = 1_048_576,
        cache_namespace: str = "insight-v1",
    ) -> None:
        if cache_ttl_seconds < 0 or cache_max_entries < 1 or cache_max_bytes < 1:
            raise ValueError("Limites de cache inválidos.")
        self._cache_ttl = cache_ttl_seconds
        self._cache_entries = cache_max_entries
        self._cache_bytes_limit = cache_max_bytes
        self._cache_namespace = cache_namespace
        self._cache_sizes: dict[str, int] = {}
        self._cache_bytes = 0
        self._gold_pending: dict[str, asyncio.Task] = {}
        self._gold_waiters: dict[str, int] = {}
        self._http_client = http_client
        self._base_url = base_url.rstrip("/") if base_url else None
        self._service_token = service_token
        self._gold_insights: OrderedDict[str, tuple[float, AIInsightResponse]] = OrderedDict()

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


    def _cache_key(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(
            {"namespace": self._cache_namespace, "payload": {
                k: v for k, v in payload.items() if k != "remaining_timeout_ms"
            }}, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()

    def _drop_cached(self, key: str) -> None:
        self._gold_insights.pop(key, None)
        self._cache_bytes -= self._cache_sizes.pop(key, 0)

    async def synthesize_gold(self, payload: dict[str, Any], *, correlation_id: str) -> AIInsightResponse:
        if self._cache_ttl == 0:
            return await self._synthesize_gold(payload, correlation_id=correlation_id)
        key = self._cache_key(payload)
        task = self._gold_pending.get(key)
        if task is not None:
            logger.info("genai_insight_cache outcome=shared")
        if task is None:
            if len(self._gold_pending) >= self._cache_entries:
                return await self._synthesize_gold(payload, correlation_id=correlation_id)
            task = asyncio.create_task(self._synthesize_gold(payload, correlation_id=correlation_id))
            self._gold_pending[key] = task
            def finished(done):
                if self._gold_pending.get(key) is done:
                    self._gold_pending.pop(key, None)
                if not done.cancelled():
                    done.exception()
            task.add_done_callback(finished)
        self._gold_waiters[key] = self._gold_waiters.get(key, 0) + 1
        try:
            result = await asyncio.shield(task)
            return result.model_copy(deep=True, update={
                "correlation_id": correlation_id, "audit_reference": None,
            })
        finally:
            self._gold_waiters[key] -= 1
            if self._gold_waiters[key] == 0:
                self._gold_waiters.pop(key)
                if not task.done():
                    self._gold_pending.pop(key, None)
                    task.cancel()

    async def _synthesize_gold(self, payload: dict[str, Any], *, correlation_id: str) -> AIInsightResponse:
        """Usa a borda interna; o contexto nunca vem diretamente do navegador."""
        # O coordenador sempre refaz autorização, prontidão e leitura antes daqui.
        # O conteúdo completo (incluindo escopo e lote) isola a síntese reutilizada.
        key = self._cache_key(payload)
        now = monotonic()
        for expired_key, (expires, _) in list(self._gold_insights.items()):
            if expires <= now:
                self._drop_cached(expired_key)
        cached = self._gold_insights.get(key)
        if cached and cached[0] > monotonic():
            logger.info("genai_insight_cache outcome=hit entries=%d payload_bytes=%d",
                        len(self._gold_insights), self._cache_bytes)
            self._gold_insights.move_to_end(key)
            return cached[1].model_copy(deep=True, update={
                "correlation_id": correlation_id, "audit_reference": None,
            })
        self._drop_cached(key)
        logger.info("genai_insight_cache outcome=miss")
        response = await _post_genai_json(
            http_client=self._http_client, base_url=self._base_url,
            service_token=self._service_token,
            path="/api/v1/internal/insight-syntheses", payload=payload,
            correlation_id=correlation_id,
        )
        try:
            result = AIInsightResponse.model_validate(response)
        except (ValueError, ValidationError) as exc:
            raise GenAIResponseInvalid from exc
        if result.correlation_id != correlation_id:
            raise GenAIResponseInvalid
        # Armazena somente síntese respondida e vinculada ao contexto recebido.
        screen = payload["screen"]
        if result.status == "answered" and (
            result.context.model_dump(mode="json") == {
                k: v for k, v in screen.items()
                if k not in {"observations", "reference", "limitations"}
            }
            and [v.model_dump(mode="json") for v in result.observation.values]
            == screen["observations"]
            and result.evidence
            and all(not v.is_demo and v.source == "gold.local" for v in result.evidence)
            and set(screen["limitations"]) <= set(result.limitations)
        ):
            size = len(key.encode()) + len(result.model_dump_json().encode())
            if self._cache_ttl > 0 and size <= self._cache_bytes_limit:
                self._drop_cached(key)
                self._gold_insights[key] = (monotonic() + self._cache_ttl, result.model_copy(deep=True))
                self._cache_sizes[key] = size
                self._cache_bytes += size
                while (len(self._gold_insights) > self._cache_entries
                       or self._cache_bytes > self._cache_bytes_limit):
                    self._drop_cached(next(iter(self._gold_insights)))
        return result
