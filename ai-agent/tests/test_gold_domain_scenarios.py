"""GENAI-10A: formato, cobertura e privacidade da matriz única de cenários Gold v2.

A matriz define perguntas, regras de período/amostra, controles independentes e
estados esperados; resultados observados ficam fora do repositório (work/genai10a/).
Contrato: docs/contracts/genai-domain-scenarios.md.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.readiness import V2_CAPABILITY_REQUIREMENTS

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
MATRIX = json.loads((FIXTURES / "gold_domain_scenarios.json").read_text(encoding="utf-8"))
CASES = MATRIX["casos"]
CONTROLS = MATRIX["controles"]

DOMAINS = {"faturamento", "consumo", "interrupcoes", "atendimento",
           "ambiguidade_limites", "protecao_falhas"}
REQUIRED_DOMAINS = {"faturamento", "consumo", "interrupcoes", "atendimento"}
PRD_EXAMPLES = {"residencial_comercial", "competencia_pagamento", "preco_volume",
                "gd_queda", "continuidade", "atendimento"}
CASE_MUNICIPALITIES = {"Recife", "Olinda", "Jaboatão dos Guararapes"}
FICTITIOUS_PLACES = {"Lumenia"}
EXISTING_CONTROLS = {f"C{index:02d}" for index in range(1, 16)}
CONTROL_STATES = {"existente_referenciado", "proposto", "estado_sem_valor", "bloqueado", "aprovado"}
BLOCK_OWNERS = {"Dados", "10B", "11", "12", "lote"}
PLACEHOLDER = re.compile(r"^\{[a-z_0-9]+\}$")
CASE_ID = re.compile(r"^(FAT|CON|INT|ATE|AMB|SEG)-\d{2}$")
CASE_KEYS = {
    "id", "dominio", "obrigatorio", "exemplo_prd", "pergunta", "contexto", "metrica",
    "capacidade", "periodo", "filtros", "amostra", "fonte_lote", "unidade",
    "estado_esperado", "status_publico_esperado", "tipo_verificacao", "controle",
    "tolerancia", "bloqueio", "referencias", "modo_execucao", "observacao",
    "resultado_observado", "referencia_execucao",
}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_header_pins_gold_v2_references():
    assert MATRIX["versao_matriz"] == "gold-domain-scenarios-v1"
    assert MATRIX["referencias"] == {
        "dicionario": "docs/dicionario_gold.md", "contrato_csv": "gold-csv-v2",
        "catalogo": "gold-catalog-v2", "schema_fisico": "gold_v2",
        "perfil": GRID360_GOLD_PROFILE.profile_id, "prontidao": "gold-readiness-v2",
        "documento": "docs/contracts/genai-domain-scenarios.md",
    }
    assert set(MATRIX["dominios_obrigatorios"]) == REQUIRED_DOMAINS
    assert (ROOT / MATRIX["referencias"]["documento"]).is_file()


def test_case_ids_are_unique_and_well_formed():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    assert all(CASE_ID.match(case_id) for case_id in ids)
    assert all(set(case) == CASE_KEYS for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_case_references_resolve(case):
    assert case["dominio"] in DOMAINS
    assert case["estado_esperado"] in MATRIX["estados_esperados"]
    assert case["tolerancia"] in MATRIX["tolerancias"]
    assert case["periodo"]["regra"] in MATRIX["regras_periodo"]
    assert case["amostra"] is None or case["amostra"] in MATRIX["regras_amostra"]
    assert set(case["tipo_verificacao"]) <= set(MATRIX["tipos_divergencia"])
    assert case["modo_execucao"] in {"fluxo_integrado", "regressao_tecnica"}
    metrics = {metric.id for metric in GRID360_GOLD_PROFILE.metrics}
    dimensions = {dimension.id for dimension in GRID360_GOLD_PROFILE.dimensions}
    capabilities = {item.id for item in V2_CAPABILITY_REQUIREMENTS}
    assert case["metrica"] is None or case["metrica"] in metrics
    assert case["capacidade"] is None or case["capacidade"] in capabilities
    assert all(item["dimensao"] in dimensions for item in case["filtros"])
    table = case["fonte_lote"]["tabela"]
    assert table is None or table.startswith("gold_v2.")
    for turn in case["contexto"]:
        assert set(turn) == {"role", "content"} and turn["role"] in {"user", "assistant"}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_control_state_and_approval_fields(case):
    control = case["controle"]
    assert set(control) == {"ref", "estado_do_controle", "aprovado_por"}
    assert control["estado_do_controle"] in CONTROL_STATES
    assert isinstance(control["aprovado_por"], str)
    # Aprovação é registrada pela pessoa usuária; até lá o campo fica vazio.
    assert (control["estado_do_controle"] == "aprovado") == bool(control["aprovado_por"])
    if control["ref"] is None:
        assert control["estado_do_controle"] in {"estado_sem_valor", "bloqueado", "aprovado"}
        return
    assert control["ref"] in CONTROLS
    kind = CONTROLS[control["ref"]]["tipo"]
    expected = "existente_referenciado" if kind == "existente" else "proposto"
    assert control["estado_do_controle"] in {expected, "aprovado"}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_numeric_cases_have_control_unit_and_numeric_tolerance(case):
    numeric = "numero" in case["tipo_verificacao"]
    integrated = case["modo_execucao"] == "fluxo_integrado"
    if case["estado_esperado"] in {"sucesso", "zero"} and integrated:
        assert numeric, "estado numérico exige verificação de número"
    if numeric:
        assert case["controle"]["ref"] is not None
        assert case["unidade"] and case["fonte_lote"]["tabela"]
        assert MATRIX["tolerancias"][case["tolerancia"]]["absoluta"] is not None
        runner = case["referencias"].get("consulta_runner", case["controle"]["ref"])
        assert CONTROLS[runner]["sql"], "o runner precisa de SQL para o número esperado"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_blocked_cases_name_reason_owner_and_current_state(case):
    block = case["bloqueio"]
    if case["estado_esperado"] == "bloqueado":
        assert block is not None
    if block is None:
        return
    assert set(block) == {"motivo", "dono", "estado_publico_atual", "pergunta_dados"}
    assert block["motivo"] and block["dono"] in BLOCK_OWNERS
    allowed = {state["status_publico"] for state in MATRIX["estados_esperados"].values()}
    assert block["estado_publico_atual"] in allowed | {
        "needs_clarification", "error:service_unavailable", "error:access_denied", "refused",
    }
    assert block["pergunta_dados"] is None or block["dono"] == "Dados"


def test_minimum_coverage_per_required_domain():
    by_domain = {domain: [case for case in CASES if case["dominio"] == domain]
                 for domain in DOMAINS}
    for domain in REQUIRED_DOMAINS:
        cases = by_domain[domain]
        assert len(cases) >= 5, domain
        assert any(case["obrigatorio"] and case["controle"]["ref"] for case in cases), domain
        assert {case["estado_esperado"] for case in cases} - {"bloqueado"}, domain
    # Domínios sem número executável ainda precisam de caso com estado-alvo explícito.
    for domain in ("interrupcoes", "atendimento"):
        assert any(case["estado_esperado"] == "bloqueado" and case["controle"]["ref"]
                   for case in by_domain[domain])
    for domain in ("faturamento", "consumo"):
        assert any(case["estado_esperado"] == "sucesso" and case["controle"]["ref"]
                   for case in by_domain[domain])


def test_every_expected_state_and_group_is_represented():
    states = Counter(case["estado_esperado"] for case in CASES)
    assert set(MATRIX["estados_esperados"]) <= set(states)
    assert {case["dominio"] for case in CASES} >= DOMAINS


def test_prd_business_examples_are_all_present():
    assert {case["exemplo_prd"] for case in CASES if case["exemplo_prd"]} >= PRD_EXAMPLES
    assert {case["exemplo_prd"] for case in CASES} <= PRD_EXAMPLES | {None}


def test_dimension_values_are_case_municipalities_or_runtime_placeholders():
    for case in CASES:
        for item in case["filtros"]:
            value = item["valor"]
            if PLACEHOLDER.match(value):
                assert case["amostra"] is not None, case["id"]
            elif item["dimensao"] == "geography.municipality":
                assert value in CASE_MUNICIPALITIES | FICTITIOUS_PLACES, case["id"]
            elif item["dimensao"] in {"geography.neighborhood", "network.feeder",
                                      "customer.consumer_unit"}:
                pytest.fail(f"{case['id']}: bairro, alimentador e UC vêm de regra de amostra")
            else:
                assert value in {"COMERCIAL", "RESIDENCIAL", "Sim", "Não"}, case["id"]


def test_matrix_contains_no_batch_values_or_observed_results():
    for case in CASES:
        assert case["resultado_observado"] is None
        assert case["referencia_execucao"] is None
    text = "\n".join(_strings(MATRIX))
    assert not re.search(r"GOLD_\d{8}T\d{6}Z_[0-9a-f]{8}", text)
    uuid4 = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    assert not re.search(uuid4, text)
    assert not re.search(r"\b(19|20)\d{2}-(0[1-9]|1[0-2])\b", text), "competência literal"
    for case in CASES:
        question = " ".join([case["pergunta"], *(t["content"] for t in case["contexto"])])
        assert not re.search(r"\b(19|20)\d{2}\b", question), case["id"]
        assert not re.search(r"\d+[.,]\d+", question), case["id"]


def test_sql_controls_are_read_only_parameterized_and_gold_v2_only():
    used = set()
    for case in CASES:
        used.add(case["controle"]["ref"])
        used.add(case["referencias"].get("consulta_runner"))
    for control_id, control in CONTROLS.items():
        if control["tipo"] == "existente":
            assert control_id in EXISTING_CONTROLS
            assert control["sql"] is None and control["aprovacao_registrada"]
            continue
        assert control_id.startswith("CTL-") and control_id in used, control_id
        sql = control["sql"]
        assert re.match(r"^(SELECT|WITH)\b", sql)
        assert ";" not in sql
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|TRUNCATE|COPY)\b",
                             sql, re.IGNORECASE)
        tables = set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_0-9.]+)", sql, re.IGNORECASE))
        tables -= {"m", "b", "x"}
        assert tables and all(table.startswith("gold_v2.") for table in tables), control_id
        assert "gold_cadastro" not in sql
        assert set(re.findall(r":([a-z_0-9]+)", sql)) == set(control["parametros"]), control_id
        assert set(control["relacionados"]) <= EXISTING_CONTROLS
    for rule in [*MATRIX["regras_periodo"].values(), *MATRIX["regras_amostra"].values()]:
        if rule.get("sql"):
            assert re.match(r"^SELECT\b", rule["sql"]) and ";" not in rule["sql"]
            assert "gold_v2." in rule["sql"]


def test_existing_controls_are_referenced_by_id_with_documented_approval():
    referenced = {case["controle"]["ref"] for case in CASES} | {
        ref for case in CASES for ref in case["referencias"].get("existentes", [])
    }
    assert {"C04", "C11", "C14", "C15"} <= referenced
    assert {"C01", "C02", "C08", "C10", "C12", "C13"} <= referenced
    local = {"C01", "C02", "C03", "C04", "C10", "C11", "C12", "C13", "C14", "C15"}
    for control_id in local:
        assert "lote local" in CONTROLS[control_id]["aprovacao_registrada"]


def test_question_matrix_and_safety_references_exist():
    q04 = (ROOT / "docs/gold-question-matrix.md").read_text(encoding="utf-8")
    corpus_rules = {
        item["expected_rule"]
        for item in json.loads((FIXTURES / "safety_corpus.json").read_text(encoding="utf-8"))
    }
    for case in CASES:
        for q04_id in case["referencias"].get("q04", []):
            assert f"| {q04_id} |" in q04, (case["id"], q04_id)
        safety = case["referencias"].get("seguranca", {})
        for rule in safety.get("safety_corpus.json", []):
            assert rule in corpus_rules, (case["id"], rule)
        if "safety_project_questions.json" in safety:
            assert (FIXTURES / "safety_project_questions.json").is_file()
        for reference in case["referencias"].get("regressao_tecnica", []):
            path = reference.split("::")[0]
            assert (ROOT / path).is_file(), reference
            if "::" in reference:
                source = (ROOT / path).read_text(encoding="utf-8")
                assert f"def {reference.split('::')[1]}" in source


def test_protection_cases_cover_every_refusal_family_of_the_corpus():
    referenced = {
        rule
        for case in CASES
        for rule in case["referencias"].get("seguranca", {}).get("safety_corpus.json", [])
    }
    corpus_rules = {
        item["expected_rule"]
        for item in json.loads((FIXTURES / "safety_corpus.json").read_text(encoding="utf-8"))
    } - {None}
    assert corpus_rules <= referenced


def test_regression_criteria_forbid_hiding_mandatory_failures():
    criteria = MATRIX["criterios_regressao"]
    assert set(criteria["classes_resultado"]) == {
        "PASS", "FAIL", "FALHA_CONHECIDA", "BLOQUEADO", "SEM_AMOSTRA_NO_LOTE",
    }
    text = " ".join(criteria["regras"])
    assert "taxa global" in text and "skip" in text and "xfail" in text
    ids = {case["id"] for case in CASES}
    for known in criteria["falhas_conhecidas"]:
        assert set(known) == {"id", "motivo", "dono"} and known["id"] in ids
