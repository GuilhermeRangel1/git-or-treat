"""Importação local explícita, atômica e sem payloads nos logs."""
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, Date, Float, Numeric, func, select, text
from sqlalchemy.engine import Engine

from app.models.gold_v1 import BATCH, TABLES


class GoldImportError(ValueError):
    """Erro público sem conteúdo das linhas ou mensagens SQL."""


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
        return date.fromisoformat(value)
    if column.name == "competencia" and not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
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


def import_gold(engine: Engine, directory: Path, batch_name: str) -> dict:
    """Substitui só as tabelas Gold; publica metadados após reconciliar."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", batch_name):
        raise GoldImportError("Identificador do lote inválido.")
    files = discover_files(directory)
    signature, hashes = fingerprint(files)
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(73460127)"))
        previous = connection.execute(select(BATCH)).mappings().first()
        if previous and previous["fingerprint"] == signature and previous["lote"] == batch_name:
            return {"status": "unchanged", "lote": batch_name, "tables": previous["manifesto"]}
        manifest = {}
        for name, table in TABLES.items():
            connection.execute(table.delete())
            count = 0
            rows = []
            totals = {field: Decimal(0) for field in table.c.keys() if field in {
                "consumo_kwh", "consumo_total_kwh", "receita_reais", "receita_total_reais",
            }}
            for row in _read_rows(files[name], table):
                count += 1
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
            manifest[name] = {"rows": count, "files": hashes[name], "totals": {k: str(v) for k, v in totals.items()}}
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
            id=1, lote=batch_name, fingerprint=signature,
            importado_em=datetime.now(timezone.utc), manifesto=manifest,
        ))
    return {"status": "loaded", "lote": batch_name, "tables": manifest}
