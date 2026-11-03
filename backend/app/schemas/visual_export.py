"""Pedido de revalidação; não recebe linhas, SQL ou valores de gráfico."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ai_question_publication import AIExpectedPublication
from app.schemas.genai_evidence import GoldBatchRef
from app.schemas.genai_plan import LogicalIdentifier


class VisualExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: LogicalIdentifier
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    batch_reference: GoldBatchRef | None = None
    expected_publication: AIExpectedPublication | None = None

    @model_validator(mode="after")
    def require_one_publication(self) -> Self:
        if (self.batch_reference is None) == (self.expected_publication is None):
            raise ValueError("informe uma única publicação esperada")
        if self.batch_reference is not None and not self.batch_reference.startswith(
            "gold-csv-v2:"
        ):
            raise ValueError("exportação exige Gold v2")
        if len(set(self.dimension_ids)) != len(self.dimension_ids):
            raise ValueError("dimensão repetida")
        return self


class VisualExportPermission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorized: bool = True
