"""Carga local transacional das quinze tabelas analíticas Gold CSV v2."""
import csv
import hashlib
import json
import math
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    func,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.gold_v2 import SCHEMA as DATA_SCHEMA
from app.models.gold_v2_load import ATTEMPTS, BATCH, SCHEMA_VERSION, TABLES
from app.schemas.gold_publication import PublicationReference
from app.schemas.gold_publication_v2 import GoldManifestV2, read_export_manifest_v2
from app.services.gold_import import GoldImportError, _finish_attempt

GOLD_RUN_PATTERN = re.compile(r"GOLD_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}")
BATCH_SIZE = 1000
RECONCILED_TOTALS = {
    "diagnostico_receita": {
        "receita_total_reais": "receita_reais",
        "receita_com_leitura_reais": "receita_com_leitura_reais",
        "receita_sem_leitura_reais": "receita_sem_leitura_reais",
        "consumo_total_kwh": "consumo_kwh",
        "receita_base_comparavel_reais": "receita_base_comparavel_reais",
        "consumo_base_comparavel_kwh": "consumo_base_comparavel_kwh",
    },
    "consumo_receita_bairro": {
        "receita_total_reais": "receita_reais",
        "receita_com_leitura_reais": "receita_com_leitura_reais",
        "receita_sem_leitura_reais": "receita_sem_leitura_reais",
        "consumo_total_kwh": "consumo_kwh",
        "receita_base_comparavel_reais": "receita_base_comparavel_reais",
        "consumo_base_comparavel_kwh": "consumo_base_comparavel_kwh",
    },
}
class GoldV2ImportError(GoldImportError):
    """Erro de importação v2 sem valores das linhas nem SQL interno."""


def _validate_package_shape(directory: Path) -> None:
    expected = {"manifest.json", *TABLES}
    actual = {entry.name for entry in directory.iterdir()}
    if actual != expected:
        raise GoldV2ImportError("Inventário de arquivos v2 incompleto ou contém itens fora do contrato.", "invalid_files")
    for name in TABLES:
        folder = directory / name
        if folder.is_symlink() or not folder.is_dir():
            raise GoldV2ImportError(f"{name}: pasta ausente ou inválida.", "invalid_files")
        entries = list(folder.iterdir())
        if not entries or any(
            item.is_symlink() or not item.is_file() or item.suffix.lower() != ".csv"
            for item in entries
        ):
            raise GoldV2ImportError(f"{name}: partes CSV ausentes ou inválidas.", "invalid_files")


def discover_files(directory: Path) -> dict[str, list[Path]]:
    _validate_package_shape(directory)
    return {
        name: sorted((directory / name).glob("*.csv"), key=lambda path: path.name)
        for name in TABLES
    }


def fingerprint(files: dict[str, list[Path]]) -> tuple[str, dict]:
    hashes = {}
    for name, paths in files.items():
        hashes[name] = []
        for path in paths:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            hashes[name].append({"file": path.name, "sha256": digest.hexdigest()})
    signature = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return signature, hashes


