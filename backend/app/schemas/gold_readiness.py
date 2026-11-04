"""Envelope de retorno da prontidão; contrato independente do processo GenAI."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.genai_evidence import GoldBatchRef


class CapabilityReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["available", "unavailable"]
    reasons: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def validate_reasons(self):
        allowed = {"table_missing", "table_empty", "period_missing", "period_insufficient",
                   "definition_pending", "control_pending", "source_not_in_gold",
                   "publication_stale", "publication_mixed", "publication_unidentified",
                   "backend_unavailable", "control_failed", "control_publication_mismatch",
                   "coverage_missing", "coverage_incomplete", "coverage_publication_mismatch"}
        if (not set(self.reasons) <= allowed or len(set(self.reasons)) != len(self.reasons)
                or (self.status == "available") != (not self.reasons)):
            raise ValueError("Estado de prontidão inválido.")
        return self


class GoldReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    readiness_version: Literal["gold-readiness-v2"]
    batch_ref: GoldBatchRef
    lot_state: Literal["ready", "partial", "mixed", "stale", "empty", "unavailable", "invalid"]
    capabilities: dict[str, CapabilityReadiness] = Field(max_length=64)
