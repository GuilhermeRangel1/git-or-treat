"""Leitura da identidade atual para os futuros consumidores Gold."""

from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.models.gold_load import BATCH
from app.schemas.gold_publication import PublicationReference


class GoldPublicationUnavailable(ValueError):
    """Base compatível para falhas de identidade da publicação, sem dados do lote."""

    code = "publication_invalid"
    retryable = False


class GoldPublicationInvalid(GoldPublicationUnavailable):
    """Publicação ausente ou referência inválida; exige corrigir a origem."""


class GoldPublicationChanged(GoldPublicationUnavailable):
    """Duas referências válidas divergem; permite reiniciar com novo planejamento."""

    code = "publication_changed"
    retryable = True


def current_publication(
    connection: Connection, expected: str | None = None
) -> PublicationReference:
    """Valida a identidade observada sem confundir ausência com troca de lote."""
    try:
        expected_reference = PublicationReference.parse(expected) if expected is not None else None
    except ValueError:
        raise GoldPublicationInvalid("Referência esperada da publicação Gold inválida.") from None
    if connection.dialect.name == "postgresql":
        row = (
            connection.execute(
                text("SELECT schema_version, lote, publication_id FROM gold.publicacao_atual")
            )
            .mappings()
            .first()
        )
    else:
        row = (
            connection.execute(
                select(BATCH.c.schema_version, BATCH.c.lote, BATCH.c.publication_id).where(
                    BATCH.c.origem.is_not(None), BATCH.c.publication_id.is_not(None)
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise GoldPublicationInvalid("Nenhuma publicação Gold validada disponível.")
    try:
        reference = PublicationReference(
            schema_version=row["schema_version"],
            run_id=row["lote"],
            publication_id=row["publication_id"],
        )
    except ValueError:
        raise GoldPublicationInvalid("Referência da publicação Gold inválida.") from None
    if expected_reference is not None and expected_reference != reference:
        raise GoldPublicationChanged("A publicação Gold mudou; reinicie o planejamento.")
    return reference
