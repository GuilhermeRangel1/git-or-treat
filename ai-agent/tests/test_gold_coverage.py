"""Conferência de lote Gold com CSVs inventados: só agregados, sem identificadores."""

import importlib.util
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

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


def _batch(
    base: Path,
    *,
    duplicate_monthly: bool = False,
    bairro_receita: str = "30.00",
    diag_receita: str = "30.00",
    extra_uc: dict[str, tuple[str, str, str]] | None = None,
) -> None:
    extra_uc = extra_uc or {}
    uc_header = ["id_uc", "municipio", "bairro", "classe", "alimentador", "status", "possui_gd"]
    uc_header += ["media_consumo_historico", "data_ligacao", *extra_uc]
    uc_values = ["MUNICIPIO A", "BAIRRO X", "RESIDENCIAL", "AL01", "ATIVA", "Não", "100.0"]
    ucs = [
        [uc, *uc_values, "2020-01-01", *(values[i] for values in extra_uc.values())]
        for i, uc in enumerate(UC_IDS)
    ]
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
        [["2025-01", "MUNICIPIO A", "RESIDENCIAL", "B1", "VERDE", "Não", "200.0", diag_receita,
          "2"]],
    )


def test_consistent_batch_reconciles_without_manifest(tmp_path):
    _batch(tmp_path)

    report = gold_coverage.build_report(tmp_path)

    assert report["manifesto_ou_controle_encontrado"] == []
    assert report["tabelas"]["variacao_consumo_uc"] == {"estado": "ausente"}
    recon = report["reconciliacoes"]
    assert recon["medidas_nulas_ou_invalidas_por_tabela"] == {}
    assert recon["ucs_x_visao_360"]["consumo_mensal_uc"]["so_na_visao_360"] == 1
    by_municipio = recon["bairro_x_diagnostico_por_competencia_municipio"]
    assert by_municipio["estado"] == "verificada"
    assert by_municipio["grupos_divergentes_receita_reais"] == 0
    assert recon["consumo_mensal_x_diagnostico_por_competencia"]["grupos_divergentes_ucs"] == 0


def test_invalid_measures_with_equal_totals_are_not_verifiable(tmp_path):
    # Antes, "abc" e vazio entravam como zero e as duas tabelas fechavam com 0 divergências.
    _batch(tmp_path, bairro_receita="abc", diag_receita="")

    report = gold_coverage.build_report(tmp_path)

    recon = report["reconciliacoes"]
    assert recon["medidas_nulas_ou_invalidas_por_tabela"] == {
        "consumo_receita_bairro": {"receita_reais_invalido": 1},
        "diagnostico_receita": {"receita_reais_nulo": 1},
    }
    for name in (
        "bairro_x_diagnostico_por_competencia",
        "bairro_x_diagnostico_por_competencia_municipio",
        "bairro_x_diagnostico_por_competencia_classe",
        "consumo_mensal_x_diagnostico_por_competencia",
        "consumo_mensal_com_municipio_da_visao_x_diagnostico",
        "consumo_mensal_com_classe_da_visao_x_diagnostico",
    ):
        assert recon[name]["estado"] == "nao_verificavel"
        assert not any(key.startswith("grupos_divergentes") for key in recon[name])
    assert recon["diagnostico_checagens"]["linhas_com_medida_nula_ou_invalida"] == 1
    assert report["exemplos_exploratorios_prd_7_6"]["estado"] == "nao_verificavel"
    controls = _controls(report)
    for cid in ("C01", "C02", "C04", "C12"):
        assert controls[cid]["estado"] == "nao_verificavel"


def test_invalid_measures_in_both_tables_are_not_verifiable(tmp_path):
    _batch(tmp_path, bairro_receita="n/d", diag_receita="n/d")

    recon = gold_coverage.build_report(tmp_path)["reconciliacoes"]

    gap = recon["bairro_x_diagnostico_por_competencia"]
    assert gap["estado"] == "nao_verificavel"
    assert gap["medidas_nulas_ou_invalidas"] == {
        "consumo_receita_bairro": {"receita_reais_invalido": 1},
        "diagnostico_receita": {"receita_reais_invalido": 1},
    }


def test_null_monthly_consumption_blocks_monthly_comparisons(tmp_path):
    _batch(tmp_path)
    monthly = tmp_path / "consumo_mensal_uc" / "consumo_mensal_uc.csv"
    monthly.write_text(
        monthly.read_text(encoding="utf-8").replace('"100.0";"10.00"', '"";"10.00"'),
        encoding="utf-8",
    )

    recon = gold_coverage.build_report(tmp_path)["reconciliacoes"]

    assert recon["consumo_mensal_x_diagnostico_por_competencia"]["estado"] == "nao_verificavel"
    assert recon["bairro_x_diagnostico_por_competencia"]["estado"] == "verificada"
    media = recon["media_consumo_visao_x_media_do_consumo_mensal"]
    assert media["nao_verificavel_consumo_nulo_ou_invalido"] == 1


