"""GENAI-10A: runner contra servidor HTTP e banco de controle sintéticos.

Usa a matriz versionada, o cliente HTTP real do runner (``httpx.MockTransport`` no lugar da rede)
e um banco que responde às regras/controles pelo nome. Nenhum dado do lote é usado.
"""

import copy
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_gold_domain_scenarios.py"
_spec = importlib.util.spec_from_file_location("run_gold_domain_scenarios_it", SCRIPT)
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_gold_domain_scenarios_it"] = runner
_spec.loader.exec_module(runner)

MATRIX = runner.load_json(runner.DEFAULT_MATRIX)
CATALOG = runner.load_json(runner.CATALOG_PATH)
CASES = {case["id"]: case for case in MATRIX["casos"]}
PASSWORD = "senha-sintetica-nao-publicar"
ORIGIN = "http://portal.sintetico"
MUNICIPALITIES = [{"municipio": "Recife"}, {"municipio": "Olinda"},
                  {"municipio": "JABOATAO DOS GUARARAPES"}]


class SyntheticDatabase:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch_all(self, name, sql, params):
        self.calls.append((name, sql, dict(params)))
        response = self.responses[name]
        return response(params) if callable(response) else copy.deepcopy(response)

    def close(self):
        pass


def answered(answer, metric, filters, unit, *, is_demo=False, period="março de 2000"):
    return 200, {
        "contract_version": "v1", "correlation_id": "a" * 32,
        "audit_reference": "referencia-sintetica", "status": "answered", "answer": answer,
        "message": None, "error": None,
        "evidence": [{"source": "gold.local", "description": "Evidência sintética.",
                      "is_demo": is_demo}],
        "limitations": [],
        "analysis_context": {"metric": metric, "unit": unit, "period": period,
                             "filters": filters},
    }


def status(state, code=None, http=200):
    body = {"contract_version": "v1", "correlation_id": "a" * 32, "status": state,
            "message": "Mensagem sintética.", "answer": None, "evidence": []}
    if code:
        body["error"] = {"code": code, "retryable": False}
    return http, body


def server(reply, *, seen=None):
    """Exige login JSON com Origin e o cookie de sessão na pergunta."""
    def handler(request):
        if request.headers.get("origin") != ORIGIN:
            return httpx.Response(403, json={"detail": "origem"})
        if request.url.path == "/api/v1/auth/login":
            assert json.loads(request.content)["password"] == PASSWORD
            return httpx.Response(200, json={"enabled": True},
                                  headers={"set-cookie": "grid360_session=s1; Path=/api/v1"})
        assert request.url.path == "/api/v1/ai/questions"
        assert "grid360_session=s1" in request.headers.get("cookie", "")
        payload = json.loads(request.content)
        if seen is not None:
            seen.append(payload)
        code, body = reply(payload)
        return httpx.Response(code, json=body)
    return httpx.MockTransport(handler)


def client(reply, **kwargs):
    flow = runner.HttpFlowClient("http://backend.sintetico", ORIGIN,
                                 transport=server(reply, **kwargs))
    flow.login("leitor", PASSWORD)
    return flow


def revenue_database(**overrides):
    responses = {
        "periodo:ULTIMA_COMPETENCIA_RECEITA": [{"competencia": "2000-03"}],
        "amostra:MUNICIPIO_DO_CASE": MUNICIPALITIES,
        "amostra:MUNICIPIO_MAIOR_RECEITA": [{"municipio": "Recife"}],
        "controle:C04": [{"municipio": "Recife", "valor": Decimal("1234.567"),
                          "consumo_kwh": Decimal("10")}],
    }
    responses.update(overrides)
    return SyntheticDatabase(responses)


def run(case_id, flow, db, *, matrix=MATRIX, denied=None):
    return runner.run_case(matrix, CATALOG, matrix_case(matrix, case_id), flow, db, {}, denied)


def matrix_case(matrix, case_id):
    return next(case for case in matrix["casos"] if case["id"] == case_id)


