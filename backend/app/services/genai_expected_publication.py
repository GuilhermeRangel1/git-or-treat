"""Confere a publicação exibida pelo portal antes de planejar uma pergunta Gold.

Lê o registro operacional da carga, o mesmo que identifica `lote`/`fingerprint` nas
leituras analíticas, e devolve a referência exata que o planejamento deve capturar.
"""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine

from app.models.gold_load import BATCH
from app.repositories.gold_publication import GoldPublicationInvalid
from app.schemas.ai_question_publication import AIExpectedPublication
from app.schemas.gold_publication import PublicationReference

GOLD_V2_SCHEMA_VERSION = "gold-csv-v2"


class ExpectedPublicationMismatch(Exception):
    """A tela exibe outra publicação; repetir sem recarregar não muda o resultado."""


def resolve_expected_batch_ref(engine: Engine, expected: AIExpectedPublication) -> str:
    """Devolve o `batch_ref` atual se coincidir com a publicação exibida."""
    with engine.connect() as connection:
        statement = select(
            BATCH.c.schema_version,
            BATCH.c.lote,
            BATCH.c.fingerprint,
            BATCH.c.publication_id,
        ).where(
            BATCH.c.id == 1,
            BATCH.c.origem.is_not(None),
            BATCH.c.publication_id.is_not(None),
        )
        if connection.dialect.name == "postgresql":
            statement = text(
                "SELECT schema_version, lote, fingerprint, publication_id FROM gold.publicacao_contexto"
            )
        row = connection.execute(statement).mappings().one_or_none()
    if row is None or row["schema_version"] != GOLD_V2_SCHEMA_VERSION:
        raise GoldPublicationInvalid("Nenhuma publicação Gold v2 validada disponível.")
    if (row["lote"], row["fingerprint"]) != (expected.lote, expected.fingerprint):
        raise ExpectedPublicationMismatch
    try:
        reference = PublicationReference(
            schema_version=row["schema_version"],
            run_id=row["lote"],
            publication_id=row["publication_id"],
        )
    except ValueError:
        raise GoldPublicationInvalid(
            "Referência da publicação Gold inválida."
        ) from None
    return reference.batch_ref