def test_profile_publishes_only_allowed_dimensions(tmp_path, capsys):
    # Dados pessoais fictícios: nenhum deles pode sair no console nem no JSON.
    personal = {
        "nome_titular": ("Fulana Ficticia", "Beltrano Ficticio", "Fulana Ficticia"),
        "email": ("fulana@exemplo.invalid", "beltrano@exemplo.invalid", "x@exemplo.invalid"),
        "observacao": ("TEXTO LIVRE UM", "TEXTO LIVRE DOIS", "TEXTO LIVRE UM"),
        "nota_livre": ("2020-01-01 visita", "OUTRA NOTA", "OUTRA NOTA"),
    }
    lote = tmp_path / "lote"
    _batch(lote, extra_uc=personal)
    json_path = tmp_path / "out.json"

    assert gold_coverage.main([str(lote), "--json", str(json_path)]) == 0

    saved_text = json_path.read_text(encoding="utf-8")
    for printed in (capsys.readouterr().out, saved_text):
        for values in personal.values():
            for value in values:
                assert value not in printed
        assert "Ficticia" not in printed and "@exemplo" not in printed
    perfil = json.loads(saved_text)["tabelas"]["visao_360_uc"]["perfil"]
    assert perfil["municipio"]["valores"] == {"MUNICIPIO A": 3}
    assert perfil["classe"]["valores"] == {"RESIDENCIAL": 3}
    for column in ("nome_titular", "email", "observacao", "nota_livre", "bairro", "data_ligacao"):
        assert "valores" not in perfil[column]
    assert perfil["email"]["padrao_email"] == 3
    assert perfil["email"]["distintos"] == 3
    assert "minimo_texto" not in perfil["nota_livre"]
    assert perfil["data_ligacao"]["minimo_texto"] == "2020-01-01"


def test_allowed_dimension_with_personal_name_or_values_is_suppressed(monkeypatch):
    monkeypatch.setattr(
        gold_coverage, "PUBLISHABLE_DIMENSIONS", {"status", "cep", "nome_titular"}
    )
    cases = {
        "status": ("123.456.789-09", "ATIVA"),
        "cep": ("ZONA 1", "ZONA 2"),
        "nome_titular": ("A", "B"),
    }
    for name, values in cases.items():
        profile = gold_coverage.ColumnProfile(name)
        for value in values:
            profile.add(value)
        assert "valores" not in profile.summary(len(values)), name

    allowed = gold_coverage.ColumnProfile("status")
    allowed.add("ATIVA")
    assert allowed.summary(1)["valores"] == {"ATIVA": 1}


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
    lote = tmp_path / "lote"
    _batch(lote)
    json_path = tmp_path / "out.json"

    assert gold_coverage.main([str(lote), "--json", str(json_path)]) == 0

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


def _bairros(lote: Path, rows: list[list[str]]) -> None:
    path = lote / "consumo_receita_bairro" / "consumo_receita_bairro.csv"
    header = path.read_text(encoding="utf-8").splitlines()[0]
    lines = [";".join(f'"{v}"' for v in row) for row in rows]
    path.write_text("\n".join([header, *lines]) + "\n", encoding="utf-8")


def test_c13_counts_rows_and_distinct_bairros_without_duplicity(tmp_path):
    _batch(tmp_path)
    _bairros(tmp_path, [
        ["2025-01", "MUNICIPIO A", "SÃO JOSÉ FICTICIO", "RESIDENCIAL", "100.0", "15.00", "1"],
        ["2025-01", "MUNICIPIO A", "BAIRRO X", "RESIDENCIAL", "100.0", "15.00", "1"],
        ["2025-01", "MUNICIPIO B", "BAIRRO X", "RESIDENCIAL", "0.0", "0.00", "0"],
    ])

    controls = _controls(gold_coverage.build_report(tmp_path))

    # O mesmo nome em municípios diferentes são bairros diferentes.
    assert controls["C13"] == {
        "linhas": 3,
        "bairros_distintos": 3,
        "bairros_distintos_normalizados": 3,
        "possivel_duplicidade_de_bairro": False,
    }


