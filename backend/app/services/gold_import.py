"""Importação local explícita, atômica e sem payloads nos logs."""
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Date, Float, Numeric, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.gold_load import ATTEMPTS, BATCH, SCHEMA_VERSION, TABLES


class GoldImportError(ValueError):
    """Erro público sem conteúdo das linhas ou mensagens SQL."""

    def __init__(self, message, code="validation_error", attempt_id=None):
        super().__init__(message)
        self.code = code
        self.attempt_id = attempt_id


def discover_files(directory: Path) -> dict[str, list[Path]]:
    result = {}
    for name in TABLES:
        folder = directory / name
        files = sorted(folder.glob("*.csv")) if folder.is_dir() else []
        if not files:
            raise GoldImportError(f"{name}: nenhum CSV encontrado na pasta da tabela.")
        result[name] = files
    return result


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


def _convert(value, column):
    if value == "":
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
    if isinstance(column.type, (Numeric, Float)):
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("número não finito")
        if isinstance(column.type, Float):
            converted = float(number)
            if not math.isfinite(converted):
                raise ValueError("número fora do intervalo")
            return converted
        if number != number.quantize(Decimal(1).scaleb(-column.type.scale)):
            raise ValueError("escala excedida")
        if abs(number) >= Decimal(10) ** (column.type.precision - column.type.scale):
            raise ValueError("precisão excedida")
        return number
    if isinstance(column.type, Date):
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("data fora do formato ISO")
        return date.fromisoformat(value)
    if not column.nullable and not value.strip():
        raise ValueError("chave vazia")
    if column.name == "competencia" and not re.fullmatch(r"(?!0000)[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("competência inválida")
    return value


def _read_rows(paths, table):
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";", strict=True)
            columns = [column.name for column in table.columns]
            if reader.fieldnames is None or len(reader.fieldnames) != len(columns) or set(reader.fieldnames) != set(columns):
                raise GoldImportError(f"{table.name}: cabeçalho incompatível com o contrato v1.")
            for index, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise GoldImportError(f"{table.name}: estrutura inválida no registro {index}.")
                try:
                    yield {column.name: _convert(row[column.name], column) for column in table.columns}
                except (ValueError, InvalidOperation):
                    raise GoldImportError(f"{table.name}: tipo ou chave inválida no registro {index}.") from None


def _finish_attempt(connection, attempt_id, status, manifest, signature, error=None):
    result = connection.execute(ATTEMPTS.update().where(
        ATTEMPTS.c.id == attempt_id, ATTEMPTS.c.status == "running",
    ).values(
        status=status, finalizado_em=datetime.now(timezone.utc), fingerprint=signature,
        manifesto=json.loads(json.dumps(manifest, default=str)),
        erro_codigo=error.code if error else None,
        erro_mensagem=str(error) if error else None,
    ))
    if result.rowcount != 1:
        raise GoldImportError("Estado da tentativa não permite finalização; confira o lote publicado.", "audit_unavailable")