REVENUE_OK = answered("A receita faturada em Recife em março de 2000 foi de R$ 1.234,57.",
                      "billing.revenue", {"geography.municipality": "Recife"}, "R$")


def test_numeric_case_passes_and_uses_the_independent_control_with_resolved_scope():
    seen = []
    db = revenue_database()
    outcome = run("FAT-01", client(lambda payload: REVENUE_OK, seen=seen), db)
    assert outcome.classe == "PASS" and outcome.divergencias == []
    assert outcome.valores_esperados == ["1234.57"]
    assert seen == [{
        "question": "Qual foi a receita faturada no município de Recife em março de 2000?",
        "context": [],
    }]
    name, sql, params = db.calls[-1]
    assert name == "controle:C04" and sql == MATRIX["controles"]["C04"]["sql"]
    assert params == {"competencia": "2000-03"}


@pytest.mark.parametrize("reply,divergence", [
    (answered("Foi de R$ 1.240,00.", "billing.revenue",
              {"geography.municipality": "Recife"}, "R$"), "numero"),
    (answered("Foi de R$ 1.234,57.", "billing.revenue",
              {"geography.municipality": "Olinda"}, "R$"), "plano"),
    (answered("Foi de R$ 1.234,57.", "energy.consumption",
              {"geography.municipality": "Recife"}, "R$"), "interpretacao"),
    (answered("Foi de R$ 1.234,57.", "billing.revenue",
              {"geography.municipality": "Recife"}, "R$", is_demo=True), "fundamentacao"),
    (status("needs_clarification"), "recusa"),
], ids=["numero", "plano", "interpretacao", "fundamentacao", "estado"])
def test_numeric_divergences_are_classified_by_type(reply, divergence):
    outcome = run("FAT-01", client(lambda payload: reply), revenue_database())
    assert outcome.classe == "FAIL"
    assert divergence in outcome.divergencias


def test_series_case_requires_every_month_of_the_window():
    rows = [{"competencia": "2000-01", "valor": Decimal("10")},
            {"competencia": "2000-02", "valor": Decimal("20")},
            {"competencia": "2000-03", "valor": Decimal("30.5")}]
    db = revenue_database(**{"controle:CTL-FAT-MUN-CLASSE-JANELA": rows})
    filters = {"geography.municipality": "Jaboatão dos Guararapes",
               "customer.consumption_class": "COMERCIAL"}
    full = answered("Janeiro R$ 10,00; fevereiro R$ 20,00; março R$ 30,50.",
                    "billing.revenue", filters, "R$", period="2000-01-01 a 2000-03-31")
    partial = answered("Janeiro R$ 10,00; março R$ 30,50.", "billing.revenue", filters, "R$",
                       period="2000-01-01 a 2000-03-31")
    assert run("FAT-02", client(lambda payload: full), db).classe == "PASS"
    outcome = run("FAT-02", client(lambda payload: partial), db)
    assert outcome.classe == "FAIL" and "numero" in outcome.divergencias
    # A grafia publicada do município é a usada no controle, sem acento imposto pela matriz.
    assert db.calls[-1][2]["municipio"] == "JABOATAO DOS GUARARAPES"
    assert (db.calls[-1][2]["inicio"], db.calls[-1][2]["fim"]) == ("2000-01", "2000-03")


def feeder_database():
    return SyntheticDatabase({
        "periodo:ULTIMA_COMPETENCIA_DEC_FEC": [{"competencia": "2000-03"}],
        "amostra:MUNICIPIO_DO_CASE": MUNICIPALITIES,
        "amostra:ALIMENTADOR_MAIOR_DEC": [{"alimentador": "AL-SINTETICO"}],
    })


def test_blocked_case_with_expected_unavailability_is_blocked_not_pass():
    reply = status("error", "service_unavailable", http=503)
    db = feeder_database()
    outcome = run("INT-01", client(lambda payload: reply), db)
    assert outcome.classe == "BLOQUEADO"
    assert not any(name.startswith("controle:") for name, _, _ in db.calls)


