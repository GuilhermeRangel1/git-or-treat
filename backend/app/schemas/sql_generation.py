"""Candidato SQL F1 não confiável; validar este envelope não autoriza execução.

Contrato independente espelhado no Backend e verificado por fixtures comuns.
Não importa planner, HTTP, provedor nem conexão de banco.
"""

import json
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

ShortText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True,
                                            min_length=1, max_length=1000)]
ParameterName = Annotated[str, StringConstraints(strict=True,
                                                pattern=r"^[a-z][a-z0-9_]{0,62}$")]
Scalar = StrictStr | StrictInt | StrictFloat | StrictBool
Dimension = Literal["geography.municipality", "customer.consumption_class"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class SqlParameter(ClosedModel):
    type: Literal["string", "integer", "number", "boolean", "date", "decimal"]
    value: Scalar

    @model_validator(mode="after")
    def check_type(self) -> Self:
        value = self.value
        valid = {
            "string": type(value) is str,
            "integer": type(value) is int,
            "number": type(value) in (int, float),
            "boolean": type(value) is bool,
            "date": type(value) is str,
            "decimal": type(value) is str,
        }[self.type]
        if not valid or isinstance(value, str) and len(value) > 1000:
            raise ValueError("tipo ou tamanho de parâmetro incompatível")
        if type(value) is float and not isfinite(value):
            raise ValueError("parâmetro numérico não finito")
        if self.type == "date":
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError("data deve usar YYYY-MM-DD")
        if self.type == "decimal":
            try:
                number = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError("decimal inválido") from exc
            if not number.is_finite():
                raise ValueError("decimal não finito")
        return self


class SqlPeriod(ClosedModel):
    start: date
    end: date

    @model_validator(mode="before")
    @classmethod
    def reject_timestamp_coercion(cls, data):
        if isinstance(data, dict):
            for key in ("start", "end"):
                value = data.get(key)
                if type(value) is date:
                    continue
                if type(value) is not str or date.fromisoformat(value).isoformat() != value:
                    raise ValueError("data exige representação ISO sem timestamp")
        return data

    @model_validator(mode="after")
    def check_monthly_window(self) -> Self:
        if (self.start > self.end or self.start.day != 1
                or self.end.day != monthrange(self.end.year, self.end.month)[1]):
            raise ValueError("janela exige meses completos ordenados")
        return self


class SqlAnalysisFilter(ClosedModel):
    dimension_id: Dimension
    operator: Literal["eq", "in"]
    values: tuple[Annotated[str, StringConstraints(strict=True, min_length=1,
                                                  max_length=120)], ...] = Field(
        min_length=1, max_length=20
    )

    @model_validator(mode="after")
    def check_values(self) -> Self:
        if len(set(self.values)) != len(self.values) or any(not x.strip() for x in self.values):
            raise ValueError("filtros exigem valores únicos e não vazios")
        if (self.operator == "eq" and len(self.values) != 1
                or self.operator == "in" and len(self.values) < 2):
            raise ValueError("quantidade de valores incompatível com operador")
        return self


class SqlSemanticIntent(ClosedModel):
    """Reconhecimento mínimo de pedido sem execução na capacidade F1."""

    metric_id: Annotated[str, StringConstraints(
        strict=True, pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", max_length=120,
    )]
    periods: tuple[SqlPeriod, ...] = Field(default=(), max_length=2)
    filters: tuple[SqlAnalysisFilter, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def check_unique_filters(self) -> Self:
        if len({item.dimension_id for item in self.filters}) != len(self.filters):
            raise ValueError("intenção semântica não pode repetir dimensão de filtro")
        return self


class SqlInterpretation(ClosedModel):
    metric_id: Literal["billing.revenue"]
    operation: Literal["total", "monthly_series", "grouped_total", "ranking", "comparison"]
    aggregation: Literal["sum"]
    periods: tuple[SqlPeriod, ...] = Field(min_length=1, max_length=2)
    filters: tuple[SqlAnalysisFilter, ...] = Field(default=(), max_length=2)
    group_by: tuple[Literal["competency", "municipality", "consumption_class"], ...] = Field(
        default=(), max_length=3
    )
    ranking_direction: Literal["asc", "desc"] | None = None
    ranking_limit: Annotated[int, Field(strict=True, ge=1, le=100)] | None = None

    @model_validator(mode="after")
    def check_operation(self) -> Self:
        if len(self.periods) != (2 if self.operation == "comparison" else 1):
            raise ValueError("comparação exige duas janelas; demais operações uma")
        ranked = self.ranking_direction is not None and self.ranking_limit is not None
        if self.operation == "ranking":
            if not ranked or not self.group_by:
                raise ValueError("ranking exige direção, limite e agrupamento")
        elif self.ranking_direction is not None or self.ranking_limit is not None:
            raise ValueError("metadados de ranking exigem operação ranking")
        if len(set(self.group_by)) != len(self.group_by):
            raise ValueError("agrupamento duplicado")
        if len({item.dimension_id for item in self.filters}) != len(self.filters):
            raise ValueError("filtro de dimensão duplicado")
        if self.operation == "total" and self.group_by:
            raise ValueError("total não admite agrupamento")
        if self.operation == "grouped_total" and not self.group_by:
            raise ValueError("total agrupado exige agrupamento")
        if self.operation == "monthly_series" and "competency" not in self.group_by:
            raise ValueError("série mensal exige competência")
        return self


class SqlResultColumn(ClosedModel):
    name: ParameterName
    role: Literal["measure", "dimension"]
    value_type: Literal["decimal", "string"]
    unit: Literal["R$"] | None = None

    @model_validator(mode="after")
    def check_role(self) -> Self:
        if self.role == "measure":
            if self.value_type != "decimal" or self.unit != "R$":
                raise ValueError("medida F1 exige decimal e R$")
        elif self.value_type != "string" or self.unit is not None:
            raise ValueError("dimensão F1 exige string sem unidade monetária")
        return self


class SqlClarification(ClosedModel):
    question: ShortText
    missing_fields: tuple[Literal["metric", "period", "dimension", "filter",
                                  "comparison_baseline", "context"], ...] = Field(
        min_length=1, max_length=6
    )


class SqlUnsupported(ClosedModel):
    code: Literal["metric_outside_f1", "operation_outside_f1", "source_outside_f1"]
    message: ShortText


class SqlGenerationCandidate(ClosedModel):
    generation_contract_version: Literal["text-to-sql-f1-v1"]
    status: Literal["sql_candidate", "needs_clarification", "unsupported"]
    context_version: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
    sql: Annotated[str, StringConstraints(strict=True, strip_whitespace=True,
                                         min_length=1, max_length=16000)] | None = None
    parameters: dict[ParameterName, SqlParameter] = Field(default_factory=dict, max_length=32)
    interpretation: SqlInterpretation | None = None
    semantic_intent: SqlSemanticIntent | None = None
    result_columns: tuple[SqlResultColumn, ...] = Field(default=(), max_length=32)
    clarification: SqlClarification | None = None
    unsupported_reason: SqlUnsupported | None = None

    @model_validator(mode="after")
    def check_status(self) -> Self:
        if self.status == "sql_candidate":
            if (self.sql is None or self.interpretation is None or not self.result_columns
                    or self.clarification is not None or self.unsupported_reason is not None
                    or self.semantic_intent is not None):
                raise ValueError("candidato exige SQL, interpretação e colunas sem esclarecimento")
            names = [column.name for column in self.result_columns]
            if len(set(names)) != len(names) or not any(
                column.role == "measure" for column in self.result_columns
            ):
                raise ValueError("resultado exige aliases únicos e medida")
        else:
            if (self.sql is not None or self.parameters
                    or self.interpretation or self.result_columns):
                raise ValueError("estado sem candidato não pode transportar consulta parcial")
            if ((self.status == "needs_clarification") != (self.clarification is not None)
                    or (self.status == "unsupported") != (self.unsupported_reason is not None)):
                raise ValueError("estado exige explicação específica compatível")
            if self.status == "needs_clarification" and self.semantic_intent is not None:
                raise ValueError("esclarecimento não pode transportar intenção parcial")
        return self


class SqlGenerationRequest(ClosedModel):
    generation_contract_version: Literal["text-to-sql-f1-v1"] = "text-to-sql-f1-v1"
    context_version: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
    contents: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=65536)]
    remaining_timeout_ms: Annotated[int, Field(strict=True, ge=1, le=60000)]

    @model_validator(mode="after")
    def check_context_envelope(self) -> Self:
        if len(self.contents.encode("utf-8")) > 65536:
            raise ValueError("contexto excede limite de bytes")
        try:
            context = json.loads(self.contents)
        except ValueError:
            raise ValueError("contexto deve ser JSON válido") from None
        if (not isinstance(context, dict)
                or context.get("context_version") != self.context_version
                or context.get("generation_contract_version") != self.generation_contract_version
                or context.get("dialect") != "postgres"):
            raise ValueError("contexto incompatível com envelope F1")
        return self


class SqlGenerationResponse(ClosedModel):
    generation_contract_version: Literal["text-to-sql-f1-v1"] = "text-to-sql-f1-v1"
    correlation_id: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")]
    candidate: SqlGenerationCandidate