def test_c13_flags_bairro_duplicated_by_encoding_that_c12_misses(tmp_path, capsys):
    _batch(tmp_path)
    mojibake = "SÃO JOSÉ FICTICIO".encode().decode("latin-1")
    # Mesmo bairro em três grafias; os totais por competência continuam iguais ao diagnóstico.
    _bairros(tmp_path, [
        ["2025-01", "MUNICIPIO A", "SÃO JOSÉ FICTICIO", "RESIDENCIAL", "100.0", "10.00", "1"],
        ["2025-01", "MUNICIPIO A", mojibake, "RESIDENCIAL", "50.0", "10.00", "1"],
        ["2025-01", "MUNICIPIO A", "Sao Jose  Ficticio", "COMERCIAL", "50.0", "10.00", "0"],
    ])

    assert gold_coverage.main([str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "FICTICIO" not in out.upper() and mojibake not in out
    controls = _controls(gold_coverage.build_report(tmp_path))
    assert controls["C12"] == 0
    assert controls["C13"] == {
        "linhas": 3,
        "bairros_distintos": 3,
        "bairros_distintos_normalizados": 1,
        "possivel_duplicidade_de_bairro": True,
    }


def _c14(base: Path, chamados=None, medias=None) -> dict:
    columns = {}
    if chamados is not None:
        columns["total_chamados_callcenter"] = chamados
    if medias is not None:
        columns["media_satisfacao_atendimento"] = medias
    _batch(base, extra_uc=columns)
    return _controls(gold_coverage.build_report(base))["C14"]


def _c14_states(**counts: int) -> dict:
    states = ("sem_chamados_sem_media", "sem_chamados_com_media", "com_chamados_sem_media",
              "com_chamados_com_media")
    return {state: counts.get(state, 0) for state in states}


def test_c14_preserves_confirmed_zero_rating_in_gold_v2(tmp_path):
    c14 = _c14(tmp_path, ("1", "1", "0"), ("0", "8", r"\N"))
    assert c14["estado"] == "verificada"
    assert c14["consistente"] is True
    assert "premissa_escala_1_a_5" not in c14


def _attendance_details(base, rows):
    _write(base, "atendimentos_uc", ["protocolo", "id_uc", "nota_satisfacao",
                                    "data_abertura"], rows)


def test_c14_reconciles_protocols_and_nullable_average_without_leaking_records(tmp_path):
    _c14(tmp_path, ("2", "1", "0"), ("2", r"\N", r"\N"))
    _attendance_details(tmp_path, [
        ["PROTOCOLO_FICTICIO_A", UC_IDS[0], "0", "2025-01-01T00:00:00Z"],
        ["PROTOCOLO_FICTICIO_B", UC_IDS[0], "4", "2025-01-31T23:59:59Z"],
        ["PROTOCOLO_FICTICIO_C", UC_IDS[1], r"\N", r"\N"],
    ])
    report = gold_coverage.build_report(tmp_path)
    check = report["reconciliacoes"]["atendimento_protocolos_x_visao_360"]
    assert check["estado"] == "verificada"
    assert check["consistente"] is True
    assert check["ucs_com_contagem_divergente"] == 0
    assert check["ucs_com_media_divergente"] == 0
    assert not any(value in json.dumps(check) for value in (*UC_IDS, "PROTOCOLO_FICTICIO_A"))


@pytest.mark.parametrize(("summary_count", "summary_average", "counts", "averages"), [
    ("1", "2", 1, 0), ("2", "3", 0, 1), ("2", r"\N", 0, 1),
    ("2", "2.005", 0, 0), ("2", "2.006", 0, 1),
])
def test_c14_checks_exact_counts_and_average_tolerance(
    tmp_path, summary_count, summary_average, counts, averages
):
    _c14(tmp_path, (summary_count, "0", "0"), (summary_average, r"\N", r"\N"))
    _attendance_details(tmp_path, [["A", UC_IDS[0], "0", ""], ["B", UC_IDS[0], "4", ""]])
    result = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert result["ucs_com_contagem_divergente"] == counts
    assert result["ucs_com_media_divergente"] == averages
    assert result["consistente"] is (counts == averages == 0)


@pytest.mark.parametrize("rating", ["-1", "abc", "Infinity", "NaN"])
def test_c14_invalid_detail_rating_does_not_validate_the_summary(tmp_path, rating):
    _c14(tmp_path, ("1", "0", "0"), (r"\N", r"\N", r"\N"))
    _attendance_details(tmp_path, [["A", UC_IDS[0], rating, ""]])
    result = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    # NaN é token de ausência compatível com o exportador legado; não vira zero.
    assert result["estado"] == ("verificada" if rating == "NaN" else "nao_verificavel")


def test_c14_duplicate_protocols_are_not_silently_deduplicated(tmp_path):
    _c14(tmp_path, ("1", "0", "0"), ("4", "", ""))
    _attendance_details(tmp_path, [["A", UC_IDS[0], "4", ""], ["A", UC_IDS[0], "4", ""]])
    result = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert result == {"estado": "nao_verificavel", "inconsistencias": {"protocolo_duplicado": 1}}


def test_c14_missing_detail_is_not_evidence_of_zero_calls(tmp_path):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    result = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert result == {"estado": "nao_verificavel", "tabela_ausente": "atendimentos_uc"}


def test_c14_empty_detail_with_schema_can_confirm_zero_calls(tmp_path):
    _c14(tmp_path, ("0", "0", "0"), (r"\N", r"\N", r"\N"))
    _attendance_details(tmp_path, [])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check["estado"] == "verificada" and check["consistente"] is True


def test_c14_orphan_uc_blocks_consistency_without_exposing_the_key(tmp_path):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [["PROTOCOLO_NAO_PUBLICAVEL", "UC_ORFA_NAO_PUBLICAVEL", "0", ""]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check["ucs_fora_da_visao_360"] == 1 and check["consistente"] is False
    assert "NAO_PUBLICAVEL" not in json.dumps(check)


def test_c14_detail_missing_rating_column_does_not_assume_null(tmp_path):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    _write(tmp_path, "atendimentos_uc", ["protocolo", "id_uc"], [["A", UC_IDS[0]]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check == {"estado": "nao_verificavel", "tabela": "atendimentos_uc",
                     "colunas_ausentes": ["nota_satisfacao"]}


def test_c14_clean_batch_is_consistent(tmp_path):
    c14 = _c14(tmp_path, ("1", "2", "3"), ("4.0", "3.5", "5"))

    assert c14 == {
        "estado": "verificada",
        "ucs_por_estado": _c14_states(com_chamados_com_media=3),
        "inconsistencias": {
            "chamados_negativo": 0,
            "chamados_nao_inteiro": 0,
            "media_presente_sem_chamados": 0,
            "media_negativa": 0,
        },
        "consistente": True,
    }


def test_c14_uc_without_calls_has_null_average_not_zero(tmp_path):
    c14 = _c14(tmp_path, ("0", "2", "0"), ("", "4", ""))

    assert c14["ucs_por_estado"] == _c14_states(sem_chamados_sem_media=2, com_chamados_com_media=1)
    assert c14["inconsistencias"]["media_negativa"] == 0
    assert c14["consistente"] is True


def test_c14_uc_with_calls_but_no_rating_is_valid(tmp_path):
    c14 = _c14(tmp_path, ("2", "1", "3"), ("", "4", ""))

    assert c14["ucs_por_estado"] == _c14_states(com_chamados_sem_media=2, com_chamados_com_media=1)
    assert c14["consistente"] is True


def test_c14_flags_average_present_without_calls(tmp_path):
    # Média presente sem protocolos é inconsistente; zero com protocolo é válido.
    c14 = _c14(tmp_path, ("0", "0", "2"), ("3.0", "0", "0"))

    assert c14["ucs_por_estado"] == _c14_states(sem_chamados_com_media=2, com_chamados_com_media=1)
    assert c14["inconsistencias"] == {
        "chamados_negativo": 0,
        "chamados_nao_inteiro": 0,
        "media_presente_sem_chamados": 2,
        "media_negativa": 0,
    }
    assert c14["consistente"] is False


def test_c14_does_not_invent_a_maximum_rating(tmp_path):
    c14 = _c14(tmp_path, ("1", "1", "1"), ("0.5", "5.5", "3"))

    assert "premissa_escala_1_a_5" not in c14
    assert not any(c14["inconsistencias"].values())
    assert c14["consistente"] is True


def test_c14_negative_or_fractional_calls_are_inconsistent(tmp_path):
    c14 = _c14(tmp_path, ("-1", "2.5", "3"), ("4", "4", "4"))

    assert c14["inconsistencias"]["chamados_negativo"] == 1
    assert c14["inconsistencias"]["chamados_nao_inteiro"] == 1
    assert c14["ucs_por_estado"] == _c14_states(com_chamados_com_media=1)
    assert c14["consistente"] is False


def test_c14_null_or_invalid_measure_is_not_verifiable(tmp_path):
    c14 = _c14(tmp_path, ("", "abc", "1"), ("", "4", "n/d"))

    assert c14 == {
        "estado": "nao_verificavel",
        "medidas_nulas_ou_invalidas": {
            "visao_360_uc": {
                "chamados_invalido": 1,
                "chamados_nulo": 1,
                "media_satisfacao_invalido": 1,
            }
        },
    }


@pytest.mark.parametrize(
    ("chamados", "medias", "missing"),
    [
        (("1", "2", "3"), None, ["media_satisfacao_atendimento"]),
        (None, ("4", "4", "4"), ["total_chamados_callcenter"]),
        (None, None, ["total_chamados_callcenter", "media_satisfacao_atendimento"]),
    ],
)
def test_c14_missing_column_is_not_verifiable_not_zero(tmp_path, chamados, medias, missing):
    c14 = _c14(tmp_path, chamados, medias)

    assert c14 == {"estado": "nao_verificavel", "colunas_ausentes": missing}


def test_c14_output_has_no_identifiers_or_values(tmp_path, capsys):
    lote = tmp_path / "lote"
    chamados, medias = ("7", "13", "29"), ("2.111", "4.321", "4.987")
    _batch(lote, extra_uc={
        "total_chamados_callcenter": chamados,
        "media_satisfacao_atendimento": medias,
    })
    json_path = tmp_path / "out.json"

    assert gold_coverage.main([str(lote), "--json", str(json_path)]) == 0

    out = capsys.readouterr().out
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    c14 = next(c for c in saved["controles_candidatos"] if c["id"] == "C14")
    c14_line = next(line for line in out.splitlines() if line.startswith("  - C14 "))
    for printed in (json.dumps(c14["valor"]), c14_line.split(":", 1)[1]):
        for value in (*chamados, *medias):
            assert value not in printed
    for printed in (out, json_path.read_text(encoding="utf-8")):
        assert not any(uc in printed for uc in UC_IDS)
        assert "4.321" not in printed  # nem mínimo nem máximo: não aparece no perfil
    assert c14["valor"]["ucs_por_estado"]["com_chamados_com_media"] == 3


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


def _bairro_recon(months: list[str]):
    recon = gold_coverage.Recon()
    for i, comp in enumerate(months):
        consumo = Decimal(110) if i >= len(months) - 12 else Decimal(100)
        recon.bairro_cells[(comp, "MUNICIPIO A", "BAIRRO X", "RESIDENCIAL")] = [consumo, consumo]
    return recon


def test_continuous_months_compute_twelve_month_windows():
    months = gold_coverage._months_between("2023-01", "2024-12")

    examples = gold_coverage.exploratory_examples(_bairro_recon(months))

    assert examples["janelas"]["primeiros_12m"] == ["2023-01", "2023-12"]
    assert examples["janelas"]["ultimos_12m"] == ["2024-01", "2024-12"]
    assert examples["todas_as_classes"]["consumo_ultimos_vs_primeiros_pct"] == 10.0


def test_missing_month_blocks_twelve_month_windows():
    # 24 competências, mas sem 2023-05: os "primeiros 12" cobririam 13 meses de calendário.
    months = [m for m in gold_coverage._months_between("2023-01", "2025-01") if m != "2023-05"]

    examples = gold_coverage.exploratory_examples(_bairro_recon(months))

    assert examples["estado"] == "janela incompleta"
    # 2023-01 a 2025-01 são 25 meses: primeiros e penúltimos 12 se sobrepõem e ambos perdem 2023-05.
    assert examples["meses_faltantes"] == {
        "primeiros_12m": ["2023-05"],
        "penultimos_12m": ["2023-05"],
    }
    assert "todas_as_classes" not in examples and "por_classe" not in examples


def test_feeder_average_requires_continuous_months(tmp_path):
    _batch(tmp_path)
    header = ["id_alimentador", "municipio", "competencia", "total_ucs_alimentador",
              "ucs_interrompidas", "frequencia_total_interrupcoes",
              "duracao_total_interrupcoes_horas", "DEC", "FEC"]
    rows = [
        ["ALFICT01", "MUNICIPIO A", "2025-01", "10", "2", "2", "5.0", "0.5", "0.2"],
        ["ALFICT01", "MUNICIPIO A", "2025-03", "10", "4", "4", "30.0", "3.0", "0.4"],
        ["ALFICT02", "MUNICIPIO A", "2025-02", "10", "1", "1", "10.0", "1.0", "0.1"],
    ]
    _write(tmp_path, "indicadores_dec_fec", header, rows)

    c11 = next(
        c for c in gold_coverage.build_report(tmp_path)["controles_candidatos"] if c["id"] == "C11"
    )

    assert c11["valor"] == {
        "dec_mes": 3.0,
        "fec_mes": 0.4,
        "media_mensal": {"estado": "janela incompleta", "meses_faltantes": ["2025-02"]},
    }


def _csv(lote: Path) -> Path:
    return lote / "visao_360_uc" / "visao_360_uc.csv"


def _refused(lote: Path, target: Path, capsys) -> None:
    original = _csv(lote).read_bytes()
    with pytest.raises(SystemExit) as error:
        gold_coverage.main([str(lote), "--json", str(target)])
    assert error.value.code == 2
    assert "--json não pode" in capsys.readouterr().err
    assert _csv(lote).read_bytes() == original


def test_json_target_inside_batch_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)

    _refused(lote, lote / "out.json", capsys)
    assert not (lote / "out.json").exists()


def test_json_target_equal_to_input_csv_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)

    _refused(lote, _csv(lote), capsys)


def test_json_target_with_dotdot_into_batch_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)
    (tmp_path / "fora").mkdir()

    _refused(lote, tmp_path / "fora" / ".." / "lote" / "visao_360_uc" / "out.json", capsys)


def test_json_symlink_into_batch_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)
    link = tmp_path / "link.json"
    try:
        link.symlink_to(_csv(lote))
    except OSError:
        pytest.skip("o sistema não permite criar link simbólico")

    _refused(lote, link, capsys)


def test_json_hard_link_to_input_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)
    link = tmp_path / "hard.json"
    try:
        os.link(_csv(lote), link)
    except OSError:
        pytest.skip("o sistema não permite criar hard link")

    _refused(lote, link, capsys)


