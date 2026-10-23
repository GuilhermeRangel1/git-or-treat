"""Projeta linhas do ensaio SQL em evidência explicitamente demonstrativa."""

import asyncio
from datetime import date
from math import isfinite

from app.agent.read_plan import PlanCapabilityUnavailable
from app.ports.evidence import EvidenceContractInvalid, EvidenceToolUnavailable
from app.schemas.access import AccessContext
from app.schemas.domain_profile import CatalogGranularity
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.read_plan import LogicalReadPlan, WindowKind
from app.sql.executors import QueryExecutionError, QueryResult
from app.sql.plan import SqlPlanReader
from app.sql.validator import SqlRejected

_UNSUPPORTED_PLAN_CODES = frozenset(
    {"plan_out_of_catalog", "unsupported_window", "unsupported_filter"}
)


class SqlArtificialEvidenceSource:
    """Adapta o leitor SQLite artificial à porta sem reter o acesso entre requisições."""

    def __init__(
        self,
        reader: SqlPlanReader,
        *,
        demo_limitation: str,
        truncation_limitation: str,
    ) -> None:
        self._reader = reader
        self._demo_limitation = demo_limitation
        self._truncation_limitation = truncation_limitation

    async def retrieve(
        self, plan: LogicalReadPlan, access_context: AccessContext
    ) -> EvidenceLookupResult:
        try:
            result = await asyncio.to_thread(self._reader.read, plan, access_context)
        except PlanCapabilityUnavailable:
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                message="O recorte solicitado não está disponível neste ensaio.",
            )
        except SqlRejected as exc:
            if exc.code in _UNSUPPORTED_PLAN_CODES:
                return EvidenceLookupResult(
                    status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                    message="O recorte solicitado não está disponível neste ensaio.",
                )
            raise EvidenceToolUnavailable("Falha controlada na consulta artificial.") from exc
        except QueryExecutionError as exc:
            raise EvidenceToolUnavailable("Falha controlada na consulta artificial.") from exc
        return project_artificial_sql_evidence(
            plan,
            result,
            demo_limitation=self._demo_limitation,
            truncation_limitation=self._truncation_limitation,
        )


def project_artificial_sql_evidence(
    plan: LogicalReadPlan,
    result: QueryResult,
    *,
    demo_limitation: str,
    truncation_limitation: str | None = None,
) -> EvidenceLookupResult:
    """Converte apenas a saída de um leitor autorizado; não aprova nem executa planos."""

    window = plan.window
    if (
        not plan.source_id.startswith("synthetic.")
        or window.kind is not WindowKind.BOUNDED
        or window.granularity is not CatalogGranularity.MONTH
        or window.start is None
        or window.end is None
        or not demo_limitation.strip()
    ):
        raise EvidenceContractInvalid("projeção SQL demonstrativa incompatível")

    grouped = plan.group_by_dimension_ids
    if len(grouped) > 1:
        raise EvidenceContractInvalid("agrupamento SQL demonstrativo incompatível")
    expected_columns = ("period", grouped[0], "value") if grouped else ("period", "value")
    if result.columns != expected_columns or len(result.rows) > plan.limit:
        raise EvidenceContractInvalid("resultado SQL demonstrativo fora do plano")
    if result.truncated and (
        not result.rows or not truncation_limitation or not truncation_limitation.strip()
    ):
        raise EvidenceContractInvalid("truncamento SQL demonstrativo sem limitação")

    records: list[dict[str, object]] = []
    for row in result.rows:
        if len(row) != len(expected_columns):
            raise EvidenceContractInvalid("linha SQL demonstrativa inválida")
        period, *values = row
        if not isinstance(period, str) or len(period) != 7:
            raise EvidenceContractInvalid("período SQL demonstrativo inválido")
        try:
            month = date.fromisoformat(f"{period}-01")
        except ValueError as exc:
            raise EvidenceContractInvalid("período SQL demonstrativo inválido") from exc
        if month < window.start or month > window.end:
            raise EvidenceContractInvalid("período SQL demonstrativo fora do plano")
        value = values[-1]
        if type(value) not in (int, float) or (type(value) is float and not isfinite(value)):
            raise EvidenceContractInvalid("valor SQL demonstrativo inválido")
        record: dict[str, object] = {"period": period, "value": value, "unit": plan.unit}
        if grouped:
            category = values[0]
            if not isinstance(category, str) or not category.strip():
                raise EvidenceContractInvalid("categoria SQL demonstrativa inválida")
            record["category"] = category
        records.append(record)

    if not records:
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Não há evidência para o recorte solicitado.",
        )

    reference = EvidenceReference(
        source=plan.source_id,
        description="Resultado agregado do ensaio SQL artificial.",
        is_demo=True,
    )
    limitations = [demo_limitation]
    if result.truncated:
        assert truncation_limitation is not None
        limitations.append(truncation_limitation)
    return EvidenceLookupResult(
        status=EvidenceLookupStatus.AVAILABLE,
        evidence=EvidenceResult(
            reference=reference,
            records=records,
            provenance=EvidenceProvenance(
                source_id=plan.source_id,
                reference_source=reference.source,
                plan_fingerprint=plan.fingerprint(),
                catalog_version=plan.catalog_version,
                metric_id=plan.metric_id,
                unit=plan.unit,
                window=plan.window,
                filters=plan.filters,
                dimension_ids=plan.dimension_ids,
            ),
        ),
        limitations=limitations,
    )
