"""Validation and row parsing for the separated restricted-cadastro package."""

import csv
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from app.models.gold_cadastro import CADASTRO_TITULAR_UC
from app.schemas.gold_cadastro import CadastroManifest, read_cadastro_manifest
from app.schemas.gold_publication_v2 import GoldManifestV2
from app.services.gold_import import GoldImportError


class GoldCadastroImportError(GoldImportError):
    """Sanitized cadastral import failure."""


def validate_pair(cadastro: CadastroManifest, analytic: GoldManifestV2) -> None:
    if (
        cadastro.run_id != analytic.run_id
        or cadastro.run_id_silver != analytic.run_id_silver
        or cadastro.lote_bronze_silver != analytic.lote_bronze_silver
        or cadastro.data_processamento_gold != analytic.data_processamento_gold
        or cadastro.export_id != analytic.cadastro_export_id
        or cadastro.analytic_export_id != analytic.export_id
        or analytic.cadastro_schema_version != cadastro.schema_version
    ):
        raise GoldCadastroImportError(
            "Manifestos cadastral e analítico não pertencem à mesma publicação.",
            "publication_mismatch",
        )


def discover_files(directory: Path) -> tuple[CadastroManifest, list[Path]]:
    try:
        manifest = read_cadastro_manifest(directory)
    except Exception:
        raise GoldCadastroImportError("Manifesto cadastral inválido.", "invalid_manifest") from None
    entries = list(Path(directory).iterdir())
    if any(item.is_symlink() or not item.is_file() for item in entries if item.name != "manifest.json"):
        raise GoldCadastroImportError("Inventário cadastral contém itens inválidos.", "invalid_files")
    if {item.name for item in entries if item.name != "manifest.json"} == set():
        raise GoldCadastroImportError("Arquivos CSV cadastrais ausentes.", "invalid_files")
    paths = sorted(
        (item for item in entries if item.name != "manifest.json" and item.suffix.lower() == ".csv"),
        key=lambda item: item.name,
    )
    if len(paths) != len([item for item in entries if item.name != "manifest.json"]):
        raise GoldCadastroImportError("Inventário cadastral contém arquivos fora do contrato.", "invalid_files")
    return manifest, paths


def fingerprint(paths: list[Path]) -> list[dict[str, str]]:
    output = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        output.append({"file": path.name, "sha256": digest.hexdigest()})
    return output


def read_rows(paths: list[Path], manifest: CadastroManifest):
    table = CADASTRO_TITULAR_UC
    expected_columns = ["id_uc", "nome_exibicao_titular", "situacao_identificacao", "data_processamento_gold"]
    seen_ids: set[str] = set()
    count = 0
    package_timestamp: datetime | None = None
    for path in paths:
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, delimiter=";", strict=True, doublequote=True)
                if reader.fieldnames != expected_columns:
                    raise ValueError
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError
                    uc_id, name, status, processed = (row[key] for key in expected_columns)
                    if uc_id in {"", r"\N"} or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", uc_id, flags=re.ASCII):
                        raise ValueError
                    if uc_id in seen_ids:
                        raise GoldCadastroImportError("Identificador UC duplicado no cadastro.", "duplicate_key")
                    seen_ids.add(uc_id)
                    if status not in {"DISPONIVEL", "AUSENTE_NA_ORIGEM", "CONFLITO_NA_ORIGEM"}:
                        raise ValueError
                    name = None if name == r"\N" else name
                    if status == "DISPONIVEL" and (name is None or name == ""):
                        raise ValueError
                    if status != "DISPONIVEL" and name is not None:
                        raise ValueError
                    if not re.fullmatch(r"\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)", processed):
                        raise ValueError
                    timestamp = datetime.fromisoformat(processed.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        raise ValueError
                    timestamp = timestamp.astimezone(UTC)
                    if package_timestamp is None:
                        package_timestamp = timestamp
                    elif timestamp != package_timestamp:
                        raise GoldCadastroImportError(
                            "Timestamps cadastrais divergem entre registros.",
                            "timestamp_mismatch",
                        )
                    count += 1
                    yield {
                        "run_id": manifest.run_id,
                        "analytic_export_id": manifest.analytic_export_id,
                        "cadastro_export_id": manifest.export_id,
                        "id_uc": uc_id,
                        "nome_exibicao_titular": name,
                        "situacao_identificacao": status,
                        "data_processamento_gold": timestamp,
                    }
        except GoldCadastroImportError:
            raise
        except (OSError, UnicodeError, csv.Error, ValueError):
            raise GoldCadastroImportError("CSV cadastral incompatível com o manifesto.", "invalid_csv") from None
    if count != manifest.controles_tabelas["cadastro_titular_uc"].registros:
        raise GoldCadastroImportError("Contagem do cadastro diverge do manifesto.", "row_count_mismatch")
