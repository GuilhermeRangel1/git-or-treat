"""Compose the two independently admitted results of the TSQL-11 analysis."""

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.genai_evidence import PublishedWindows


class CompoundEvidenceUnavailable(ValueError):
    """The complete compound result cannot be supported by the evidence."""


@dataclass(frozen=True)
class EvidenceScope:
    batch_ref: str
    scope_digest: str
    windows: PublishedWindows


@dataclass(frozen=True)
class ConsumptionTotals:
    municipality: str
    previous_kwh: Decimal
    current_kwh: Decimal


@dataclass(frozen=True)
class RevenueEffect:
    municipality: str
    consumption_class: str
    variation_brl: Decimal
    volume_effect_brl: Decimal


@dataclass(frozen=True)
class MunicipalityDecline:
    consumption: ConsumptionTotals
    change_kwh: Decimal
    change_percent: Decimal
    revenue_by_class: tuple[RevenueEffect, ...]


@dataclass(frozen=True)
class CompoundResult:
    scope: EvidenceScope
    municipalities: tuple[MunicipalityDecline, ...]


def compose_consumption_revenue(
    consumption_scope: EvidenceScope,
    revenue_scope: EvidenceScope,
    consumption: tuple[ConsumptionTotals, ...],
    revenue: tuple[RevenueEffect, ...],
    *,
    expected_municipalities: frozenset[str],
    expected_revenue_groups: frozenset[tuple[str, str]],
) -> CompoundResult:
    """Combine validated totals and published effects, without joining raw facts.

    Expected groups come from the admitted coverage for the requested scope.
    A missing class must not disappear silently from the explanation.
    """
    if consumption_scope != revenue_scope:
        raise CompoundEvidenceUnavailable("Publicação, escopo ou janelas divergentes.")

    seen_municipalities: set[str] = set()
    declines = []
    for row in consumption:
        if (
            not row.municipality
            or row.municipality in seen_municipalities
            or any(
                not value.is_finite() or value < 0
                for value in (row.previous_kwh, row.current_kwh)
            )
        ):
            raise CompoundEvidenceUnavailable("Totais municipais inválidos ou duplicados.")
        seen_municipalities.add(row.municipality)
        if row.current_kwh < row.previous_kwh:
            declines.append(row)

    if not seen_municipalities or seen_municipalities != expected_municipalities:
        raise CompoundEvidenceUnavailable("Evidência de consumo incompleta para o recorte.")

    groups: dict[str, list[RevenueEffect]] = {}
    seen_groups: set[tuple[str, str]] = set()
    for effect in revenue:
        key = (effect.municipality, effect.consumption_class)
        if (
            not all(key)
            or key in seen_groups
            or not effect.variation_brl.is_finite()
            or not effect.volume_effect_brl.is_finite()
        ):
            raise CompoundEvidenceUnavailable("Decomposição inválida ou duplicada.")
        seen_groups.add(key)
        groups.setdefault(effect.municipality, []).append(effect)
    if seen_groups != expected_revenue_groups or any(
        row.municipality not in groups for row in declines
    ):
        raise CompoundEvidenceUnavailable("Decomposição incompleta para o recorte.")

    results = []
    for row in declines:
        change = row.current_kwh - row.previous_kwh
        results.append(
            MunicipalityDecline(
                consumption=row,
                change_kwh=change,
                change_percent=change * 100 / row.previous_kwh,
                revenue_by_class=tuple(
                    sorted(groups[row.municipality], key=lambda item: item.consumption_class)
                ),
            )
        )
    return CompoundResult(
        scope=consumption_scope,
        municipalities=tuple(
            sorted(results, key=lambda item: (item.change_kwh, item.consumption.municipality))
        ),
    )
