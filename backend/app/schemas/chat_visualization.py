"""Apresentação pública derivada somente da evidência autorizada pelo Backend."""

from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from app.schemas.genai_plan import LogicalIdentifier
from app.schemas.visual_reading import VisualReading


class ChatVisualPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(pattern=r"^row_[1-9][0-9]{0,2}$")
    label: str = Field(min_length=1, max_length=200)
    value: FiniteFloat = Field(strict=True)


class ChatVisualSector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(min_length=1, max_length=200)
    value: FiniteFloat = Field(ge=0)
    percentage: FiniteFloat = Field(ge=0, le=100)
    observation_ids: tuple[str, ...] = Field(min_length=1, max_length=100)


class ChatVisualization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["v1"] = "v1"
    kind: Literal["bars", "horizontal", "line", "donut"]
    metric: LogicalIdentifier
    title: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=200)
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    precision: int = Field(strict=True, ge=0, le=6)
    period: str = Field(min_length=1, max_length=200)
    category_label: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=300)
    points: list[ChatVisualPoint] = Field(min_length=1, max_length=100)
    plot_points: list[ChatVisualPoint] = Field(min_length=1, max_length=100)
    reading: VisualReading | None = None
    total: FiniteFloat | None = None
    sectors: list[ChatVisualSector] | None = Field(default=None, max_length=6)

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
        if self.kind == "donut":
            if (
                self.metric not in {"billing.revenue", "energy.consumption"}
                or len(self.points) < 2
                or len(self.plot_points) != len(self.points)
                or len({p.label for p in self.points}) != len(self.points)
                or any(p.value < 0 for p in self.points)
                or not 0
                < sum(Decimal(str(p.value)) for p in self.points)
                < Decimal("1e308")
            ):
                raise ValueError("partição visual incompatível")
            total = sum(Decimal(str(p.value)) for p in self.points)
            if (
                self.total is None
                or abs(Decimal(str(self.total)) - total) > total * Decimal("1e-12")
                or not self.sectors
            ):
                raise ValueError("total visual incompatível")
            ids = [key for sector in self.sectors for key in sector.observation_ids]
            if len(ids) != len(set(ids)) or set(ids) != set(points):
                raise ValueError("setores fora da partição")
            for sector in self.sectors:
                amount = sum(
                    Decimal(str(points[key].value)) for key in sector.observation_ids
                )
                if abs(Decimal(str(sector.value)) - amount) > total * Decimal(
                    "1e-12"
                ) or abs(
                    Decimal(str(sector.percentage)) - amount / total * 100
                ) > Decimal("1e-8"):
                    raise ValueError("setor visual incompatível")
        elif self.total is not None or self.sectors is not None:
            raise ValueError("participação somente em rosca")
        elif len(self.plot_points) > 24:
            raise ValueError("limite visual excedido")
        if self.reading and (
            len(set(self.reading.observation_ids)) != len(self.reading.observation_ids)
            or not set(self.reading.observation_ids)
            <= {p.observation_id for p in self.plot_points}
        ):
            raise ValueError("leitura fora das observações exibidas")
        return self
