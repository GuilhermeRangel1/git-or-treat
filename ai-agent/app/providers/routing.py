"""Escolhe o nível de modelo conforme o tipo de pergunta e o tamanho da evidência.

O roteador recebe só strings e inteiros, sem depender dos contratos de intenção e de
evidência, para continuar isolado do fluxo de perguntas. A retentativa com o nível mais
forte, quando a saída do modelo leve não tiver sustentação na evidência (``observation_ids``
ausentes, repetidos ou inexistentes), fica a cargo de quem chamar ``escalate``.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.providers.protocols import ModelAdapter


class ModelTier(StrEnum):
    """Níveis de modelo, do mais barato e rápido ao mais capaz."""

    LIGHT = "light"
    STRONG = "strong"


class RoutingPolicy(BaseModel):
    """Regras para decidir quando o modelo leve basta.

    ``light_intents`` lista os tipos de pergunta conhecidos que o modelo leve pode atender, e
    ``strong_intents`` os que exigem o modelo forte. Intenção ausente ou fora das duas listas
    vai para o modelo forte. As listas começam vazias porque os tipos de pergunta ainda estão
    sendo definidos; até serem configuradas, toda pergunta usa o modelo forte.

    Os limites de evidência são inclusivos: o modelo leve atende até ``max_light_evidence_records``
    registros e até ``max_light_evidence_chars`` caracteres de evidência serializada. O padrão
    de 50 registros cobre séries mensais de alguns anos ou um ranking curto; o de 8.000
    caracteres equivale a cerca de 2.000 tokens, folga pequena para um modelo leve conferir
    números sem perder detalhes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    light_intents: frozenset[str] = Field(default_factory=frozenset)
    strong_intents: frozenset[str] = Field(default_factory=frozenset)
    max_light_evidence_records: int = Field(default=50, ge=0)
    max_light_evidence_chars: int = Field(default=8_000, ge=0)

    @model_validator(mode="after")
    def reject_ambiguous_intents(self) -> Self:
        ambiguous = self.light_intents & self.strong_intents
        if ambiguous:
            raise ValueError(
                "Tipos de pergunta em light_intents e strong_intents ao mesmo tempo: "
                + ", ".join(sorted(ambiguous))
            )
        return self


def select_tier(
    *,
    intent: str | None,
    evidence_records: int,
    evidence_chars: int,
    policy: RoutingPolicy,
) -> ModelTier:
    """Devolve o nível exigido pela pergunta; na dúvida, o modelo forte."""

    if evidence_records < 0 or evidence_chars < 0:
        raise ValueError("O tamanho da evidência não pode ser negativo.")
    if intent is None or intent not in policy.light_intents:
        return ModelTier.STRONG
    if evidence_records > policy.max_light_evidence_records:
        return ModelTier.STRONG
    if evidence_chars > policy.max_light_evidence_chars:
        return ModelTier.STRONG
    return ModelTier.LIGHT


def escalate(tier: ModelTier) -> ModelTier | None:
    """Devolve o próximo nível mais forte, ou ``None`` se já estiver no mais forte."""

    if tier is ModelTier.LIGHT:
        return ModelTier.STRONG
    return None


class ModelTierNotConfigured(LookupError):
    """Sinaliza pedido de um nível de modelo sem adaptador configurado."""


class ModelRouter:
    """Associa cada nível a um adaptador, que pode ser uma cadeia de fallback.

    O nível forte é obrigatório e o leve, opcional. Se a política escolher o nível leve e ele
    não estiver configurado, ``route`` usa o forte.
    """

    def __init__(
        self,
        adapters: Mapping[ModelTier, ModelAdapter],
        policy: RoutingPolicy,
    ) -> None:
        normalized = {ModelTier(tier): adapter for tier, adapter in adapters.items()}
        if ModelTier.STRONG not in normalized:
            raise ValueError("Configure o nível de modelo 'strong'; ele é obrigatório.")
        self._adapters = MappingProxyType(normalized)
        self._policy = policy

    @property
    def tiers(self) -> frozenset[ModelTier]:
        return frozenset(self._adapters)

    def adapter_for(self, tier: ModelTier) -> ModelAdapter:
        try:
            return self._adapters[tier]
        except KeyError:
            configured = ", ".join(sorted(self._adapters))
            raise ModelTierNotConfigured(
                f"Nível de modelo '{tier}' não configurado; disponíveis: {configured}."
            ) from None

    def route(
        self,
        *,
        intent: str | None,
        evidence_records: int,
        evidence_chars: int,
    ) -> tuple[ModelTier, ModelAdapter]:
        tier = select_tier(
            intent=intent,
            evidence_records=evidence_records,
            evidence_chars=evidence_chars,
            policy=self._policy,
        )
        if tier not in self._adapters:
            tier = ModelTier.STRONG
        return tier, self.adapter_for(tier)
