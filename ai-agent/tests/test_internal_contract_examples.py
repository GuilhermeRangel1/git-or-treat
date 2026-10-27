"""Exemplos do contrato interno Backend ↔ GenAI conferidos contra os schemas existentes.

Os exemplos JSON são lidos de docs/contracts/genai-query-execution.md; se um bloco sumir
ou mudar de lugar, o teste falha em vez de ignorá-lo.

Lacunas documentadas, sem modelo de produção ainda: os envelopes completos de planejar e
sintetizar (QuestionPlanRequest, QuestionPlanResponse, QuestionSynthesisRequest), os
estados planned/refused desses envelopes, access_scope sem correlation_id e a exigência
de batch_ref na proveniência. Dependem do formato do batch_ref, ainda em aberto com Dados.
Os testes do lado Backend (revalidação, execução, papel somente leitura) são do Felipe.
"""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import EvidenceGuard
from app.agent.read_plan import PlanCapabilityUnavailable, ReadPlanValidator
from app.ports.evidence import EvidenceAccessDenied, EvidenceContractInvalid
from app.schemas.access import AccessContext
from app.schemas.domain_profile import DomainProfile
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.questions import QuestionResponse, QuestionStatus
from app.schemas.read_plan import LogicalReadPlan

from .test_domain_profile import profile_data

CONTRACT = Path(__file__).parents[2] / "docs" / "contracts" / "genai-query-execution.md"
CORRELATION_ID = "0123456789abcdef0123456789abcdef"
SOURCE_ID = "gold.local"


def _json_example(heading: str) -> dict:
    """Primeiro bloco ```json da seção; falha se a seção ou o bloco não existirem."""

    text = CONTRACT.read_text(encoding="utf-8")
    match = re.search(rf"^#+ {re.escape(heading)}\s*$", text, flags=re.MULTILINE)
    assert match, f"seção '{heading}' não encontrada em {CONTRACT.name}"
    section = re.split(r"^#+ ", text[match.end():], maxsplit=1, flags=re.MULTILINE)[0]
    blocks = re.findall(r"```json\n(.*?)\n```", section, flags=re.DOTALL)
    assert len(blocks) == 1, f"seção '{heading}' deveria ter um bloco json, tem {len(blocks)}"
    return json.loads(blocks[0])


def _gold_profile() -> DomainProfile:
    """Catálogo só de teste com os IDs ilustrativos do contrato; não é o catálogo Gold."""

    data = profile_data()
    data.update(
        profile_id="grid360_gold",
        domains=[
            {"id": "faturamento", "label": "Faturamento", "example_questions": ["Quanto?"]}
        ],
        metrics=[
            {
                "id": "energia_faturada",
                "domain_id": "faturamento",
                "aliases": ["energia faturada"],
                "unit": "kWh",
                "granularities": ["month"],
                "dimension_ids": ["municipio"],
                "sensitivity": "internal",
                "evidence_fields": [
                    {"name": "valor", "role": "measure", "value_type": "number",
                     "sensitivity": "internal"},
                    {"name": "unidade", "role": "unit", "value_type": "string",
                     "sensitivity": "internal"},
                    {"name": "competencia", "role": "period", "value_type": "date",
                     "sensitivity": "internal"},
                    {"name": "municipio", "role": "dimension", "dimension_id": "municipio",
                     "value_type": "string", "sensitivity": "internal"},
                ],
            }
        ],
        dimensions=[
            {
                "id": "municipio",
                "label": "Município",
                "role": "geography",
                "aliases": ["município"],
                "value_type": "string",
                "operators": ["eq", "in"],
                "sensitivity": "internal",
                "values": [
                    {"value": "Recife", "aliases": ["Recife"]},
                    {"value": "Olinda", "aliases": ["Olinda"]},
                ],
            }
        ],
    )
    return DomainProfile.model_validate(data)


def _plan_example() -> dict:
    return _json_example("Válido — plano pronto (planejar)")


def _lookup_example() -> dict:
    """Trecho do lookup sem batch_ref, campo ainda proposto (ver lacunas no topo)."""

    lookup = _json_example("Válido — resposta fundamentada (sintetizar)")
    provenance = lookup["evidence"]["provenance"]
    assert "batch_ref" in provenance, "o exemplo deixou de mostrar o batch_ref proposto"
    del provenance["batch_ref"]
    return lookup


