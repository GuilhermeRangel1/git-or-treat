"""Confere proveniência e reduz dados da fonte antes de qualquer modelo ou resposta."""

import json
import re
from datetime import date
from hashlib import sha256
from math import isfinite

from pydantic import TypeAdapter, ValidationError

from app.ports.evidence import EvidenceContractInvalid
from app.schemas.domain_profile import (
    CatalogSensitivity,
    DomainProfile,
    EvidenceFieldRole,
    FilterOperator,
    FilterValueType,
)
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceReference,
    EvidenceResult,
    GoldBatchRef,
)
from app.schemas.read_plan import LogicalReadPlan

_PERIOD = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
_BATCH_REF = TypeAdapter(GoldBatchRef)


def _safe_period(value: object) -> str:
    if not isinstance(value, str) or not _PERIOD.fullmatch(value):
        raise EvidenceContractInvalid("período de observação inválido")
    try:
        full_date = (
            f"{value}-01-01" if len(value) == 4
            else f"{value}-01" if len(value) == 7
            else value
        )
        date.fromisoformat(full_date)
    except ValueError as exc:
        raise EvidenceContractInvalid("período de observação inválido") from exc
    return value


def safe_reference_source(source_id: str, raw_reference: str) -> str:
    """Preserva a origem lógica e mantém a referência pública dentro do contrato."""

    prefix = source_id
    if len(prefix) > 55:
        prefix = f"source:{sha256(source_id.encode('utf-8')).hexdigest()[:16]}"
    reference_digest = sha256(raw_reference.encode("utf-8")).hexdigest()
    return f"{prefix}:{reference_digest}"


