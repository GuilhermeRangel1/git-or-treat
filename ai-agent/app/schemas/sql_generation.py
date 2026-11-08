"""Candidato SQL F1 não confiável; validar este envelope não autoriza execução.

Contrato independente espelhado no Backend e verificado por fixtures comuns.
Não importa planner, HTTP, provedor nem conexão de banco.
"""

import json
from calendar import monthrange
from datetime import UTC, date, datetime
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

ShortText = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1000)
]
ParameterName = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z][a-z0-9_]{0,62}$")]
Scalar = StrictStr | StrictInt | StrictFloat | StrictBool
Dimension = Literal[
    "geography.municipality",
    "geography.neighborhood",
    "customer.consumption_class",
    "network.feeder",
    "generation.distributed",
]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class SqlParameter(ClosedModel):
    type: Literal["string", "integer", "number", "boolean", "date", "timestamp", "decimal"]
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
            "timestamp": type(value) is str,
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
        if self.type == "timestamp":
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("timestamp inválido") from exc
            if (
                parsed.tzinfo is None
                or parsed.utcoffset() is None
                or parsed.astimezone(UTC).isoformat().replace("+00:00", "Z") != value
            ):
                raise ValueError("timestamp deve ser UTC canônico com sufixo Z")
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
        if (
            self.start > self.end
            or self.start.day != 1
            or self.end.day != monthrange(self.end.year, self.end.month)[1]
        ):
            raise ValueError("janela exige meses completos ordenados")
        return self


class SqlAnalysisFilter(ClosedModel):
    dimension_id: Dimension
    operator: Literal["eq", "in"]
    values: tuple[
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)], ...
    ] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def check_values(self) -> Self:
        if len(set(self.values)) != len(self.values) or any(not x.strip() for x in self.values):
            raise ValueError("filtros exigem valores únicos e não vazios")
        if (
            self.operator == "eq"
            and len(self.values) != 1
            or self.operator == "in"
            and len(self.values) < 2
        ):
            raise ValueError("quantidade de valores incompatível com operador")
        return self


