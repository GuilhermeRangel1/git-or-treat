"""Checagem somente de metadados da fonte Gold usada pela SQL F1."""

from sqlalchemy import Float, Numeric, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.models.gold_v2 import TABLES
from app.services.gold_catalog import GoldCatalogIncompatible, load_gold_catalog


def assert_live_f1_catalog(
    connection: Connection, dimension_ids: frozenset[str]
) -> None:
    """Falha fechada se a tabela F1 publicada divergir do catálogo autorizado.

    A checagem lê apenas metadados PostgreSQL. Não consulta linhas Gold. Ela é
    executada na admissão e novamente dentro do snapshot de execução.
    """
    catalog = load_gold_catalog()
    metric = next(
        (item for item in catalog.metrics if item.metric_id == "billing.revenue"), None
    )
    source = (
        next(
            (
                item
                for item in metric.sources
                if item.capability_id == "faturamento.receita"
            ),
            None,
        )
        if metric
        else None
    )
    if metric is None or source is None:
        raise GoldCatalogIncompatible("Fonte F1 ausente do catálogo aprovado.")

    expected = TABLES[source.table]
    inspector = inspect(connection)
    try:
        columns = inspector.get_columns(source.table, schema=catalog.physical_schema)
        primary_key = inspector.get_pk_constraint(
            source.table, schema=catalog.physical_schema
        )
    except SQLAlchemyError:
        raise GoldCatalogIncompatible(
            "Metadados da publicação Gold incompatíveis."
        ) from None

    actual_by_name = {column["name"]: column["type"] for column in columns}
    if set(actual_by_name) != set(expected.c.keys()):
        raise GoldCatalogIncompatible("Schema Gold divergente do catálogo autorizado.")
    for name, expected_column in expected.c.items():
        actual_type = actual_by_name[name]
        expected_type = expected_column.type
        if not isinstance(actual_type, type(expected_type)):
            raise GoldCatalogIncompatible(
                "Tipo físico Gold divergente do catálogo autorizado."
            )
        # Float herda Numeric no SQLAlchemy, mas PostgreSQL reflete FLOAT como
        # DOUBLE PRECISION(53). Essa precisão binária não é escala decimal.
        if isinstance(expected_type, Numeric) and not isinstance(expected_type, Float) and (
            actual_type.precision,
            actual_type.scale,
        ) != (expected_type.precision, expected_type.scale):
            raise GoldCatalogIncompatible(
                "Precisão física Gold divergente do catálogo autorizado."
            )
        if hasattr(expected_type, "timezone") and (
            getattr(actual_type, "timezone", None) != expected_type.timezone
        ):
            raise GoldCatalogIncompatible(
                "Fuso físico Gold divergente do catálogo autorizado."
            )

    if tuple(primary_key.get("constrained_columns") or ()) != tuple(source.grain):
        raise GoldCatalogIncompatible(
            "Grão físico Gold divergente do catálogo autorizado."
        )

    required_select = {source.temporal_column, source.measure_column}
    required_select.update(
        column
        for dimension_id, column in source.dimension_columns.items()
        if dimension_id in dimension_ids
    )
    required_select.discard(None)
    if connection.dialect.name != "postgresql":
        return

    if not connection.execute(
        text("SELECT has_schema_privilege(current_user, :schema, 'USAGE')"),
        {"schema": catalog.physical_schema},
    ).scalar_one():
        raise GoldCatalogIncompatible(
            "Papel leitor sem acesso ao schema Gold autorizado."
        )
    for column in sorted(required_select):
        allowed = connection.execute(
            text("""
                SELECT has_column_privilege(
                    current_user, :qualified_table, :column_name, 'SELECT'
                )
            """),
            {
                "qualified_table": f"{catalog.physical_schema}.{source.table}",
                "column_name": column,
            },
        ).scalar_one()
        if not allowed:
            raise GoldCatalogIncompatible(
                "Papel leitor sem acesso às colunas F1 autorizadas."
            )
