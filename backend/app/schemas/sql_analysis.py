"""Envelope público da análise Text-to-SQL; nunca expõe SQL nem parâmetros."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.ai import AICorrelationId, AIQuestionRequest
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlClarification, SqlUnsupported

PresentationText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class SqlPresentationColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    role: Literal["dimension", "measure"]
    semantic_id: Literal[
        "competency",
        "municipality",
        "consumption_class",
        "revenue_total",
        "period_0_total",
        "period_1_total",
        "period_0_minus_period_1",
        "period_0_growth_percent",
    ]
    unit: str | None = Field(default=None, max_length=20)


class SqlPresentationRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(pattern=r"^row_[1-9][0-9]{0,2}$")
    cells: tuple[str | None, ...] = Field(min_length=1, max_length=32)


class SqlAnalysisPresentation(BaseModel):
    """Texto e tabela projetados da mesma evidência imutável do executor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[
        "text-to-sql-f1-presentation-v1", "text-to-sql-f1-presentation-v2",
    ]
    state: Literal["ready", "empty", "all_measures_null"]
    operation: Literal[
        "total", "monthly_series", "grouped_total", "ranking", "comparison"
    ]
    answer: PresentationText
    period: str = Field(min_length=1, max_length=100)
    filters: tuple[str, ...] = Field(max_length=20)
    universe: tuple[str, ...] = Field(max_length=3)
    limitations: tuple[str, ...] = Field(max_length=10)
    columns: tuple[SqlPresentationColumn, ...] = Field(min_length=1, max_length=32)
    rows: tuple[SqlPresentationRow, ...] = Field(max_length=100)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SqlAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: AICorrelationId
    audit_reference: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")]
    status: Literal["answered", "needs_clarification", "unsupported"]
    evidence: SqlEvidence | None = None
    presentation: SqlAnalysisPresentation | None = None
    clarification: SqlClarification | None = None
    unsupported_reason: SqlUnsupported | None = None
    continuation_token: Annotated[str, StringConstraints(min_length=1, max_length=16000)] | None = None

    @model_validator(mode="after")
    def validate_result_shape(self):
        if self.status == "answered":
            from app.services.genai_sql_presentation import present_sql_evidence

            if (
                self.evidence is None
                or self.presentation is None
                or self.clarification is not None
                or self.unsupported_reason is not None
                or self.presentation.evidence_digest != self.evidence.evidence_digest
                or self.presentation.state
                != {
                    "available": "ready",
                    "empty": "empty",
                    "all_measures_null": "all_measures_null",
                }[self.evidence.status]
                or len(self.presentation.rows) != len(self.evidence.rows)
                or tuple(column.key for column in self.presentation.columns)
                != tuple(column.name for column in self.evidence.columns)
                or tuple(
                    (column.role, column.unit) for column in self.presentation.columns
                )
                != tuple((column.role, column.unit) for column in self.evidence.columns)
                or self.presentation.operation != self.evidence.interpretation.operation
                or self.presentation != present_sql_evidence(self.evidence)
            ):
                raise ValueError("resposta exige apresentação vinculada à evidência")
            for index, row in enumerate(self.presentation.rows, start=1):
                if (
                    row.observation_id != f"row_{index}"
                    or len(row.cells) != len(self.presentation.columns)
                    or row.cells != self.evidence.rows[index - 1]
                ):
                    raise ValueError("tabela de apresentação diverge da evidência")
        elif self.evidence is not None or self.presentation is not None:
            raise ValueError(
                "estado não respondido não pode incluir resultado quantitativo"
            )
        elif self.status == "needs_clarification":
            if self.clarification is None or self.unsupported_reason is not None:
                raise ValueError("esclarecimento exige somente a pergunta pendente")
        elif self.unsupported_reason is None or self.clarification is not None:
            raise ValueError("capacidade não suportada exige motivo tipado")
        return self

    @classmethod
    def from_run(cls, correlation_id, run, *, audit_reference):
        candidate = run.candidate
        if run.evidence is not None:
            from app.services.genai_sql_presentation import present_sql_evidence

            return cls(
                correlation_id=correlation_id,
                audit_reference=audit_reference,
                status="answered",
                evidence=run.evidence,
                presentation=present_sql_evidence(run.evidence),
            )
        return cls(
            correlation_id=correlation_id,
            audit_reference=audit_reference,
            status=candidate.status,
            clarification=candidate.clarification,
            unsupported_reason=candidate.unsupported_reason,
        )


class SqlAnalysisRequest(AIQuestionRequest):
    """Pergunta F1 autenticada; contexto de follow-up exige token assinado."""

    conversation_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9-]{36}$")] | None = None
    continuation_token: Annotated[str, StringConstraints(min_length=1, max_length=16000)] | None = None