def _access_context() -> AccessContext:
    scope = _json_example("Requisição (proposta: `QuestionPlanRequest`)")["access_scope"]
    return AccessContext.model_validate({**scope, "correlation_id": CORRELATION_ID})


def _validator(profile: DomainProfile) -> ReadPlanValidator:
    return ReadPlanValidator(profile, SOURCE_ID, ReadAccessPolicy(profile, SOURCE_ID))


# (1) Exemplos válidos do contrato


def test_ready_plan_example_is_accepted_and_fingerprint_matches() -> None:
    envelope = _plan_example()
    plan = LogicalReadPlan.model_validate(envelope["plan"])

    assert envelope["status"] == "planned"
    assert plan.fingerprint() == envelope["plan_fingerprint"]
    assert _validator(_gold_profile()).approve(envelope["plan"], _access_context()) == plan


def test_lookup_example_without_batch_ref_is_accepted_by_schema_and_guard() -> None:
    plan = LogicalReadPlan.model_validate(_plan_example()["plan"])
    lookup = EvidenceLookupResult.model_validate(_lookup_example())

    assert lookup.status is EvidenceLookupStatus.AVAILABLE
    assert lookup.evidence.provenance.plan_fingerprint == plan.fingerprint()
    safe = EvidenceGuard(_gold_profile()).validate(plan, lookup)
    assert safe.evidence.records == [
        {
            "observation_id": "row_1", "value": 1234567.8, "unit": "kWh",
            "period": "2025-03", "dimensions": {"municipio": "Recife"},
        }
    ]


def test_proposed_batch_ref_is_still_rejected_by_current_provenance() -> None:
    lookup = _json_example("Válido — resposta fundamentada (sintetizar)")

    with pytest.raises(ValidationError, match="batch_ref"):
        EvidenceLookupResult.model_validate(lookup)


def test_clarification_example_response_is_a_public_envelope() -> None:
    envelope = _json_example("Válido — esclarecimento (planejar)")
    response = QuestionResponse.model_validate(envelope["response"])

    assert envelope["status"] == "needs_clarification"
    assert envelope["plan"] is None and envelope["plan_fingerprint"] is None
    assert response.status is QuestionStatus.NEEDS_CLARIFICATION
    assert response.correlation_id == envelope["correlation_id"]
    assert response.error is None


# (2) Campo extra


@pytest.mark.parametrize("target", ["plan", "lookup", "evidence", "reference", "provenance"])
def test_extra_field_is_rejected(target: str) -> None:
    plan = _plan_example()["plan"]
    lookup = _lookup_example()
    nodes = {
        "plan": plan,
        "lookup": lookup,
        "evidence": lookup["evidence"],
        "reference": lookup["evidence"]["reference"],
        "provenance": lookup["evidence"]["provenance"],
    }
    nodes[target]["sql"] = "SELECT * FROM gold_faturamento"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        if target == "plan":
            LogicalReadPlan.model_validate(plan)
        else:
            EvidenceLookupResult.model_validate(lookup)


# (3) SQL ou nome físico nos identificadores do plano

SQL_TEXT = [
    "SELECT valor FROM gold_faturamento",
    "energia_faturada; DROP TABLE faturas",
    '"DEC"',
    "energia_faturada--",
]


def _set_identifier(plan: dict, field: str, value: str) -> None:
    if field == "dimension_ids":
        plan["dimension_ids"] = [value]
    elif field == "filters.dimension_id":
        plan["filters"][0]["dimension_id"] = value
    elif field == "order.field_id":
        plan["order"] = {"field_id": value, "direction": "desc"}
    else:
        plan[field] = value


@pytest.mark.parametrize("value", SQL_TEXT)
@pytest.mark.parametrize(
    "field",
    ["profile_id", "source_id", "domain_id", "metric_id", "dimension_ids",
     "filters.dimension_id", "order.field_id"],
)
def test_sql_text_in_plan_identifier_is_rejected_by_schema(field: str, value: str) -> None:
    plan = _plan_example()["plan"]
    _set_identifier(plan, field, value)

    with pytest.raises(ValidationError):
        LogicalReadPlan.model_validate(plan)


