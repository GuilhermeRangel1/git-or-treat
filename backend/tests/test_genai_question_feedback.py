"""Decisão pública de assunto: motivo normalizado e contradições recusadas antes da admissão."""

import copy
import json
from pathlib import Path

import pytest

from app.schemas.sql_generation import SqlGenerationCandidate, SqlScopeAssessment
from app.services.genai_question_feedback import (
    ScopeDecisionRejected,
    enforce_scope_decision,
)

EXAMPLES = (
    Path(__file__).resolve().parents[2]
    / "docs/contracts/examples/text-to-sql-f1-v1.json"
)


@pytest.fixture
def examples():
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))["valid"]


def _candidate(payload):
    return SqlGenerationCandidate.model_validate(payload)


def _with(payload, **fields):
    payload = copy.deepcopy(payload)
    payload.update(fields)
    return payload


def _scope(status, terms=()):
    return {"status": status, "unresolved_terms": list(terms)}


def test_in_domain_candidate_passes_unchanged(examples):
    candidate = _candidate(_with(examples[0], scope_assessment=_scope("in_domain")))
    assert enforce_scope_decision(candidate) == candidate


@pytest.mark.parametrize("assessment", [None, "uncertain", "out_of_domain"])
def test_executable_candidate_requires_an_in_domain_assessment(examples, assessment):
    payload = copy.deepcopy(examples[0])
    if assessment is None:
        candidate = _candidate(payload)
    else:
        # O contrato já recusa o candidato contraditório; o avaliador também não confia nele.
        candidate = SqlGenerationCandidate.model_construct(
            **{
                **_candidate(payload).__dict__,
                "scope_assessment": SqlScopeAssessment(status=assessment),
            }
        )
    with pytest.raises(ScopeDecisionRejected):
        enforce_scope_decision(candidate)


def test_every_new_decision_requires_an_assessment(examples):
    for payload in (examples[1], examples[2]):
        with pytest.raises(ScopeDecisionRejected):
            enforce_scope_decision(_candidate(payload))


def test_external_subject_is_normalized_to_out_of_domain_refusal(examples):
    payload = _with(examples[2], scope_assessment=_scope("out_of_domain", ["UFC"]))
    result = enforce_scope_decision(_candidate(payload))
    assert result.unsupported_reason.reason_code == "out_of_domain"
    assert (
        result.sql is None and not result.parameters and result.interpretation is None
    )


def test_uncertain_subject_is_normalized_to_ambiguous_subject_clarification(examples):
    payload = _with(examples[1], scope_assessment=_scope("uncertain", ["CAR"]))
    result = enforce_scope_decision(_candidate(payload))
    assert result.clarification.reason_code == "ambiguous_subject"
    assert result.sql is None


def test_uncertain_subject_cannot_be_labelled_as_missing_period(examples):
    payload = copy.deepcopy(examples[1])
    payload["clarification"]["reason_code"] = "missing_context"
    payload["scope_assessment"] = _scope("uncertain", ["CAR"])
    with pytest.raises(ScopeDecisionRejected):
        enforce_scope_decision(_candidate(payload))


def test_in_domain_clarification_defaults_to_missing_context(examples):
    payload = _with(examples[1], scope_assessment=_scope("in_domain"))
    result = enforce_scope_decision(_candidate(payload))
    assert result.clarification.reason_code == "missing_context"


def test_declared_capability_refusal_keeps_its_reason_or_defaults_structurally(
    examples,
):
    explicit = copy.deepcopy(examples[2])
    explicit["unsupported_reason"]["reason_code"] = "security_restriction"
    explicit["scope_assessment"] = _scope("in_domain")
    assert (
        enforce_scope_decision(_candidate(explicit)).unsupported_reason.reason_code
        == "security_restriction"
    )
    implicit = _with(examples[2], scope_assessment=_scope("in_domain"))
    assert (
        enforce_scope_decision(_candidate(implicit)).unsupported_reason.reason_code
        == "unsupported_capability"
    )


def test_out_of_domain_refusal_is_never_downgraded_to_capability(examples):
    payload = copy.deepcopy(examples[2])
    payload["unsupported_reason"]["reason_code"] = "unsupported_capability"
    payload["scope_assessment"] = _scope("in_domain")
    result = enforce_scope_decision(_candidate(payload))
    assert result.unsupported_reason.reason_code == "unsupported_capability"
    contradiction = SqlGenerationCandidate.model_construct(
        **{
            **_candidate(
                _with(examples[2], scope_assessment=_scope("out_of_domain"))
            ).__dict__,
            "unsupported_reason": _candidate(payload).unsupported_reason,
        }
    )
    with pytest.raises(ScopeDecisionRejected):
        enforce_scope_decision(contradiction)


def test_options_are_deduplicated_limited_and_free_of_statements(examples):
    payload = copy.deepcopy(examples[1])
    payload["scope_assessment"] = _scope("in_domain")
    payload["clarification"]["options"] = [
        {"label": "2025", "question": "Qual a receita em junho de 2025?"},
        {"label": "Também 2025", "question": "Qual a receita em junho de 2025?"},
        {"label": "Injeção", "question": "SELECT * FROM gold_v2.diagnostico_receita"},
        {"label": "Multi", "question": "Qual a receita?; DROP TABLE x"},
        {"label": "2026", "question": "Qual a receita em junho de 2026?"},
    ]
    options = enforce_scope_decision(_candidate(payload)).clarification.options
    assert [option.label for option in options] == ["2025", "2026"]


