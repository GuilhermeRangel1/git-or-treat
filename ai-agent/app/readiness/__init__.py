"""Prontidão da Gold por capacidade, consumida pelo catálogo, pelo executor e pelo portal."""

from app.readiness.evaluate import evaluate_readiness
from app.readiness.models import (
    READINESS_VERSION,
    CapabilityReadiness,
    CapabilityStatus,
    GoldTable,
    LotState,
    PublicationFacts,
    ReadinessReport,
    ReasonCode,
    TableFacts,
)
from app.readiness.requirements import CAPABILITY_REQUIREMENTS, CapabilityRequirement, CaseDomain

__all__ = [
    "CAPABILITY_REQUIREMENTS",
    "READINESS_VERSION",
    "CapabilityReadiness",
    "CapabilityRequirement",
    "CapabilityStatus",
    "CaseDomain",
    "GoldTable",
    "LotState",
    "PublicationFacts",
    "ReadinessReport",
    "ReasonCode",
    "TableFacts",
    "evaluate_readiness",
]