@pytest.mark.parametrize("case_id", ["INT-01", "FAT-07", "SEG-01"])
def test_numeric_answer_where_state_is_expected_fails(case_id):
    reply = answered("Foi de 3,5.", "billing.revenue", {}, "R$")
    db = feeder_database() if case_id == "INT-01" else revenue_database()
    outcome = run(case_id, client(lambda payload: reply), db)
    assert outcome.classe == "FAIL" and "recusa" in outcome.divergencias


@pytest.mark.parametrize("case_id,reply", [
    ("FAT-07", status("needs_clarification")),
    ("SEG-01", status("refused", "policy_refusal")),
    ("AMB-01", status("needs_clarification")),
])
def test_expected_clarification_and_refusal_pass(case_id, reply):
    assert run(case_id, client(lambda payload: reply), revenue_database()).classe == "PASS"


def test_access_denied_needs_dedicated_account():
    allowed = client(lambda payload: REVENUE_OK)
    outcome = run("SEG-05", allowed, revenue_database())
    assert outcome.classe == "NAO_EXECUTADO" and "GENAI10A_DENIED_USERNAME" in outcome.motivo
    denied = client(lambda payload: status("error", "access_denied", http=403))
    assert run("SEG-05", allowed, revenue_database(), denied=denied).classe == "PASS"


def test_technical_regression_cases_are_listed_as_not_executed():
    outcome = run("SEG-06", None, None)
    assert outcome.classe == "NAO_EXECUTADO"
    assert "genai_failure_matrix.py" in outcome.motivo


def test_missing_sample_is_pending_and_never_pass():
    db = revenue_database(**{"amostra:RECORTE_RECEITA_ZERO": []})
    outcome = run("FAT-12", client(lambda payload: REVENUE_OK), db)
    assert outcome.classe == "SEM_AMOSTRA_NO_LOTE"


def test_control_pointing_to_another_scope_fails_instead_of_comparing():
    db = revenue_database(**{"controle:C04": [{"municipio": "Olinda", "valor": 1}]})
    outcome = run("FAT-01", client(lambda payload: REVENUE_OK), db)
    assert outcome.classe == "FAIL" and outcome.status_observado is None


def test_infrastructure_error_is_reported_without_leaking_details():
    def broken(params):
        raise RuntimeError("postgresql://leitor:segredo@banco/privado")

    outcome = run("FAT-01", client(lambda payload: REVENUE_OK),
                  revenue_database(**{"amostra:MUNICIPIO_MAIOR_RECEITA": broken}))
    assert outcome.classe == "NAO_EXECUTADO" and outcome.erro_execucao
    assert outcome.motivo == "erro de execução: RuntimeError"


def test_known_failures_are_separated_from_unexpected_ones():
    matrix = copy.deepcopy(MATRIX)
    matrix["criterios_regressao"]["falhas_conhecidas"] = [
        {"id": "FAT-01", "motivo": "divergência sintética", "dono": "10B"}]
    wrong = answered("Foi de R$ 9,00.", "billing.revenue",
                     {"geography.municipality": "Recife"}, "R$")
    known = run("FAT-01", client(lambda payload: wrong), revenue_database(), matrix=matrix)
    unexpected = run("FAT-01", client(lambda payload: wrong), revenue_database())
    assert (known.classe, unexpected.classe) == ("FALHA_CONHECIDA", "FAIL")
    summary = runner.summarize(matrix, [known])
    assert summary["falhas_conhecidas"] == ["FAT-01"] and summary["falhas_inesperadas"] == []
    assert summary["dominios"]["faturamento"]["coberto"] is False


