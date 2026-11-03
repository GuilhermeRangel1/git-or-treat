"""Apresentação pública derivada somente da evidência autorizada pelo Backend."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from app.schemas.genai_plan import LogicalIdentifier
from app.schemas.visual_reading import VisualReading


class ChatVisualPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(pattern=r"^row_[1-9][0-9]{0,2}$")
    label: str = Field(min_length=1, max_length=200)
    value: FiniteFloat = Field(strict=True)


class ChatVisualization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["v1"] = "v1"
    kind: Literal["bars", "horizontal", "line"]
    metric: LogicalIdentifier
    title: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=200)
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    precision: int = Field(strict=True, ge=0, le=6)
    period: str = Field(min_length=1, max_length=200)
    category_label: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=300)
    points: list[ChatVisualPoint] = Field(min_length=1, max_length=100)
    plot_points: list[ChatVisualPoint] = Field(min_length=1, max_length=24)
    reading: VisualReading | None = None

    @model_validator(mode="after")
    def references_are_exact(self) -> Self:
        if len(set(self.dimension_ids)) != len(self.dimension_ids):
            raise ValueError("dimensão visual repetida")
        if any(p.observation_id != f"row_{i}" for i, p in enumerate(self.points, 1)):
            raise ValueError("sequência de observações inválida")
        points = {p.observation_id: p for p in self.points}
        if len(points) != len(self.points) or len(
            {p.observation_id for p in self.plot_points}
        ) != len(self.plot_points):
            raise ValueError("observação visual repetida")
        if any(points.get(p.observation_id) != p for p in self.plot_points):
            raise ValueError("ponto visual fora da evidência publicada")
        if self.reading and (len(set(self.reading.observation_ids)) != len(self.reading.observation_ids) or not set(self.reading.observation_ids) <= {p.observation_id for p in self.plot_points}):
            raise ValueError("leitura fora das observações exibidas")
        return self
