"""Identidade do catálogo físico Gold v2 compartilhada entre plano, evidência e cache.

O digest é calculado sobre o JSON canônico do mapeamento; o Backend calcula o mesmo
valor a partir de ``backend/app/catalogs/gold_v2.json`` sem importar a GenAI.
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def physical_catalog_digest(payload: dict) -> str:
    """SHA-256 do mapeamento serializado de forma canônica."""

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PhysicalCatalogRef(BaseModel):
    """Catálogo físico sob o qual um plano foi produzido ou uma evidência calculada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_version: Literal["gold-catalog-v2"]
    physical_schema: Literal["gold_v2"]
    dictionary_version: Literal["gold-csv-v2"]
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
