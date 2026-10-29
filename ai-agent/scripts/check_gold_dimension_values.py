"""Confere se os valores de dimensão declarados no perfil Gold existem nas colunas do lote.

Para cada valor declarado em ``GRID360_GOLD_PROFILE`` (municípios do case, classes do
dicionário e o Sim/Não de GD) e para cada tabela/coluna em que ``GRID360_GOLD_MAPPING`` lê
essa dimensão, o script procura o valor na coluna física em duas formas:

- ``PASS exato``: algum valor da coluna é igual ao declarado;
- ``PASS normalizado``: só existe igual sem diferenciar caixa, acento e espaços repetidos; o
  executor que filtrar por igualdade não encontrará o valor declarado;
- ``FAIL``: nenhuma das duas, ou tabela/coluna ausente ou ilegível.

Imprime apenas a dimensão, ``<tabela>.<coluna>``, o valor declarado (que vem do case ou do
catálogo) e o resultado. Nunca imprime outro valor da coluna, contagem ou linha. Sai com código
1 se houver FAIL.

Uso:
    python scripts/check_gold_dimension_values.py <diretório do lote>

Layout esperado: ``<dir>/<tabela>/*.csv``, separador ``;``, UTF-8 com ou sem BOM; nomes de
coluna comparados sem diferenciar maiúsculas de minúsculas, como em ``check_gold_dictionary``.
"""

import argparse
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE  # noqa: E402
from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING  # noqa: E402

csv.field_size_limit(10_000_000)

EXACT = "PASS exato"
NORMALIZED = "PASS normalizado"
FAIL = "FAIL"


@dataclass(frozen=True)
class ValueCheck:
    dimension_id: str
    table: str
    column: str
    declared: str
    result: str
    reason: str = ""

    def line(self) -> str:
        fields = (self.dimension_id, f"{self.table}.{self.column}", self.declared, self.result)
        return "\t".join((*fields, self.reason) if self.reason else fields)


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip()


def declared_values() -> dict[str, tuple[str, ...]]:
    """Dimensão -> valores canônicos declarados no perfil Gold."""

    return {
        dimension.id: tuple(value.value for value in dimension.values)
        for dimension in GRID360_GOLD_PROFILE.dimensions
        if dimension.values
    }


def physical_columns(dimension_id: str) -> list[tuple[str, str]]:
    """(tabela, coluna) em que o mapeamento lê a dimensão, sem repetição e em ordem estável."""

    columns: dict[tuple[str, str], None] = {}
    for metric in GRID360_GOLD_MAPPING.metrics:
        for source in metric.sources:
            column = source.dimension_columns.get(dimension_id)
            if column is not None:
                columns[(source.table.value, column)] = None
    return list(columns)


def column_values(folder: Path, column: str) -> tuple[set[str] | None, str]:
    """Valores distintos da coluna em todos os CSVs da pasta; só ficam em memória."""

    files = sorted(path for path in folder.glob("*.csv") if path.is_file())
    if not files:
        return None, "tabela ausente"
    values: set[str] = set()
    for path in files:
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter=";")
                header = [name.strip().casefold() for name in next(reader, [])]
                if column.casefold() not in header:
                    return None, "coluna ausente"
                index = header.index(column.casefold())
                values.update(row[index] for row in reader if index < len(row))
        except (OSError, UnicodeDecodeError, csv.Error):
            return None, "arquivo ilegível"
    return values, ""


def check_batch(base: Path) -> list[ValueCheck]:
    checks: list[ValueCheck] = []
    for dimension_id, declared in declared_values().items():
        for table, column in physical_columns(dimension_id):
            values, reason = column_values(base / table, column)
            normalized = {normalize(value) for value in values} if values is not None else set()
            for value in declared:
                if values is None:
                    result = FAIL
                elif value in values:
                    result = EXACT
                elif normalize(value) in normalized:
                    result = NORMALIZED
                else:
                    result = FAIL
                checks.append(ValueCheck(dimension_id, table, column, value, result, reason))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path, help="diretório do lote, com uma pasta por tabela")
    args = parser.parse_args(argv)
    if not args.data_dir.is_dir():
        parser.error(f"diretório não encontrado: {args.data_dir}")

    checks = check_batch(args.data_dir)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for check in checks:
        print(check.line())
    return 0 if all(check.result != FAIL for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
