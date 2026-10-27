"""Conferência de lote Gold com CSVs inventados: só agregados, sem identificadores."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gold_coverage.py"
_spec = importlib.util.spec_from_file_location("gold_coverage", SCRIPT)
gold_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gold_coverage)

UC_IDS = ("UCFICT0001", "UCFICT0002", "UCFICT0003")


def _write(base: Path, table: str, header: list[str], rows: list[list[str]]) -> None:
    folder = base / table
    folder.mkdir(parents=True)
    lines = [";".join(f'"{v}"' for v in line) for line in [header, *rows]]
    (folder / f"{table}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _batch(base: Path, *, duplicate_monthly: bool = False, bairro_receita: str = "30.00") -> None:
    uc_header = ["id_uc", "municipio", "bairro", "classe", "alimentador", "status", "possui_gd"]
    uc_header += ["media_consumo_historico", "data_ligacao"]
    uc_values = ["MUNICIPIO A", "BAIRRO X", "RESIDENCIAL", "AL01", "ATIVA", "Não", "100.0"]
    ucs = [[uc, *uc_values, "2020-01-01"] for uc in UC_IDS]
    _write(base, "visao_360_uc", uc_header, ucs)
    fila_header = ["id_uc", "municipio", "classe", "possui_geracao_solar"]
    fila_header += ["media_consumo_historico", "total_inspecoes_realizadas"]
    fila_header += ["total_inspecoes_irregulares", "prioridade_inspecao"]
    fila_values = ["MUNICIPIO A", "RESIDENCIAL", "Não", "100.0", "0", "0"]
    fila = [[uc, *fila_values, "MEDIA - NUNCA INSPECIONADO"] for uc in UC_IDS]
    _write(base, "fila_inspecao", fila_header, fila)
    monthly = [[UC_IDS[0], "2025-01", "100.0", "10.00"], [UC_IDS[1], "2025-01", "100.0", "20.00"]]
    if duplicate_monthly:
        monthly.append([UC_IDS[0], "2025-01", "1.0", "1.00"])
    monthly_header = ["id_uc", "competencia", "consumo_kwh", "receita_reais"]
    _write(base, "consumo_mensal_uc", monthly_header, monthly)
    agg = ["consumo_total_kwh", "receita_total_reais", "qtd_ucs_distintas_faturadas_no_mes"]
    _write(
        base,
        "consumo_receita_bairro",
        ["competencia", "municipio", "bairro", "classe_consumo", *agg],
        [["2025-01", "MUNICIPIO A", "BAIRRO X", "RESIDENCIAL", "200.0", bairro_receita, "2"]],
    )
    _write(
        base,
        "diagnostico_receita",
        ["competencia", "municipio", "classe_consumo", "subgrupo_tarifario", "bandeira_tarifaria",
         "possui_gd", *agg],
        [["2025-01", "MUNICIPIO A", "RESIDENCIAL", "B1", "VERDE", "Não", "200.0", "30.00", "2"]],
    )


def test_consistent_batch_reconciles_without_manifest(tmp_path):
    _batch(tmp_path)

    report = gold_coverage.build_report(tmp_path)

    assert report["manifesto_ou_controle_encontrado"] == []
    assert report["tabelas"]["variacao_consumo_uc"] == {"estado": "ausente"}
    recon = report["reconciliacoes"]
    assert recon["ucs_x_visao_360"]["consumo_mensal_uc"]["so_na_visao_360"] == 1
    by_municipio = recon["bairro_x_diagnostico_por_competencia_municipio"]
    assert by_municipio["grupos_divergentes_receita_reais"] == 0
    assert recon["consumo_mensal_x_diagnostico_por_competencia"]["grupos_divergentes_ucs"] == 0


def test_duplicate_key_and_revenue_gap_are_reported(tmp_path):
    _batch(tmp_path, duplicate_monthly=True, bairro_receita="31.00")

    report = gold_coverage.build_report(tmp_path)

    monthly = report["tabelas"]["consumo_mensal_uc"]
    assert monthly["chave_unica"] is False
    assert monthly["chave_duplicatas"] == 1
    gap = report["reconciliacoes"]["bairro_x_diagnostico_por_competencia"]
    assert gap["grupos_divergentes_receita_reais"] == 1
    assert gap["maior_diferenca_receita_reais"] == "1.00"


def test_output_never_contains_uc_or_feeder_identifiers(tmp_path, capsys):
    _batch(tmp_path)
    json_path = tmp_path / "out.json"

    assert gold_coverage.main([str(tmp_path), "--json", str(json_path)]) == 0

    printed = capsys.readouterr().out + json_path.read_text(encoding="utf-8")
    for identifier in (*UC_IDS, "AL01"):
        assert identifier not in printed
    assert "MEDIA - NUNCA INSPECIONADO" in printed
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["tabelas"]["visao_360_uc"]["linhas"] == 3


def _controls(report: dict) -> dict:
    return {item["id"]: item["valor"] for item in report["controles_candidatos"]}


def test_candidate_controls_cover_totals_zero_null_and_mismatch(tmp_path):
    _batch(tmp_path, bairro_receita="31.00")

    controls = _controls(gold_coverage.build_report(tmp_path))

    assert controls["C01"] == {"consumo_kwh": "200.0", "receita_reais": "30.00"}
    assert controls["C02"] == {"RESIDENCIAL": {"consumo_kwh": "200.0", "receita_reais": "30.00"}}
    assert controls["C03"] == "2"
    assert controls["C04"]["municipio"] == "MUNICIPIO A"
    assert controls["C05"] == {"RESIDENCIAL": 3}
    assert controls["C06"] == {"MEDIA - NUNCA INSPECIONADO": 3}
    assert controls["C07"] == 0
    assert controls["C10"] == {"ucs_media_nula": 0, "das_quais_sem_serie_mensal": 0}
    assert controls["C12"] == 1
    assert "C08" not in controls and "C11" not in controls


def test_worst_feeder_control_reports_values_without_identifier(tmp_path, capsys):
    _batch(tmp_path)
    header = ["id_alimentador", "municipio", "competencia", "total_ucs_alimentador",
              "ucs_interrompidas", "frequencia_total_interrupcoes",
              "duracao_total_interrupcoes_horas", "DEC", "FEC"]
    rows = [
        ["ALFICT01", "MUNICIPIO A", "2025-01", "10", "2", "2", "5.0", "0.5", "0.2"],
        ["ALFICT01", "MUNICIPIO A", "2025-02", "10", "4", "4", "30.0", "3.0", "0.4"],
        ["ALFICT02", "MUNICIPIO A", "2025-02", "10", "1", "1", "10.0", "1.0", "0.1"],
    ]
    _write(tmp_path, "indicadores_dec_fec", header, rows)

    assert gold_coverage.main([str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "ALFICT01" not in out and "ALFICT02" not in out
    report = gold_coverage.build_report(tmp_path)
    assert _controls(report)["C11"] == {
        "dec_mes": 3.0,
        "fec_mes": 0.4,
        "dec_media_mensal": 1.75,
        "fec_media_mensal": 0.3,
    }


def test_reads_directory_from_environment(tmp_path, monkeypatch, capsys):
    _batch(tmp_path)
    monkeypatch.setenv("GOLD_DATA_DIR", str(tmp_path))

    assert gold_coverage.main([]) == 0
    assert "## visao_360_uc" in capsys.readouterr().out