class EvidenceGuard:
    """A fonte é confiável apenas depois de conferir o recorte e classificar campos."""

    def __init__(self, profile: DomainProfile, *, max_bytes: int = 16_384) -> None:
        if max_bytes < 1:
            raise ValueError("limite de evidência inválido")
        self._profile = profile
        self._max_bytes = max_bytes

    def validate(
        self,
        plan: LogicalReadPlan,
        result: EvidenceLookupResult,
        *,
        expected_batch_ref: str | None = None,
    ) -> EvidenceLookupResult:
        # A publicação esperada vem do Backend, não da fonte ou do modelo.
        if expected_batch_ref is not None:
            try:
                expected_batch_ref = _BATCH_REF.validate_python(expected_batch_ref)
            except ValidationError:
                raise EvidenceContractInvalid("referência de publicação inválida") from None
        if plan.source_id.startswith("gold.") and expected_batch_ref is None:
            raise EvidenceContractInvalid("publicação esperada ausente")
        if result.status is not EvidenceLookupStatus.AVAILABLE:
            # Mensagens e limitações da fonte são texto livre; não são refletidas ao público.
            message = (
                "Não consegui aplicar o recorte solicitado; esclareça o filtro ou período."
                if result.status is EvidenceLookupStatus.NEEDS_CLARIFICATION
                else "Não há evidência para o recorte solicitado."
            )
            return EvidenceLookupResult(status=result.status, message=message)

        evidence = result.evidence
        if evidence is None or evidence.provenance is None:
            raise EvidenceContractInvalid("proveniência ausente")
        if evidence.reference.is_demo and not plan.source_id.startswith("synthetic."):
            raise EvidenceContractInvalid("fonte externa devolveu evidência demonstrativa")
        provenance = evidence.provenance
        if provenance.batch_ref != expected_batch_ref:
            raise EvidenceContractInvalid("publicação incompatível com a esperada")
        if (
            provenance.source_id != plan.source_id
            or provenance.reference_source != evidence.reference.source
            or provenance.plan_fingerprint != plan.fingerprint()
            or provenance.catalog_version != plan.catalog_version
            or provenance.metric_id != plan.metric_id
            or provenance.unit != plan.unit
            or provenance.window != plan.window
            or provenance.filters != plan.filters
            or provenance.dimension_ids != plan.dimension_ids
            or not (
                evidence.reference.source == plan.source_id
                or evidence.reference.source.startswith(
                    f"{plan.source_id.replace('.', '_')}:"
                )
            )
            or (plan.source_id.startswith("synthetic.") and not evidence.reference.is_demo)
        ):
            raise EvidenceContractInvalid("proveniência incompatível com plano")
        if len(evidence.records) > plan.limit:
            raise EvidenceContractInvalid("resultado excede limite do plano")

        metric = next(
            (item for item in self._profile.metrics if item.id == plan.metric_id), None
        )
        if metric is None or not metric.evidence_fields:
            raise EvidenceContractInvalid("métrica sem classificação de evidência")
        if any(item not in metric.limitation_texts for item in result.limitations):
            raise EvidenceContractInvalid("limitação não aprovada no catálogo")
        if evidence.reference.is_demo and not result.limitations:
            raise EvidenceContractInvalid("demonstração sem limitação declarada")

        try:
            raw_size = len(
                json.dumps(
                    result.model_dump(mode="json"), ensure_ascii=False, allow_nan=False
                ).encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            raise EvidenceContractInvalid("payload não serializável") from exc
        if raw_size > self._max_bytes:
            raise EvidenceContractInvalid("payload de evidência excede limite")

        fields = {
            field.name: field
            for field in metric.evidence_fields
            if field.sensitivity is not CatalogSensitivity.PERSONAL
        }
        measure = next(
            (field for field in fields.values() if field.role is EvidenceFieldRole.MEASURE),
            None,
        )
        if measure is None:
            raise EvidenceContractInvalid("medida não classificada")
        dimensions = {item.id: item for item in self._profile.dimensions}
        safe_records: list[dict[str, object]] = []
        for index, row in enumerate(evidence.records, start=1):
            if not isinstance(row, dict):
                raise EvidenceContractInvalid("registro inválido")
            value = row.get(measure.name)
            if (
                type(value) not in (int, float)
                or (type(value) is float and not isfinite(value))
                or measure.value_type is not FilterValueType.NUMBER
            ):
                raise EvidenceContractInvalid("medida ausente ou inválida")
            for field in fields.values():
                if field.role is EvidenceFieldRole.UNIT and row.get(field.name) != plan.unit:
                    raise EvidenceContractInvalid("unidade incompatível")
            safe_row: dict[str, object] = {
                "observation_id": f"row_{index}", "value": value, "unit": plan.unit
            }
            row_dimensions: dict[str, object] = {}
            for field in fields.values():
                if field.role is EvidenceFieldRole.PERIOD:
                    safe_row["period"] = _safe_period(row.get(field.name))
                elif field.role is EvidenceFieldRole.DIMENSION:
                    dimension_id = field.dimension_id
                    if field.name not in row:
                        if dimension_id in plan.group_by_dimension_ids:
                            raise EvidenceContractInvalid("dimensão agrupada ausente")
                        continue
                    if dimension_id is None or dimension_id not in plan.dimension_ids:
                        raise EvidenceContractInvalid("dimensão de observação fora do plano")
                    dimension = dimensions.get(dimension_id)
                    if dimension is None or dimension.value_type is not field.value_type:
                        raise EvidenceContractInvalid("dimensão de observação incompatível")
                    raw_dimension = row.get(field.name)
                    applied_filter = next(
                        (item for item in plan.filters if item.dimension_id == dimension_id),
                        None,
                    )
                    if field.value_type is FilterValueType.STRING:
                        approved = {item.value for item in dimension.values}
                        if (
                            self._profile.structured_dimension_filters
                            and applied_filter is not None
                            and applied_filter.operator in (FilterOperator.EQ, FilterOperator.IN)
                        ):
                            # O Backend autenticado devolve a grafia da publicação.
                            # Só aceita valores exatos do filtro já reautorizado,
                            # sem confiar em novos valores trazidos pelo registro.
                            approved.update(applied_filter.values)
                        if type(raw_dimension) is not str or raw_dimension not in approved:
                            raise EvidenceContractInvalid("valor de dimensão não aprovado")
                    elif field.value_type is FilterValueType.INTEGER:
                        if type(raw_dimension) is not int:
                            raise EvidenceContractInvalid("valor de dimensão inválido")
                    elif field.value_type is FilterValueType.NUMBER:
                        if type(raw_dimension) not in (int, float) or not isfinite(raw_dimension):
                            raise EvidenceContractInvalid("valor de dimensão inválido")
                    elif field.value_type is FilterValueType.BOOLEAN:
                        if type(raw_dimension) is not bool:
                            raise EvidenceContractInvalid("valor de dimensão inválido")
                    elif field.value_type is FilterValueType.DATE:
                        raw_dimension = _safe_period(raw_dimension)
                    if applied_filter is not None:
                        if applied_filter.operator in (FilterOperator.EQ, FilterOperator.IN):
                            if raw_dimension not in applied_filter.values:
                                raise EvidenceContractInvalid("dimensão fora do filtro aprovado")
                        elif (
                            applied_filter.operator is FilterOperator.NE
                            and raw_dimension in applied_filter.values
                        ):
                            raise EvidenceContractInvalid("dimensão fora do filtro aprovado")
                    row_dimensions[dimension_id] = raw_dimension
            if row_dimensions:
                safe_row["dimensions"] = row_dimensions
            safe_records.append(safe_row)

        safe_source = safe_reference_source(plan.source_id, evidence.reference.source)
        safe_reference = EvidenceReference(
            source=safe_source,
            description="Evidência agregada validada pelo serviço.",
            is_demo=evidence.reference.is_demo,
        )
        safe_provenance = provenance.model_copy(
            update={"reference_source": safe_source}
        )
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=safe_reference,
                records=safe_records,
                provenance=safe_provenance,
            ),
            limitations=result.limitations,
        )
