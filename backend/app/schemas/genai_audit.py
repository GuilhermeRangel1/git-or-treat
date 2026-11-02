"""Contrato interno de eventos; não aceita pergunta, SQL ou valores de filtros."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.genai_evidence import GoldBatchRef
from app.schemas.genai_plan import LogicalIdentifier, LogicalReadPlan

Hex32 = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{32}$")]
Hex64 = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
Count = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]


class GenAIAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: Hex32
    flow: Literal["question", "insight"] = "question"
    stage: Literal["request", "policy", "plan", "source", "evidence", "model", "response"]
    code: Literal[
        "started", "allowed", "denied", "ready", "clarification", "no_evidence",
        "available", "invalid", "unavailable", "completed", "refused", "escalated",
        "limit", "cancelled",
    ]
    outcome: Literal["started", "success", "refused", "error", "cancelled"]
    duration_ms: Count
    source_calls: Count = 0
    model_calls: Count = 0
    row_count: Count = 0
    contract_version: Literal["v1"] = "v1"
    catalog_version: Literal["v1"] | None = None
    plan_id: Hex64 | None = None
    evidence_ref: Hex64 | None = None
    prompt_version: Literal[
        "genai-grounding-v1", "genai-grounding-v2", "genai-grounding-v3", "genai-grounding-v4",
    ] = "genai-grounding-v4"


class AuditExecutionArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_version: Literal["gold-execution-v1"] = "gold-execution-v1"
    compiler_version: Literal["gold-v2-compiler-v1"] = "gold-v2-compiler-v1"
    catalog_digest: Hex64
    redacted_plan: LogicalReadPlan
    query_template: str = Field(min_length=1, max_length=16384)
    max_rows: Count
    max_bytes: Count
    statement_timeout_ms: Count
    result_digest: Hex64 | None = None


class BackendAuditEvent(GenAIAuditEvent):
    """Metadados derivados do plano admitido; nunca recebe conteúdo do navegador."""

    batch_ref: GoldBatchRef | None = None
    caller_ref: LogicalIdentifier | None = None
    metric_id: LogicalIdentifier | None = None
    source_id: LogicalIdentifier | None = None

    artifact: AuditExecutionArtifact | None = None
