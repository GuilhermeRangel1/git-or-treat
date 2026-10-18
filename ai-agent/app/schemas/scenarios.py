"""Contratos tipados para cenários analíticos de demonstração."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisIntent
from app.tools.evidence import EvidenceResult


class SyntheticScenario(BaseModel):
    """Pergunta de demonstração, intenção esperada e evidência inteiramente sintética."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    question: str = Field(min_length=1, max_length=1000)
    intent: AnalysisIntent
    evidence: EvidenceResult
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_demo_evidence(self) -> Self:
        if not self.evidence.reference.is_demo:
            raise ValueError(
                "evidência de cenário sintético precisa estar marcada como demonstração"
            )
        return self
