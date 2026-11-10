"""Garante que a fixture e o avaliador de recusas/esclarecimentos rejeitam resultados errados."""

import collections
import copy

import pytest

from .genai_feedback_evaluation import (
    GROUPS,
    RESERVE_PATH,
    evaluate_all,
    evaluate_outcome,
    load_cases,
    validate_case_shape,
)

CASES = load_cases()
BY_ID = {case["id"]: case for case in CASES}


def ideal_outcome(case):
    """Resultado mínimo que cumpre o oráculo, derivado da primeira opção permitida."""
    allowed = case["allowed_outcomes"][0]
    status = allowed["status"]
    outcome = {
        "status": status,
        "reason_code": allowed.get("reason_code") or case["expected_reason"],
        "missing_fields": [],
        "message": "",
        "options": [],
        "sql": None,
        "has_quantitative_evidence": False,
        "model_calls": min(1, case["expected_source_calls"]["max_model_calls"]),
        "source_queries": 0,
    }
    if status == "sql_candidate":
        outcome["sql"] = "SELECT 1"
        outcome["source_queries"] = case["expected_source_calls"]["max_source_queries"]
    elif status == "needs_clarification":
        outcome["missing_fields"] = list(case["pending_fields"][:1])
        outcome["message"] = "Pode confirmar essa informação para eu continuar?"
    elif status == "unsupported":
        outcome["message"] = "Posso ajudar com os indicadores de energia da V-Energy."
    elif status == "access_denied":
        outcome["message"] = "Seu perfil não permite consultar esses dados."
    else:
        outcome["message"] = "O serviço está indisponível no momento."
        outcome["model_calls"] = 1
    return outcome


def test_fixture_has_the_four_balanced_groups_of_twelve():
    counts = collections.Counter(case["group"] for case in CASES)
    assert set(counts) == GROUPS
    assert all(count == 12 for count in counts.values())
    assert len(CASES) == 48


def test_case_ids_are_unique_and_shapes_valid():
    assert len({case["id"] for case in CASES}) == len(CASES)
    for case in CASES:
        assert validate_case_shape(case) == [], case["id"]
        assert case["split"] == "development"


def test_ufc_reports_are_development_cases_that_forbid_sql_and_municipality_prompt():
    ufc = [case for case in CASES if case["origin"] == "user_report"]
    assert {case["id"] for case in ufc} == {"FB-EXT-01", "FB-EXT-02"}
    for case in ufc:
        assert {"sql", "ask_municipality_class"} <= set(case["forbidden_behaviors"])
    first = BY_ID["FB-EXT-01"]
    assert [o["status"] for o in first["allowed_outcomes"]] == ["unsupported"]
    assert first["expected_reason"] == "out_of_domain"
    second = BY_ID["FB-EXT-02"]
    assert {o["reason_code"] for o in second["allowed_outcomes"]} == {
        "out_of_domain",
        "ambiguous_subject",
    }