def import_gold(engine: Engine, directory: Path, batch_name: str, schema_version: str = SCHEMA_VERSION) -> dict:
    """Audita a tentativa; sucesso é confirmado na mesma transação da publicação."""
    attempt_id = str(uuid4())
    batch_valid = isinstance(batch_name, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", batch_name)
    version_valid = isinstance(schema_version, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", schema_version)
    try:
        with engine.begin() as connection:
            connection.execute(ATTEMPTS.insert().values(
                id=attempt_id, lote=batch_name if batch_valid else None,
                schema_version=schema_version if version_valid else None,
                status="running", iniciado_em=datetime.now(timezone.utc), manifesto={},
            ))
    except SQLAlchemyError:
        raise GoldImportError(
            "Não foi possível registrar a tentativa. Confira conexão e migrações; publicação não iniciada.",
            "audit_unavailable", attempt_id,
        ) from None
    manifest = {}
    signature = None
    try:
        if not batch_valid:
            raise GoldImportError("Identificador do lote inválido.", "invalid_batch")
        if schema_version != SCHEMA_VERSION:
            raise GoldImportError("Versão do esquema não suportada.", "unsupported_schema")
        files = discover_files(directory)
        signature, hashes = fingerprint(files)
        return _publish(engine, directory, batch_name, files, signature, hashes, attempt_id, manifest)
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, GoldImportError):
            public = error
        elif isinstance(error, IntegrityError):
            public = GoldImportError("Chave duplicada ou restrição do banco violada.", "constraint_error")
        elif isinstance(error, SQLAlchemyError):
            public = GoldImportError("Falha de persistência; confira conexão e migrações.", "database_error")
        elif isinstance(error, (OSError, UnicodeError, csv.Error)):
            public = GoldImportError("Falha de leitura ou formato CSV; confira os arquivos.", "file_error")
        elif isinstance(error, KeyboardInterrupt):
            public = GoldImportError("Carga interrompida pelo operador.", "interrupted")
        else:
            public = GoldImportError("Falha inesperada na carga; confira a execução.", "unexpected_error")
        public.attempt_id = attempt_id
        # O contexto da publicação já encerrou; nunca sobrescrever sucesso confirmado.
        try:
            with engine.begin() as connection:
                _finish_attempt(connection, attempt_id, "failed", manifest, signature, public)
        except (SQLAlchemyError, GoldImportError):
            raise GoldImportError(
                "Falha ao finalizar a auditoria. Confira o lote publicado antes de repetir a carga.",
                "audit_unavailable", attempt_id,
            ) from None
        raise public from None


def _publish(engine, directory, batch_name, files, signature, hashes, attempt_id, manifest):
    """Substitui só as tabelas Gold; publica metadados após reconciliar."""
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(73460127)"))
        previous = connection.execute(select(BATCH)).mappings().first()
        if (previous and previous["fingerprint"] == signature and previous["lote"] == batch_name
                and previous["schema_version"] == SCHEMA_VERSION):
            _finish_attempt(connection, attempt_id, "unchanged", previous["manifesto"], signature)
            return {"status": "unchanged", "lote": batch_name, "schema_version": SCHEMA_VERSION,
                    "attempt_id": attempt_id, "tables": previous["manifesto"]}
        for name, table in TABLES.items():
            connection.execute(table.delete())
            count = 0
            rows = []
            totals = {field: Decimal(0) for field in table.c.keys() if field in {
                "consumo_kwh", "consumo_total_kwh", "receita_reais", "receita_total_reais",
            }}
            progress = {"rows": 0, "files": hashes[name], "totals": totals, "validated": False}
            manifest[name] = progress
            for row in _read_rows(files[name], table):
                count += 1
                progress["rows"] = count
                for field in totals:
                    if row[field] is not None:
                        totals[field] += Decimal(str(row[field]))
                rows.append(row)
                if len(rows) == 1000:
                    connection.execute(table.insert(), rows)
                    rows = []
            if rows:
                connection.execute(table.insert(), rows)
            if not count:
                raise GoldImportError(f"{name}: tabela vazia.")
            observed = connection.scalar(select(func.count()).select_from(table))
            if observed != count:
                raise GoldImportError(f"{name}: contagem divergente após a carga.")
            for field, expected in totals.items():
                actual = connection.scalar(select(func.sum(table.c[field])))
                if actual is None or abs(Decimal(str(actual)) - expected) > Decimal("0.0001"):
                    raise GoldImportError(f"{name}: soma divergente após a carga ({field}).")
            manifest[name] = {"rows": count, "files": hashes[name], "totals": {k: str(v) for k, v in totals.items()}, "validated": True}
        reference = manifest["diagnostico_receita"]["totals"]
        for name, energy, revenue in (
            ("consumo_receita_bairro", "consumo_total_kwh", "receita_total_reais"),
            ("consumo_mensal_uc", "consumo_kwh", "receita_reais"),
        ):
            totals = manifest[name]["totals"]
            if any(Decimal(totals[left]) != Decimal(reference[right]) for left, right in (
                (energy, "consumo_total_kwh"), (revenue, "receita_total_reais"),
            )):
                raise GoldImportError("As tabelas financeiras não reconciliam entre si.")
        if fingerprint(discover_files(directory))[0] != signature:
            raise GoldImportError("Os arquivos mudaram durante a carga; lote revertido.")
        connection.execute(BATCH.delete())
        connection.execute(BATCH.insert().values(
            id=1, lote=batch_name, fingerprint=signature, schema_version=SCHEMA_VERSION,
            importado_em=datetime.now(timezone.utc), manifesto=manifest,
        ))
        _finish_attempt(connection, attempt_id, "loaded", manifest, signature)
    return {"status": "loaded", "lote": batch_name, "schema_version": SCHEMA_VERSION,
            "attempt_id": attempt_id, "tables": manifest}
