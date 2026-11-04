"""Strict contract for the restricted holder-cadastro export package."""

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from app.schemas.gold_publication_v2 import CSV_FORMAT, MAX_MANIFEST_BYTES


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
    registros: StrictInt
    versao_delta: StrictInt
    spark_schema: SparkSchema = Field(alias="schema")


class CadastroManifest(StrictModel):
    schema_version: Literal["gold-cadastro-v1"]
    ambiente: Literal["prod"]
    restrito: Literal[True]
    finalidade: Literal["identificacao_titular_atendimento"]
    run_id: StrictStr
    run_id_silver: StrictStr
    lote_bronze_silver: StrictStr
    data_processamento_gold: datetime
    data_exportacao_csv: datetime
    status_gold: Literal["CONCLUIDO"]
    export_id: StrictStr
    analytic_export_id: StrictStr
    analytic_schema_version: Literal["gold-csv-v2"]
    tabelas_exportadas: list[StrictStr]
    controles_tabelas: dict[StrictStr, TableControl]
    formato_csv: dict[StrictStr, StrictStr]

    @model_validator(mode="after")
    def validate_manifest_contract(self):
        if self.run_id != self.run_id_silver and not self.run_id_silver:
            raise ValueError("linhagem Silver inválida")
        if self.data_processamento_gold.tzinfo is None or self.data_processamento_gold.utcoffset() is None:
            raise ValueError("processamento sem fuso")
        if self.data_exportacao_csv.tzinfo is None or self.data_exportacao_csv.utcoffset() is None:
            raise ValueError("exportação sem fuso")
        if self.tabelas_exportadas != ["cadastro_titular_uc"]:
            raise ValueError("inventário cadastral incompatível")
        if set(self.controles_tabelas) != {"cadastro_titular_uc"}:
            raise ValueError("controle cadastral incompatível")
        schema = self.controles_tabelas["cadastro_titular_uc"].spark_schema
        fields = [(field.name, field.type, field.nullable) for field in schema.fields]
        if fields != [
            ("id_uc", "string", True),
            ("nome_exibicao_titular", "string", True),
            ("situacao_identificacao", "string", True),
            ("data_processamento_gold", "timestamp", True),
        ]:
            raise ValueError("schema cadastral incompatível")
        if self.formato_csv != CSV_FORMAT:
            raise ValueError("formato CSV cadastral incompatível")
        return self


def read_cadastro_manifest(directory: Path) -> CadastroManifest:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("diretório cadastral inválido")
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifesto cadastral ausente ou inválido")

    def unique_keys(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("chave repetida no manifesto cadastral")
            data[key] = value
        return data

    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    return CadastroManifest.model_validate(payload)
