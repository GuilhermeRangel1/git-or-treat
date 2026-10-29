"""Conferência local dos valores de dimensão declarados, com CSVs sintéticos em pasta temporária."""

import csv
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_gold_dimension_values.py"
_spec = importlib.util.spec_from_file_location("check_gold_dimension_values", SCRIPT)
check_values = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_values)

SECRET = "VALOR-SINTETICO-QUE-NAO-PODE-VAZAR"
CLASSES = ["RESIDENCIAL", "COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RURAL"]


def _write(base: Path, table: str, header: list[str], rows: list[list[str]], **options) -> None:
    folder = base / table
    folder.mkdir(parents=True, exist_ok=True)
    encoding = options.get("encoding", "utf-8")
    with (folder / options.get("name", "part-00000.csv")).open(
        "w", encoding=encoding, newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _batch(base: Path, *, municipalities: list[str], gd: tuple[str, ...] = ("Sim", "Não")) -> Path:
    """Lote mínimo: só as colunas de dimensão lidas pelo mapeamento, mais um valor secreto."""

    diagnostico = [
        [municipality, klass, value]
        for municipality in [*municipalities, SECRET]
        for klass in CLASSES
        for value in gd
    ]
    _write(base, "diagnostico_receita", ["municipio", "classe_consumo", "possui_gd"], diagnostico)
    _write(
        base,
        "consumo_receita_bairro",
        ["municipio", "bairro", "classe_consumo"],
        [[municipality, SECRET, klass] for municipality in municipalities for klass in CLASSES],
        encoding="utf-8-sig",
    )
    _write(
        base,
        "indicadores_dec_fec",
        ["ID_ALIMENTADOR", "MUNICIPIO"],
        [[SECRET, municipality] for municipality in municipalities],
    )
    return base


def _results(checks) -> dict[tuple[str, str], str]:
    return {(f"{check.table}.{check.column}", check.declared): check.result for check in checks}


def test_every_declared_value_is_checked_in_every_mapped_column(tmp_path: Path) -> None:
    base = _batch(tmp_path, municipalities=["RECIFE", "OLINDA", "JABOATÃO DOS GUARARAPES"])

    results = _results(check_values.check_batch(base))

    assert set(results.values()) == {check_values.EXACT}
    assert {column for column, _ in results} == {
        "diagnostico_receita.municipio",
        "diagnostico_receita.classe_consumo",
        "diagnostico_receita.possui_gd",
        "consumo_receita_bairro.municipio",
        "consumo_receita_bairro.classe_consumo",
        "indicadores_dec_fec.municipio",
    }
    assert ("diagnostico_receita.possui_gd", "Não") in results
    assert check_values.main([str(base)]) == 0


def test_value_present_only_with_other_case_or_accent_is_normalized_pass(tmp_path: Path) -> None:
    base = _batch(tmp_path, municipalities=["Recife", "OLINDA", "Jaboatão  dos Guararapes"])

    results = _results(check_values.check_batch(base))

    assert results[("diagnostico_receita.municipio", "RECIFE")] == check_values.NORMALIZED
    assert (
        results[("indicadores_dec_fec.municipio", "JABOATÃO DOS GUARARAPES")]
        == check_values.NORMALIZED
    )
    assert results[("diagnostico_receita.municipio", "OLINDA")] == check_values.EXACT
    assert check_values.main([str(base)]) == 0


def test_accented_declared_value_passes_exact_and_unaccented_only_normalized(
    tmp_path: Path,
) -> None:
    declared = "JABOATÃO DOS GUARARAPES"
    accented = _results(
        check_values.check_batch(
            _batch(tmp_path / "acento", municipalities=["RECIFE", "OLINDA", declared])
        )
    )
    unaccented = _results(
        check_values.check_batch(
            _batch(tmp_path / "sem", municipalities=["RECIFE", "OLINDA", "jaboatao dos guararapes"])
        )
    )

    assert declared in check_values.declared_values()["geography.municipality"]
    for column in (
        "diagnostico_receita.municipio",
        "consumo_receita_bairro.municipio",
        "indicadores_dec_fec.municipio",
    ):
        assert accented[(column, declared)] == check_values.EXACT
        assert unaccented[(column, declared)] == check_values.NORMALIZED


def test_missing_value_table_or_column_fails(tmp_path: Path) -> None:
    base = _batch(tmp_path, municipalities=["RECIFE", "JABOATÃO DOS GUARARAPES"], gd=("Sim",))
    _write(base, "indicadores_dec_fec", ["id_alimentador"], [[SECRET]])
    for path in (base / "consumo_receita_bairro").iterdir():
        path.unlink()

    checks = check_values.check_batch(base)
    results = _results(checks)
    reasons = {(f"{check.table}.{check.column}", check.declared): check.reason for check in checks}

    assert results[("diagnostico_receita.municipio", "OLINDA")] == check_values.FAIL
    assert results[("diagnostico_receita.possui_gd", "Não")] == check_values.FAIL
    assert reasons[("consumo_receita_bairro.municipio", "RECIFE")] == "tabela ausente"
    assert reasons[("indicadores_dec_fec.municipio", "RECIFE")] == "coluna ausente"
    assert check_values.main([str(base)]) == 1


def test_output_prints_only_declared_values(tmp_path: Path, capsys) -> None:
    base = _batch(tmp_path, municipalities=["Recife", "Cidade Sintética Não Declarada"])

    check_values.main([str(base)])
    output = capsys.readouterr().out

    assert SECRET not in output
    assert "Sintética" not in output
    assert "Recife" not in output
    declared = {value for values in check_values.declared_values().values() for value in values}
    allowed_results = {check_values.EXACT, check_values.NORMALIZED, check_values.FAIL}
    for line in output.splitlines():
        dimension_id, column, value, result, *reason = line.split("\t")
        assert dimension_id in check_values.declared_values()
        assert "." in column
        assert value in declared
        assert result in allowed_results
        assert reason in ([], ["tabela ausente"], ["coluna ausente"], ["arquivo ilegível"])
        assert not any(character.isdigit() for character in line)
