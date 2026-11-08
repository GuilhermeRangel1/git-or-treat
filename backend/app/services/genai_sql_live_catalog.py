"""Checagem somente de metadados da fonte Gold usada pela SQL F1."""

from sqlalchemy import Float, Numeric, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.models.gold_v2 import TABLES
from app.services.gold_catalog import GoldCatalogIncompatible, load_gold_catalog


def assert_live_f1_catalog(
    connection: Connection,
    dimension_ids: frozenset[str],
    metric_ids: frozenset[str] = frozenset({"billing.revenue"}),
    source_capability_ids: dict[str, str] | None = None,
) -> None:
    """Falha fechada se a tabela F1 publicada divergir do catálogo autorizado.

    A checagem lê apenas metadados PostgreSQL. Não consulta linhas Gold. Ela é
    executada na admissão e novamente dentro do snapshot de execução.
    """
    catalog = load_gold_catalog()
    catalog_metrics = {item.metric_id: item for item in catalog.metrics}
    if not metric_ids or not metric_ids <= {
        "billing.revenue",
        "energy.consumption",
        "service.attendance",
        "service.satisfaction",
        "service.accumulated_attendance",
        "service.accumulated_satisfaction",
        "energy.gd_units",
        "energy.gd_consumption_drop",
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }:
        raise GoldCatalogIncompatible("Métrica F1 fora do catálogo SQL autorizado.")
    inspector = inspect(connection)
    checked_tables = set()
    required_by_table = {}
    for metric_id in sorted(metric_ids):
        metric = catalog_metrics.get(metric_id)
        source_capability_id = (source_capability_ids or {}).get(
            metric_id, metric.capability_id if metric else None
        )
        source = (
            next(
                (
                    item
                    for item in metric.sources
                    if item.capability_id == source_capability_id
                ),
                None,
            )
            if metric
            else None
        )
        if metric is None or source is None:
            raise GoldCatalogIncompatible("Fonte F1 ausente do catálogo aprovado.")
        required = {source.temporal_column, source.measure_column}
        required.update(
            column
            for dimension_id, column in source.dimension_columns.items()
            if dimension_id in dimension_ids
        )
        if metric_id == "energy.gd_consumption_drop":
            required.update({
                "queda_consumo_superior_30_pct",
                "meses_com_leitura_p1",
                "meses_com_leitura_p2",
            })
        required_by_table.setdefault(source.table, set()).update(
            column for column in required if column is not None
        )
        if source.table in checked_tables:
            continue
        checked_tables.add(source.table)
        expected = TABLES[source.table]
        try:
            columns = inspector.get_columns(
                source.table, schema=catalog.physical_schema
            )
            primary_key = inspector.get_pk_constraint(
                source.table, schema=catalog.physical_schema
            )
        except SQLAlchemyError:
            raise GoldCatalogIncompatible(
                "Metadados da publicação Gold incompatíveis."
            ) from None
        actual_by_name = {column["name"]: column["type"] for column in columns}
        if set(actual_by_name) != set(expected.c.keys()):
            raise GoldCatalogIncompatible(
                "Schema Gold divergente do catálogo autorizado."
            )
        for name, expected_column in expected.c.items():
            actual_type = actual_by_name[name]
            expected_type = expected_column.type
            if not isinstance(actual_type, type(expected_type)):
                raise GoldCatalogIncompatible(
                    "Tipo físico Gold divergente do catálogo autorizado."
                )
            if (
                isinstance(expected_type, Numeric)
                and not isinstance(expected_type, Float)
                and (actual_type.precision, actual_type.scale)
                != (expected_type.precision, expected_type.scale)
            ):
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
    if connection.dialect.name != "postgresql":
        return

    if not connection.execute(
        text("SELECT has_schema_privilege(current_user, :schema, 'USAGE')"),
        {"schema": catalog.physical_schema},
    ).scalar_one():
        raise GoldCatalogIncompatible(
            "Papel leitor sem acesso ao schema Gold autorizado."
        )
    for table, columns in sorted(required_by_table.items()):
        for column in sorted(columns):
            allowed = connection.execute(
                text("""
                    SELECT has_column_privilege(
                        current_user, :qualified_table, :column_name, 'SELECT'
                    )
                """),
                {
                    "qualified_table": f"{catalog.physical_schema}.{table}",
                    "column_name": column,
                },
            ).scalar_one()
            if not allowed:
                raise GoldCatalogIncompatible(
                    "Papel leitor sem acesso às colunas F1 autorizadas."
                )
