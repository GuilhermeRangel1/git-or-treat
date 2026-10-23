"""Operational evidence v1, independent of evolving analytical response models.

Missing schema version identifies records created before explicit versioning.
JSON extension fields retain evidence without interpreting future analytical fields.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue


class SuspicionEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue]

    uc_id: str
    reason: str
    rule_version: str
    priority: float
    potential_recoverable_energy_kwh: float | None
    indicators: list[str]
    signals: list[dict[str, JsonValue]]
    estimate_evidence: dict[str, JsonValue]
    limitations: list[str]


class OrderSnapshotV1(BaseModel):
    snapshot_schema_version: Literal["1"] = "1"
    data: SuspicionEvidenceV1
    metadata: dict[str, JsonValue]
