"""Composição implantável Gold v2: Backend executa; GenAI planeja e sintetiza."""

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.main import create_app
from app.ports.evidence import EvidenceAccessDenied
from app.profiles.grid360_gold_catalog import GRID360_GOLD_RUNTIME_PROFILE
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceLookupResult
from app.schemas.read_plan import LogicalReadPlan


class BackendOwnedEvidenceSource:
    """Impede consulta direta: evidência entra somente pela síntese interna tipada."""

    async def retrieve(
        self, plan: LogicalReadPlan, access_context: AccessContext
    ) -> EvidenceLookupResult:
        raise EvidenceAccessDenied("A execução pertence ao Backend.")


def create_gold_app(settings: Settings | None = None) -> FastAPI:
    """Entrypoint uvicorn app.gold_runtime:create_gold_app --factory."""
    active = settings or get_settings()
    if active.audit_url is None or active.audit_write_token is None:
        raise ValueError("Gold exige destino de auditoria durável configurado.")
    return create_app(
        settings=active,
        domain_profile=GRID360_GOLD_RUNTIME_PROFILE,
        evidence_source=BackendOwnedEvidenceSource(),
        source_id="gold.local",
        source_mode="external",
        # O token técnico não concede identidade à rota pública GenAI.
        access_context_resolver=lambda request: None,
    )