class SqlSemanticIntent(ClosedModel):
    """Reconhecimento mínimo de pedido sem execução na capacidade F1."""

    metric_id: Annotated[
        str,
        StringConstraints(
            strict=True,
            pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$",
            max_length=120,
        ),
    ]
    periods: tuple[SqlPeriod, ...] = Field(default=(), max_length=2)
    filters: tuple[SqlAnalysisFilter, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def check_unique_filters(self) -> Self:
        if len({item.dimension_id for item in self.filters}) != len(self.filters):
            raise ValueError("intenção semântica não pode repetir dimensão de filtro")
        return self


class SqlInterpretation(ClosedModel):
    metric_id: Literal[
        "billing.revenue",
        "energy.consumption",
        "billing.average_ticket",
        "billing.effective_tariff",
        "energy.average_consumption_per_uc",
        "service.attendance",
        "service.satisfaction",
        "service.accumulated_attendance",
        "service.accumulated_satisfaction",
        "energy.gd_units",
        "energy.gd_consumption_drop",
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    ]
    operation: Literal[
        "total",
        "monthly_series",
        "grouped_total",
        "ranking",
        "comparison",
        "grain_read",
        "accumulated_total",
        "average",
        "snapshot_total",
        "accumulated_average",
        "ratio_of_sums",
        "weighted_continuity",
    ]
    aggregation: Literal[
        "sum",
        "count_non_null",
        "count_gd_drop",
        "key_grain_read",
        "average_non_null",
        "ratio_of_sums",
        "weighted_ratio",
    ]
    periods: tuple[SqlPeriod, ...] = Field(max_length=2)
    filters: tuple[SqlAnalysisFilter, ...] = Field(default=(), max_length=2)
    group_by: tuple[
        Literal["competency", "municipality", "neighborhood", "consumption_class", "feeder"], ...
    ] = Field(default=(), max_length=4)
    ranking_direction: Literal["asc", "desc"] | None = None
    ranking_limit: Annotated[int, Field(strict=True, ge=1, le=100)] | None = None

    @model_validator(mode="after")
    def check_operation(self) -> Self:
        expected_periods = (
            2
            if self.operation == "comparison"
            else 0
            if self.operation
            in {
                "accumulated_total",
                "snapshot_total",
                "accumulated_average",
            }
            else 1
        )
        if len(self.periods) != expected_periods:
            raise ValueError("comparação exige duas janelas; demais operações uma")
        ranked = self.ranking_direction is not None and self.ranking_limit is not None
        if self.operation == "ranking":
            if not ranked or not self.group_by:
                raise ValueError("ranking exige direção, limite e agrupamento")
        elif (self.ranking_direction is not None or self.ranking_limit is not None) and (
            self.operation != "comparison" or not ranked or not self.group_by
        ):
            raise ValueError("ranking de comparação exige agrupamento, direção e limite")
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
        if self.operation == "accumulated_total" and (
            self.metric_id != "service.accumulated_attendance"
            or self.aggregation != "sum"
            or self.filters
            or self.group_by
            or self.ranking_direction is not None
            or self.ranking_limit is not None
        ):
            raise ValueError("histórico acumulado exige total sem período ou recortes")
        if self.operation == "average" and (
            self.metric_id != "service.satisfaction"
            or self.aggregation != "average_non_null"
            or self.filters
            or self.group_by
            or self.ranking_direction is not None
            or self.ranking_limit is not None
        ):
            raise ValueError("média mensal exige satisfação sem filtros ou agrupamentos")
        if self.operation == "accumulated_average" and (
            self.metric_id != "service.accumulated_satisfaction"
            or self.aggregation != "average_non_null"
            or self.filters
            or self.group_by
            or self.ranking_direction is not None
            or self.ranking_limit is not None
        ):
            raise ValueError("satisfação histórica exige média sem período ou recortes")
        if self.operation == "ratio_of_sums" and (
            self.metric_id not in {
                "energy.average_consumption_per_uc",
                "billing.average_ticket",
                "billing.effective_tariff",
            }
            or self.aggregation != "ratio_of_sums"
            or self.group_by
            or self.ranking_direction is not None
            or self.ranking_limit is not None
        ):
            raise ValueError("razão de somas exige métrica F1 compatível sem grupos")
        if self.operation == "snapshot_total":
            gd_filters = [
                item for item in self.filters if item.dimension_id == "generation.distributed"
            ]
            drop_metric = self.metric_id == "energy.gd_consumption_drop"
            if (
                self.metric_id not in {"energy.gd_units", "energy.gd_consumption_drop"}
                or self.aggregation != ("count_gd_drop" if drop_metric else "count_non_null")
                or len(gd_filters) != 1
                or gd_filters[0].operator != "eq"
                or gd_filters[0].values != ("Sim",)
                or any(
                    item.dimension_id
                    not in {
                        "geography.municipality",
                        "generation.distributed",
                    }
                    for item in self.filters
                )
                or any(item != "municipality" for item in self.group_by)
                or len(self.group_by) > 1
                or self.ranking_direction is not None
                or self.ranking_limit is not None
            ):
                raise ValueError("retrato de GD exige contagem aprovada sem período")
        if self.metric_id == "service.satisfaction" and self.operation != "average":
            raise ValueError("satisfação F1 libera somente média mensal")
        if self.metric_id == "energy.gd_units" and self.operation != "snapshot_total":
            raise ValueError("GD cadastrado libera somente retrato do lote")
        if self.metric_id == "energy.gd_consumption_drop" and self.operation != "snapshot_total":
            raise ValueError("queda de consumo com GD libera somente o retrato das janelas fixas")
        if (
            self.metric_id == "service.accumulated_satisfaction"
            and self.operation != "accumulated_average"
        ):
            raise ValueError("satisfação acumulada libera somente o histórico publicado")
        if self.operation == "grain_read":
            feeder_filters = [
                item for item in self.filters if item.dimension_id == "network.feeder"
            ]
            if (
                self.metric_id
                not in {
                    "network.equivalent_interruption_duration",
                    "network.equivalent_interruption_frequency",
                }
                or self.aggregation != "key_grain_read"
                or self.group_by
                or len(self.periods) != 1
                or len(feeder_filters) != 1
                or feeder_filters[0].operator != "eq"
                or self.ranking_direction is not None
                or self.ranking_limit is not None
            ):
                raise ValueError("leitura DEC/FEC exige grão e alimentador fixos")
        elif self.operation == "weighted_continuity":
            feeder_filters = [
                item for item in self.filters if item.dimension_id == "network.feeder"
            ]
            if (
                self.metric_id not in {
                    "network.equivalent_interruption_duration",
                    "network.equivalent_interruption_frequency",
                }
                or self.aggregation != "weighted_ratio"
                or self.group_by
                or len(feeder_filters) > 1
                or any(item.dimension_id != "network.feeder" for item in self.filters)
                or feeder_filters and feeder_filters[0].operator not in {"eq", "in"}
                or self.ranking_direction is not None
                or self.ranking_limit is not None
            ):
                raise ValueError("DEC/FEC ponderado exige janela e alimentadores autorizados")
        elif (
            self.aggregation == "key_grain_read"
            or self.aggregation == "weighted_ratio"
            or "feeder" in self.group_by
            or self.metric_id
            in {
                "network.equivalent_interruption_duration",
                "network.equivalent_interruption_frequency",
            }
        ):
            raise ValueError("DEC/FEC não admite agregação nem agrupamento adicional")
        return self


class SqlResultColumn(ClosedModel):
    name: ParameterName
    role: Literal["measure", "dimension"]
    value_type: Literal["decimal", "integer", "string"]
    unit: (
        Literal[
            "R$",
            "R$ por UC faturada no mês",
            "R$/kWh",
            "kWh",
            "kWh por UC com leitura no mês",
            "protocolos",
            "UCs",
            "pontos",
            "horas por UC",
            "interrupções por UC",
            "alimentadores",
            "%",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def check_role(self) -> Self:
        if self.role == "measure":
            if (
                self.unit in {"protocolos", "UCs", "alimentadores"}
                and self.value_type != "integer"
                or self.unit not in {"protocolos", "UCs", "alimentadores"}
                and (
                    self.value_type != "decimal"
                    or self.unit
                    not in {
                        "R$",
                        "R$ por UC faturada no mês",
                        "R$/kWh",
                        "kWh",
                        "kWh por UC com leitura no mês",
                        "pontos",
                        "horas por UC",
                        "interrupções por UC",
                        "alimentadores",
                        "%",
                    }
                )
            ):
                raise ValueError("medida F1 exige tipo e unidade autorizados")
        elif self.value_type != "string" or self.unit is not None:
            raise ValueError("dimensão F1 exige string sem unidade monetária")
        return self


class SqlClarification(ClosedModel):
    question: ShortText
    missing_fields: tuple[
        Literal["metric", "period", "dimension", "filter", "comparison_baseline", "context"], ...
    ] = Field(min_length=1, max_length=6)


class SqlUnsupported(ClosedModel):
    code: Literal["metric_outside_f1", "operation_outside_f1", "source_outside_f1"]
    message: ShortText


GenerationContractVersion = Literal[
    "text-to-sql-f1-v1",
    "text-to-sql-f1-v2",
    "text-to-sql-f1-v3",
    "text-to-sql-f1-v4",
    "text-to-sql-f1-v5",
    "text-to-sql-f1-v7",
    "text-to-sql-f1-v8",
    "text-to-sql-f1-v9",
    "text-to-sql-f1-v10",
    "text-to-sql-f1-v11",
    "text-to-sql-f1-v12",
    "text-to-sql-f1-v13",
]


class SqlGenerationCandidate(ClosedModel):
    generation_contract_version: GenerationContractVersion
    status: Literal["sql_candidate", "needs_clarification", "unsupported"]
    context_version: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
    sql: (
        Annotated[
            str,
            StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=16000),
        ]
        | None
    ) = None
    parameters: dict[ParameterName, SqlParameter] = Field(default_factory=dict, max_length=32)
    interpretation: SqlInterpretation | None = None
    semantic_intent: SqlSemanticIntent | None = None
    result_columns: tuple[SqlResultColumn, ...] = Field(default=(), max_length=32)
    clarification: SqlClarification | None = None
    unsupported_reason: SqlUnsupported | None = None

    @model_validator(mode="after")
    def check_status(self) -> Self:
        if self.status == "sql_candidate":
            if (
                self.sql is None
                and not (
                    self.generation_contract_version == "text-to-sql-f1-v12"
                    and self.interpretation is not None
                    and self.interpretation.operation == "weighted_continuity"
                )
                or self.interpretation is None
                or not self.result_columns
                or self.clarification is not None
                or self.unsupported_reason is not None
                or self.semantic_intent is not None
            ):
                raise ValueError("candidato exige SQL, interpretação e colunas sem esclarecimento")
            names = [column.name for column in self.result_columns]
            if len(set(names)) != len(names) or not any(
                column.role == "measure" for column in self.result_columns
            ):
                raise ValueError("resultado exige aliases únicos e medida")
            if (
                self.generation_contract_version == "text-to-sql-f1-v1"
                and self.interpretation.metric_id != "billing.revenue"
            ):
                raise ValueError("F1 v1 só admite faturamento")
            if (
                self.generation_contract_version == "text-to-sql-f1-v3"
                and self.interpretation.metric_id != "service.attendance"
            ):
                raise ValueError("F1 v3 só admite atendimento mensal")
            if (
                self.generation_contract_version == "text-to-sql-f1-v4"
                and self.interpretation.metric_id
                not in {
                    "network.equivalent_interruption_duration",
                    "network.equivalent_interruption_frequency",
                }
            ):
                raise ValueError("F1 v4 só admite leitura de DEC/FEC")
            if (
                self.generation_contract_version == "text-to-sql-f1-v5"
                and self.interpretation.metric_id != "service.accumulated_attendance"
            ):
                raise ValueError("F1 v5 só admite atendimento acumulado")
            if (
                self.generation_contract_version == "text-to-sql-f1-v7"
                and self.interpretation.metric_id != "service.satisfaction"
            ):
                raise ValueError("F1 v7 só admite satisfação mensal")
            if (
                self.generation_contract_version == "text-to-sql-f1-v8"
                and self.interpretation.metric_id != "energy.gd_units"
            ):
                raise ValueError("F1 v8 só admite retrato de UCs com GD")
            if (
                self.generation_contract_version == "text-to-sql-f1-v9"
                and self.interpretation.metric_id != "service.accumulated_satisfaction"
            ):
                raise ValueError("F1 v9 só admite satisfação do histórico publicado")
            if (
                self.generation_contract_version == "text-to-sql-f1-v10"
                and self.interpretation.metric_id != "energy.gd_consumption_drop"
            ):
                raise ValueError("F1 v10 só admite queda de consumo elegível com GD")
            if (
                self.generation_contract_version == "text-to-sql-f1-v11"
                and self.interpretation.metric_id
                != "energy.average_consumption_per_uc"
            ):
                raise ValueError("F1 v11 só admite consumo médio por UC com leitura")
            if (
                self.generation_contract_version == "text-to-sql-f1-v12"
                and self.interpretation.operation != "weighted_continuity"
            ):
                raise ValueError("F1 v12 só admite agregação ponderada DEC/FEC")
            if (
                self.generation_contract_version == "text-to-sql-f1-v13"
                and (
                    self.interpretation.metric_id
                    not in {"billing.average_ticket", "billing.effective_tariff"}
                    or self.interpretation.operation != "ratio_of_sums"
                )
            ):
                raise ValueError("F1 v13 só admite ticket médio e preço observado")
        else:
            if (
                self.sql is not None
                or self.parameters
                or self.interpretation
                or self.result_columns
            ):
                raise ValueError("estado sem candidato não pode transportar consulta parcial")
            if (self.status == "needs_clarification") != (self.clarification is not None) or (
                self.status == "unsupported"
            ) != (self.unsupported_reason is not None):
                raise ValueError("estado exige explicação específica compatível")
            if self.status == "needs_clarification" and self.semantic_intent is not None:
                raise ValueError("esclarecimento não pode transportar intenção parcial")
        return self


class SqlGenerationRequest(ClosedModel):
    generation_contract_version: GenerationContractVersion = "text-to-sql-f1-v1"
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
        if (
            not isinstance(context, dict)
            or context.get("context_version") != self.context_version
            or context.get("generation_contract_version") != self.generation_contract_version
            or context.get("dialect") != "postgres"
        ):
            raise ValueError("contexto incompatível com envelope F1")
        return self


class SqlGenerationResponse(ClosedModel):
    generation_contract_version: GenerationContractVersion = "text-to-sql-f1-v1"
    correlation_id: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")]
    candidate: SqlGenerationCandidate

    @model_validator(mode="after")
    def check_contract_version(self) -> Self:
        if self.candidate.generation_contract_version != self.generation_contract_version:
            raise ValueError("versão do envelope e candidato divergem")
        return self
