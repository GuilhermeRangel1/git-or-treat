"""Controles B1/B7 para a futura coordenação Gold; sem executar plano ou chamar IA."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from app.models.gold_v2 import TABLES as GOLD_V2_TABLES
from app.repositories.gold_publication import current_publication
from app.schemas.genai_internal import (
    AccessScope,
    DimensionValueCoverage,
    TemporalCoverage,
)
from app.schemas.gold_publication import PublicationReference
from app.services.gold_catalog import load_gold_catalog


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

    def planning_fields(
        self, engine: Engine, access_scope: AccessScope | None = None
    ) -> dict[str, object]:
        """Produz lote e metadados v2 sem ampliar o escopo recebido.

        Sem escopo mantém a leitura legada da referência usada pelos controles B1.
        Com escopo, os metadados são lidos sob a mesma publicação e limitados aos
        IDs lógicos permitidos. Isso prepara o envelope; não autoriza consultas.
        """
        if access_scope is None:
            self.assert_current(engine)
            return {"batch_ref": self.batch_ref}

        if access_scope.source_id != "gold.local":
            raise ValueError("metadados de planejamento exigem a fonte Gold local")
        if "read" not in access_scope.allowed_operations:
            raise ValueError("metadados de planejamento exigem operação de leitura")
        catalog = load_gold_catalog()
        if access_scope.profile_id != catalog.profile_id:
            raise ValueError("perfil fora do catálogo Gold v2 aprovado")

        if engine.dialect.name == "postgresql":
            with self.execution_snapshot(engine) as connection:
                fields = _planning_metadata(connection, access_scope, catalog)
        else:
            self.assert_current(engine)
            with engine.connect() as connection:
                fields = _planning_metadata(connection, access_scope, catalog)
            self.assert_current(engine)
        return {"batch_ref": self.batch_ref, **fields}

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
            engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            current_publication(connection, self.batch_ref)
            yield connection
        self.assert_current(engine)

    def synthesis_fields(self, engine: Engine) -> dict[str, str]:
        self.assert_current(engine)
        return {"expected_batch_ref": self.batch_ref}


def _planning_metadata(
    connection, access_scope: AccessScope, catalog
) -> dict[str, object]:
    """Resolve cobertura observada e vocabulário público do schema físico v2."""
    metric_ids = access_scope.allowed_metric_ids
    metrics_by_id = {metric.metric_id: metric for metric in catalog.metrics}
    if not metric_ids <= metrics_by_id.keys():
        raise ValueError("métrica autorizada ausente do catálogo Gold v2")

    temporal_coverage = []
    for metric_id in sorted(metric_ids):
        metric = metrics_by_id[metric_id]
        temporal_sources = [
            source for source in metric.sources if source.temporal_column
        ]
        if not temporal_sources:
            temporal_coverage.append(
                TemporalCoverage(metric_id=metric_id, kind="none").model_dump(
                    mode="json"
                )
            )
            continue

        competencies = set()
        for source in temporal_sources:
            table = GOLD_V2_TABLES[source.table]
            column = table.c[source.temporal_column]
            if source.temporal_transform == "utc_month":
                if connection.dialect.name == "postgresql":
                    period = func.to_char(func.timezone("UTC", column), "YYYY-MM")
                else:
                    period = func.strftime("%Y-%m", column)
            else:
                period = column
            values = connection.execute(
                select(period).where(column.is_not(None)).distinct().limit(1201)
            ).scalars()
            competencies.update(values)
            if len(competencies) > 1200:
                raise ValueError("cobertura mensal excede o limite do contrato GenAI")
        normalized = tuple(
            sorted(str(value) for value in competencies if value is not None)
        )
        temporal_coverage.append(
            TemporalCoverage(
                metric_id=metric_id,
                kind="monthly",
                competencies=normalized,
            ).model_dump(mode="json")
        )

    dimension_sources: dict[str, set[tuple[str, str]]] = {}
    for metric_id in sorted(metric_ids):
        for source in metrics_by_id[metric_id].sources:
            for dimension_id, column_name in source.dimension_columns.items():
                if (
                    dimension_id in access_scope.allowed_dimension_ids
                    and dimension_id != "customer.consumer_unit"
                ):
                    dimension_sources.setdefault(dimension_id, set()).add(
                        (source.table, column_name)
                    )

    dimension_coverage = []
    for dimension_id in sorted(dimension_sources):
        values = set()
        for table_name, column_name in sorted(dimension_sources[dimension_id]):
            column = GOLD_V2_TABLES[table_name].c[column_name]
            values.update(
                value
                for value in connection.execute(
                    select(column).where(column.is_not(None)).distinct().limit(2001)
                ).scalars()
                if isinstance(value, str) and value.strip()
            )
            if len(values) > 2000:
                raise ValueError("vocabulário excede o limite do contrato GenAI")
        if values:
            dimension_coverage.append(
                DimensionValueCoverage(
                    dimension_id=dimension_id,
                    values=tuple(
                        sorted(values, key=lambda value: (value.casefold(), value))
                    ),
                ).model_dump(mode="json")
            )

    return {
        "temporal_coverage": temporal_coverage,
        "dimension_value_coverage": dimension_coverage,
    }
