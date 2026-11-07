"""Execução interna ponta a ponta da primeira fatia Text-to-SQL.

Não é rota pública: a composição autenticada e persistente pertence à etapa
posterior. A função recebe escopo e dependências resolvidos pelo Backend.
"""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.engine import Engine

from app.schemas.genai_audit import SqlF1AuditArtifact
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_evidence import build_sql_evidence
from app.services.genai_sql_executor import execute_sql_admission
from app.services.genai_sql_observation import prepare_sql_candidate
from app.services.genai_sql_telemetry import sql_stage


@dataclass(frozen=True)
class SqlQuestionRun:
    candidate: SqlGenerationCandidate
    evidence: SqlEvidence | None
    audit_artifact: SqlF1AuditArtifact | None = None
    model_calls: int = 1


async def run_sql_question(
    request: QuestionPlanRequest,
    *,
    engine: Engine,
    readiness_engine: Engine,
    publication: GoldPublicationContext,
    client: GenAIQuestionClient,
    resolve_scope: Callable[[], AccessScope],
    approved_controls: frozenset[str],
    deadline: GenAIRequestDeadline,
    correlation_id: str,
) -> SqlQuestionRun:
    """Gera, admite, executa e fundamenta sob o mesmo prazo e escopo."""
    prepared = await prepare_sql_candidate(
        request,
        engine=engine,
        readiness_engine=readiness_engine,
        publication=publication,
        client=client,
        resolve_scope=resolve_scope,
        approved_controls=approved_controls,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    if prepared.admission is None:
        deadline.remaining_seconds(60)
        if resolve_scope() != request.access_scope:
            raise SqlAdmissionDenied("Escopo mudou após geração SQL sem consulta.")
        publication.assert_current(engine)
        return SqlQuestionRun(prepared.candidate, None, model_calls=prepared.model_calls)

    execution = await execute_sql_admission(
        prepared.admission,
        prepared.candidate,
        request,
        engine=engine,
        readiness_engine=readiness_engine,
        publication=publication,
        client=client,
        resolve_scope=resolve_scope,
        approved_controls=approved_controls,
        deadline=deadline,
        correlation_id=correlation_id,
    )
    with sql_stage(
        correlation_id, "evidence", context_version=prepared.admission.context_version,
    ):
        evidence = build_sql_evidence(
            execution,
            prepared.admission,
            prepared.candidate,
            request,
            resolve_scope=resolve_scope,
            deadline=deadline,
        )
    if evidence.batch_ref != publication.batch_ref:
        raise SqlAdmissionDenied("Publicação mudou antes de devolver evidência SQL.")
    context = build_sql_generation_context(request)
    template = prepared.admission.review.canonical_sql
    artifact = SqlF1AuditArtifact(
        context_version=prepared.admission.context_version,
        batch_ref=prepared.admission.batch_ref,
        mapping_version=context.mapping_version,
        dictionary_version=context.dictionary_version,
        candidate_digest=prepared.admission.candidate_digest,
        admission_digest=prepared.admission.digest,
        execution_digest=execution.execution_digest,
        result_digest=execution.result_digest,
        template_digest=sha256(template.encode("utf-8")).hexdigest(),
        canonical_sql_template=template,
    )
    return SqlQuestionRun(prepared.candidate, evidence, artifact)
