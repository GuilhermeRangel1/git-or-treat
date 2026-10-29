"""Leitura da identidade atual para os futuros consumidores Gold."""
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.models.gold_load import BATCH
from app.schemas.gold_publication import PublicationReference


class GoldPublicationUnavailable(ValueError):
    """Não há publicação validada, ou a referência esperada já não é atual."""


def current_publication(connection: Connection, expected: str | None = None) -> PublicationReference:
    """Consulta metadados mínimos; o executor futuro deve manter snapshot consistente."""
    if connection.dialect.name == "postgresql":
        row = connection.execute(text("SELECT schema_version, lote, publication_id FROM gold.publicacao_atual")).mappings().first()
    else:
        row = connection.execute(select(BATCH.c.schema_version, BATCH.c.lote, BATCH.c.publication_id)
                                 .where(BATCH.c.origem.is_not(None), BATCH.c.publication_id.is_not(None))).mappings().first()
    if row is None:
        raise GoldPublicationUnavailable("Nenhuma publicação Gold validada disponível.")
    try:
        reference = PublicationReference(schema_version=row["schema_version"], run_id=row["lote"], publication_id=row["publication_id"])
        if expected is not None and PublicationReference.parse(expected) != reference:
            raise ValueError("Publicação alterada")
    except ValueError:
        raise GoldPublicationUnavailable("Referência Gold inválida ou publicação alterada.") from None
    return reference
