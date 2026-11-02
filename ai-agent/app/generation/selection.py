"""Saída mínima do provedor para observações Gold já autorizadas pelo núcleo."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import EvidenceResult


class ObservationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "needs_clarification", "refused"]
    observation_ids: tuple[
        Annotated[str, StringConstraints(pattern=r"^row_[1-9][0-9]{0,2}$")], ...
    ] = Field(max_length=10)


def response_model(evidence: EvidenceResult) -> type[ObservationSelection] | type[GeneratedAnswer]:
    """Insight minimizado e demonstração conservam seus contratos existentes."""
    if (not evidence.reference.is_demo and evidence.provenance is not None
            and evidence.provenance.source_id.startswith("gold.")):
        return ObservationSelection
    return GeneratedAnswer


def parse_answer(payload: str, evidence: EvidenceResult) -> GeneratedAnswer:
    result = response_model(evidence).model_validate_json(payload)
    if isinstance(result, ObservationSelection):
        # Nenhum texto/claim do provedor é descartado para tornar uma saída
        # inválida aceitável: o schema recusa esses campos antes desta conversão.
        # Os IDs continuam sujeitos às guardas do núcleo e ao escopo da evidência.
        return GeneratedAnswer(
            status=result.status,
            answer="Resultado observado no recorte solicitado.",
            observation_ids=result.observation_ids,
        )
    return result
