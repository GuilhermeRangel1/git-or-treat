"""Mapeamento artificial de plano lógico para a borda SQL de teste.

O catálogo é injetado e não contém definições Gold oficiais. A política do núcleo aprova
o plano antes desta borda; esta classe confere novamente os IDs e recortes que consegue ler.
"""

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, NoReturn

from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator
from app.ports.evidence import EvidenceAccessDenied
from app.schemas.access import AccessContext
from app.schemas.domain_profile import CatalogGranularity, FilterOperator
from app.schemas.read_plan import LogicalReadPlan, WindowKind
from app.sql.audit import SqlAuditContext
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
    filter_operators: frozenset[FilterOperator]
    allow_value_order: bool = False


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
    """Revalida plano e escopo atuais antes de consultar o catálogo artificial."""

    def __init__(
        self,
        catalog: SqlPlanCatalog,
        dictionary: SqlDictionary,
        service: ReadOnlySqlService,
        validator: ReadPlanValidator,
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
            if not binding.filter_operators <= {FilterOperator.EQ, FilterOperator.IN}:
                raise ValueError("operador não implementado no catálogo SQL artificial")
        if any(column not in table.columns for column in catalog.dimensions.values()):
            raise ValueError("dimensão física ausente do dicionário")
        self._catalog = catalog
        self._service = service
        self._validator = validator

    def _reject(self, code: str, detail: str) -> NoReturn:
        self._service.record_pre_sql_rejection(code)
        raise SqlRejected(code, detail)

    def read(
        self,
        proposed_plan: LogicalReadPlan | dict[str, object],
        access_context: AccessContext | None,
    ) -> QueryResult:
        try:
            plan = self._validator.approve(proposed_plan, access_context)
        except EvidenceAccessDenied:
            self._service.record_pre_sql_rejection("access_denied")
            raise
        except PlanCapabilityUnavailable:
            self._service.record_pre_sql_rejection("unsupported_plan")
            raise

        catalog = self._catalog
        metric = catalog.metrics.get(plan.metric_id)
        grouped_dimensions = set(plan.group_by_dimension_ids)
        covered_dimensions = grouped_dimensions | {
            item.dimension_id for item in plan.filters
        }
        if (
            plan.operation != "read"
            or plan.profile_id != catalog.profile_id
            or plan.source_id != catalog.source_id
            or plan.catalog_version != catalog.version
            or metric is None
            or plan.domain_id != metric.domain_id
            or plan.unit != metric.unit
            or not set(plan.dimension_ids) <= metric.dimension_ids
            or set(plan.dimension_ids) != covered_dimensions
            or len(grouped_dimensions) > 1
            or (
                plan.order is not None
                and (not metric.allow_value_order or plan.order.field_id != plan.metric_id)
            )
        ):
            self._reject("plan_out_of_catalog", "recorte fora do catálogo artificial")

        window = plan.window
        if (
            window.kind is not WindowKind.BOUNDED
            or window.granularity is not CatalogGranularity.MONTH
            or window.start is None
            or window.end is None
            or window.start.day != 1
            or window.end.day != calendar.monthrange(window.end.year, window.end.month)[1]
        ):
            self._reject("unsupported_window", "janela mensal artificial indisponível")

        table = f'"{catalog.table}"'
        period = f'"{catalog.period_column}"'
        measure = f'"{metric.column}"'
        group_id = next(iter(grouped_dimensions), None)
        group_column = catalog.dimensions.get(group_id) if group_id is not None else None
        if group_id is not None and group_column is None:
            self._reject("plan_out_of_catalog", "dimensão fora do catálogo artificial")
        conditions = [f"{period} BETWEEN ? AND ?"]
        parameters: list[str | int | float | bool] = [
            window.start.strftime("%Y-%m"),
            window.end.strftime("%Y-%m"),
        ]
        for item in plan.filters:
            column = catalog.dimensions.get(item.dimension_id)
            if column is None or item.dimension_id not in metric.dimension_ids:
                self._reject("plan_out_of_catalog", "dimensão fora do catálogo artificial")
            if item.operator not in metric.filter_operators:
                self._reject("unsupported_filter", "filtro artificial indisponível")
            if item.operator is FilterOperator.EQ and len(item.values) == 1:
                conditions.append(f'"{column}" = ?')
                parameters.append(item.values[0])
            elif item.operator is FilterOperator.IN and len(item.values) >= 2:
                placeholders = ", ".join("?" for _ in item.values)
                conditions.append(f'"{column}" IN ({placeholders})')
                parameters.extend(item.values)
            else:
                self._reject("unsupported_filter", "filtro artificial indisponível")

        category_projection = f', "{group_column}" AS category' if group_column else ""
        category_group = f', "{group_column}"' if group_column else ""
        category_select = ", category" if group_column else ""
        category_order = ", category ASC" if group_column else ""
        ordering = (
            f"value {plan.order.direction.value.upper()}, period ASC{category_order}"
            if plan.order is not None
            else f"period ASC{category_order}"
        )
        sql = (
            "WITH plan_rows AS ("
            f"SELECT {period} AS period{category_projection}, "
            f"SUM({measure}) AS value FROM {table} "
            f"WHERE {' AND '.join(conditions)} GROUP BY {period}{category_group}) "
            f"SELECT period{category_select}, value, "
            "(SELECT COUNT(*) FROM plan_rows) AS total_rows "
            f"FROM plan_rows ORDER BY {ordering} LIMIT {plan.limit}"
        )
        result = self._service.run(
            sql,
            tuple(parameters),
            audit_context=SqlAuditContext(
                plan_fingerprint=plan.fingerprint(), catalog_version=plan.catalog_version
            ),
        )
        expected_columns = (
            ("period", "category", "value", "total_rows")
            if group_id is not None
            else ("period", "value", "total_rows")
        )
        if result.columns != expected_columns or any(
            len(row) != len(expected_columns) for row in result.rows
        ):
            raise SqlRejected("invalid_result", "resultado artificial fora do contrato")
        total_rows = result.rows[0][-1] if result.rows else 0
        if type(total_rows) is not int or total_rows < result.row_count:
            raise SqlRejected("invalid_result", "contagem do resultado artificial inválida")
        return QueryResult(
            columns=("period", group_id, "value") if group_id else ("period", "value"),
            rows=tuple(row[:-1] for row in result.rows[: plan.limit]),
            truncated=result.truncated or total_rows > result.row_count,
        )