def test_domain_is_covered_only_when_every_mandatory_case_passes():
    passed = runner.Outcome("FAT-01", "faturamento", True, classe="PASS")
    blocked = runner.Outcome("FAT-09", "faturamento", True, classe="BLOQUEADO")
    optional = runner.Outcome("AMB-05", "ambiguidade_limites", False, classe="FAIL")
    summary = runner.summarize(MATRIX, [passed, blocked, optional])
    pending = summary["dominios"]["faturamento"]["obrigatorios_fora_de_pass"]
    assert pending == [f"FAT-{i:02d}" for i in range(2, 18)]
    assert summary["dominios"]["faturamento"]["coberto"] is False
    assert "faturamento" in summary["dominios_obrigatorios_pendentes"]
    # Caso opcional em falha continua sendo falha inesperada; não some do relatório.
    assert summary["falhas_inesperadas"] == ["AMB-05"]
    assert runner.summarize(MATRIX, [passed])["dominios"]["faturamento"]["coberto"] is False


def test_main_runs_end_to_end_and_keeps_values_and_secrets_out_of_stdout(
    tmp_path, monkeypatch, capsys,
):
    real_client = runner.HttpFlowClient

    def reply(payload):
        if "receita faturada" in payload["question"]:
            return REVENUE_OK
        return status("error", "service_unavailable", http=503)

    db = SyntheticDatabase({**revenue_database().responses, **feeder_database().responses})
    monkeypatch.setattr(runner, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(runner, "HttpFlowClient",
                        lambda url, origin: real_client(url, origin, transport=server(reply)))
    monkeypatch.setattr(runner, "PsycopgControlDatabase", lambda dsn: db)
    environ = {
        "GENAI10A_BACKEND_URL": "http://backend.sintetico", "GENAI10A_ORIGIN": ORIGIN,
        "GENAI10A_USERNAME": "leitor", "GENAI10A_PASSWORD": PASSWORD,
        "GENAI10A_CONTROL_DSN": "postgresql://leitor:dsn-secreto@banco/sintetico",
    }
    argv = ["--ids", "FAT-01,INT-01,SEG-06", "--output-dir", str(tmp_path / "genai10a")]
    assert runner.main(argv, environ=environ) == 0
    assert runner.main([*argv, "--strict"], environ=environ) == 3
    output = capsys.readouterr().out
    assert "FAT-01 PASS estado=answered" in output
    assert "INT-01 BLOQUEADO estado=error:service_unavailable" in output
    assert "SEG-06 NAO_EXECUTADO" in output and "faturamento: pendente" in output
    for secret in (PASSWORD, "dsn-secreto", "1234.57", "1.234,57", "Recife", "AL-SINTETICO"):
        assert secret not in output
    runs = sorted((tmp_path / "genai10a").iterdir())
    assert len(runs) == 2
    stored = (runs[0] / "resultados.json").read_text(encoding="utf-8")
    assert '"valores_esperados": [\n      "1234.57"\n    ]' in stored
    for secret in (PASSWORD, "dsn-secreto", "foi de R$", "Mensagem sintética"):
        assert secret not in stored
    assert json.loads((runs[0] / "resumo.json").read_text(encoding="utf-8"))[
        "falhas_inesperadas"] == []


def test_full_execution_requires_approval_before_certifying_domain():
    matrix = copy.deepcopy(MATRIX)
    matrix["casos"] = [matrix_case(matrix, "FAT-01")]
    # Estado artificial explícito: o aceite do lote versionado pode evoluir.
    matrix["casos"][0]["controle"].update(
        estado_do_controle="existente_referenciado", aprovado_por="",
    )
    outcome = runner.Outcome("FAT-01", "faturamento", True, classe="PASS")
    summary = runner.summarize(matrix, [outcome])["dominios"]["faturamento"]
    assert not summary["coberto"]
    assert summary["controles_sem_aprovacao"] == ["FAT-01"]
    matrix["casos"][0]["controle"].update(estado_do_controle="aprovado",
                                          aprovado_por="Revisor sintético")
    assert runner.summarize(matrix, [outcome])["dominios"]["faturamento"]["coberto"]


def test_matching_number_for_wrong_period_fails():
    reply = copy.deepcopy(REVENUE_OK)
    reply[1]["analysis_context"]["period"] = "abril de 2000"
    outcome = run("FAT-01", client(lambda payload: reply), revenue_database())
    assert outcome.classe == "FAIL" and "plano" in outcome.divergencias