def test_json_target_outside_batch_is_written(tmp_path):
    lote = tmp_path / "lote"
    _batch(lote)
    # A pasta intermediária precisa existir: no Linux, "saida/.." só vale se "saida" existir.
    (tmp_path / "saida").mkdir()
    target = tmp_path / "saida" / ".." / "out.json"

    assert gold_coverage.main([str(lote), "--json", str(target)]) == 0

    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["tabelas"]
    assert not list(lote.rglob("*.json"))


def test_json_target_inside_table_subfolder_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)

    _refused(lote, lote / "visao_360_uc" / "out.json", capsys)
    assert not (lote / "visao_360_uc" / "out.json").exists()


def _flatten(lote: Path) -> None:
    """Converte o lote para o layout de CSVs soltos na pasta."""
    for folder in [p for p in lote.iterdir() if p.is_dir() and p.name in gold_coverage.TABLES]:
        (folder / f"{folder.name}.csv").rename(lote / f"{folder.name}.csv")
        folder.rmdir()


def _seven_tables(lote: Path) -> None:
    _batch(lote)
    _write(
        lote,
        "variacao_consumo_uc",
        ["id_uc", "municipio", "possui_gd", "consumo_medio_inicial", "consumo_medio_final"],
        [[uc, "MUNICIPIO A", "Não", "100.0", "100.0"] for uc in UC_IDS],
    )
    _write(
        lote,
        "indicadores_dec_fec",
        ["id_alimentador", "municipio", "competencia", "total_ucs_alimentador",
         "duracao_total_interrupcoes_horas", "frequencia_total_interrupcoes", "DEC", "FEC"],
        [["ALFICT01", "MUNICIPIO A", "2025-01", "3", "3.0", "3", "1.0", "1.0"]],
    )


