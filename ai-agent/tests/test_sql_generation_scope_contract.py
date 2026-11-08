"""Contrato de motivo, avaliação de assunto e opções de esclarecimento do candidato F1."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.sql_generation import SqlGenerationCandidate

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs/contracts/examples/text-to-sql-f1-v1.json"


@pytest.fixture
def examples():
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))["valid"]


def _scope(status, terms=()):
    return {"status": status, "unresolved_terms": list(terms)}


def _clarification(examples, *, reason="ambiguous_subject", scope=None, options=None):
    payload = copy.deepcopy(examples[1])
    payload["clarification"]["reason_code"] = reason
    if options is not None:
        payload["clarification"]["options"] = options
    if scope is not None:
        payload["scope_assessment"] = scope
    return payload


def _unsupported(examples, *, reason="out_of_domain", scope=None):
    payload = copy.deepcopy(examples[2])
    payload["unsupported_reason"]["reason_code"] = reason
    if scope is not None:
        payload["scope_assessment"] = scope
    return payload


def test_legacy_payloads_without_new_fields_stay_valid(examples):
    for payload in examples:
        candidate = SqlGenerationCandidate.model_validate(payload)
        assert candidate.scope_assessment is None
    assert SqlGenerationCandidate.model_validate(examples[1]).clarification.reason_code is None
    assert SqlGenerationCandidate.model_validate(examples[2]).unsupported_reason.reason_code is None


def test_executable_candidate_accepts_only_an_in_domain_assessment(examples):
    payload = copy.deepcopy(examples[0])
    payload["scope_assessment"] = _scope("in_domain")
    assert SqlGenerationCandidate.model_validate(payload).scope_assessment.status == "in_domain"
    for status in ("out_of_domain", "uncertain"):
        payload["scope_assessment"] = _scope(status, ["UFC"])
        with pytest.raises(ValidationError):
            SqlGenerationCandidate.model_validate(payload)


def test_uncertain_subject_requires_clarification_not_refusal(examples):
    ok = _clarification(examples, scope=_scope("uncertain", ["UFC"]))
    assert SqlGenerationCandidate.model_validate(ok).scope_assessment.unresolved_terms == ("UFC",)
    refusal = _unsupported(examples, reason="out_of_domain", scope=_scope("uncertain", ["UFC"]))
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(refusal)


def test_out_of_domain_assessment_requires_an_out_of_domain_refusal(examples):
    ok = _unsupported(examples, scope=_scope("out_of_domain", ["UFC"]))
    assert (
        SqlGenerationCandidate.model_validate(ok).unsupported_reason.reason_code == "out_of_domain"
    )
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(
            _clarification(examples, scope=_scope("out_of_domain", ["UFC"]))
        )
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(
            _unsupported(examples, reason="unsupported_capability", scope=_scope("out_of_domain"))
        )


def test_in_domain_assessment_cannot_carry_a_subject_reason(examples):
    for reason in ("out_of_domain",):
        with pytest.raises(ValidationError):
            SqlGenerationCandidate.model_validate(
                _unsupported(examples, reason=reason, scope=_scope("in_domain"))
            )
    # Um esclarecimento rotulado como assunto, mas com assunto conhecido, é legível: o Backend
    # o normaliza para falta de contexto em vez de transformá-lo em erro técnico.
    tolerated = _clarification(examples, reason="ambiguous_subject", scope=_scope("in_domain"))
    assert SqlGenerationCandidate.model_validate(tolerated)
    ok = _clarification(examples, reason="missing_context", scope=_scope("in_domain"))
    assert SqlGenerationCandidate.model_validate(ok)


def test_out_of_domain_assessment_may_carry_a_security_refusal(examples):
    payload = _unsupported(examples, reason="security_restriction", scope=_scope("out_of_domain"))
    candidate = SqlGenerationCandidate.model_validate(payload)
    assert candidate.unsupported_reason.reason_code == "security_restriction"


@pytest.mark.parametrize(
    "reason", ["out_of_domain", "unsupported_capability", "security_restriction"]
)
def test_clarification_reason_must_be_a_clarification_reason(examples, reason):
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(_clarification(examples, reason=reason))


@pytest.mark.parametrize("reason", ["ambiguous_subject", "missing_context"])
def test_unsupported_reason_must_be_a_refusal_reason(examples, reason):
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(_unsupported(examples, reason=reason))


def test_unknown_reason_code_is_rejected(examples):
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(_unsupported(examples, reason="because_i_said_so"))
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(_clarification(examples, reason="because"))


@pytest.mark.parametrize(
    "terms",
    [["a", "b", "c", "d"], ["x" * 81], [""], ["ok", 3]],
)
def test_unresolved_terms_are_bounded(examples, terms):
    payload = _clarification(examples, scope=_scope("uncertain", terms))
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)


def test_scope_assessment_rejects_free_form_reasoning(examples):
    payload = _clarification(examples, scope=_scope("uncertain", ["UFC"]))
    payload["scope_assessment"]["reasoning"] = "porque parece esporte"
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)


def test_clarification_options_are_optional_bounded_and_closed(examples):
    options = [{"label": f"Opção {i}", "question": f"Qual a receita de 202{i}?"} for i in range(5)]
    ok = _clarification(examples, reason="missing_context", options=options)
    assert len(SqlGenerationCandidate.model_validate(ok).clarification.options) == 5
    too_many = options + [{"label": "Mais", "question": "Qual a receita?"}]
    for bad in (
        too_many,
        [{"label": "x", "question": "y", "sql": "SELECT 1"}],
        [{"label": "x"}],
        [{"label": "", "question": "y"}],
    ):
        with pytest.raises(ValidationError):
            SqlGenerationCandidate.model_validate(
                _clarification(examples, reason="missing_context", options=bad)
            )


def test_options_never_make_a_candidate_executable(examples):
    payload = copy.deepcopy(examples[0])
    payload["clarification"] = copy.deepcopy(examples[1]["clarification"])
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)


SCOPE_EXAMPLES = ROOT / "docs/contracts/examples/text-to-sql-f1-scope-v1.json"


def test_shared_scope_examples_are_accepted_and_rejected_by_the_ai_agent_contract():
    document = json.loads(SCOPE_EXAMPLES.read_text(encoding="utf-8"))
    for row in document["valid"]:
        SqlGenerationCandidate.model_validate(row["payload"])
    for row in document["invalid"]:
        with pytest.raises(ValidationError):
            SqlGenerationCandidate.model_validate(row["payload"])
        # ids documentados devem continuar rastreáveis
        assert row["id"]


def test_shared_scope_examples_match_the_backend_contract():
    import subprocess
    import sys

    code = """
import json, sys
from pydantic import ValidationError
from app.schemas.sql_generation import SqlGenerationCandidate
payload = json.load(sys.stdin)
accepted = []
for row in payload['valid']:
    accepted.append(SqlGenerationCandidate.model_validate(row['payload']).model_dump(mode='json'))
rejected = []
for row in payload['invalid']:
    try:
        SqlGenerationCandidate.model_validate(row['payload'])
    except ValidationError:
        rejected.append(row['id'])
print(json.dumps({'accepted': accepted, 'rejected': rejected}))
"""
    document = json.loads(SCOPE_EXAMPLES.read_text(encoding="utf-8"))
    result = subprocess.run(
        [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-c", code],
        input=json.dumps(document),
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    backend = json.loads(result.stdout)
    assert backend["rejected"] == [row["id"] for row in document["invalid"]]
    assert backend["accepted"] == [
        SqlGenerationCandidate.model_validate(row["payload"]).model_dump(mode="json")
        for row in document["valid"]
    ]
