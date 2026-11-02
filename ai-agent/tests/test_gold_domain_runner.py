"""GENAI-10A: funções puras e modo --dry-run do runner da matriz (sem rede nem banco)."""

import copy
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_gold_domain_scenarios.py"
_spec = importlib.util.spec_from_file_location("run_gold_domain_scenarios", SCRIPT)
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_gold_domain_scenarios"] = runner
_spec.loader.exec_module(runner)

MATRIX = runner.load_json(runner.DEFAULT_MATRIX)
CATALOG = runner.load_json(runner.CATALOG_PATH)


@pytest.mark.parametrize("text,expected", [
    ("A receita foi de R$ 1.234,56.", Decimal("1234.56")),
    ("Foram 1,234,567.89 kWh", Decimal("1234567.89")),
    ("DEC de 0,05 horas por UC", Decimal("0.05")),
    ("12 R$ em março", Decimal("12")),
    ("valor 12.0", Decimal("12.0")),
    ("Total: 1.234 protocolos", Decimal("1234")),
])
def test_numbers_are_read_in_brazilian_and_english_notation(text, expected):
    assert expected in runner.parse_numbers(text)


def test_answer_without_numbers_yields_nothing():
    assert runner.parse_numbers("Não há evidência para o recorte.") == []
    assert runner.parse_numbers(None) == []


@pytest.mark.parametrize("text,wrong", [
    ("80,00", Decimal(8000)),
    ("-4.17", Decimal(-417)),
    ("1234.56", Decimal(123456)),
])
def test_decimal_separator_cannot_be_removed_to_match_a_wrong_value(text, wrong):
    assert wrong not in runner.parse_numbers(text)


@pytest.mark.parametrize("value,decimals,expected", [
    (Decimal("1.005"), 2, Decimal("1.00")),
    (Decimal("1.015"), 2, Decimal("1.02")),
    (0.123456, 4, Decimal("0.1235")),
    (3, 0, Decimal("3")),
])
def test_control_values_use_catalog_half_even_rounding(value, decimals, expected):
    assert runner.rounded(value, decimals) == expected


def test_named_parameters_become_psycopg_placeholders_without_touching_literals():
    sql = "SELECT to_char(x, 'YYYY-MM') FROM t WHERE a = :competencia AND b::text = :municipio"
    converted = runner.to_pyformat(sql)
    assert "%(competencia)s" in converted and "%(municipio)s" in converted
    assert "b::text" in converted and "'YYYY-MM'" in converted
    assert runner.to_pyformat("SELECT '10%' AS x") == "SELECT '10%%' AS x"


@pytest.mark.parametrize("http,body,expected", [
    (200, {"status": "answered"}, "answered"),
    (200, {"status": "recoverable_error"}, "recoverable_error"),
    (403, {"status": "error", "error": {"code": "access_denied"}}, "error:access_denied"),
    (503, {"status": "error", "error": {"code": "service_unavailable"}},
     "error:service_unavailable"),
    (502, None, "error:transport"),
])
def test_observed_status_uses_public_envelope(http, body, expected):
    assert runner.observed_status(http, body) == expected


def test_expected_status_accepts_documented_alternatives():
    assert runner.status_matches("answered|needs_clarification", "needs_clarification")
    assert runner.status_matches("error:service_unavailable|recoverable_error", "recoverable_error")
    assert not runner.status_matches("needs_clarification", "answered")


def test_names_are_compared_without_accents_or_case():
    published = "JABOATAO DOS GUARARAPES"
    assert runner.normalize("Jaboatão  dos Guararapes") == runner.normalize(published)


class PeriodDatabase:
    def __init__(self, month):
        self.month = month

    def fetch_all(self, name, sql, params):
        return [{"competencia": self.month}]


@pytest.mark.parametrize("rule,month,expected", [
    ("ULTIMA_COMPETENCIA_RECEITA", "2000-03",
     {"competencia": "2000-03", "mes_extenso": "março", "ano": "2000"}),
    ("COMPETENCIA_APOS_ULTIMA", "2000-12",
     {"competencia": "2001-01", "mes_extenso": "janeiro", "ano": "2001"}),
    ("ULTIMO_TRIMESTRE_RECEITA", "2000-02", {"inicio": "1999-12", "fim": "2000-02"}),
    ("ANO_CORRENTE_PARCIAL", "2000-05", {"inicio": "2000-01", "fim": "2000-05"}),
])
def test_period_rules_are_derived_from_the_latest_published_month(rule, month, expected):
    assert runner.resolve_period(MATRIX, rule, PeriodDatabase(month), {}) == expected


def test_year_over_year_pair_and_complete_year_without_partial_period():
    pair = runner.resolve_period(MATRIX, "PAR_ANO_A_ANO_RECEITA", PeriodDatabase("2000-03"), {})
    assert (pair["p0"], pair["p1"], pair["mes_p0"], pair["ano_p1"]) == (
        "1999-03", "2000-03", "março", "2000")
    with pytest.raises(runner.NoSample):
        runner.resolve_period(MATRIX, "ANO_CORRENTE_PARCIAL", PeriodDatabase("2000-12"), {})


