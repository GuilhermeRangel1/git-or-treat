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
    "revenue_total", "period_0_total", "period_1_total",
    "period_0_minus_period_1", "period_0_growth_percent",
]
DimensionMeaning = Literal["competency", "municipality", "consumption_class"]
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]{0,100})(?:\.[0-9]{1,100})?\Z")


def sql_evidence_digest(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SqlEvidence(ClosedModel):
    evidence_contract_version: Literal[
        "text-to-sql-f1-evidence-v1", "text-to-sql-f1-evidence-v2",
    ]
    source_id: Literal["gold.local"]
    source_table: Literal["gold_v2.diagnostico_receita"]
    metric_id: Literal["billing.revenue"]
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
        if self.interpretation.operation == "comparison":
            base_meanings = {
                "period_0_total", "period_1_total", "period_0_minus_period_1",
            }
            has_growth = "period_0_growth_percent" in self.measure_semantics.values()
            expected_meanings = base_meanings | (
                {"period_0_growth_percent"} if has_growth else set()
            )
            expected_version = (
                "text-to-sql-f1-evidence-v2"
                if has_growth else "text-to-sql-f1-evidence-v1"
            )
            if (len(measures) != len(expected_meanings)
                    or set(self.measure_semantics.values()) != expected_meanings
                    or self.evidence_contract_version != expected_version):
                raise ValueError("comparação exige dois totais e diferença com linhagem")
        elif (set(self.measure_semantics.values()) != {"revenue_total"}
              or self.evidence_contract_version != "text-to-sql-f1-evidence-v1"):
            raise ValueError("medida condicional exige comparação")
        for column in self.columns:
            meaning = self.measure_semantics.get(column.name)
            expected_unit = "%" if meaning == "period_0_growth_percent" else "R$"
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
