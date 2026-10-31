"""Controles B1/B7 para a futura coordenação Gold; sem executar plano ou chamar IA."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.engine import Connection, Engine

from app.repositories.gold_publication import current_publication
from app.schemas.gold_publication import PublicationReference


@dataclass(frozen=True)
class GoldPublicationContext:
    """Referência capturada no servidor, independente de plano, lookup ou portal."""

    reference: PublicationReference

    @classmethod
    def capture(cls, engine: Engine) -> "GoldPublicationContext":
        with engine.connect() as connection:
            return cls(current_publication(connection))

    @property
    def batch_ref(self) -> str:
        return self.reference.batch_ref

    def assert_current(self, engine: Engine) -> None:
        """Abre leitura nova para não esconder troca atrás de um snapshot antigo."""
        with engine.connect() as connection:
            current_publication(connection, self.batch_ref)

    def planning_fields(self, engine: Engine) -> dict[str, str]:
        self.assert_current(engine)
        return {"batch_ref": self.batch_ref}

    @contextmanager
    def execution_snapshot(self, engine: Engine) -> Iterator[Connection]:
        """Leitura PostgreSQL consistente; descarta o resultado se a publicação mudou.

        O futuro executor deve materializar os resultados dentro deste bloco e
        só usá-los se a saída do contexto concluir sem erro. Não manter a conexão
        durante chamadas de rede. Não substitui papel restrito, escopo ou limites.
        """
        if engine.dialect.name != "postgresql":
            raise ValueError("O snapshot de execução Gold exige PostgreSQL.")
        with (
            engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection,
            connection.begin(),
        ):
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            current_publication(connection, self.batch_ref)
            yield connection
        self.assert_current(engine)

    def synthesis_fields(self, engine: Engine) -> dict[str, str]:
        self.assert_current(engine)
        return {"expected_batch_ref": self.batch_ref}
