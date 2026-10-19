"""Monta os casos de uso a partir de contratos, sem importar HTTP ou adaptadores concretos."""

from dataclasses import dataclass

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController
from app.agent.insights import ScreenInsightOrchestrator
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.ports.events import EventSink, NoopEventSink
from app.ports.evidence import EvidenceSource
from app.providers.protocols import ModelAdapter
from app.schemas.domain_profile import DomainProfile


@dataclass(frozen=True)
class CoreServices:
    question: QuestionOrchestrator
    insight: ScreenInsightOrchestrator


def compose_core(
    *,
    profile: DomainProfile,
    source_id: str,
    evidence_source: EvidenceSource,
    model_adapter: ModelAdapter,
    execution_controller: ExecutionController,
    access_policy: ReadAccessPolicy | None = None,
    event_sink: EventSink | None = None,
    require_durable_audit: bool = False,
    max_rows: int = 100,
    max_evidence_bytes: int = 16_384,
) -> CoreServices:
    """Usa um perfil, uma política, uma fonte e um modelo em ambos os fluxos."""

    policy = access_policy if access_policy is not None else ReadAccessPolicy(profile, source_id)
    if policy.profile != profile or policy.source_id != source_id:
        raise ValueError("A política deve corresponder ao perfil e à fonte injetados.")
    sink = event_sink if event_sink is not None else NoopEventSink()
    return CoreServices(
        question=QuestionOrchestrator(
            analysis_planner=QuestionAnalysisPlanner(
                interpreter=QuestionInterpreter(profile=profile),
                evidence_source=evidence_source,
                access_policy=policy,
                max_rows=max_rows,
                max_evidence_bytes=max_evidence_bytes,
            ),
            model_adapter=model_adapter,
            execution_controller=execution_controller,
            event_sink=sink,
            require_durable_audit=require_durable_audit,
        ),
        insight=ScreenInsightOrchestrator(
            model_adapter,
            execution_controller=execution_controller,
            event_sink=sink,
            require_durable_audit=require_durable_audit,
        ),
    )