def test_missing_latest_month_is_a_missing_sample():
    class Empty:
        def fetch_all(self, name, sql, params):
            return [{"competencia": None}]

    with pytest.raises(runner.NoSample):
        runner.resolve_period(MATRIX, "ULTIMA_COMPETENCIA_DEC_FEC", Empty(), {})


def test_versioned_matrix_is_executable_for_the_runner():
    assert runner.validate_matrix(MATRIX, CATALOG) == {}


def test_validation_rejects_numeric_case_without_control_sql():
    broken = copy.deepcopy(MATRIX)
    broken["controles"]["C04"]["sql"] = None
    errors = runner.validate_matrix(broken, CATALOG)
    assert "caso numérico sem SQL de controle" in errors["FAT-01"]


def test_validation_rejects_unknown_period_rule_and_unresolved_placeholder():
    broken = copy.deepcopy(MATRIX)
    case = next(item for item in broken["casos"] if item["id"] == "FAT-03")
    case["pergunta"] += " {bairro}"
    broken["regras_periodo"]["REGRA_NOVA"] = {"descricao": "x", "sql": None}
    ambiguous = next(item for item in broken["casos"] if item["id"] == "AMB-01")
    ambiguous["periodo"]["regra"] = "REGRA_NOVA"
    errors = runner.validate_matrix(broken, CATALOG)
    assert any("marcadores sem origem" in item for item in errors["FAT-03"])
    assert any("sem implementação" in item for item in errors["AMB-01"])


def test_output_must_stay_inside_ignored_work_directory(tmp_path):
    assert runner.safe_output_dir(runner.WORK_ROOT / "genai10a").is_relative_to(runner.WORK_ROOT)
    with pytest.raises(ValueError):
        runner.safe_output_dir(tmp_path)
    with pytest.raises(ValueError):
        runner.safe_output_dir(runner.REPO_ROOT / "docs")


def test_backend_url_with_credentials_is_refused():
    with pytest.raises(ValueError):
        runner.HttpFlowClient("http://leitor:segredo@backend:8000", "http://localhost:5173")


def test_dry_run_validates_all_cases_without_network(capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run não pode abrir conexão")

    monkeypatch.setattr(runner, "HttpFlowClient", forbidden)
    monkeypatch.setattr(runner, "PsycopgControlDatabase", forbidden)
    assert runner.main(["--dry-run"], environ={}) == 0
    output = capsys.readouterr().out
    assert output.count(" OK\n") == len(MATRIX["casos"])
    assert "SELECT" not in output


def test_dry_run_reports_broken_matrix(tmp_path, capsys):
    broken = copy.deepcopy(MATRIX)
    broken["controles"]["C04"]["sql"] = None
    path = tmp_path / "matriz.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    assert runner.main(["--dry-run", "--matrix", str(path)], environ={}) == 1
    assert "FAT-01 ERRO" in capsys.readouterr().out


def test_missing_configuration_lists_only_variable_names(capsys, monkeypatch):
    monkeypatch.setattr(runner, "HttpFlowClient", lambda *a, **k: pytest.fail("sem rede"))
    environ = {"GENAI10A_BACKEND_URL": "http://backend:8000", "GENAI10A_PASSWORD": "segredo-x"}
    assert runner.main([], environ=environ) == 2
    output = capsys.readouterr().out
    assert "GENAI10A_USERNAME" in output and "GENAI10A_CONTROL_DSN" in output
    assert "segredo-x" not in output and "backend:8000" not in output


def test_unknown_ids_and_output_outside_work_are_configuration_errors(tmp_path, capsys):
    assert runner.main(["--dry-run", "--ids", "XYZ-99"], environ={}) == 2
    assert runner.main(["--dry-run", "--output-dir", str(tmp_path)], environ={}) == 2
    assert "Configuração inválida" in capsys.readouterr().out


@pytest.mark.parametrize("rule,params,period,expected", [
    ("ULTIMA_COMPETENCIA_RECEITA", {"competencia": "2000-02"},
     "2000-02-01 a 2000-02-29", True),
    ("ULTIMO_TRIMESTRE_RECEITA", {"inicio": "2000-01", "fim": "2000-03"},
     "2000-01-01 a 2000-03-31", True),
    ("ULTIMO_TRIMESTRE_RECEITA", {"inicio": "2000-01", "fim": "2000-03"},
     "março de 2000", False),
    ("HISTORICO_ACUMULADO", {}, "histórico acumulado", True),
    ("HISTORICO_ACUMULADO", {}, "março de 2000", False),
])
def test_resolved_period_must_match_public_context(rule, params, period, expected):
    assert runner.period_matches({"periodo": {"regra": rule}}, period, params) is expected
