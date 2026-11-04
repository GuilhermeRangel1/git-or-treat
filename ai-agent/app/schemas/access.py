"""Escopo interno produzido pela borda do serviço, nunca pelo corpo da solicitação."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import LogicalIdentifier
from app.schemas.domain_profile import CatalogOperation
from app.schemas.responses import CorrelationId


class AccessContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    caller_ref: LogicalIdentifier
    profile_id: LogicalIdentifier
    source_id: LogicalIdentifier
    correlation_id: CorrelationId
    allowed_operations: frozenset[CatalogOperation] = Field(default_factory=frozenset)
    allowed_metric_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)
    allowed_dimension_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)
