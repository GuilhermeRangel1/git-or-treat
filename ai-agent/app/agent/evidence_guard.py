"""Confere proveniência e reduz dados da fonte antes de qualquer modelo ou resposta."""

import json
from math import isfinite

from app.ports.evidence import EvidenceContractInvalid
from app.schemas.domain_profile import (
    CatalogSensitivity,
    DomainProfile,
    EvidenceFieldRole,
    FilterValueType,
)
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.read_plan import LogicalReadPlan


class EvidenceGuard:
    """A fonte é confiável apenas depois de conferir o recorte e classificar campos."""

    def __init__(self, profile: DomainProfile, *, max_bytes: int = 16_384) -> None:
        if max_bytes < 1:
            raise ValueError("limite de evidência inválido")
        self._profile = profile
        self._max_bytes = max_bytes

    def validate(
        self, plan: LogicalReadPlan, result: EvidenceLookupResult
    ) -> EvidenceLookupResult:
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
        provenance = evidence.provenance
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
            # Texto livre da fonte, inclusive período, notas e campos desconhecidos, não vai ao LLM.
            safe_records.append(
                {"observation_id": f"row_{index}", "value": value, "unit": plan.unit}
            )

        safe_reference = EvidenceReference(
            source=evidence.reference.source,
            description="Evidência agregada validada pelo serviço.",
            is_demo=evidence.reference.is_demo,
        )
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=safe_reference,
                records=safe_records,
                provenance=provenance,
            ),
            limitations=result.limitations,
        )
