"""Execução interna ponta a ponta da primeira fatia Text-to-SQL.

Não é rota pública: a composição autenticada e persistente pertence à etapa
posterior. A função recebe escopo e dependências resolvidos pelo Backend.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_evidence import build_sql_evidence
from app.services.genai_sql_executor import execute_sql_admission
from app.services.genai_sql_observation import prepare_sql_candidate


@dataclass(frozen=True)
class SqlQuestionRun:
    candidate: SqlGenerationCandidate
    evidence: SqlEvidence | None


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
        return SqlQuestionRun(prepared.candidate, None)

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
    return SqlQuestionRun(prepared.candidate, evidence)