def test_reserve_is_separate_authorial_and_large_enough():
    reserve = load_cases(RESERVE_PATH)
    assert len(reserve) >= 12
    assert {case["split"] for case in reserve} == {"authorial_reserve"}
    assert not {case["id"] for case in reserve} & set(BY_ID)
    questions = {case["question"] for case in CASES}
    assert not questions & {case["question"] for case in reserve}
    for case in reserve:
        assert validate_case_shape(case) == [], case["id"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_ideal_outcome_passes(case):
    assert evaluate_outcome(case, ideal_outcome(case)) == []


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_every_allowed_outcome_is_accepted(case):
    for allowed in case["allowed_outcomes"]:
        probe = copy.deepcopy(case)
        probe["allowed_outcomes"] = [allowed]
        assert evaluate_outcome(probe, ideal_outcome(probe)) == []


def test_non_candidate_states_never_pass_with_sql_or_evidence():
    for case in CASES:
        outcome = ideal_outcome(case)
        if outcome["status"] == "sql_candidate":
            continue
        assert evaluate_outcome(case, {**outcome, "sql": "SELECT 1"}), case["id"]
        assert evaluate_outcome(case, {**outcome, "has_quantitative_evidence": True}), case["id"]


def test_external_cases_reject_sql_capability_label_and_municipality_prompt():
    for case in CASES:
        if case["group"] != "external_mixed":
            continue
        base = ideal_outcome(case)
        assert evaluate_outcome(
            case,
            {
                **base,
                "status": "sql_candidate",
                "reason_code": None,
                "sql": "SELECT 1",
                "message": "",
            },
        ), case["id"]
        assert evaluate_outcome(
            case, {**base, "status": "unsupported", "reason_code": "unsupported_capability"}
        ), case["id"]
        assert evaluate_outcome(
            case,
            {
                **base,
                "status": "needs_clarification",
                "reason_code": "missing_context",
                "missing_fields": ["filter"],
                "message": "Qual município você quer consultar?",
            },
        ), case["id"]


def test_external_refusal_does_not_pass_as_missing_capability():
    case = BY_ID["FB-EXT-01"]
    outcome = {**ideal_outcome(case), "reason_code": "unsupported_capability"}
    violations = evaluate_outcome(case, outcome)
    assert any("não permitido" in item or "motivo" in item for item in violations)


def test_clarification_fails_when_asking_an_already_resolved_field():
    case = BY_ID["FB-AMB-03"]
    structured = {
        **ideal_outcome(case),
        "status": "needs_clarification",
        "reason_code": "missing_context",
        "missing_fields": ["period"],
        "message": "De qual ano?",
    }
    assert evaluate_outcome(case, structured)
    generic = {
        **structured,
        "missing_fields": ["context"],
        "message": "Qual município você quer consultar?",
    }
    assert evaluate_outcome(case, generic)
    prose_only = {**structured, "missing_fields": ["context"], "message": "Junho de qual ano?"}
    assert any("já resolvido" in item for item in evaluate_outcome(case, prose_only))


def test_generic_clarification_fails_for_fully_explicit_question():
    case = BY_ID["FB-AMB-09"]
    outcome = {
        **ideal_outcome(case),
        "status": "needs_clarification",
        "sql": None,
        "missing_fields": ["period"],
        "message": "De qual ano você fala?",
    }
    assert evaluate_outcome(case, outcome)


def test_legitimate_question_refused_or_blocked_fails():
    for case in CASES:
        if case["group"] != "legitimate_near_external":
            continue
        refused = {
            **ideal_outcome(case),
            "status": "unsupported",
            "reason_code": "out_of_domain",
            "sql": None,
            "message": "Essa pergunta está fora do domínio de energia.",
        }
        assert evaluate_outcome(case, refused), case["id"]


def test_partial_year_case_forbids_annual_doubt_and_unauthorized_full_year():
    explicit = BY_ID["FB-LIM-05"]
    doubt = {
        **ideal_outcome(explicit),
        "status": "needs_clarification",
        "sql": None,
        "reason_code": "insufficient_coverage",
        "missing_fields": ["period"],
        "message": "Você quer o ano inteiro de 2026?",
    }
    assert evaluate_outcome(explicit, doubt)
    full_year = BY_ID["FB-LIM-02"]
    assert evaluate_outcome(
        full_year,
        {
            **ideal_outcome(full_year),
            "status": "sql_candidate",
            "reason_code": None,
            "sql": "SELECT 1",
        },
    )


def test_technical_failure_must_not_be_business_outcome_or_ask_to_rephrase():
    for case_id in ("FB-LIM-08", "FB-LIM-12"):
        case = BY_ID[case_id]
        base = ideal_outcome(case)
        assert evaluate_outcome(
            case, {**base, "status": "unsupported", "reason_code": "out_of_domain"}
        )
        assert evaluate_outcome(
            case,
            {
                **base,
                "status": "needs_clarification",
                "missing_fields": ["context"],
                "message": "Pode reformular a pergunta?",
            },
        )
        assert evaluate_outcome(case, {**base, "message": "Tente reformular sua pergunta."})


def test_internal_terms_and_call_budget_are_enforced():
    case = BY_ID["FB-EXT-04"]
    base = ideal_outcome(case)
    assert evaluate_outcome(case, {**base, "message": "Contrato F1 retornou unsupported."})
    assert evaluate_outcome(case, {**base, "model_calls": 1})
    sql_case = BY_ID["FB-LEG-04"]
    assert evaluate_outcome(sql_case, {**ideal_outcome(sql_case), "source_queries": 2})


def test_deterministic_cases_demand_zero_model_calls():
    zero = {case["id"] for case in CASES if case["expected_source_calls"]["max_model_calls"] == 0}
    assert {"FB-EXT-04", "FB-EXT-05", "FB-AMB-08", "FB-LIM-11"} <= zero


def test_missing_outcomes_and_unknown_status_fail():
    report = evaluate_all(CASES, {})
    assert all(items == ["resultado ausente"] for items in report.values())
    assert evaluate_outcome(CASES[0], {"status": "maybe"}) == ["status desconhecido: maybe"]


def test_live_report_counts_provider_total_tokens():
    from .genai_feedback_live_eval import build_report

    case = BY_ID["FB-LIM-08"]
    report = build_report([case], {case["id"]: ideal_outcome(case)},
                          {case["id"]: {"usage": [{"total_tokens": 321}]}},
                          mode="live", model_name="test")
    assert report["summary"]["total_tokens"] == 321
