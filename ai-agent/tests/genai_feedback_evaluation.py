"""Avaliador determinístico das decisões de recusa, esclarecimento e erro do Assistente.

Compara um resultado observado (de um modelo controlado ou, na Task 6, do Gemini real)
com o oráculo de `fixtures/genai_feedback_cases.json`. O avaliador confere status, motivo,
campos pendentes, comportamentos proibidos e contagem de chamadas; não mede a verdade
semântica da resposta numérica nem a qualidade da redação além das regras abaixo.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
CASES_PATH = FIXTURES / "genai_feedback_cases.json"
RESERVE_PATH = FIXTURES / "genai_feedback_reserve.json"

STATUSES = frozenset(
    {"sql_candidate", "needs_clarification", "unsupported", "access_denied", "technical_error"}
)
REASON_CODES = frozenset(
    {
        "out_of_domain",
        "ambiguous_subject",
        "missing_context",
        "unsupported_capability",
        "insufficient_coverage",
        "security_restriction",
    }
)
MISSING_FIELDS = frozenset(
    {"metric", "period", "dimension", "filter", "comparison_baseline", "context"}
)
GROUPS = frozenset(
    {"external_mixed", "legitimate_near_external", "ambiguity_continuation", "limits"}
)
FORBIDDEN_BEHAVIORS = frozenset(
    {
        "sql",
        "quantitative_evidence",
        "quantitative_evidence_without_sql",
        "ask_municipality_class",
        "ask_resolved_field",
        "ask_to_rephrase",
        "ask_annual_doubt",
        "refuse",
        "refuse_as_external",
        "substitute_metric",
        "present_partial_as_full",
        "resume_previous_subject",
    }
)

_INTERNAL_TERMS = re.compile(
    r"\b(?:f1|gold|sql|missing_fields|reason_code|context_version|text-to-sql|"
    r"unsupported|needs_clarification|sql_candidate|json)\b",
    re.IGNORECASE,
)
_MUNICIPALITY_OR_CLASS = re.compile(r"\b(?:municipio|cidade|classe|categoria)\b")
_REPHRASE = re.compile(
    r"\b(?:reformul\w*|escrev\w* de outra forma|pergunt\w* de outro modo|"
    r"tente (?:outra|uma outra) pergunta)\b"
)
_EXTERNAL_WORDING = re.compile(
    r"\b(?:fora do dominio|assunto externo|nao (?:e|faz parte) do dominio|"
    r"nao tenho dados financeiros de)\b"
)
_ANNUAL_DOUBT = re.compile(r"\b(?:ano inteiro|ano completo|doze meses|janeiro a dezembro)\b")
_FIELD_QUESTION = {
    "period": re.compile(r"\b(?:qual|que) (?:ano|mes|periodo|competencia)\b|\bde qual ano\b"),
    "metric": re.compile(r"\b(?:qual|que) (?:indicador|metrica)\b"),
    "filter": re.compile(r"\b(?:qual|que) (?:municipio|cidade|classe)\b"),
}


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def validate_case_shape(case: dict[str, Any]) -> list[str]:
    """Confere o formato de uma entrada da fixture, sem avaliar nenhum resultado."""
    problems: list[str] = []
    required = {
        "id",
        "group",
        "split",
        "question",
        "context",
        "allowed_outcomes",
        "expected_reason",
        "pending_fields",
        "resolved_fields",
        "forbidden_behaviors",
        "expected_source_calls",
    }
    missing = required - set(case)
    if missing:
        return [f"campos ausentes: {sorted(missing)}"]
    if case["group"] not in GROUPS:
        problems.append("grupo desconhecido")
    if not case["allowed_outcomes"]:
        problems.append("sem resultado permitido")
    for allowed in case["allowed_outcomes"]:
        if allowed.get("status") not in STATUSES:
            problems.append(f"status inválido: {allowed.get('status')}")
        if allowed.get("reason_code") not in REASON_CODES | {None}:
            problems.append(f"motivo inválido: {allowed.get('reason_code')}")
    if case["expected_reason"] not in REASON_CODES | {None}:
        problems.append("motivo esperado inválido")
    if not set(case["pending_fields"]) <= MISSING_FIELDS:
        problems.append("campo pendente desconhecido")
    if not set(case["resolved_fields"]) <= MISSING_FIELDS:
        problems.append("campo resolvido desconhecido")
    if not set(case["forbidden_behaviors"]) <= FORBIDDEN_BEHAVIORS:
        problems.append("comportamento proibido desconhecido")
    calls = case["expected_source_calls"]
    if set(calls) != {"max_model_calls", "max_source_queries"}:
        problems.append("contagem de chamadas incompleta")
    if any(turn.get("role") not in {"user", "assistant"} for turn in case["context"]):
        problems.append("papel de turno inválido")
    needs_clarification = any(
        a["status"] == "needs_clarification" for a in case["allowed_outcomes"]
    )
    if needs_clarification and not case["pending_fields"]:
        problems.append("esclarecimento permitido exige campos pendentes esperados")
    return problems


def evaluate_outcome(case: dict[str, Any], outcome: dict[str, Any]) -> list[str]:
    """Devolve as violações; lista vazia significa que o resultado cumpre o oráculo.

    `outcome`: status, reason_code, missing_fields, message, options, sql,
    has_quantitative_evidence, model_calls, source_queries.
    """
    violations: list[str] = []
    status = outcome.get("status")
    reason = outcome.get("reason_code")
    missing = set(outcome.get("missing_fields") or ())
    message = outcome.get("message") or ""
    folded = _fold(message)
    sql = outcome.get("sql")
    evidence = bool(outcome.get("has_quantitative_evidence"))

    if status not in STATUSES:
        return [f"status desconhecido: {status}"]
    if reason not in REASON_CODES | {None}:
        violations.append(f"motivo desconhecido: {reason}")

    if not any(
        allowed["status"] == status
        and (allowed.get("reason_code") is None or allowed["reason_code"] == reason)
        for allowed in case["allowed_outcomes"]
    ):
        violations.append(f"resultado não permitido: {status}/{reason}")
    if case["expected_reason"] is not None and reason != case["expected_reason"]:
        violations.append(f"motivo diferente do esperado: {reason}")

    # Regras globais: só candidato carrega consulta; recusa/esclarecimento nunca têm evidência.
    if status != "sql_candidate" and (sql or evidence):
        violations.append("estado sem candidato transporta SQL ou evidência")
    if status == "sql_candidate" and not sql:
        violations.append("candidato sem SQL")
    if message and _INTERNAL_TERMS.search(message):
        violations.append("termo interno exposto na mensagem")

    if status == "needs_clarification":
        if not missing:
            violations.append("esclarecimento sem campo pendente")
        elif not missing <= set(case["pending_fields"]):
            violations.append(f"campos pendentes fora do esperado: {sorted(missing)}")
        if not message.strip():
            violations.append("esclarecimento sem mensagem")

    forbidden = set(case["forbidden_behaviors"])
    resolved = set(case["resolved_fields"])
    if "sql" in forbidden and sql:
        violations.append("proibido: SQL")
    if "quantitative_evidence" in forbidden and evidence:
        violations.append("proibido: evidência quantitativa")
    if "quantitative_evidence_without_sql" in forbidden and evidence and not sql:
        violations.append("proibido: evidência sem consulta")
    if (
        "ask_municipality_class" in forbidden
        and status == "needs_clarification"
        and (missing & {"filter", "dimension"} or _MUNICIPALITY_OR_CLASS.search(folded))
    ):
        violations.append("proibido: pedir município/classe")
    if "ask_resolved_field" in forbidden and status == "needs_clarification":
        asked = missing & resolved
        asked |= {
            field
            for field, pattern in _FIELD_QUESTION.items()
            if field in resolved and pattern.search(folded)
        }
        if asked:
            violations.append(f"proibido: pedir campo já resolvido {sorted(asked)}")
    if "ask_to_rephrase" in forbidden and _REPHRASE.search(folded):
        violations.append("proibido: pedir reformulação por falha técnica")
    if "refuse" in forbidden and status in {"unsupported", "access_denied"}:
        violations.append("proibido: recusar pergunta legítima")
    if "refuse_as_external" in forbidden and (
        reason == "out_of_domain" or _EXTERNAL_WORDING.search(folded)
    ):
        violations.append("proibido: tratar como assunto externo")
    if "substitute_metric" in forbidden and status == "sql_candidate":
        violations.append("proibido: substituir a métrica pedida")
    if "present_partial_as_full" in forbidden and status == "sql_candidate":
        violations.append("proibido: apresentar cobertura parcial como completa")
    if (
        "ask_annual_doubt" in forbidden
        and status == "needs_clarification"
        and ("period" in missing or _ANNUAL_DOUBT.search(folded))
    ):
        violations.append("proibido: reapresentar intervalo explícito como dúvida anual")
    if "resume_previous_subject" in forbidden and (status == "sql_candidate" or "junho" in folded):
        violations.append("proibido: retomar o pedido anterior")

    calls = case["expected_source_calls"]
    if int(outcome.get("model_calls", 0)) > calls["max_model_calls"]:
        violations.append("excedeu chamadas ao modelo")
    if int(outcome.get("source_queries", 0)) > calls["max_source_queries"]:
        violations.append("excedeu consultas à fonte")
    return violations


def evaluate_all(
    cases: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    """Resultado por ID, com a primeira divergência em primeiro lugar; ID sem resultado falha."""
    report: dict[str, list[str]] = {}
    for case in cases:
        outcome = outcomes.get(case["id"])
        report[case["id"]] = (
            ["resultado ausente"] if outcome is None else evaluate_outcome(case, outcome)
        )
    return report
