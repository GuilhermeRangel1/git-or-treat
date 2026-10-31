"""Ponto de composição do serviço GenAI e entrypoint do servidor."""

from fastapi import FastAPI

from app.agent.access import ReadAccessPolicy
from app.agent.composition import compose_core
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.insights import ScreenInsightOrchestrator
from app.agent.orchestrator import QuestionOrchestrator
from app.api.access import SYNTHETIC_SOURCE_ID, AccessContextResolver
from app.api.application import SourceMode, create_api_application
from app.config import Settings, get_settings
from app.ports.events import EventSink
from app.ports.evidence import EvidenceSource
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.profiles.grid360_sql_demo import GRID360_SQL_DEMO_PROFILE
from app.providers.factory import build_model_adapter, build_model_router
from app.providers.protocols import ModelAdapter
from app.providers.routing import ModelRouter, ModelTier
from app.readiness import evaluate_readiness
from app.scenarios import SYNTHETIC_SCENARIOS
from app.schemas.domain_profile import DomainProfile
from app.sql.demo import SQL_DEMO_SOURCE_ID, build_sql_demo_source
from app.tools.synthetic_analytics import SyntheticScenarioTool


def create_app(
    settings: Settings | None = None,
    question_orchestrator: QuestionOrchestrator | None = None,
    insight_orchestrator: ScreenInsightOrchestrator | None = None,
    domain_profile: DomainProfile | None = None,
    evidence_source: EvidenceSource | None = None,
    model_adapter: ModelAdapter | None = None,
    model_router: ModelRouter | None = None,
    access_policy: ReadAccessPolicy | None = None,
    event_sink: EventSink | None = None,
    require_durable_audit: bool = False,
    source_id: str = SYNTHETIC_SOURCE_ID,
    source_mode: SourceMode = "demo",
    access_context_resolver: AccessContextResolver | None = None,
) -> FastAPI:
    """Compõe a demonstração ou uma fonte externa explicitamente autorizada."""

    active_settings = settings or get_settings()
    if active_settings.demo_source == "sqlite":
        if (
            source_mode != "demo"
            or domain_profile is not None
            or evidence_source is not None
            or source_id != SYNTHETIC_SOURCE_ID
            or active_settings.environment != "local"
            or not active_settings.enable_demo_access
            or active_settings.demo_sqlite_path is None
        ):
            raise ValueError("Fonte SQLite demonstrativa exige composição local explícita.")
        domain_profile = GRID360_SQL_DEMO_PROFILE
        source_id = SQL_DEMO_SOURCE_ID
        evidence_source = build_sql_demo_source(active_settings.demo_sqlite_path)
    active_domain_profile = domain_profile or GRID360_DEMO_PROFILE
    routing_requested = active_settings.model_routing_enabled or model_router is not None
    is_synthetic_schema = (
        active_domain_profile == GRID360_DEMO_PROFILE and source_id == SYNTHETIC_SOURCE_ID
    )
    if routing_requested and not is_synthetic_schema:
        raise ValueError(
            "O roteamento de modelos está restrito ao perfil Grid 360 demonstrativo "
            "e à fonte synthetic.fixture."
        )
    if source_mode not in {"demo", "external"}:
        raise ValueError("Modo da fonte desconhecido.")
    if source_mode == "external":
        if (
            domain_profile is None
            or evidence_source is None
            or access_context_resolver is None
            or domain_profile == GRID360_DEMO_PROFILE
            or source_id.startswith("synthetic.")
        ):
            raise ValueError(
                "Fonte externa exige perfil próprio, fonte e resolvedor de acesso explícitos."
            )
        if active_settings.enable_demo_access or active_settings.service_api_token is None:
            raise ValueError("Fonte externa exige token interno e acesso demonstrativo desligado.")
        if (
            not require_durable_audit
            or event_sink is None
            or getattr(event_sink, "durable", False) is not True
        ):
            raise ValueError("Fonte externa exige auditoria durável configurada.")
        if question_orchestrator is not None or insight_orchestrator is not None:
            raise ValueError("Fonte externa deve ser composta pelo núcleo com a fonte declarada.")
    else:
        if access_context_resolver is not None:
            raise ValueError("Resolvedor de acesso externo exige modo external.")
        if not source_id.startswith("synthetic."):
            raise ValueError("Modo demo exige fonte sintética explícita.")
    execution_controller = ExecutionController(
        ExecutionLimits(
            request_seconds=active_settings.request_timeout_ms / 1000,
            source_seconds=active_settings.source_timeout_ms / 1000,
            model_seconds=active_settings.model_timeout_ms / 1000,
            max_source_calls=active_settings.source_max_calls,
            max_model_calls=active_settings.model_max_calls,
            concurrent_requests=active_settings.concurrent_requests,
            concurrent_sources=active_settings.concurrent_sources,
            concurrent_models=active_settings.concurrent_models,
        )
    )

    core = None
    if question_orchestrator is None or insight_orchestrator is None:
        active_model_adapter = model_adapter
        if active_model_adapter is None:
            active_model_adapter = (
                model_router.adapter_for(ModelTier.STRONG)
                if model_router is not None
                else build_model_adapter(active_settings)
            )
        active_model_router = model_router or build_model_router(
            active_settings,
            active_model_adapter,
        )
        core = compose_core(
            profile=active_domain_profile,
            source_id=source_id,
            evidence_source=(
                evidence_source
                if evidence_source is not None
                else SyntheticScenarioTool(SYNTHETIC_SCENARIOS)
            ),
            model_adapter=active_model_adapter,
            model_router=active_model_router,
            execution_controller=execution_controller,
            access_policy=access_policy,
            event_sink=event_sink,
            require_durable_audit=require_durable_audit,
            max_rows=active_settings.evidence_max_rows,
            max_evidence_bytes=active_settings.evidence_max_bytes,
        )
    return create_api_application(
        settings=active_settings,
        question_handler=question_orchestrator or core.question,
        insight_handler=insight_orchestrator or core.insight,
        domain_profile=active_domain_profile,
        source_id=source_id,
        source_mode=source_mode,
        access_context_resolver=access_context_resolver,
        readiness_handler=evaluate_readiness,
    )


app = create_app()
