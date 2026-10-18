"""Política de leitura independente de nomes físicos da fonte."""

from pydantic import ValidationError

from app.ports.evidence import EvidenceAccessDenied
from app.schemas.access import AccessContext
from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import (
    CatalogOperation,
    CatalogSensitivity,
    DimensionRole,
    DomainProfile,
)


class ReadAccessPolicy:
    def __init__(self, profile: DomainProfile, source_id: str) -> None:
        self._profile = profile
        self._source_id = source_id

    def authorize(self, intent: AnalysisIntent, context: AccessContext | None) -> None:
        if context is not None:
            try:
                context = AccessContext.model_validate(dict(context))
            except (AttributeError, TypeError, ValidationError) as exc:
                raise EvidenceAccessDenied("contexto interno inválido") from exc
        if (
            context is None
            or context.profile_id != self._profile.profile_id
            or context.source_id != self._source_id
            or CatalogOperation.READ not in context.allowed_operations
            or CatalogOperation.READ not in self._profile.operations
        ):
            raise EvidenceAccessDenied("escopo de leitura indisponível")

        metric = next((item for item in self._profile.metrics if item.id == intent.metric_id), None)
        if (
            metric is None
            or metric.domain_id != intent.domain
            or metric.id not in context.allowed_metric_ids
            or metric.sensitivity is CatalogSensitivity.PERSONAL
        ):
            raise EvidenceAccessDenied("métrica fora do escopo")

        dimensions = {item.id: item for item in self._profile.dimensions}
        requested = set(intent.dimension_ids) | set(intent.filters)
        if intent.geography_phrase:
            requested.update(
                item.id
                for item in self._profile.dimensions
                if item.role is DimensionRole.GEOGRAPHY
            )
        if intent.class_phrase:
            requested.update(
                item.id
                for item in self._profile.dimensions
                if item.role is DimensionRole.CLASSIFICATION
            )
        if not requested <= set(metric.dimension_ids) & context.allowed_dimension_ids:
            raise EvidenceAccessDenied("dimensão fora do escopo")
        if any(
            dimensions[item].sensitivity is CatalogSensitivity.PERSONAL
            for item in requested
        ):
            raise EvidenceAccessDenied("dimensão pessoal não autorizada")
