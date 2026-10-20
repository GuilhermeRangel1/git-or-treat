"""Política de leitura independente de nomes físicos da fonte."""

from pydantic import ValidationError

from app.ports.evidence import EvidenceAccessDenied
from app.schemas.access import AccessContext
from app.schemas.domain_profile import (
    CatalogOperation,
    CatalogSensitivity,
    DomainProfile,
)
from app.schemas.read_plan import LogicalReadPlan


class ReadAccessPolicy:
    def __init__(self, profile: DomainProfile, source_id: str) -> None:
        self._profile = profile
        self._source_id = source_id

    @property
    def profile(self) -> DomainProfile:
        return self._profile

    @property
    def source_id(self) -> str:
        return self._source_id

    def authorize_context(self, context: AccessContext | None) -> AccessContext:
        """Confere a origem e o escopo mínimo antes de qualquer fluxo de leitura."""

        if context is None:
            raise EvidenceAccessDenied("escopo de leitura indisponível")
        try:
            validated = AccessContext.model_validate(dict(context))
        except (AttributeError, TypeError, ValidationError) as exc:
            raise EvidenceAccessDenied("contexto interno inválido") from exc
        if (
            validated.profile_id != self._profile.profile_id
            or validated.source_id != self._source_id
            or CatalogOperation.READ not in validated.allowed_operations
            or CatalogOperation.READ not in self._profile.operations
        ):
            raise EvidenceAccessDenied("escopo de leitura indisponível")
        return validated

    def authorize_insight(self, context: AccessContext | None) -> None:
        """O insight sintético exige algum escopo analítico aprovado para o perfil."""

        validated = self.authorize_context(context)
        allowed_metrics = {
            item.id
            for item in self._profile.metrics
            if item.sensitivity is not CatalogSensitivity.PERSONAL
        }
        allowed_dimensions = {
            item.id
            for item in self._profile.dimensions
            if item.sensitivity is not CatalogSensitivity.PERSONAL
        }
        if (
            not validated.allowed_metric_ids & allowed_metrics
            or not validated.allowed_dimension_ids & allowed_dimensions
        ):
            raise EvidenceAccessDenied("escopo analítico indisponível")

    def authorize(self, plan: LogicalReadPlan, context: AccessContext | None) -> None:
        context = self.authorize_context(context)
        if (
            plan.profile_id != context.profile_id
            or plan.source_id != context.source_id
            or plan.operation != CatalogOperation.READ
        ):
            raise EvidenceAccessDenied("escopo de leitura indisponível")

        metric = next((item for item in self._profile.metrics if item.id == plan.metric_id), None)
        if (
            metric is None
            or metric.domain_id != plan.domain_id
            or metric.id not in context.allowed_metric_ids
            or metric.sensitivity is CatalogSensitivity.PERSONAL
        ):
            raise EvidenceAccessDenied("métrica fora do escopo")

        dimensions = {item.id: item for item in self._profile.dimensions}
        requested = set(plan.dimension_ids) | {item.dimension_id for item in plan.filters}
        if not requested <= set(metric.dimension_ids) & context.allowed_dimension_ids:
            raise EvidenceAccessDenied("dimensão fora do escopo")
        if any(
            dimensions[item].sensitivity is CatalogSensitivity.PERSONAL
            for item in requested
        ):
            raise EvidenceAccessDenied("dimensão pessoal não autorizada")
