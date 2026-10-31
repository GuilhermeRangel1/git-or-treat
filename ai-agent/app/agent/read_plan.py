"""Compila e valida planos lógicos antes de qualquer chamada à fonte."""

import unicodedata
from collections.abc import Mapping
from datetime import date
from math import isfinite

from pydantic import ValidationError

from app.agent.access import ReadAccessPolicy
from app.agent.temporal import GoldTemporalWindowResolver, TemporalResolutionUnavailable
from app.ports.evidence import EvidenceAccessDenied
from app.schemas.access import AccessContext
from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import (
    CatalogGranularity,
    DimensionDefinition,
    DimensionRole,
    DomainProfile,
    FilterOperator,
    FilterValueType,
    MetricDefinition,
)
from app.schemas.read_plan import (
    LogicalReadPlan,
    ReadFilter,
    ReadWindow,
    WindowKind,
)


class PlanCapabilityUnavailable(Exception):
    """O catálogo não permite representar fielmente o recorte solicitado."""


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class ReadPlanBuilder:
    """Transforma intenção lexical em IDs e valores lógicos do catálogo."""

    def __init__(self, profile: DomainProfile, source_id: str, *, default_limit: int = 100) -> None:
        if profile is None:
            raise ValueError("catálogo ausente")
        if not 1 <= default_limit <= 100:
            raise ValueError("limite padrão fora do contrato")
        self._profile = profile
        self._source_id = source_id
        self._default_limit = default_limit

    def build(
        self,
        intent: AnalysisIntent,
        temporal_coverage: Mapping[str, tuple[str, tuple[str, ...]]] | None = None,
    ) -> LogicalReadPlan:
        metric = next(
            (item for item in self._profile.metrics if item.id == intent.metric_id),
            None,
        )
        if metric is None or metric.domain_id != intent.domain:
            raise PlanCapabilityUnavailable("O indicador solicitado não está neste catálogo.")
        if intent.period_phrase is None or _normalize(intent.period_phrase) not in {
            _normalize(item) for item in self._profile.period_phrases
        }:
            raise PlanCapabilityUnavailable(
                "Não há uma janela aprovada para esse período; reformule a consulta."
            )

        _validate_metric_period(metric, intent.period_phrase, self._profile)
        dimensions = {item.id: item for item in self._profile.dimensions}
        selected_ids = set(intent.dimension_ids)
        filters: dict[str, ReadFilter] = {}
        for role, phrase in (
            (DimensionRole.GEOGRAPHY, intent.geography_phrase),
            (DimensionRole.CLASSIFICATION, intent.class_phrase),
        ):
            if phrase is None:
                continue
            matches = [
                (dimension, value.value)
                for dimension in self._profile.dimensions
                if dimension.role is role
                for value in dimension.values
                if _normalize(phrase) in {_normalize(alias) for alias in value.aliases}
            ]
            if len(matches) != 1:
                raise PlanCapabilityUnavailable(
                    "O filtro solicitado não está definido no catálogo."
                )
            dimension, canonical_value = matches[0]
            selected_ids.add(dimension.id)
            filters[dimension.id] = ReadFilter(
                dimension_id=dimension.id,
                operator=FilterOperator.EQ,
                values=(canonical_value,),
            )

        for key, value in intent.filters.items():
            if key not in dimensions or key in filters:
                raise PlanCapabilityUnavailable(
                    "Não há uma regra aprovada para aplicar esse filtro."
                )
            selected_ids.add(key)
            filters[key] = ReadFilter(dimension_id=key, operator=FilterOperator.EQ, values=(value,))

        period_window = next(
            (
                window
                for window in self._profile.period_windows
                if _normalize(window.phrase) == _normalize(intent.period_phrase)
            ),
            None,
        )
        if temporal_coverage is not None:
            unavailable = (
                self._profile.clarifications.temporal_coverage_unavailable
                or "A cobertura mensal não permite esse período. Informe outra janela."
            )
            metric_coverage = temporal_coverage.get(metric.id)
            if metric_coverage is None:
                raise PlanCapabilityUnavailable(unavailable)
            coverage_kind, competencies = metric_coverage
            if coverage_kind == "monthly":
                try:
                    window = GoldTemporalWindowResolver().resolve(
                        intent.period_phrase, competencies
                    )
                except TemporalResolutionUnavailable as exc:
                    raise PlanCapabilityUnavailable(unavailable) from exc
            else:
                if not metric.accumulated_period_phrases or (
                    _normalize(intent.period_phrase)
                    not in {_normalize(item) for item in metric.accumulated_period_phrases}
                ):
                    raise PlanCapabilityUnavailable(unavailable)
                window = ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase=intent.period_phrase)
        else:
            window = (
                ReadWindow(
                    kind=WindowKind.BOUNDED,
                    start=period_window.start,
                    end=period_window.end,
                    granularity=period_window.granularity,
                )
                if period_window is not None
                else ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase=intent.period_phrase)
            )
        return LogicalReadPlan(
            catalog_version=self._profile.contract_version,
            operation="read",
            profile_id=self._profile.profile_id,
            source_id=self._source_id,
            domain_id=intent.domain,
            metric_id=metric.id,
            dimension_ids=tuple(sorted(selected_ids)),
            unit=metric.unit,
            window=window,
            filters=tuple(filters[key] for key in sorted(filters)),
            limit=self._default_limit,
        )


