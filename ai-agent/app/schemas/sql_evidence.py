"""Evidência F1 de execução; contrato espelhado e independente do plano legado.

Digest confere integridade, não concede autorização nem certifica dados.
"""

import hashlib
import json
import re
from typing import Annotated, Literal, Self

from pydantic import Field, StrictStr, StringConstraints, model_validator

from app.schemas.sql_generation import (
    ClosedModel,
    ParameterName,
    SqlInterpretation,
    SqlResultColumn,
)

Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
Batch = Annotated[str, StringConstraints(strict=True, pattern=(
    r"^gold-csv-v2:GOLD_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}:"
    r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"))]
Version = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
Cell = Annotated[StrictStr, Field(max_length=16384)] | None
Row = Annotated[tuple[Cell, ...], Field(min_length=1, max_length=32)]
Meaning = Literal[
    "revenue_total", "energy_total", "attendance_total", "attendance_accumulated_total",
    "gd_units_total", "dec_value", "fec_value", "satisfaction_average",
    "period_0_total", "period_1_total",
    "satisfaction_accumulated_average",
    "period_0_minus_period_1", "period_0_growth_percent",
]
DimensionMeaning = Literal["competency", "municipality", "neighborhood",
                          "consumption_class", "feeder"]
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]{0,100})(?:\.[0-9]{1,100})?\Z")


def sql_evidence_digest(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SqlEvidence(ClosedModel):
    evidence_contract_version: Literal[
        "text-to-sql-f1-evidence-v1", "text-to-sql-f1-evidence-v2",
        "text-to-sql-f1-evidence-v3", "text-to-sql-f1-evidence-v4",
        "text-to-sql-f1-evidence-v5",
        "text-to-sql-f1-evidence-v6",
        "text-to-sql-f1-evidence-v7",
        "text-to-sql-f1-evidence-v8",
        "text-to-sql-f1-evidence-v9",
    ]
    source_id: Literal["gold.local"]
    source_table: Literal[
        "gold_v2.diagnostico_receita", "gold_v2.atendimentos_uc",
        "gold_v2.indicadores_dec_fec",
        "gold_v2.consumo_receita_bairro", "gold_v2.visao_360_uc",
        "gold_v2.variacao_consumo_uc",
    ]
    metric_id: Literal[
        "billing.revenue", "energy.consumption", "service.attendance",
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
        "service.accumulated_attendance",
        "service.satisfaction",
        "service.accumulated_satisfaction",
        "energy.gd_units",
    ]
    coverage_quality: Literal["certified", "observed_uncertified"] = "certified"
    batch_ref: Batch
    context_version: Digest
    admission_digest: Digest
    execution_digest: Digest
    result_digest: Digest
    evidence_digest: Digest
    mapping_version: Version
    dictionary_version: Version
    interpretation: SqlInterpretation
    columns: tuple[SqlResultColumn, ...] = Field(min_length=1, max_length=32)
    measure_semantics: dict[ParameterName, Meaning] = Field(min_length=1, max_length=32)
    dimension_semantics: dict[ParameterName, DimensionMeaning] = Field(max_length=3)
    rows: tuple[Row, ...] = Field(max_length=100)
    status: Literal["empty", "all_measures_null", "available"]

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        names = [column.name for column in self.columns]
        measures = {column.name for column in self.columns if column.role == "measure"}
        dimensions = set(names) - measures
        if (len(names) != len(set(names)) or not measures
                or set(self.measure_semantics) != measures
                or set(self.dimension_semantics) != dimensions
                or len(set(self.dimension_semantics.values())) != len(dimensions)
                or set(self.dimension_semantics.values()) != set(self.interpretation.group_by)):
            raise ValueError("linhagem/colunas incompatíveis com a evidência F1")
        continuity = self.metric_id in {
            "network.equivalent_interruption_duration",
            "network.equivalent_interruption_frequency",
        }
        if continuity:
            expected_meaning = (
                "dec_value" if self.metric_id == "network.equivalent_interruption_duration"
                else "fec_value"
            )
            if (self.source_table != "gold_v2.indicadores_dec_fec"
                    or self.interpretation.operation != "grain_read"
                    or self.interpretation.aggregation != "key_grain_read"
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v5"
                    or set(self.measure_semantics.values()) != {expected_meaning}
                    or self.coverage_quality == "observed_uncertified" and (
                        len(self.interpretation.periods) != 1
                        or self.interpretation.periods[0].start.year
                        != self.interpretation.periods[0].end.year
                        or self.interpretation.periods[0].start.month
                        != self.interpretation.periods[0].end.month
                        or len(self.interpretation.filters) != 1
                        or self.interpretation.filters[0].dimension_id != "network.feeder"
                        or self.interpretation.filters[0].operator != "eq"
                    )):
                raise ValueError("DEC/FEC exige fonte, grão, evidência e qualidade compatíveis")
        elif self.coverage_quality != "certified":
            raise ValueError("qualidade observacional sem certificação só vale para DEC/FEC")
        if self.metric_id == "energy.gd_units":
            gd_filters = [item for item in self.interpretation.filters
                          if item.dimension_id == "generation.distributed"]
            if (self.source_table != "gold_v2.variacao_consumo_uc"
                    or self.interpretation.operation != "snapshot_total"
                    or self.interpretation.aggregation != "count_non_null"
                    or self.interpretation.periods
                    or len(gd_filters) != 1 or gd_filters[0].operator != "eq"
                    or gd_filters[0].values != ("Sim",)
                    or set(self.measure_semantics.values()) != {"gd_units_total"}
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v8"):
                raise ValueError("GD exige contagem cadastral do lote sem período")
        elif self.metric_id == "service.satisfaction":
            if (self.source_table != "gold_v2.atendimentos_uc"
                    or self.interpretation.operation != "average"
                    or self.interpretation.aggregation != "average_non_null"
                    or set(self.measure_semantics.values()) != {"satisfaction_average"}
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v7"):
                raise ValueError("satisfação exige média mensal da fonte autorizada")
        elif self.metric_id == "service.attendance":
            if (self.source_table != "gold_v2.atendimentos_uc"
                    or self.interpretation.operation != "total"
                    or self.interpretation.aggregation != "count_non_null"
                    or set(self.measure_semantics.values()) != {"attendance_total"}
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v4"):
                raise ValueError("atendimento exige contagem mensal da fonte autorizada")
        elif self.metric_id == "service.accumulated_attendance":
            if (self.source_table != "gold_v2.visao_360_uc"
                    or self.interpretation.operation != "accumulated_total"
                    or self.interpretation.periods
                    or self.interpretation.aggregation != "sum"
                    or set(self.measure_semantics.values()) != {
                        "attendance_accumulated_total",
                    }
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v6"):
                raise ValueError(
                    "atendimento acumulado exige histórico sem período e fonte autorizada"
                )
        elif self.metric_id == "service.accumulated_satisfaction":
            if (self.source_table != "gold_v2.atendimentos_uc"
                    or self.interpretation.operation != "accumulated_average"
                    or self.interpretation.periods
                    or self.interpretation.aggregation != "average_non_null"
                    or set(self.measure_semantics.values()) != {
                        "satisfaction_accumulated_average",
                    }
                    or self.evidence_contract_version != "text-to-sql-f1-evidence-v9"):
                raise ValueError(
                    "satisfação acumulada exige média sem período e fonte autorizada"
                )
        elif (self.metric_id == "billing.revenue"
              and self.source_table == "gold_v2.consumo_receita_bairro"):
            if self.evidence_contract_version not in {
                "text-to-sql-f1-evidence-v1", "text-to-sql-f1-evidence-v2",
            }:
                raise ValueError("receita por bairro exige contrato de receita compatível")
        elif (not continuity and self.metric_id not in {
                  "service.accumulated_attendance", "service.accumulated_satisfaction",
                  "energy.gd_units",
              }
              and self.source_table != "gold_v2.diagnostico_receita"):
            raise ValueError("fonte SQL diverge da métrica F1")
        if self.interpretation.operation == "comparison":
            base_meanings = {
                "period_0_total", "period_1_total", "period_0_minus_period_1",
            }
            has_growth = "period_0_growth_percent" in self.measure_semantics.values()
            expected_meanings = base_meanings | (
                {"period_0_growth_percent"} if has_growth else set()
            )
            expected_version = (
                "text-to-sql-f1-evidence-v3" if self.metric_id == "energy.consumption"
                else "text-to-sql-f1-evidence-v2" if has_growth
                else "text-to-sql-f1-evidence-v1"
            )
            if (len(measures) != len(expected_meanings)
                    or set(self.measure_semantics.values()) != expected_meanings
                    or self.evidence_contract_version != expected_version):
                raise ValueError("comparação exige dois totais e diferença com linhagem")
        elif (set(self.measure_semantics.values()) != {
                  "energy_total" if self.metric_id == "energy.consumption"
                  else "attendance_total" if self.metric_id == "service.attendance"
                  else "attendance_accumulated_total"
                  if self.metric_id == "service.accumulated_attendance"
                  else "satisfaction_accumulated_average"
                  if self.metric_id == "service.accumulated_satisfaction"
                  else "gd_units_total" if self.metric_id == "energy.gd_units"
                  else "satisfaction_average" if self.metric_id == "service.satisfaction"
                  else "dec_value" if self.metric_id == "network.equivalent_interruption_duration"
                  else "fec_value" if self.metric_id == "network.equivalent_interruption_frequency"
                  else "revenue_total",
              }
              or self.evidence_contract_version != (
                  "text-to-sql-f1-evidence-v4" if self.metric_id == "service.attendance"
                  else "text-to-sql-f1-evidence-v7" if self.metric_id == "service.satisfaction"
                  else "text-to-sql-f1-evidence-v6"
                  if self.metric_id == "service.accumulated_attendance"
                  else "text-to-sql-f1-evidence-v9"
                  if self.metric_id == "service.accumulated_satisfaction"
                  else "text-to-sql-f1-evidence-v8" if self.metric_id == "energy.gd_units"
                  else "text-to-sql-f1-evidence-v5" if continuity
                  else "text-to-sql-f1-evidence-v3" if self.metric_id == "energy.consumption"
                  else "text-to-sql-f1-evidence-v1"
              )):
            raise ValueError("medida condicional exige comparação")
        for column in self.columns:
            meaning = self.measure_semantics.get(column.name)
            expected_unit = (
                "%" if meaning == "period_0_growth_percent"
                else "protocolos" if self.metric_id in {
                    "service.attendance", "service.accumulated_attendance",
                }
                else "UCs" if self.metric_id == "energy.gd_units"
                else "pontos" if self.metric_id == "service.satisfaction"
                else "pontos" if self.metric_id == "service.accumulated_satisfaction"
                else "horas por UC" if meaning == "dec_value"
                else "interrupções por UC" if meaning == "fec_value"
                else "kWh" if self.metric_id == "energy.consumption"
                else "R$"
            )
            if column.role == "measure" and column.unit != expected_unit:
                raise ValueError("unidade diverge da semântica da medida")
        present = False
        for row in self.rows:
            if len(row) != len(names):
                raise ValueError("linha diverge das colunas da evidência")
            for column, value in zip(self.columns, row, strict=True):
                if column.role == "measure" and value is not None:
                    if not _DECIMAL.fullmatch(value):
                        raise ValueError("medida exige decimal canônico em texto")
                    present = True
        expected = "empty" if not self.rows else "available" if present else "all_measures_null"
        if self.status != expected:
            raise ValueError("estado diverge das medidas da evidência")
        payload = self.model_dump(mode="json", exclude={"evidence_digest"})
        if self.evidence_contract_version not in {
            "text-to-sql-f1-evidence-v5", "text-to-sql-f1-evidence-v6",
            "text-to-sql-f1-evidence-v7",
            "text-to-sql-f1-evidence-v8",
            "text-to-sql-f1-evidence-v9",
        }:
            # Existing v1-v4 digests predate the quality field; the validator
            # fixes those legacy contracts to the certified value above.
            payload.pop("coverage_quality", None)
        try:
            encoded = json.dumps(self.model_dump(mode="json"), ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8")
            size = len(encoded)
            valid_digest = sql_evidence_digest(payload) == self.evidence_digest
            result = {"columns": names, "measure_semantics": [
                [name, self.measure_semantics[name]] for name in names if name in measures],
                "rows": self.rows, "status": self.status}
            serialized = json.dumps(result, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")
            valid_result = hashlib.sha256(serialized).hexdigest() == self.result_digest
        except (ValueError, UnicodeError):
            raise ValueError("evidência não serializável") from None
        if size > 32768 or not valid_digest or not valid_result:
            raise ValueError("evidência excede limite ou digest divergente")
        return self
