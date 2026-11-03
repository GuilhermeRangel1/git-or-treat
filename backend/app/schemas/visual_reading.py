"""Leitura numérica montada no servidor sobre observações identificadas."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class VisualReading(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str = Field(min_length=1, max_length=900)
    observation_ids: tuple[
        Annotated[str, StringConstraints(pattern=r"^row_[1-9][0-9]{0,2}$")], ...
    ] = Field(min_length=1, max_length=24)
    next_step: str = Field(min_length=1, max_length=300)