def _manifest(base: Path, where: str = "manifesto/manifest.json", **overrides) -> None:
    data = {
        "ambiente": "PROD",
        "lote": "LOTEFICT01",
        "run_id_silver": "RUNFICT01",
        "lote_bronze_silver": "BRONZEFICT01",
        "tabelas_exportadas": list(gold_coverage.TABLES),
        # Campos de negócio inventados: nunca podem sair na saída.
        "receita_total_reais": "987654.32",
        "contagens": {"visao_360_uc": 31337},
    }
    data.update(overrides)
    target = base / where
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(data), encoding="utf-8")


def test_loose_and_subfolder_layouts_give_the_same_profile(tmp_path):
    soltos, subpastas = tmp_path / "soltos", tmp_path / "subpastas"
    _seven_tables(soltos)
    _flatten(soltos)
    _seven_tables(subpastas)
    assert (soltos / "visao_360_uc.csv").is_file() and not (soltos / "visao_360_uc").exists()
    assert (subpastas / "visao_360_uc" / "visao_360_uc.csv").is_file()

    loose, nested = (gold_coverage.build_report(base) for base in (soltos, subpastas))

    for report in (loose, nested):
        assert all(info["estado"] == "presente" for info in report["tabelas"].values())
        assert report["manifesto"] is None
    assert loose["tabelas"] == nested["tabelas"]
    assert loose["reconciliacoes"] == nested["reconciliacoes"]