class ReadPlanValidator:
    """Aprova o plano inteiro e seu escopo; nenhuma chamada depende de texto do modelo."""

    def __init__(
        self,
        profile: DomainProfile,
        source_id: str,
        access_policy: ReadAccessPolicy,
        *,
        max_rows: int = 100,
        max_window_days: int = 366 * 5,
    ) -> None:
        if profile is None:
            raise ValueError("catálogo ausente")
        if not 1 <= max_rows <= 100 or max_window_days < 1:
            raise ValueError("limites da política inválidos")
        self._profile = profile
        self._source_id = source_id
        self._access_policy = access_policy
        self._max_rows = max_rows
        self._max_window_days = max_window_days

    def approve(
        self, proposed: LogicalReadPlan | dict[str, object], context: AccessContext | None
    ) -> LogicalReadPlan:
        try:
            raw = (
                proposed.model_dump(mode="python", warnings="error")
                if isinstance(proposed, LogicalReadPlan)
                else proposed
            )
            if not isinstance(raw, dict) or raw.get("operation") != "read":
                raise EvidenceAccessDenied("operação não autorizada")
            plan = LogicalReadPlan.model_validate(raw)
        except EvidenceAccessDenied:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise PlanCapabilityUnavailable("O plano de leitura não segue o contrato.") from exc

        if (
            plan.catalog_version != self._profile.contract_version
            or plan.profile_id != self._profile.profile_id
            or plan.source_id != self._source_id
        ):
            raise EvidenceAccessDenied("plano de outra fonte ou versão")
        if plan.limit > self._max_rows:
            raise PlanCapabilityUnavailable("A consulta excede o limite de resultados.")

        metric = next((item for item in self._profile.metrics if item.id == plan.metric_id), None)
        if (
            metric is None
            or metric.domain_id != plan.domain_id
            or metric.unit != plan.unit
            or not set(plan.dimension_ids) <= set(metric.dimension_ids)
        ):
            raise PlanCapabilityUnavailable("Métrica, unidade ou dimensão indisponível.")
        _validate_metric_period(metric, plan.window.phrase, self._profile, plan.window.granularity)
        self._validate_window(plan, metric.granularities, metric.max_window_days)

        dimensions = {item.id: item for item in self._profile.dimensions}
        for plan_filter in plan.filters:
            dimension = dimensions.get(plan_filter.dimension_id)
            if (
                dimension is None
                or plan_filter.dimension_id not in metric.dimension_ids
                or plan_filter.operator not in dimension.operators
            ):
                raise PlanCapabilityUnavailable("Filtro ou operador indisponível.")
            self._validate_filter(plan_filter, dimension)
        if plan.order is not None and plan.order.field_id not in {
            plan.metric_id,
            *plan.dimension_ids,
        }:
            raise PlanCapabilityUnavailable("Ordenação indisponível.")

        self._access_policy.authorize(plan, context)
        return plan

    def _validate_window(
        self,
        plan: LogicalReadPlan,
        allowed_grains: tuple[CatalogGranularity, ...],
        metric_max_window_days: int | None,
    ) -> None:
        window = plan.window
        max_window_days = min(
            self._max_window_days,
            metric_max_window_days
            if metric_max_window_days is not None
            else self._max_window_days,
        )
        if window.granularity is not None and window.granularity not in allowed_grains:
            raise PlanCapabilityUnavailable("Granularidade indisponível para a métrica.")
        if window.kind is WindowKind.CATALOG_PHRASE:
            if _normalize(window.phrase or "") not in {
                _normalize(item) for item in self._profile.period_phrases
            }:
                raise PlanCapabilityUnavailable("Período fora do catálogo.")
        elif (
            window.start is None
            or window.end is None
            or (window.end - window.start).days > max_window_days
        ):
            raise PlanCapabilityUnavailable("Janela solicitada excede o limite.")

    @staticmethod
    def _validate_filter(plan_filter: ReadFilter, dimension: DimensionDefinition) -> None:
        for value in plan_filter.values:
            expected = dimension.value_type
            valid = {
                FilterValueType.STRING: type(value) is str,
                FilterValueType.INTEGER: type(value) is int,
                FilterValueType.NUMBER: type(value) in (int, float) and isfinite(value),
                FilterValueType.BOOLEAN: type(value) is bool,
                FilterValueType.DATE: type(value) is str and _valid_iso_date(value),
            }[expected]
            if not valid:
                raise PlanCapabilityUnavailable("Valor incompatível com o tipo do filtro.")
            if dimension.values and _normalize(str(value)) not in {
                _normalize(item.value) for item in dimension.values
            }:
                raise PlanCapabilityUnavailable("Valor de filtro ausente do catálogo.")


def _valid_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _validate_metric_period(
    metric: MetricDefinition,
    phrase: str | None,
    profile: DomainProfile,
    granularity: CatalogGranularity | None = None,
) -> None:
    accumulated = {_normalize(p) for m in profile.metrics for p in m.accumulated_period_phrases}
    normalized = _normalize(phrase or "")
    if metric.accumulated_period_phrases:
        if granularity is not None:
            raise PlanCapabilityUnavailable(
                "Histórico acumulado não possui granularidade de calendário."
            )
        if normalized not in {_normalize(p) for p in metric.accumulated_period_phrases}:
            raise PlanCapabilityUnavailable(
                "Este indicador só possui histórico acumulado, sem recorte por datas."
            )
    elif normalized in accumulated:
        raise PlanCapabilityUnavailable("Este indicador exige um período de calendário.")