def _convert(value: str, column):
    if value == r"\N":
        if not column.nullable:
            raise ValueError("chave nula")
        return None
    if isinstance(column.type, Boolean):
        if value not in {"true", "false"}:
            raise ValueError("booleano inválido")
        return value == "true"
    if isinstance(column.type, BigInteger):
        if not re.fullmatch(r"-?[0-9]+", value):
            raise ValueError("inteiro inválido")
        number = int(value)
        if not -(2**63) <= number < 2**63:
            raise ValueError("inteiro fora do intervalo")
        return number
    if isinstance(column.type, Integer):
        if not re.fullmatch(r"-?[0-9]+", value):
            raise ValueError("inteiro inválido")
        number = int(value)
        if not -(2**31) <= number < 2**31:
            raise ValueError("inteiro fora do intervalo")
        return number
    if isinstance(column.type, (Numeric, Float)):
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("número não finito")
        if isinstance(column.type, Float):
            converted = float(number)
            if not math.isfinite(converted):
                raise ValueError("número fora do intervalo")
            return converted
        with localcontext() as context:
            context.prec = max(column.type.precision + 1, len(number.as_tuple().digits) + abs(column.type.scale) + 2)
            quantum = Decimal((0, (1,), -column.type.scale))
            quantized = number.quantize(quantum)
        if number != quantized:
            raise ValueError("escala excedida")
        limit = Decimal((0, (1,), column.type.precision - column.type.scale))
        if number.copy_abs() >= limit:
            raise ValueError("precisão excedida")
        return number
    if isinstance(column.type, DateTime):
        if "T" not in value:
            raise ValueError("timestamp fora do formato ISO")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp sem offset")
        return parsed.astimezone(UTC)
    if isinstance(column.type, Date):
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("data fora do formato ISO")
        return date.fromisoformat(value)
    if column.name == "competencia" and not re.fullmatch(r"(?!0000)[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("competência inválida")
    if not column.nullable and not value.strip():
        raise ValueError("chave vazia")
    return value


def _read_rows(paths: list[Path], table, expected_rows: int):
    columns = [column.name for column in table.columns]
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";", strict=True)
            if (
                reader.fieldnames is None
                or len(reader.fieldnames) != len(columns)
                or len(set(reader.fieldnames)) != len(reader.fieldnames)
                or set(reader.fieldnames) != set(columns)
            ):
                raise GoldV2ImportError(f"{table.name}: cabeçalho incompatível com o contrato v2.", "invalid_schema")
            for index, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise GoldV2ImportError(f"{table.name}: estrutura inválida na linha {index}.", "invalid_csv")
                try:
                    yield {column.name: _convert(row[column.name], column) for column in table.columns}
                except (ValueError, InvalidOperation, OverflowError):
                    raise GoldV2ImportError(f"{table.name}: tipo, chave ou valor incompatível na linha {index}.", "invalid_value") from None


def _add_total(current: Decimal | None, value) -> Decimal | None:
    if value is None:
        return current
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise GoldV2ImportError("Valor numérico não finito.", "invalid_value")
    if current is None:
        return amount
    least_exponent = min(current.as_tuple().exponent, amount.as_tuple().exponent)
    greatest_adjusted = max(current.adjusted() if current else 0, amount.adjusted() if amount else 0)
    with localcontext() as context:
        context.prec = max(1, greatest_adjusted - least_exponent + 2)
        return current + amount