# ---- ano fechado: "em 2026" usa as competências disponíveis; "fechado" exige o ano completo ----

from app.services.genai_question_feedback import (
    FullYearCoverageGap,
    full_year_coverage_gap,
)

JAN_JUN_2026 = tuple(f"2026-{month:02d}" for month in range(1, 7))
ALL_2025 = tuple(f"2025-{month:02d}" for month in range(1, 13))


@pytest.mark.parametrize(
    "question",
    [
        "Qual a receita total de Recife em 2026 fechado?",
        "Qual a receita total de Recife no ano inteiro de 2026?",
        "Qual a receita total de Recife no ano completo de 2026?",
        "Qual a receita total de Recife de janeiro a dezembro de 2026?",
        "Qual a receita total de Recife de janeiro até dezembro de 2026?",
        "Qual a receita de 2026 inteiro em Recife?",
    ],
)
def test_closed_year_wording_with_partial_coverage_reports_the_gap(question):
    gap = full_year_coverage_gap(question, JAN_JUN_2026 + ALL_2025)
    assert isinstance(gap, FullYearCoverageGap)
    assert gap.year == 2026
    assert gap.missing_months == (
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
        "2026-12",
    )
    assert gap.available_range == ("2026-01", "2026-06")
    assert gap.alternative_question is not None
    assert "janeiro a junho de 2026" in gap.alternative_question
    assert (
        "Recife" in gap.alternative_question or "receita de" in gap.alternative_question
    )
    assert (
        "fechado" not in gap.alternative_question
        and "dezembro" not in gap.alternative_question
    )


@pytest.mark.parametrize(
    "question",
    [
        "Qual a receita total de Recife em 2026?",
        "Qual a receita total de Recife no ano de 2026?",
        "Qual a receita total de Recife de janeiro a junho de 2026?",
        "Qual a receita total de Recife no primeiro semestre de 2026?",
        "Qual a receita de Recife em junho de 2026, mês fechado?",
    ],
)
def test_plain_year_and_explicit_partial_ranges_are_not_a_closed_year_request(question):
    assert full_year_coverage_gap(question, JAN_JUN_2026) is None


def test_complete_year_has_no_gap_and_missing_year_has_no_alternative():
    assert full_year_coverage_gap("Qual a receita de 2025 fechado?", ALL_2025) is None
    gap = full_year_coverage_gap("Qual a receita de 2027 fechado?", JAN_JUN_2026)
    assert gap.year == 2027 and len(gap.missing_months) == 12
    assert gap.available_range is None and gap.alternative_question is None


def test_internal_hole_offers_no_continuous_alternative():
    coverage = ("2026-01", "2026-02", "2026-04", "2026-05")
    gap = full_year_coverage_gap("Qual a receita de 2026 fechado?", coverage)
    assert "2026-03" in gap.missing_months
    assert gap.available_range is None and gap.alternative_question is None


def test_question_without_a_recognizable_year_is_left_to_the_model():
    assert (
        full_year_coverage_gap("Qual a receita do ano inteiro?", JAN_JUN_2026) is None
    )


def test_known_subject_labelled_as_ambiguous_is_normalized_to_missing_context(examples):
    payload = copy.deepcopy(examples[1])
    payload["clarification"]["reason_code"] = "ambiguous_subject"
    payload["scope_assessment"] = _scope("in_domain")
    result = enforce_scope_decision(_candidate(payload))
    assert result.clarification.reason_code == "missing_context"


def test_external_subject_may_keep_a_security_refusal_reason(examples):
    payload = copy.deepcopy(examples[2])
    payload["unsupported_reason"]["reason_code"] = "security_restriction"
    payload["scope_assessment"] = _scope("out_of_domain", ["senha do banco de dados"])
    result = enforce_scope_decision(_candidate(payload))
    assert result.unsupported_reason.reason_code == "security_restriction"


def test_uncertain_subject_never_asks_for_municipality_or_class(examples):
    payload = copy.deepcopy(examples[1])
    payload["clarification"] = {
        "question": "Você quer a receita de qual município ou classe?",
        "missing_fields": ["dimension", "filter"],
        "options": [{"label": "Recife", "question": "Qual a receita de Recife?"}],
    }
    payload["scope_assessment"] = _scope("uncertain", ["CAR"])
    clarification = enforce_scope_decision(_candidate(payload)).clarification
    assert clarification.reason_code == "ambiguous_subject"
    assert clarification.missing_fields == ("context",)
    assert clarification.options == ()
    assert "município" not in clarification.question.casefold()
    assert "classe" not in clarification.question.casefold()


def test_uncertain_subject_keeps_a_neutral_model_question(examples):
    payload = copy.deepcopy(examples[1])
    payload["clarification"] = {
        "question": "Você se refere a qual assunto?",
        "missing_fields": ["context"],
    }
    payload["scope_assessment"] = _scope("uncertain", ["CAR"])
    clarification = enforce_scope_decision(_candidate(payload)).clarification
    assert clarification.question == "Você se refere a qual assunto?"


def test_feedback_harness_supplies_authorized_gd_values():
    from tests.genai_feedback_harness import build_request

    request = build_request({"question": "Quantas UCs com GD existem?", "context": []})
    coverage = {item.dimension_id: item.values for item in request.dimension_value_coverage}
    assert "Sim" in coverage["generation.distributed"]
