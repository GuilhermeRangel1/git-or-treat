"""Sugere correções pequenas para confirmação; nunca autoriza nem executa a sugestão."""

import re
import unicodedata
from collections.abc import Iterator
from difflib import SequenceMatcher

from app.agent.temporal import complete_yearless_months
from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import DomainProfile
from app.schemas.questions import ConversationTurn


def intent_question(intent: AnalysisIntent, profile: DomainProfile) -> str | None:
    """Expressa somente slots representáveis; nenhuma restrição é descartada."""
    metric = next((m for m in profile.metrics if m.id == intent.metric_id), None)
    dimensions = {d.id: d for d in profile.dimensions}
    if (metric is None or len(intent.group_by_dimension_ids) > 1
            or set(intent.filters) - dimensions.keys()):
        return None
    question = metric.aliases[0]
    if intent.group_by_dimension_ids:
        dimension = dimensions.get(intent.group_by_dimension_ids[0])
        if dimension is None:
            return None
        if intent.ranking_direction:
            direction = "maior" if intent.ranking_direction == "desc" else "menor"
            question = (
                f"Top {intent.ranking_limit} {dimension.aliases[0]} com {direction} {question}"
                if intent.ranking_limit is not None
                else f"Qual {dimension.aliases[0]} teve {direction} {question}"
            )
        else:
            question += f" por {dimension.aliases[0]}"
    for key, value in intent.filters.items():
        dimension = dimensions[key]
        known = next((v for v in dimension.values if v.value == value), None)
        if known is None or not isinstance(value, str):
            return None
        # GD usa aliases como "com GD"; município/classe precisam do qualificador.
        alias = known.aliases[0]
        if key == "generation.distributed":
            question += " " + alias
        else:
            question += f" no {dimension.aliases[0]} {alias}"
    if intent.comparison_period_phrases:
        first, second = intent.comparison_period_phrases
        question = f"Compare {question} entre {first} e {second}"
    elif intent.period_phrase:
        question += f" em {intent.period_phrase}"
    return question + "?" if len(question) < 1000 else None


def _normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold())
                   if not unicodedata.combining(c))


def spelling_suggestions(question: str, profile: DomainProfile) -> Iterator[str]:
    """Um token desconhecido, um candidato inequívoco do catálogo e tamanho limitado.

    O chamador precisa validar o plano inteiro e pedir confirmação antes de executar.
    Não muda siglas, números, identificadores hifenizados ou frases com várias correções.
    """
    aliases = {
        alias for metric in profile.metrics for alias in metric.aliases
    } | {
        alias for dimension in profile.dimensions for value in dimension.values
        for alias in value.aliases
    }
    vocabulary = {
        _normalize(alias): alias for alias in aliases
        if re.fullmatch(r"[^\W\d_]{5,40}", alias, flags=re.UNICODE)
    }
    # Nomes de dimensões e métricas são palavras válidas, nunca erros de um valor parecido
    # (ex.: "bairro" não vira o bairro "BARRO"). O plural só acrescenta "s" após vogal.
    known_words = {
        word
        for alias in (
            *(alias for dimension in profile.dimensions for alias in dimension.aliases),
            *(alias for metric in profile.metrics for alias in metric.aliases),
        )
        for word in re.findall(r"[^\W\d_]+", _normalize(alias))
    }
    known_words |= {word + "s" for word in known_words if word[-1] in "aeiou"}
    proposals = []
    for token in list(re.finditer(r"(?<![\w-])[^\W\d_]{5,40}(?![\w-])", question))[:50]:
        text = _normalize(token.group())
        if text in vocabulary or text in known_words:
            continue
        candidates = [key for key in vocabulary if key[0] == text[0]
                      and abs(len(key) - len(text)) <= 2
                      and SequenceMatcher(None, text, key).ratio() >= .86]
        if len(candidates) == 1:
            proposals.append((token, vocabulary[candidates[0]]))
    if len(proposals) == 1:
        token, replacement = proposals[0]
        yield question[:token.start()] + replacement + question[token.end():]


def pending_year_answer(
    question: str, context: list[ConversationTurn], profile: DomainProfile,
) -> str | None:
    """Completa uma resposta curta explícita; o resultado ainda precisa ser interpretado."""
    if len(context) < 2 or context[-2].role != "user" or context[-1].role != "assistant":
        return None
    answer = _normalize(question).strip(" ?!.")
    match = re.fullmatch(r"(?P<choice>.*?)\s*(?:[,;]\s*)?(?P<year>[0-9]{4})", answer)
    if match is None:
        return None
    choice = re.sub(r"^(?:o|a|em|no ano de|ano de)\s+", "", match["choice"]).strip(" ,;")
    if choice in {"em", "no ano de", "ano de"}:
        choice = ""
    metrics = [metric for metric in profile.metrics
               if choice and choice in {_normalize(alias) for alias in metric.aliases}]
    if choice and len(metrics) != 1:
        return None
    original = context[-2].content
    if metrics:
        for rule in profile.ambiguities:
            if metrics[0].id in rule.alternative_metric_ids:
                for phrase in sorted(rule.phrases, key=len, reverse=True):
                    original = re.sub(r"(?<!\w)" + re.escape(_normalize(phrase)) + r"(?!\w)",
                                      " ", _normalize(original))
        original += " " + metrics[0].aliases[0]
    return complete_yearless_months(original, match["year"])
