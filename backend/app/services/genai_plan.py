"""Revalidação B3 antes da futura execução do plano pela coordenação Backend."""

from typing import Any

from pydantic import TypeAdapter

from app.schemas.genai_plan import LogicalReadPlan, PlanFingerprint
from app.services.genai_client import GenAIResponseInvalid

_FINGERPRINT = TypeAdapter(PlanFingerprint)

# Identidade desta implantação; o schema v1 permanece independente do domínio.
GOLD_SOURCE_ID = "gold.local"
GOLD_PROFILE_ID = "v-energy-grid-360-gold"


def validate_genai_plan(payload: dict[str, Any], fingerprint: str) -> LogicalReadPlan:
    """Valida o plano recebido e confere seu hash, sem banco nem autorização.

    O chamador deverá revalidar também catálogo, escopo e publicação, inclusive
    em cache. A função não ativa as futuras rotas internas ou o executor SQL.
    """
    try:
        if not isinstance(payload, dict):
            raise ValueError("plano deve ser um objeto JSON")
        expected = _FINGERPRINT.validate_python(fingerprint)
        plan = LogicalReadPlan.model_validate(payload)
        if plan.fingerprint() != expected:
            raise ValueError("fingerprint incompatível com o plano validado")
    except ValueError as exc:
        raise GenAIResponseInvalid from exc
    return plan


def validate_gold_genai_plan(payload: dict[str, Any], fingerprint: str) -> LogicalReadPlan:
    """Confere B3 e o par de identificadores B4 da implantação Gold local.

    Catálogo permitido, escopo, período e publicação ainda devem ser revalidados
    pelo coordenador antes da consulta. Os identificadores não concedem acesso.
    """
    plan = validate_genai_plan(payload, fingerprint)
    if (plan.source_id, plan.profile_id) != (GOLD_SOURCE_ID, GOLD_PROFILE_ID):
        raise GenAIResponseInvalid
    return plan