@pytest.mark.parametrize("field", ["metric_id", "dimension_ids"])
def test_physical_name_with_valid_syntax_is_denied_by_the_catalog(field: str) -> None:
    # Um nome físico como gold.fato_faturamento tem a forma de um ID lógico; só o
    # catálogo o recusa, por não declará-lo.
    plan = _plan_example()["plan"]
    _set_identifier(plan, field, "gold.fato_faturamento")
    if field == "dimension_ids":
        plan["filters"] = []

    with pytest.raises(PlanCapabilityUnavailable):
        _validator(_gold_profile()).approve(plan, _access_context())


# (4) Versões incompatíveis


@pytest.mark.parametrize(
    "path",
    [
        ("plan", "contract_version"),
        ("plan", "catalog_version"),
        ("lookup", "contract_version"),
        ("evidence", "contract_version"),
        ("provenance", "catalog_version"),
    ],
)
def test_incompatible_version_is_rejected(path: tuple[str, str]) -> None:
    target, field = path
    plan = _plan_example()["plan"]
    lookup = _lookup_example()
    nodes = {
        "plan": plan,
        "lookup": lookup,
        "evidence": lookup["evidence"],
        "provenance": lookup["evidence"]["provenance"],
    }
    nodes[target][field] = "v2"

    with pytest.raises(ValidationError):
        if target == "plan":
            LogicalReadPlan.model_validate(plan)
        else:
            EvidenceLookupResult.model_validate(lookup)


# (5) Validador do plano contra o catálogo do teste


def test_validator_rejects_plan_with_divergent_catalog_version() -> None:
    # Enquanto catalog_version e a versão do perfil forem Literal["v1"], a divergência
    # é barrada pelo schema dentro de approve, antes da comparação com o perfil.
    plan = _plan_example()["plan"]
    plan["catalog_version"] = "v2"

    with pytest.raises(PlanCapabilityUnavailable, match="não segue o contrato"):
        _validator(_gold_profile()).approve(plan, _access_context())


@pytest.mark.parametrize(
    "change", [{"source_id": "gold.outro"}, {"profile_id": "grid360_outro"}]
)
def test_validator_denies_plan_for_another_source_or_profile(change: dict) -> None:
    plan = {**_plan_example()["plan"], **change}

    with pytest.raises(EvidenceAccessDenied):
        _validator(_gold_profile()).approve(plan, _access_context())


# (6) EvidenceGuard recusa evidência incompatível com o plano


def _tampered_lookup(change: str) -> dict:
    lookup = _lookup_example()
    provenance = lookup["evidence"]["provenance"]
    record = lookup["evidence"]["records"][0]
    if change == "provenance_other_municipality":
        provenance["filters"][0]["values"] = ["Olinda"]
    elif change == "record_other_municipality":
        record["municipio"] = "Olinda"
    elif change == "record_other_unit":
        record["unidade"] = "MWh"
    elif change == "provenance_other_unit":
        provenance["unit"] = "MWh"
    elif change == "other_fingerprint":
        provenance["plan_fingerprint"] = "0" * 64
    return lookup


@pytest.mark.parametrize(
    "change",
    [
        "provenance_other_municipality",
        "record_other_municipality",
        "record_other_unit",
        "provenance_other_unit",
        "other_fingerprint",
    ],
)
def test_guard_rejects_evidence_incompatible_with_plan(change: str) -> None:
    plan = LogicalReadPlan.model_validate(_plan_example()["plan"])
    lookup = EvidenceLookupResult.model_validate(_tampered_lookup(change))

    with pytest.raises(EvidenceContractInvalid):
        EvidenceGuard(_gold_profile()).validate(plan, lookup)


@pytest.mark.parametrize(
    "change",
    [
        {"limit": 50},
        {"filters": [{"dimension_id": "municipio", "operator": "eq", "values": ["Olinda"]}]},
    ],
)
def test_guard_rejects_evidence_for_tampered_plan(change: dict) -> None:
    tampered = LogicalReadPlan.model_validate({**_plan_example()["plan"], **change})
    lookup = EvidenceLookupResult.model_validate(_lookup_example())

    with pytest.raises(EvidenceContractInvalid):
        EvidenceGuard(_gold_profile()).validate(tampered, lookup)
