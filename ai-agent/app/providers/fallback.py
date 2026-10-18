"""Encadeia adaptadores de modelo para tolerar indisponibilidade de um deles."""

import asyncio
import logging
from collections.abc import Sequence

from app.providers.protocols import (
    GeneratedAnswer,
    ModelAdapter,
    ModelProviderUnavailable,
)
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn

logger = logging.getLogger(__name__)


class FallbackModelAdapter:
    """Tenta cada adaptador em ordem até um responder, dentro de um prazo total opcional.

    Só ``ModelProviderUnavailable`` aciona o próximo adaptador; outros erros sobem intactos
    para não mascarar defeitos. Hoje todos os modelos usam o mesmo provedor e a mesma chave,
    então a cadeia não protege contra fim de cota nem queda do provedor. Cada novo provedor
    entrará como um adaptador novo na lista.
    """

    def __init__(
        self,
        adapters: Sequence[ModelAdapter],
        *,
        total_timeout_seconds: float | None = None,
    ) -> None:
        if not adapters:
            raise ValueError("Informe ao menos um adaptador de modelo.")
        self._adapters = tuple(adapters)
        self._total_timeout_seconds = total_timeout_seconds

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        try:
            async with asyncio.timeout(self._total_timeout_seconds) as deadline:
                return await self._generate_in_order(question, context, evidence)
        except TimeoutError:
            if not deadline.expired():
                raise
            logger.warning("Prazo total da cadeia de modelos esgotado.")
            raise ModelProviderUnavailable(
                "O provedor de modelo está temporariamente indisponível."
            ) from None

    async def _generate_in_order(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        total = len(self._adapters)
        for position, adapter in enumerate(self._adapters, start=1):
            try:
                return await adapter.generate(question, context, evidence)
            except ModelProviderUnavailable:
                logger.warning(
                    "Adaptador de modelo %d/%d (%s) indisponível.",
                    position,
                    total,
                    type(adapter).__name__,
                )
        raise ModelProviderUnavailable("O provedor de modelo está temporariamente indisponível.")
