"""Decisão pública de assunto para recusas e esclarecimentos do Assistente.

O assunto declarado pelo modelo é um dado não confiável: aqui ele só é conferido contra o
estado do candidato e traduzido para um motivo tipado. Isso não prova entendimento
semântico; classificar como dentro do domínio algo externo continua sendo falha do modelo,
medida na avaliação, e a consulta ainda passa por AST, admissão e escopo independentes.
"""

import re
from dataclasses import dataclass

from app.schemas.sql_generation import SqlClarificationOption, SqlGenerationCandidate

_SUBJECT_QUESTION = (
    "Não consegui identificar o assunto da pergunta. Pode explicar a que ele se refere? "
    "Posso ajudar com os indicadores de energia da V-Energy."
)


class ScopeDecisionRejected(ValueError):
    """Candidato com decisão ausente ou contraditória; nunca chega à admissão."""


_STATEMENT = re.compile(
    r";|--|/\*|\b(?:select|insert|update|delete|drop|alter|create|truncate|grant|union)\b",
    re.IGNORECASE,
)


def _clean_options(options: tuple[SqlClarificationOption, ...]) -> tuple[dict, ...]:
    seen: set[str] = set()
    kept = []
    for option in options:
        key = " ".join(option.question.casefold().split())
        if (
            key in seen
            or _STATEMENT.search(option.question)
            or _STATEMENT.search(option.label)
        ):
            continue
        seen.add(key)
        kept.append({"label": option.label, "question": option.question})
    return tuple(kept)


def enforce_scope_decision(candidate: SqlGenerationCandidate) -> SqlGenerationCandidate:
    """Exige assunto declarado, recusa contradições e devolve o motivo normalizado."""
    scope = candidate.scope_assessment
    if scope is None:
        raise ScopeDecisionRejected("avaliação de assunto ausente")

    if candidate.status == "sql_candidate":
        if scope.status != "in_domain":
            raise ScopeDecisionRejected(
                "candidato executável exige assunto dentro do domínio"
            )
        return candidate

    payload = candidate.model_dump(mode="json")
    if candidate.status == "needs_clarification":
        reason = candidate.clarification.reason_code
        if scope.status == "uncertain":
            if reason not in {None, "ambiguous_subject"}:
                raise ScopeDecisionRejected(
                    "assunto incerto exige esclarecimento de assunto"
                )
            reason = "ambiguous_subject"
            asked = set(candidate.clarification.missing_fields)
            if asked & {"filter", "dimension"}:
                # Sigla ou termo desconhecido não é município nem classe: redação controlada.
                payload["clarification"]["question"] = _SUBJECT_QUESTION
                payload["clarification"]["missing_fields"] = ["context"]
                payload["clarification"]["options"] = ()
        elif scope.status == "out_of_domain":
            raise ScopeDecisionRejected(
                "assunto externo exige recusa, não esclarecimento"
            )
        elif reason in {None, "ambiguous_subject"}:
            # Assunto conhecido: a dúvida é de contexto, não de assunto.
            reason = "missing_context"
        payload["clarification"]["reason_code"] = reason
        if payload["clarification"]["options"]:
            payload["clarification"]["options"] = _clean_options(
                candidate.clarification.options
            )
    else:
        reason = candidate.unsupported_reason.reason_code
        if scope.status == "out_of_domain":
            if reason not in {None, "out_of_domain", "security_restriction"}:
                raise ScopeDecisionRejected(
                    "assunto externo exige recusa externa ou de segurança"
                )
            reason = reason or "out_of_domain"
        elif scope.status == "uncertain":
            raise ScopeDecisionRejected(
                "assunto incerto exige esclarecimento, não recusa"
            )
        elif reason == "out_of_domain":
            raise ScopeDecisionRejected(
                "motivo externo contradiz assunto dentro do domínio"
            )
        elif reason is None:
            # Código estrutural do contrato; nunca inferido do texto escrito pelo modelo.
            reason = "unsupported_capability"
        payload["unsupported_reason"]["reason_code"] = reason
    try:
        return SqlGenerationCandidate.model_validate(payload)
    except ValueError as exc:
        raise ScopeDecisionRejected("decisão normalizada inválida") from exc


# --- Ano completo: "em 2026" usa as competências disponíveis; "fechado" exige doze meses ---

_MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip
_CLOSED_YEAR = (
    # (padrão; ano no grupo 1 quando presente, prefixo da pergunta alternativa)
    (re.compile(r"\b(20\d{2})\s+(?:fechado|inteiro|completo)\b", re.IGNORECASE), ""),
    (
        re.compile(
            r"\b(?:no\s+|o\s+)?ano\s+(?:inteiro|completo)(?:\s+de)?\s+(20\d{2})\b",
            re.IGNORECASE,
        ),
        "em ",
    ),
    (
        re.compile(
            r"\bjaneiro\s+(?:a|at[eé])\s+dezembro(?:\s+de\s+(20\d{2}))?\b",
            re.IGNORECASE,
        ),
        "",
    ),
)
_ANY_YEAR = re.compile(r"\b(20\d{2})\b")


@dataclass(frozen=True)
class FullYearCoverageGap:
    year: int
    missing_months: tuple[str, ...]
    available_range: tuple[str, str] | None
    alternative_question: str | None


def _range_text(first: str, last: str) -> str:
    year = first[:4]
    first_name, last_name = _MONTHS[int(first[5:]) - 1], _MONTHS[int(last[5:]) - 1]
    return (
        f"{first_name} de {year}"
        if first == last
        else f"{first_name} a {last_name} de {year}"
    )


def _month_runs(months: tuple[str, ...]) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    for month in months:
        if runs and int(month[5:]) == int(runs[-1][1][5:]) + 1:
            runs[-1] = (runs[-1][0], month)
        else:
            runs.append((month, month))
    return runs


def full_year_coverage_gap(
    question: str, competencies: tuple[str, ...]
) -> FullYearCoverageGap | None:
    """Detecta pedido de ano completo sem cobertura dos doze meses.

    Ano simples (“em 2026”) e intervalo parcial explícito não passam por aqui. Sem ano
    reconhecível a decisão fica com o modelo.
    """
    for pattern, lead in _CLOSED_YEAR:
        match = pattern.search(question)
        if match is None:
            continue
        year_text = match.group(1)
        if year_text is None:
            found = _ANY_YEAR.search(question)
            year_text = found.group(1) if found else None
        if year_text is None:
            return None
        year = int(year_text)
        wanted = tuple(f"{year}-{month:02d}" for month in range(1, 13))
        present = set(competencies)
        available = tuple(month for month in wanted if month in present)
        missing = tuple(month for month in wanted if month not in present)
        if not missing:
            return None
        runs = _month_runs(available)
        if len(runs) != 1:
            return FullYearCoverageGap(year, missing, None, None)
        first, last = runs[0]
        range_text = _range_text(first, last)
        if match.group(1) is None:
            range_text = range_text.removesuffix(f" de {year}")
        alternative = (
            question[: match.start()] + lead + range_text + question[match.end() :]
        ).strip()
        return FullYearCoverageGap(year, missing, (first, last), alternative)
    return None


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def incomplete_year_candidate(
    gap: FullYearCoverageGap, *, generation_contract_version: str, context_version: str
) -> SqlGenerationCandidate:
    """Esclarecimento de cobertura sem consulta; a alternativa só usa meses publicados."""
    missing = _join(
        [_range_text(first, last) for first, last in _month_runs(gap.missing_months)]
    )
    options: list[dict[str, str]] = []
    if gap.available_range is not None:
        available = _range_text(*gap.available_range)
        text = (
            f"Os dados de {gap.year} cobrem {available}; faltam {missing}, então não há "
            f"cobertura do ano completo. Quer consultar {available}?"
        )
        if gap.alternative_question:
            options.append(
                {
                    "label": available[0].upper() + available[1:],
                    "question": gap.alternative_question,
                }
            )
    elif len(gap.missing_months) == 12:
        text = (
            f"Não há dados publicados de {gap.year}, "
            "então não é possível consultar o ano completo."
        )
    else:
        text = (
            f"Há lacunas nos dados de {gap.year}: faltam {missing}. "
            "Escolha um intervalo sem lacunas."
        )
    return SqlGenerationCandidate.model_validate(
        {
            "generation_contract_version": generation_contract_version,
            "status": "needs_clarification",
            "context_version": context_version,
            "scope_assessment": {"status": "in_domain"},
            "clarification": {
                "question": text,
                "missing_fields": ["period"],
                "reason_code": "insufficient_coverage",
                "options": options,
            },
        }
    )
