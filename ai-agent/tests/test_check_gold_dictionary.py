"""Conferência local de lote Gold contra o dicionário, com CSVs sintéticos em pasta temporária."""

import csv
import importlib.util
from pathlib import Path

import pytest

from tests.gold_mock import GOLD_ROWS, load_gold_metadata, load_gold_snapshot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_gold_dictionary.py"
_spec = importlib.util.spec_from_file_location("check_gold_dictionary", SCRIPT)
check_gold_dictionary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_gold_dictionary)

SNAPSHOT = load_gold_snapshot()["tables"]
SECRET = "VALOR-SINTETICO-QUE-NAO-PODE-VAZAR"


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_table(
    base: Path,
    table: str,
    header: list[str],
    rows: list[list[str]],
    *,
    encoding: str = "utf-8",
    quote_all: bool = False,
    name: str = "part-00000.csv",
) -> None:
    folder = base / table
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(
            handle,
            delimiter=";",
            quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writerow(header)
        writer.writerows(rows)


def _batch(base: Path, **options) -> Path:
    """Lote limpo com as linhas sintéticas do mock e os cabeçalhos reais (DEC/FEC maiúsculos)."""

    for table, spec in SNAPSHOT.items():
        header = list(spec["columns"])
        rows = [[_cell(row[column]) for column in header] for row in GOLD_ROWS[table]]
        _write_table(base, table, header, rows, **options)
        (base / table / "_SUCCESS").write_text("", encoding="utf-8")
    return base


def _run(base: Path, capsys, *extra: str) -> tuple[int, list[list[str]]]:
    code = check_gold_dictionary.main([str(base), *extra])
    out = capsys.readouterr().out
    return code, [line.split("\t") for line in out.splitlines()]


def _rewrite(base: Path, table: str, change) -> None:
    """Reescreve o CSV de ``table`` aplicando ``change(header, rows)``."""

    path = base / table / "part-00000.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        header, *rows = list(csv.reader(handle, delimiter=";"))
    header, rows = change(header, rows)
    path.unlink()
    _write_table(base, table, header, rows)


def _fails(lines: list[list[str]]) -> list[list[str]]:
    return [line for line in lines if line[2] == "FAIL"]


def test_clean_batch_passes_every_column(tmp_path, capsys) -> None:
    code, lines = _run(_batch(tmp_path), capsys)

    assert code == 0
    expected = {
        (table, column)
        for table, spec in load_gold_metadata()["tables"].items()
        for column in spec["columns"]
    }
    assert {(line[0], line[1]) for line in lines} == expected
    assert all(line[2:] == ["PASS"] for line in lines)


def test_quoted_header_with_bom_passes(tmp_path, capsys) -> None:
    code, lines = _run(_batch(tmp_path, encoding="utf-8-sig", quote_all=True), capsys)

    assert code == 0
    assert ["indicadores_dec_fec", "dec", "PASS"] in lines
    assert ["consumo_mensal_uc", "id_uc", "PASS"] in lines


def test_missing_column_fails(tmp_path, capsys) -> None:
    base = _batch(tmp_path)

    def drop_bairro(header, rows):
        index = header.index("bairro")
        return header[:index] + header[index + 1:], [r[:index] + r[index + 1:] for r in rows]

    _rewrite(base, "fila_inspecao", drop_bairro)
    code, lines = _run(base, capsys)

    assert code == 1
    assert _fails(lines) == [["fila_inspecao", "bairro", "FAIL", "coluna ausente"]]


def test_extra_column_fails(tmp_path, capsys) -> None:
    base = _batch(tmp_path)
    _rewrite(
        base,
        "visao_360_uc",
        lambda header, rows: (header + ["cpf_cnpj"], [row + [SECRET] for row in rows]),
    )

    code, lines = _run(base, capsys)

    assert code == 1
    assert _fails(lines) == [["visao_360_uc", "cpf_cnpj", "FAIL", "coluna extra"]]


def test_repeated_column_ignoring_case_fails(tmp_path, capsys) -> None:
    base = _batch(tmp_path)
    _rewrite(
        base,
        "indicadores_dec_fec",
        lambda header, rows: (header + ["dec"], [row + ["1.0"] for row in rows]),
    )

    code, lines = _run(base, capsys)

    assert code == 1
    assert _fails(lines) == [["indicadores_dec_fec", "dec", "FAIL", "coluna repetida"]]


@pytest.mark.parametrize(
    ("table", "column", "value", "kind"),
    [
        ("fila_inspecao", "total_inspecoes_realizadas", "1.5", "número"),
        ("fila_inspecao", "data_ligacao", "15/01/2020", "texto"),
        ("consumo_mensal_uc", "receita_reais", "10,50", "texto"),
        ("variacao_consumo_uc", "queda_consumo_superior_30_pct", "1", "inteiro"),
        ("indicadores_dec_fec", "DEC", "NaN", "texto"),
    ],
)
def test_incompatible_type_fails(tmp_path, capsys, table, column, value, kind) -> None:
    base = _batch(tmp_path)

    def corrupt(header, rows):
        rows[0][header.index(column)] = value
        return header, rows

    _rewrite(base, table, corrupt)
    code, lines = _run(base, capsys)

    assert code == 1
    expected_type = load_gold_metadata()["tables"][table]["columns"][column.casefold()]
    assert _fails(lines) == [
        [
            table,
            column.casefold(),
            "FAIL",
            f"tipo incompatível: esperado {expected_type}, há {kind}",
        ]
    ]


def test_integer_fits_double_and_decimal(tmp_path, capsys) -> None:
    base = _batch(tmp_path)

    def integers(header, rows):
        for row in rows:
            row[header.index("consumo_kwh")] = "12"
            row[header.index("receita_reais")] = "7"
        return header, rows

    _rewrite(base, "consumo_mensal_uc", integers)

    assert _run(base, capsys)[0] == 0


def test_type_is_inferred_only_from_the_first_rows(tmp_path, capsys) -> None:
    base = _batch(tmp_path)

    def corrupt_last(header, rows):
        rows[-1][header.index("consumo_kwh")] = "texto"
        return header, rows

    _rewrite(base, "consumo_mensal_uc", corrupt_last)
    rows = len(GOLD_ROWS["consumo_mensal_uc"])

    assert _run(base, capsys, "--sample-rows", str(rows - 1))[0] == 0
    code, lines = _run(base, capsys, "--sample-rows", str(rows))
    assert code == 1
    assert _fails(lines)[0][:2] == ["consumo_mensal_uc", "consumo_kwh"]


def test_missing_table_fails(tmp_path, capsys) -> None:
    base = _batch(tmp_path)
    for path in (base / "consumo_mensal_uc").iterdir():
        path.unlink()
    (base / "consumo_mensal_uc").rmdir()

    code, lines = _run(base, capsys)

    assert code == 1
    assert _fails(lines) == [["consumo_mensal_uc", "-", "FAIL", "tabela ausente"]]


def test_part_files_with_different_headers_fail(tmp_path, capsys) -> None:
    base = _batch(tmp_path)
    _write_table(base, "consumo_mensal_uc", ["id_uc", "competencia"], [], name="part-00001.csv")

    code, lines = _run(base, capsys)

    assert code == 1
    assert _fails(lines) == [
        ["consumo_mensal_uc", "-", "FAIL", "cabeçalhos diferentes entre arquivos"]
    ]


def test_output_never_contains_cell_values(tmp_path, capsys) -> None:
    """Com falhas de tipo e coluna extra, a saída só tem tabela, coluna, status e motivo."""

    base = _batch(tmp_path)

    def plant(header, rows):
        for row in rows:
            row[header.index("municipio")] = SECRET
            row[header.index("total_chamados_callcenter")] = SECRET
        return header + ["coluna_desconhecida"], [row + [SECRET] for row in rows]

    _rewrite(base, "visao_360_uc", plant)
    code = check_gold_dictionary.main([str(base)])
    out = capsys.readouterr().out

    assert code == 1
    assert SECRET not in out
    cells = {
        _cell(value)
        for rows in GOLD_ROWS.values()
        for row in rows
        for value in row.values()
        if _cell(value)
    }
    columns = {column.casefold() for spec in SNAPSHOT.values() for column in spec["columns"]}
    for line in out.splitlines():
        table, column, status, *reason = line.split("\t")
        assert table in SNAPSHOT
        assert column in columns | {"coluna_desconhecida", "-"}
        assert status in {"PASS", "FAIL"}
        assert not set(line.split("\t")) & cells, line
        assert all(not reason_text[:1].isdigit() for reason_text in reason)


def test_missing_directory_is_a_usage_error(tmp_path) -> None:
    with pytest.raises(SystemExit) as caught:
        check_gold_dictionary.main([str(tmp_path / "inexistente")])

    assert caught.value.code == 2
