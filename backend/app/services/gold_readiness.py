"""Backend observa o banco e pede avaliação ao núcleo pela operação interna."""
import asyncio
from typing import Literal

import httpx
from sqlalchemy.engine import Engine

from app.repositories.gold_publication import GoldPublicationInvalid
from app.schemas.gold_publication import PublicationReference
from app.schemas.gold_readiness import GoldReadinessReport
from app.services.genai_client import GenAIResponseInvalid, _post_genai_json
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_attendance_readiness import (
    observe_attendance_readiness,
    observe_domain_readiness,
)


async def _evaluate_readiness(
    engine: Engine, *, http_client: httpx.AsyncClient, base_url: str, service_token: str,
    requested_periods: tuple[str, ...], approved_controls: frozenset[str], correlation_id: str,
    scope: Literal["attendance", "domains"], expected_batch_ref: str | None = None,
) -> GoldReadinessReport:
    observer = observe_domain_readiness if scope == "domains" else observe_attendance_readiness
    deadline = GenAIRequestDeadline.start(35)
    if expected_batch_ref is not None:
        try:
            PublicationReference.parse(expected_batch_ref)
        except ValueError:
            raise GoldPublicationInvalid("A referência esperada da publicação é inválida.") from None
    facts = await deadline.run(35, lambda: asyncio.to_thread(
        observer, engine, requested_periods=requested_periods,
        approved_controls=approved_controls, expected_batch_ref=expected_batch_ref,
    ))
    expected = facts["batch_ref"]
    data = await deadline.run(35, lambda: _post_genai_json(
        http_client=http_client, base_url=base_url.rstrip("/"), service_token=service_token,
        path="/api/v1/internal/gold-readiness", payload=facts, correlation_id=correlation_id,
    ))
    try:
        report = GoldReadinessReport.model_validate(data)
    except ValueError as exc:
        raise GenAIResponseInvalid from exc
    if report.batch_ref != expected or set(report.capabilities) != {
        "faturamento.receita", "faturamento.receita_bairro", "faturamento.preco_volume",
        "faturamento.faturas_em_aberto", "consumo.mensal_uc", "consumo.variacao_uc",
        "interrupcoes.dec_fec", "interrupcoes.uc_acumulado", "atendimento.uc_acumulado",
        "atendimento.mensal", "apoio.fila_inspecao", "apoio.medidor_uc", "apoio.energia_recuperavel",
    }:
        raise GenAIResponseInvalid
    context = await deadline.run(35, lambda: asyncio.to_thread(GoldPublicationContext.capture, engine))
    if context.batch_ref != expected:
        from app.repositories.gold_publication import GoldPublicationChanged
        raise GoldPublicationChanged("A publicação Gold mudou antes do retorno da prontidão.")
    deadline.remaining_seconds(35)
    return report


async def evaluate_attendance_readiness(
    engine: Engine, *, http_client: httpx.AsyncClient, base_url: str, service_token: str,
    requested_periods: tuple[str, ...], approved_controls: frozenset[str], correlation_id: str,
    expected_batch_ref: str | None = None,
) -> GoldReadinessReport:
    """Compatibilidade do chamador de atendimento; usa o coordenador compartilhado."""
    return await _evaluate_readiness(engine,http_client=http_client,base_url=base_url,
        service_token=service_token,requested_periods=requested_periods,
        approved_controls=approved_controls,correlation_id=correlation_id,scope="attendance",
        expected_batch_ref=expected_batch_ref)


async def evaluate_domain_readiness(
    engine: Engine, *, http_client: httpx.AsyncClient, base_url: str, service_token: str,
    requested_periods: tuple[str, ...], approved_controls: frozenset[str], correlation_id: str,
    expected_batch_ref: str | None = None,
) -> GoldReadinessReport:
    """Reutiliza o mesmo transporte e prazo para os quatro domínios."""
    return await _evaluate_readiness(engine,http_client=http_client,base_url=base_url,
        service_token=service_token,requested_periods=requested_periods,
        approved_controls=approved_controls,correlation_id=correlation_id,scope="domains",
        expected_batch_ref=expected_batch_ref)
