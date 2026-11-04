"""Adaptador padrão usado até a configuração de um provedor real."""

from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn


class UnavailableModelAdapter:
    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        raise ModelProviderUnavailable("Nenhum provedor de modelo foi configurado.")
