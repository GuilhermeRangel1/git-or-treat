"""Perfil Gold v2 da composição implantável, com a identidade do catálogo físico.

Fica separado de ``grid360_gold`` porque o mapeamento físico importa o perfil lógico.
"""

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING
from app.schemas.physical_catalog import PhysicalCatalogRef, physical_catalog_digest

GOLD_PHYSICAL_CATALOG = PhysicalCatalogRef(
    mapping_version=GRID360_GOLD_MAPPING.mapping_version,
    physical_schema=GRID360_GOLD_MAPPING.physical_schema,
    dictionary_version=GRID360_GOLD_MAPPING.dictionary_version,
    digest=physical_catalog_digest(GRID360_GOLD_MAPPING.model_dump(mode="json")),
)

GRID360_GOLD_RUNTIME_PROFILE = GRID360_GOLD_PROFILE.model_copy(
    update={"physical_catalog": GOLD_PHYSICAL_CATALOG}
)
