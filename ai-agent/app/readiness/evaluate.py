"""Avaliação pura da prontidão Gold: sem I/O, banco ou rede."""

from collections.abc import Iterable

from app.readiness.models import (
    CapabilityReadiness,
    CapabilityStatus,
    LotState,
    PublicationFacts,
    ReadinessReport,
    ReasonCode,
)
from app.readiness.requirements import CAPABILITY_REQUIREMENTS, CapabilityRequirement

_REASON_ORDER = {reason: index for index, reason in enumerate(ReasonCode)}
_REQUIRED_TABLES = frozenset(table for req in CAPABILITY_REQUIREMENTS for table in req.tables)


def evaluate_readiness(facts: PublicationFacts) -> ReadinessReport:
    lot_state, lot_reason = _lot_state(facts)
    if lot_reason is not None:
        capabilities = {req.id: _blocked(req, lot_reason) for req in CAPABILITY_REQUIREMENTS}
    else:
        capabilities = {req.id: _evaluate(req, facts) for req in CAPABILITY_REQUIREMENTS}
    return ReadinessReport(
        lot_state=lot_state, batch_ref=facts.batch_ref, capabilities=capabilities
    )


def _lot_state(facts: PublicationFacts) -> tuple[LotState, ReasonCode | None]:
    # Indisponibilidade nunca vira "vazio": o Backend não conseguiu observar o lote.
    if not facts.backend_reachable:
        return LotState.UNAVAILABLE, ReasonCode.BACKEND_UNAVAILABLE
    present = [table for table in facts.tables.values() if table.present]
    # Publicação sem origem validada (inclusive legada) não serve como Gold real.
    if facts.batch_ref is None or any(table.batch_ref is None for table in present):
        return LotState.INVALID, ReasonCode.PUBLICATION_UNIDENTIFIED
    if facts.expected_batch_ref is not None and facts.expected_batch_ref != facts.batch_ref:
        return LotState.STALE, ReasonCode.PUBLICATION_STALE
    if len({facts.batch_ref, *(table.batch_ref for table in present)}) > 1:
        return LotState.MIXED, ReasonCode.PUBLICATION_MIXED
    if not any(table.has_rows for table in present):
        return LotState.EMPTY, None
    for name in _REQUIRED_TABLES:
        table = facts.tables.get(name)
        if table is None or not table.has_rows:
            return LotState.PARTIAL, None
    return LotState.READY, None


def _blocked(req: CapabilityRequirement, lot_reason: ReasonCode) -> CapabilityReadiness:
    reasons = [lot_reason]
    if req.source_not_in_gold:
        reasons.append(ReasonCode.SOURCE_NOT_IN_GOLD)
    return _unavailable(reasons)


def _evaluate(req: CapabilityRequirement, facts: PublicationFacts) -> CapabilityReadiness:
    if req.source_not_in_gold:
        return _unavailable([ReasonCode.SOURCE_NOT_IN_GOLD])
    reasons: list[ReasonCode] = []
    for name in req.tables:
        table = facts.tables.get(name)
        if table is None or not table.present:
            reasons.append(ReasonCode.TABLE_MISSING)
        elif not table.has_rows:
            # Tabela vazia é ausência de evidência, nunca zero.
            reasons.append(ReasonCode.TABLE_EMPTY)
        elif req.temporal_column is not None:
            period_reason = _period_reason(table.periods, req.min_consecutive_months)
            if period_reason is not None:
                reasons.append(period_reason)
    if not set(req.required_controls) <= facts.approved_controls:
        reasons.append(ReasonCode.CONTROL_PENDING)
    if not req.definition_approved:
        reasons.append(ReasonCode.DEFINITION_PENDING)
    if reasons:
        return _unavailable(reasons)
    return CapabilityReadiness(status=CapabilityStatus.AVAILABLE)


def _period_reason(periods: tuple[str, ...], min_months: int | None) -> ReasonCode | None:
    if not periods:
        return ReasonCode.PERIOD_MISSING
    months = sorted(_month_index(period) for period in periods)
    has_gap = months[-1] - months[0] + 1 != len(months)
    if has_gap or (min_months is not None and len(months) < min_months):
        return ReasonCode.PERIOD_INSUFFICIENT
    return None


def _month_index(competencia: str) -> int:
    year, month = competencia.split("-")
    return int(year) * 12 + int(month) - 1


def _unavailable(reasons: Iterable[ReasonCode]) -> CapabilityReadiness:
    ordered = tuple(sorted(set(reasons), key=_REASON_ORDER.__getitem__))
    return CapabilityReadiness(status=CapabilityStatus.UNAVAILABLE, reasons=ordered)