def _sum_matches(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    return (Decimal(str(actual)) - Decimal(str(expected))).copy_abs() <= Decimal("0.0001")


def _validate_financial_totals(manifest: dict) -> None:
    monthly = manifest["consumo_mensal_uc"]["totals"]
    for table_name, field_map in RECONCILED_TOTALS.items():
        observed = manifest[table_name]["totals"]
        for field, monthly_field in field_map.items():
            if not _sum_matches(observed[field], monthly[monthly_field]):
                raise GoldV2ImportError("Totais financeiros das projeções não reconciliam.", "reconciliation_error")
    # Componentes do faturamento preservam nulo quando não há fatura e somam o total.
    for table_name, total_field in (
        ("diagnostico_receita", "receita_total_reais"),
        ("consumo_receita_bairro", "receita_total_reais"),
        ("consumo_mensal_uc", "receita_reais"),
    ):
        totals = manifest[table_name]["totals"]
        components = (totals["receita_com_leitura_reais"], totals["receita_sem_leitura_reais"])
        if (components[0] is None) != (components[1] is None):
            raise GoldV2ImportError("Parcelas de faturamento incompletas.", "reconciliation_error")
        expected = Decimal(components[0]) + Decimal(components[1]) if components[0] is not None else None
        if not _sum_matches(totals[total_field], expected):
            raise GoldV2ImportError("Parcelas de faturamento não reconciliam com o total.", "reconciliation_error")


def import_gold_v2(engine: Engine, directory: Path, batch_name: str | None = None) -> dict:
    """Valida e publica apenas o pacote analítico; cadastro restrito não é importado."""
    directory = Path(directory)
    attempt_id = str(uuid4())
    if engine.dialect.name == "sqlite":
        engine = engine.execution_options(schema_translate_map={"gold": None, DATA_SCHEMA: None})
    batch_valid = isinstance(batch_name, str) and GOLD_RUN_PATTERN.fullmatch(batch_name)
    try:
        with engine.begin() as connection:
            connection.execute(ATTEMPTS.insert().values(
                id=attempt_id, lote=batch_name if batch_valid else None, schema_version=SCHEMA_VERSION,
                status="running", iniciado_em=datetime.now(UTC), manifesto={},
            ))
    except SQLAlchemyError:
        raise GoldV2ImportError(
            "Não foi possível registrar a tentativa. Confira conexão e migrações; publicação não iniciada.",
            "audit_unavailable", attempt_id,
        ) from None

    origin = None
    manifest = {}
    signature = None
    try:
        if batch_name is not None and not batch_valid:
            raise GoldV2ImportError("Identificador do lote inválido.", "invalid_batch")
        source = read_export_manifest_v2(directory)
        if batch_name is not None and batch_name != source.run_id:
            raise GoldV2ImportError("Identificador informado diverge do manifesto.", "invalid_batch")
        origin = source.model_dump(mode="json", by_alias=True)
        files = discover_files(directory)
        signature, hashes = fingerprint(files)
        return _publish(engine, directory, source, origin, files, hashes, signature, attempt_id, manifest)
    except KeyboardInterrupt as error:
        _record_failed_attempt(engine, attempt_id, manifest, signature, origin, error)
    except Exception as error:  # noqa: BLE001 - sanitiza falhas inesperadas e fecha a auditoria da carga.
        _record_failed_attempt(engine, attempt_id, manifest, signature, origin, error)


def _record_failed_attempt(engine, attempt_id, manifest, signature, origin, error) -> None:
    if isinstance(error, GoldImportError):
        public = error
    elif isinstance(error, (ValidationError, ValueError, KeyError, TypeError)):
        public = GoldV2ImportError("Manifesto ou dados incompatíveis com o contrato Gold v2.", "invalid_manifest")
    elif isinstance(error, IntegrityError):
        public = GoldV2ImportError("Chave duplicada ou restrição do banco violada.", "constraint_error")
    elif isinstance(error, SQLAlchemyError):
        public = GoldV2ImportError("Falha de persistência; confira conexão e migrações.", "database_error")
    elif isinstance(error, (OSError, UnicodeError, csv.Error)):
        public = GoldV2ImportError("Falha de leitura ou formato CSV; confira os arquivos.", "file_error")
    elif isinstance(error, KeyboardInterrupt):
        public = GoldV2ImportError("Carga interrompida pelo operador.", "interrupted")
    else:
        public = GoldV2ImportError("Falha inesperada na carga; confira a execução.", "unexpected_error")
    public.attempt_id = attempt_id
    try:
        with engine.begin() as connection:
            _finish_attempt(connection, attempt_id, "failed", manifest, signature, public, origin)
    except (SQLAlchemyError, GoldImportError):
        raise GoldV2ImportError(
            "Falha ao finalizar a auditoria. Confira a publicação antes de repetir a carga.",
            "audit_unavailable", attempt_id,
        ) from None
    raise public from None


def _coverage_windows(connection) -> list[dict]:
    """Metadados observados; não certifica a origem nem promove um mês a fechado."""
    columns = TABLES["cobertura_dominios"].c
    groups = connection.execute(select(
        columns.dominio, columns.recorte, columns.estado_cobertura,
        func.min(columns.competencia).label("start"),
        func.max(columns.competencia).label("end"),
        func.count().label("rows"),
    ).group_by(columns.dominio, columns.recorte, columns.estado_cobertura)
      .order_by(columns.dominio, columns.recorte, columns.estado_cobertura)).mappings()
    windows = {}
    for row in groups:
        key = (row["dominio"], row["recorte"])
        if key not in windows:
            windows[key] = {"domain":key[0], "scope":key[1], "start":row["start"],
                "end":row["end"], "rows":0, "states":{}, "is_certification":False}
        item = windows[key]
        item["start"] = min(item["start"], row["start"])
        item["end"] = max(item["end"], row["end"])
        item["rows"] += row["rows"]
        item["states"][row["estado_cobertura"] or "NAO_INFORMADO"] = row["rows"]
    return list(windows.values())


def _publish(engine, directory, source: GoldManifestV2, origin, files, hashes, signature, attempt_id, manifest):
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(73460127)"))
        previous = connection.execute(select(BATCH)).mappings().first()
        if (
            previous
            and previous["fingerprint"] == signature
            and previous["lote"] == source.run_id
            and previous["schema_version"] == SCHEMA_VERSION
            and previous["origem"] == origin
            and previous["publication_id"]
        ):
            if read_export_manifest_v2(directory).model_dump(mode="json", by_alias=True) != origin or fingerprint(discover_files(directory))[0] != signature:
                raise GoldV2ImportError("Os arquivos mudaram durante a carga; lote revertido.", "changed_during_import")
            reference = PublicationReference(schema_version=SCHEMA_VERSION, run_id=source.run_id, publication_id=previous["publication_id"])
            previous_manifest = previous["manifesto"]
            _finish_attempt(connection, attempt_id, "unchanged", previous_manifest, signature, origin=origin, publication_id=previous["publication_id"])
            return {
                "status": "unchanged", "schema_version": SCHEMA_VERSION, "lote": source.run_id,
                "publication_id": previous["publication_id"], "batch_ref": reference.batch_ref,
                "attempt_id": attempt_id, "scope": "analytical_only", "complete_delivery": False,
                "cadastro_status": "not_imported",
                "cadastro_export_id": source.cadastro_export_id,
                "restricted_cadastro": previous_manifest["restricted_cadastro"],
                "tables": previous_manifest["tables"],
            }

        for name, table in TABLES.items():
            control = source.controles_tabelas[name]
            connection.execute(table.delete())
            count = 0
            rows = []
            total_fields = tuple(table.c.keys()) if name in {"diagnostico_receita", "consumo_receita_bairro", "consumo_mensal_uc"} else ()
            totals = {field: None for field in total_fields if isinstance(table.c[field].type, (Numeric, Float))}
            present_counts = dict.fromkeys(totals, 0)
            progress = {"rows": 0, "expected_rows": control.registros, "files": hashes[name], "totals": {}, "validated": False}
            manifest[name] = progress
            for row in _read_rows(files[name], table, control.registros):
                count += 1
                if count > control.registros:
                    raise GoldV2ImportError(f"{name}: quantidade de registros excede o manifesto.", "row_count_mismatch")
                progress["rows"] = count
                for field, total in totals.items():
                    if row[field] is not None:
                        totals[field] = _add_total(total, row[field])
                        present_counts[field] += 1
                rows.append(row)
                if len(rows) == BATCH_SIZE:
                    connection.execute(table.insert(), rows)
                    rows.clear()
            if rows:
                connection.execute(table.insert(), rows)
            if count != control.registros:
                raise GoldV2ImportError(f"{name}: quantidade de registros diverge do manifesto.", "row_count_mismatch")
            observed = connection.scalar(select(func.count()).select_from(table))
            if observed != count:
                raise GoldV2ImportError(f"{name}: contagem divergente após a carga.", "row_count_mismatch")
            manifest[name] = {
                "rows": count,
                "expected_rows": control.registros,
                "delta_version": control.versao_delta,
                "files": hashes[name],
                "totals": {key: str(value) if value is not None else None for key, value in totals.items()},
                "present_counts": present_counts,
                "validated": True,
            }
        _validate_financial_totals(manifest)
        if fingerprint(discover_files(directory))[0] != signature or read_export_manifest_v2(directory).model_dump(mode="json", by_alias=True) != origin:
            raise GoldV2ImportError("Os arquivos mudaram durante a carga; lote revertido.", "changed_during_import")

        publication_id = str(uuid4())
        reference = PublicationReference(schema_version=SCHEMA_VERSION, run_id=source.run_id, publication_id=publication_id)
        publication_manifest = {
            "schema_version": SCHEMA_VERSION,
            "scope": "analytical_only",
            "complete_delivery": False,
            "tables": manifest,
            "coverage_windows": _coverage_windows(connection),
            "restricted_cadastro": {
                "status": "not_imported",
                "export_id": source.cadastro_export_id,
                "schema_version": source.cadastro_schema_version,
                "available_to_genai": False,
            },
        }
        connection.execute(BATCH.delete())
        connection.execute(BATCH.insert().values(
            id=1, lote=source.run_id, fingerprint=signature, schema_version=SCHEMA_VERSION,
            importado_em=datetime.now(UTC), manifesto=publication_manifest,
            publication_id=publication_id, origem=origin,
        ))
        _finish_attempt(connection, attempt_id, "loaded", publication_manifest, signature, origin=origin, publication_id=publication_id)
    return {
        "status": "loaded", "schema_version": SCHEMA_VERSION, "lote": source.run_id,
        "publication_id": publication_id, "batch_ref": reference.batch_ref,
        "attempt_id": attempt_id, "scope": "analytical_only", "complete_delivery": False,
        "cadastro_status": "not_imported",
        "cadastro_export_id": source.cadastro_export_id, "tables": manifest,
    }
