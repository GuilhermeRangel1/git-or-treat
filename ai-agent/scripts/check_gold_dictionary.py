"""Confere os cabeçalhos e os tipos de um lote Gold em CSV contra ``dictionary_gold.toml``.

O script lê o lote em modo somente leitura e imprime apenas nome de tabela, nome de coluna e
``PASS``/``FAIL`` com um motivo curto (tabela ausente, coluna ausente, coluna extra, coluna
repetida, cabeçalhos diferentes, tipo incompatível, arquivo ilegível). Nunca imprime valor de
célula, linha ou contagem de linhas.

Uso:
    python scripts/check_gold_dictionary.py <diretório do lote> [--dictionary <toml>]
                                            [--sample-rows N]

Layout esperado: ``<dir>/<tabela>/*.csv`` (uma pasta por tabela, um ou mais arquivos ``part-*``
do Spark com o mesmo cabeçalho), separador ``;``, UTF-8 com ou sem BOM, cabeçalho
possivelmente entre aspas. Arquivos sem extensão ``.csv``, como ``_SUCCESS``, são ignorados.

Nomes de coluna são comparados sem diferenciar maiúsculas de minúsculas: o CSV traz ``DEC`` e
``FEC``, e o dicionário só aceita identificadores em minúsculas (``dec``, ``fec``). Isso não
garante que o banco aceite a mesma grafia; ver a seção "Pontos abertos" de
``app/sql/README.md``.

A conferência de tipo é grosseira e usa no máximo ``--sample-rows`` linhas de dados por tabela:
inteiro cabe em ``bigint``, ``double`` e ``decimal``; número com ponto decimal cabe em
``double`` e ``decimal``; ``date`` exige ``AAAA-MM-DD``; ``boolean`` exige ``true``/``false``;
``text`` aceita qualquer valor. Campo vazio é nulo e não conta. Sai com código 1 se houver FAIL.
"""

import argparse
import csv
import math
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_DICTIONARY = Path(__file__).resolve().parents[1] / "app" / "sql" / "dictionary_gold.toml"
DEFAULT_SAMPLE_ROWS = 50
MAX_SAMPLE_ROWS = 1000

csv.field_size_limit(10_000_000)

_INTEGER = re.compile(r"^[+-]?\d+$")
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BOOLEANS = {"true", "false"}

# Tipo do dicionário -> classes de valor aceitas. "text" aceita qualquer classe.
_ACCEPTED = {
    "bigint": {"inteiro"},
    "int": {"inteiro"},
    "smallint": {"inteiro"},
    "double": {"inteiro", "número"},
    "float": {"inteiro", "número"},
    "decimal": {"inteiro", "número"},
    "date": {"data"},
    "boolean": {"booleano"},
}
_TEXT_TYPES = {"text", "varchar"}


@dataclass(frozen=True)
class Check:
    table: str
    column: str
    passed: bool
    reason: str = ""

    def line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return "\t".join(filter(None, (self.table, self.column, status, self.reason)))


def load_tables(dictionary_path: Path) -> dict[str, dict[str, str]]:
    """Tabela -> {coluna: tipo} das ``[tables.<nome>.columns]`` do dicionário."""

    raw = tomllib.loads(dictionary_path.read_text(encoding="utf-8"))
    return {name: dict(spec["columns"]) for name, spec in raw["tables"].items()}


def value_kind(value: str) -> str:
    """Classe grosseira de um valor não vazio; nunca devolve o próprio valor."""

    if value.casefold() in _BOOLEANS:
        return "booleano"
    if _INTEGER.match(value):
        return "inteiro"
    if _NUMBER.match(value) and math.isfinite(float(value)):
        return "número"
    if _DATE.match(value):
        try:
            date.fromisoformat(value)
        except ValueError:
            return "texto"
        return "data"
    return "texto"


def _base_type(column_type: str) -> str:
    return column_type.split("(", 1)[0].strip().casefold()


def check_table(
    folder: Path, table: str, columns: dict[str, str], sample_rows: int
) -> list[Check]:
    files = sorted(path for path in folder.glob("*.csv") if path.is_file())
    if not files:
        return [Check(table, "-", False, "tabela ausente")]

    header: list[str] | None = None
    samples: list[list[str]] = []
    for path in files:
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter=";")
                file_header = [name.strip() for name in next(reader, [])]
                if header is None:
                    header = file_header
                elif [n.casefold() for n in file_header] != [n.casefold() for n in header]:
                    return [Check(table, "-", False, "cabeçalhos diferentes entre arquivos")]
                for row in reader:
                    if len(samples) >= sample_rows:
                        break
                    samples.append(row)
        except (OSError, UnicodeDecodeError, csv.Error):
            return [Check(table, "-", False, "arquivo ilegível")]

    if not header or not any(header):
        return [Check(table, "-", False, "cabeçalho vazio")]
    positions: dict[str, int] = {}
    checks: list[Check] = []
    for index, name in enumerate(header):
        key = name.casefold()
        if key in positions:
            checks.append(Check(table, name, False, "coluna repetida"))
            continue
        positions[key] = index

    expected = {column.casefold(): column_type for column, column_type in columns.items()}
    for column, column_type in columns.items():
        index = positions.get(column.casefold())
        if index is None:
            checks.append(Check(table, column, False, "coluna ausente"))
            continue
        checks.append(_check_type(table, column, column_type, samples, index))
    for key, index in positions.items():
        if key not in expected:
            checks.append(Check(table, header[index], False, "coluna extra"))
    return checks


def _check_type(
    table: str, column: str, column_type: str, samples: list[list[str]], index: int
) -> Check:
    base = _base_type(column_type)
    if base in _TEXT_TYPES:
        return Check(table, column, True)
    accepted = _ACCEPTED.get(base)
    if accepted is None:
        return Check(table, column, False, f"tipo do dicionário não reconhecido ({column_type})")
    for row in samples:
        if index >= len(row) or not row[index].strip():
            continue
        kind = value_kind(row[index].strip())
        if kind not in accepted:
            return Check(
                table, column, False, f"tipo incompatível: esperado {column_type}, há {kind}"
            )
    return Check(table, column, True)


def check_batch(base: Path, dictionary_path: Path, sample_rows: int) -> list[Check]:
    checks: list[Check] = []
    for table, columns in load_tables(dictionary_path).items():
        checks.extend(check_table(base / table, table, columns, sample_rows))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path, help="diretório do lote, com uma pasta por tabela")
    parser.add_argument(
        "--dictionary", type=Path, default=DEFAULT_DICTIONARY, help="dicionário TOML da Gold"
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=DEFAULT_SAMPLE_ROWS,
        help=f"linhas lidas por tabela para inferir tipo (1 a {MAX_SAMPLE_ROWS})",
    )
    args = parser.parse_args(argv)
    if not args.data_dir.is_dir():
        parser.error(f"diretório não encontrado: {args.data_dir}")
    if not args.dictionary.is_file():
        parser.error(f"dicionário não encontrado: {args.dictionary}")
    if not 1 <= args.sample_rows <= MAX_SAMPLE_ROWS:
        parser.error(f"--sample-rows precisa estar entre 1 e {MAX_SAMPLE_ROWS}")

    checks = check_batch(args.data_dir, args.dictionary, args.sample_rows)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for check in checks:
        print(check.line())
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