def test_prod_manifest_prints_only_technical_identification(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    _manifest(lote)
    json_path = tmp_path / "out.json"

    assert gold_coverage.main([str(lote), "--json", str(json_path)]) == 0

    manifest = json.loads(json_path.read_text(encoding="utf-8"))["manifesto"]
    assert manifest == {
        "arquivo": "manifesto/manifest.json",
        "ambiente": "PROD",
        "lote": "LOTEFICT01",
        "run_id_silver": "RUNFICT01",
        "lote_bronze_silver": "BRONZEFICT01",
        "tabelas_exportadas": sorted(gold_coverage.TABLES),
        "avisos": [],
    }
    out = capsys.readouterr().out
    assert "LOTEFICT01" in out and "AVISO" not in out
    for printed in (out, json_path.read_text(encoding="utf-8")):
        assert "987654.32" not in printed and "31337" not in printed


def test_manifest_at_batch_root_is_read(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    # O exportador da Gold grava o manifesto na raiz, com o ambiente em minúsculas.
    _manifest(lote, where="manifest.json", ambiente="prod")

    assert gold_coverage.main([str(lote)]) == 0

    out = capsys.readouterr().out
    assert '"arquivo": "manifest.json"' in out and "LOTEFICT01" in out
    assert "AVISO" not in out
    assert "987654.32" not in out and "31337" not in out


def test_manifest_in_both_paths_uses_root_and_warns(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    _manifest(lote, where="manifest.json", lote="LOTEFICTRAIZ")
    _manifest(lote, where="manifesto/manifest.json", lote="LOTEFICTSUB", ambiente="DEV")

    assert gold_coverage.main([str(lote)]) == 0

    out = capsys.readouterr().out
    assert "LOTEFICTRAIZ" in out and "LOTEFICTSUB" not in out
    assert "AVISO: manifesto em dois caminhos: usado manifest.json" in out
    assert "não é PROD" not in out


def test_json_target_over_root_manifest_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    _manifest(lote, where="manifest.json")
    original = (lote / "manifest.json").read_bytes()

    _refused(lote, lote / "manifest.json", capsys)
    assert (lote / "manifest.json").read_bytes() == original


def test_manifest_outside_prod_is_flagged(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    _manifest(lote, ambiente="DEV")

    assert gold_coverage.main([str(lote)]) == 0

    assert "AVISO: ambiente do manifesto não é PROD: DEV" in capsys.readouterr().out


def test_manifest_with_divergent_table_list_is_flagged(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    exported = [t for t in gold_coverage.TABLES if t != "fila_inspecao"] + ["tabela_ficticia"]
    _manifest(lote, tabelas_exportadas=exported)

    assert gold_coverage.main([str(lote)]) == 0

    out = capsys.readouterr().out
    assert "AVISO: tabelas_exportadas não batem" in out
    assert "faltam no manifesto ['fila_inspecao']" in out
    assert "só no manifesto ['tabela_ficticia']" in out


def test_manifest_listing_seven_tables_with_one_missing_is_flagged(tmp_path):
    lote = tmp_path / "lote"
    _batch(lote)  # cinco tabelas: faltam variacao_consumo_uc e indicadores_dec_fec
    _manifest(lote)

    avisos = gold_coverage.build_report(lote)["manifesto"]["avisos"]

    assert len(avisos) == 1 and "encontradas 5 de 7" in avisos[0]


def test_json_target_inside_manifest_folder_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _seven_tables(lote)
    _manifest(lote)
    original = (lote / "manifesto" / "manifest.json").read_bytes()

    _refused(lote, lote / "manifesto" / "manifest.json", capsys)
    assert (lote / "manifesto" / "manifest.json").read_bytes() == original


def test_json_target_with_missing_parent_is_refused(tmp_path, capsys):
    lote = tmp_path / "lote"
    _batch(lote)

    # Antes, o lote inteiro era lido e a gravação terminava em traceback (FileNotFoundError).
    with pytest.raises(SystemExit) as error:
        gold_coverage.main([str(lote), "--json", str(tmp_path / "nao_existe" / "out.json")])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "diretório de destino não existe" in captured.err
    assert captured.out == ""
    assert not (tmp_path / "nao_existe").exists()


@pytest.mark.parametrize(("flag", "value", "rating"), [
    ("_nota_invalida", "true", "4"), ("_nota_negativa", "true", "0"),
    ("_nota_invalida", "maybe", ""),
])
def test_c14_quality_flags_cannot_contradict_a_published_rating(tmp_path, flag, value, rating):
    _c14(tmp_path, ("1", "0", "0"), (rating, "", ""))
    _write(tmp_path, "atendimentos_uc", ["protocolo", "id_uc", "nota_satisfacao", flag],
           [["A", UC_IDS[0], rating, value]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check["estado"] == "nao_verificavel"


def test_c14_test_uc_is_outside_the_allowed_population(tmp_path):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [["A", "TESTE001", "", ""]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check == {"estado": "nao_verificavel", "inconsistencias": {"uc_teste": 1}}


@pytest.mark.parametrize("case", ["duplicate_summary", "missing_protocol", "short_row"])
def test_c14_malformed_or_duplicate_input_cannot_pass(tmp_path, case):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [] if case == "duplicate_summary" else
                        [["" if case == "missing_protocol" else "A", UC_IDS[0], "", ""]])
    if case == "duplicate_summary":
        path = tmp_path / "visao_360_uc" / "visao_360_uc.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    elif case == "short_row":
        path = tmp_path / "atendimentos_uc" / "atendimentos_uc.csv"
        path.write_text(path.read_text(encoding="utf-8").rsplit(";", 1)[0], encoding="utf-8")
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"][
        "atendimento_protocolos_x_visao_360"]
    assert check["estado"] == "nao_verificavel"


@pytest.mark.parametrize(("state", "zero", "expected"), [
    ("FECHADO", "true", True), ("PARCIAL", "false", False),
    ("AUSENTE", "false", False), ("NAO_CERTIFICADA", "false", False),
])
def test_c15_does_not_infer_certified_zero_from_missing_events(tmp_path, state, zero, expected):
    _c14(tmp_path, ("0", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [])
    _write(tmp_path, "cobertura_dominios", ["dominio", "competencia", "recorte",
           "estado_cobertura", "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado"],
           [["atendimentos", "2025-01", "DOMINIO", state, "0", "0", zero]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"]["atendimento_mensal_c15"]
    assert check["estado"] == "verificada" and check["consistente"] is True
    assert check["meses_zero_confirmado"] == int(expected)
    assert check["meses_por_estado"] == {state: 1}


def test_c15_counts_undated_events_without_assigning_a_month(tmp_path):
    _c14(tmp_path, ("1", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [["A", UC_IDS[0], "", ""]])
    _write(tmp_path, "cobertura_dominios", ["dominio", "competencia", "recorte",
           "estado_cobertura", "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado"],
           [["atendimentos", "2025-01", "DOMINIO", "FECHADO", "0", "1", "true"]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"]["atendimento_mensal_c15"]
    assert check["consistente"] is False
    assert check["meses_zero_confirmado"] == 0


@pytest.mark.parametrize(("state", "count", "zero", "consistent"), [
    ("FECHADO", "1", "false", True), ("PARCIAL", "1", "false", True),
    ("AUSENTE", "1", "false", False), ("FECHADO", "0", "true", False),
])
def test_c15_reconciles_opening_month_and_declared_count(tmp_path, state, count, zero, consistent):
    _c14(tmp_path, ("1", "0", "0"), ("0", "", ""))
    _attendance_details(tmp_path, [["A", UC_IDS[0], "0", "2025-01-31T23:59:59Z"]])
    _write(tmp_path, "cobertura_dominios", ["dominio", "competencia", "recorte",
           "estado_cobertura", "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado"],
           [["atendimentos", "2025-01", "DOMINIO", state, count, "0", zero]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"]["atendimento_mensal_c15"]
    assert check["consistente"] is consistent


@pytest.mark.parametrize("case", ["missing", "duplicate", "bad_month", "bad_count", "bad_date"])
def test_c15_invalid_or_missing_coverage_never_passes(tmp_path, case):
    _c14(tmp_path, ("1", "0", "0"), ("", "", ""))
    _attendance_details(tmp_path, [["A", UC_IDS[0], "",
                                  "invalid" if case == "bad_date" else "2025-01-01T00:00:00Z"]])
    if case != "missing":
        row = ["atendimentos", "2025-13" if case == "bad_month" else "2025-01", "DOMINIO",
               "FECHADO", "1.5" if case == "bad_count" else "1", "0", "false"]
        _write(tmp_path, "cobertura_dominios", ["dominio", "competencia", "recorte",
               "estado_cobertura", "qtd_registros", "qtd_sem_competencia",
               "zero_registros_confirmado"], [row, row] if case == "duplicate" else [row])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"]["atendimento_mensal_c15"]
    assert check["estado"] == "nao_verificavel"


@pytest.mark.parametrize(("opening", "flag", "expected_state"), [
    ("2025-02-01T01:00:00+02:00", "false", "verificada"),
    ("2025-01-01T00:00:00Z", "true", "nao_verificavel"),
    ("2025-01-01T00:00:00Z", "invalid", "nao_verificavel"),
])
def test_c15_uses_utc_month_and_checks_opening_flags(tmp_path, opening, flag, expected_state):
    _c14(tmp_path, ("1", "0", "0"), ("", "", ""))
    _write(tmp_path, "atendimentos_uc", ["protocolo", "id_uc", "nota_satisfacao",
           "data_abertura", "_abertura_futura"], [["A", UC_IDS[0], "", opening, flag]])
    _write(tmp_path, "cobertura_dominios", ["dominio", "competencia", "recorte",
           "estado_cobertura", "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado"],
           [["atendimentos", "2025-01", "DOMINIO", "FECHADO", "1", "0", "false"]])
    check = gold_coverage.build_report(tmp_path)["reconciliacoes"]["atendimento_mensal_c15"]
    assert check["estado"] == expected_state
    if expected_state == "verificada":
        assert check["consistente"] is True


@pytest.mark.parametrize("table", ["atendimentos_uc", "cobertura_dominios", "manifest"])
def test_json_hard_link_to_new_control_inputs_is_refused(tmp_path, capsys, table):
    batch = tmp_path / "lote"
    _batch(batch)
    if table == "manifest":
        source = batch / "manifest.json"
        source.write_text("{}", encoding="utf-8")
    else:
        _write(batch, table, ["coluna"], [["preservar"]])
        source = batch / table / (table + ".csv")
    original = source.read_bytes()
    target = tmp_path / "external.json"
    try:
        os.link(source, target)
    except OSError:
        pytest.skip("o sistema não permite criar hard link")
    _refused(batch, target, capsys)
    assert source.read_bytes() == original
