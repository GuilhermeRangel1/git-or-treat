"""Identidade da publicação e contrato do manifesto de origem Gold."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

SCHEMA_VERSION = "gold-csv-v1"
GoldRun = Annotated[str, StringConstraints(pattern=r"^GOLD_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}$", max_length=38)]
SourceRun = Annotated[str, StringConstraints(pattern=r"^[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}$", max_length=25)]


class GoldOrigin(BaseModel):
    """Campos de origem confiáveis apenas após a validação da carga."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ambiente: Literal["prod"]
    run_id: GoldRun
    run_id_silver: SourceRun
    lote_bronze_silver: SourceRun
    data_processamento: datetime
    schema_version: Literal["gold-csv-v1"]

    @field_validator("ambiente", mode="before")
    @classmethod
    def normalize_environment(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("data_processamento")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        # Exportador atual usa America/Recife sem offset. Compatibilidade explícita.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=-3)))
        return value.astimezone(timezone.utc)


class ExportManifest(GoldOrigin):
    lote: GoldRun
    tabelas_exportadas: list[str]
    data_exportacao_csv: datetime | None = None
    responsavel: str | None = None
    status_gold: Literal["CONCLUIDO"] | None = None

    @model_validator(mode="after")
    def same_lot(self):
        if self.lote != self.run_id:
            raise ValueError("lote e run_id devem coincidir")
        return self


class PublicationReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["gold-csv-v1"]
    run_id: GoldRun
    publication_id: UUID

    @field_validator("publication_id")
    @classmethod
    def publication_uuid4(cls, value: UUID) -> UUID:
        if value.version != 4:
            raise ValueError("publication_id deve ser UUID4")
        return value

    @property
    def batch_ref(self) -> str:
        return f"{self.schema_version}:{self.run_id}:{self.publication_id}"

    @classmethod
    def parse(cls, value: str) -> "PublicationReference":
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError("batch_ref inválido")
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError("batch_ref inválido")
        result = cls(schema_version=parts[0], run_id=parts[1], publication_id=parts[2])
        if result.batch_ref != value:
            raise ValueError("batch_ref não canônico")
        return result


def read_export_manifest(directory: Path, tables: set[str], schema_version: str | None) -> GoldOrigin:
    """Lê uma única origem; versão externa explícita adapta o exportador legado."""
    paths = [directory / "manifest.json", directory / "manifesto" / "manifest.json"]
    present = [p for p in paths if p.is_file()]
    if len(present) != 1:
        raise ValueError("Informe exatamente um manifesto de origem")
    path = present[0]
    if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("Manifesto inválido")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Campo repetido no manifesto")
            result[key] = value
        return result

    payload = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    if not isinstance(payload, dict):
        raise ValueError("Manifesto deve ser objeto")
    if schema_version is not None:
        if "schema_version" in payload and payload["schema_version"] != schema_version:
            raise ValueError("Versão divergente")
        payload["schema_version"] = schema_version
    manifest = ExportManifest.model_validate(payload)
    if len(manifest.tabelas_exportadas) != len(tables) or set(manifest.tabelas_exportadas) != tables:
        raise ValueError("Inventário incompatível")
    return GoldOrigin.model_validate(manifest.model_dump(include=set(GoldOrigin.model_fields)))
