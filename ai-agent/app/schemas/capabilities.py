"""Contrato público para descoberta das capacidades disponíveis."""

from pydantic import BaseModel, ConfigDict


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: str
    question_endpoint: str
    requires_gold: bool
    requires_model: bool
