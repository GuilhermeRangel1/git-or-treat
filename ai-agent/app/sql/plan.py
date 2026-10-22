"""Mapeamento artificial de plano lógico para a borda SQL de teste.

O catálogo é injetado e não contém definições Gold oficiais. A política do núcleo aprova
o plano antes desta borda; esta classe confere novamente os IDs e recortes que consegue ler.
"""

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.schemas.domain_profile import CatalogGranularity, FilterOperator
from app.schemas.read_plan import LogicalReadPlan, WindowKind
from app.sql.dictionary import SqlDictionary
from app.sql.executors import QueryResult
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected


@dataclass(frozen=True)
class SqlMetricBinding:
    domain_id: str
    unit: str
    column: str
    aggregation: Literal["sum"]
    dimension_ids: frozenset[str]


@dataclass(frozen=True)
class SqlPlanCatalog:
    profile_id: str
    source_id: str
    version: str
    dictionary_version: str
    table: str
    period_column: str
    metrics: Mapping[str, SqlMetricBinding]
    dimensions: Mapping[str, str]
    status: Literal["artificial"] = "artificial"


class SqlPlanReader:
    """Executa somente planos aprovados pelo chamador, dentro do catálogo artificial."""

    def __init__(
        self, catalog: SqlPlanCatalog, dictionary: SqlDictionary, service: ReadOnlySqlService
    ) -> None:
        if catalog.status != "artificial" or catalog.dictionary_version != dictionary.version:
            raise ValueError("catálogo SQL artificial incompatível")
        table = dictionary.tables.get(catalog.table)
        if table is None or catalog.period_column not in table.columns:
            raise ValueError("tabela ou coluna de período ausente do dicionário")
        for binding in catalog.metrics.values():
            if binding.column not in table.columns or binding.aggregation not in {"sum"}:
                raise ValueError("métrica física ausente do dicionário")
            if not binding.dimension_ids <= catalog.dimensions.keys():
                raise ValueError("dimensão lógica ausente do catálogo SQL")
        if any(column not in table.columns for column in catalog.dimensions.values()):
            raise ValueError("dimensão física ausente do dicionário")
        self._catalog = catalog
        self._service = service

    def read(self, approved_plan: LogicalReadPlan) -> QueryResult:
        try:
            plan = LogicalReadPlan.model_validate(approved_plan.model_dump(mode="python"))
        except (AttributeError, TypeError, ValueError, ValidationError) as exc:
            raise SqlRejected("invalid_plan", "plano lógico inválido") from exc

        catalog = self._catalog
        metric = catalog.metrics.get(plan.metric_id)
        if (
            plan.operation != "read"
            or plan.profile_id != catalog.profile_id
            or plan.source_id != catalog.source_id
            or plan.catalog_version != catalog.version
            or metric is None
            or plan.domain_id != metric.domain_id
            or plan.unit != metric.unit
            or not set(plan.dimension_ids) <= metric.dimension_ids
            or set(plan.dimension_ids) != {item.dimension_id for item in plan.filters}
            or plan.order is not None
        ):
            raise SqlRejected("plan_out_of_catalog", "recorte fora do catálogo artificial")

        window = plan.window
        if (
            window.kind is not WindowKind.BOUNDED
            or window.granularity is not CatalogGranularity.MONTH
            or window.start is None
            or window.end is None
            or window.start.day != 1
            or window.end.day != calendar.monthrange(window.end.year, window.end.month)[1]
        ):
            raise SqlRejected("unsupported_window", "janela mensal artificial indisponível")

        table = f'"{catalog.table}"'
        period = f'"{catalog.period_column}"'
        measure = f'"{metric.column}"'
        conditions = [f"{period} BETWEEN ? AND ?"]
        parameters: list[str | int | float | bool] = [
            window.start.strftime("%Y-%m"),
            window.end.strftime("%Y-%m"),
        ]
        for item in plan.filters:
            if item.operator is not FilterOperator.EQ or len(item.values) != 1:
                raise SqlRejected("unsupported_filter", "filtro artificial indisponível")
            column = catalog.dimensions.get(item.dimension_id)
            if column is None or item.dimension_id not in metric.dimension_ids:
                raise SqlRejected("plan_out_of_catalog", "dimensão fora do catálogo artificial")
            conditions.append(f'"{column}" = ?')
            parameters.append(item.values[0])

        sql = (
            f"SELECT {period} AS period, SUM({measure}) AS value FROM {table} "
            f"WHERE {' AND '.join(conditions)} GROUP BY {period} "
            f"ORDER BY {period} ASC LIMIT {plan.limit}"
        )
        return self._service.run(sql, tuple(parameters))
