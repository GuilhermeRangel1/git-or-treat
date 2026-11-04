"""Validação estrita do pacote analítico Gold CSV v2."""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from app.models.gold_v2 import TABLES
from app.schemas.gold_publication import GoldRun, SourceRun

SCHEMA_VERSION = "gold-csv-v2"
MAX_MANIFEST_BYTES = 65536

CSV_FORMAT = {
    "header": "true",
    "lineSep": "\n",
    "sep": ";",
    "encoding": "UTF-8",
    "quoteAll": "true",
    "multiLine": "true",
    "escape": '"',
    "quote": '"',
    "nullValue": r"\N",
    "emptyValue": "",
    "dateFormat": "yyyy-MM-dd",
    "timestampFormat": "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX",
    "timeZone": "UTC",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SparkField(StrictModel):
    name: StrictStr
    type: StrictStr
    nullable: StrictBool
    metadata: dict[str, Any]


class SparkSchema(StrictModel):
    type: Literal["struct"]
    fields: list[SparkField]


class TableControl(StrictModel):
    registros: StrictInt = Field(ge=0)
    versao_delta: StrictInt = Field(ge=0)
    spark_schema: SparkSchema = Field(alias="schema")


class CsvFormat(StrictModel):
    header: StrictStr
    lineSep: StrictStr
    sep: StrictStr
    encoding: StrictStr
    quoteAll: StrictStr
    multiLine: StrictStr
    escape: StrictStr
    quote: StrictStr
    nullValue: StrictStr
    emptyValue: StrictStr
    dateFormat: StrictStr
    timestampFormat: StrictStr
    timeZone: StrictStr


class GoldManifestV2(StrictModel):
    schema_version: Literal["gold-csv-v2"]
    ambiente: Literal["prod"]
    lote: GoldRun
    run_id: GoldRun
    run_id_silver: SourceRun
    lote_bronze_silver: SourceRun
    data_processamento_gold: datetime
    status_gold: Literal["CONCLUIDO"]
    data_exportacao_csv: datetime
    export_id: StrictStr = Field(min_length=1, max_length=128)
    cadastro_export_id: StrictStr = Field(min_length=1, max_length=128)
    cadastro_schema_version: Literal["gold-cadastro-v1"]
    tabelas_exportadas: list[StrictStr]
    controles_tabelas: dict[StrictStr, TableControl]
    formato_csv: CsvFormat
    preco_volume_configuracao: dict[str, Any]
    preco_volume_referencia: datetime | None
    limitacoes_medidas: dict[StrictStr, StrictStr]
    responsavel: StrictStr = Field(min_length=1, max_length=200)

    @field_validator("data_processamento_gold", "data_exportacao_csv", "preco_volume_referencia")
    @classmethod
    def require_utc_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("instante Gold v2 deve incluir offset UTC")
        return value.astimezone(UTC) if value is not None else value

    @model_validator(mode="after")
    def validate_inventory_and_format(self):
        names = list(TABLES)
        if self.lote != self.run_id:
            raise ValueError("lote e run_id devem coincidir")
        if len(self.tabelas_exportadas) != len(names) or set(self.tabelas_exportadas) != set(names):
            raise ValueError("inventário de tabelas incompatível")
        if set(self.controles_tabelas) != set(names):
            raise ValueError("controles do manifesto incompatíveis")
        if self.formato_csv.model_dump() != CSV_FORMAT:
            raise ValueError("formato CSV incompatível")
        if set(self.preco_volume_configuracao) != {"estado", "janelas", "metodo"}:
            raise ValueError("configuração preço-volume incompatível")
        if set(self.limitacoes_medidas) != {
            "energia_faturada_kwh", "energia_recuperavel_kwh", "fechamento_mensal", "valor_recebido_reais",
        }:
            raise ValueError("limitações de medidas incompatíveis")
        for name, table in TABLES.items():
            control = self.controles_tabelas[name]
            fields = control.spark_schema.fields
            by_name = {field.name: field for field in fields}
            if len(by_name) != len(fields) or set(by_name) != set(table.c.keys()):
                raise ValueError(f"schema divergente para {name}")
            for column in table.columns:
                field = by_name[column.name]
                if field.type != _spark_type(column.type) or field.nullable is not True:
                    raise ValueError(f"tipo físico divergente para {name}.{column.name}")
        return self


def _spark_type(column_type) -> str:
    from sqlalchemy import (
        BigInteger,
        Boolean,
        Date,
        DateTime,
        Float,
        Integer,
        Numeric,
        Text,
    )

    if isinstance(column_type, Text):
        return "string"
    if isinstance(column_type, BigInteger):
        return "long"
    if isinstance(column_type, Integer):
        return "integer"
    if isinstance(column_type, Float):
        return "double"
    if isinstance(column_type, Numeric):
        return f"decimal({column_type.precision},{column_type.scale})"
    if isinstance(column_type, DateTime):
        return "timestamp"
    if isinstance(column_type, Date):
        return "date"
    if isinstance(column_type, Boolean):
        return "boolean"
    raise ValueError("tipo SQL não mapeado para o contrato Spark")


def read_export_manifest_v2(directory: Path) -> GoldManifestV2:
    """Lê somente o manifesto final da exportação analítica v2."""
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("diretório de exportação inválido")
    path = directory / "manifest.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifesto ausente ou inválido")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("campo duplicado no manifesto")
            result[key] = value
        return result

    payload = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    if not isinstance(payload, dict):
        raise TypeError("manifesto deve ser um objeto")
    manifest = GoldManifestV2.model_validate(payload)
    if manifest.schema_version != SCHEMA_VERSION:
        raise ValueError("versão de esquema incompatível")
    return manifest
