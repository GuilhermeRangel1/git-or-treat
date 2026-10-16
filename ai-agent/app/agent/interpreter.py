"""Interpretação determinística e conservadora de perguntas em português."""

import re
import unicodedata

from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.scenarios import AnalysisDomain, AnalysisIntent

METRIC_ALIASES: tuple[tuple[AnalysisDomain, tuple[str, ...]], ...] = (
    (
        AnalysisDomain.NETWORK,
        (
            "falta de luz",
            "falta de energia",
            "interrupção de fornecimento",
            "interrupção",
            "interrupções",
        ),
    ),
    (AnalysisDomain.CONSUMPTION, ("queda de consumo", "consumo", "leitura", "leituras")),
    (AnalysisDomain.REVENUE, ("faturamento", "receita")),
    (AnalysisDomain.SERVICE, ("atendimentos", "atendimento", "chamados", "chamado")),
)
PERIOD_PHRASES = (
    "período de demonstração",
    "últimos 12 meses",
    "último ano",
    "ano passado",
    "último trimestre",
    "últimos três meses",
    "últimos 3 meses",
    "mês passado",
    "este ano",
    "neste mês",
)
GEOGRAPHIES = ("Jaboatão dos Guararapes", "Jaboatão", "Olinda")
CLASSES = ("poder público", "residencial", "comercial", "industrial")


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _find_phrases(text: str, phrases: tuple[str, ...]) -> list[tuple[int, int, str]]:
    normalized = _normalize(text)
    found: list[tuple[int, int, str]] = []
    for phrase in phrases:
        pattern = re.compile(rf"(?<!\w){re.escape(_normalize(phrase))}(?!\w)")
        for match in pattern.finditer(normalized):
            found.append((match.start(), match.end(), text[match.start() : match.end()]))
    ordered = sorted(found, key=lambda item: (item[0], -(item[1] - item[0])))
    non_overlapping: list[tuple[int, int, str]] = []
    for item in ordered:
        if any(item[0] < previous[1] and item[1] > previous[0] for previous in non_overlapping):
            continue
        non_overlapping.append(item)
    return non_overlapping


class QuestionInterpreter:
    """Mapeia vocabulário explícito sem inventar filtros ou normalizações de negócio."""

    def interpret(self, question: str) -> IntentInterpretation:
        aliases = [
            (domain, alias)
            for domain, phrases in METRIC_ALIASES
            for alias in phrases
        ]
        metric_hits = _find_phrases(question, tuple(alias for _, alias in aliases))
        matched_domains = {
            domain
            for domain, alias in aliases
            if any(_normalize(surface) == _normalize(alias) for _, _, surface in metric_hits)
        }

        account_phrase = _find_phrases(question, ("conta de luz",))
        if account_phrase and not metric_hits:
            return self._clarify(
                "Quando você diz ‘conta de luz’, quer saber de consumo, valor faturado, "
                "valor pago ou outro dado da fatura?"
            )
        if len(matched_domains) > 1:
            return self._clarify(
                "Você quer consultar qual assunto primeiro: consumo, faturamento, "
                "interrupções ou atendimento?"
            )
        if not matched_domains:
            return self._clarify(
                "Qual indicador ou assunto você quer consultar?"
            )

        domain = next(iter(matched_domains))
        geography = _find_phrases(question, GEOGRAPHIES)
        if self._has_unrecognized_capitalized_location(question, geography):
            return self._clarify(
                "Não reconheci esse local nas referências disponíveis; confirme "
                "a geografia desejada."
            )
        class_phrase = _find_phrases(question, CLASSES)
        if self._has_unresolved_multiple_values(question, geography):
            return self._clarify("Qual local você quer consultar?")
        if self._has_unresolved_multiple_values(question, class_phrase):
            return self._clarify("Qual classe de consumo você quer consultar?")
        selected_metric = next(
            surface
            for _, _, surface in metric_hits
            if any(
                candidate_domain is domain and _normalize(candidate) == _normalize(surface)
                for candidate_domain, candidate in aliases
            )
        )
        periods = _find_phrases(question, PERIOD_PHRASES)
        if not periods:
            return self._clarify(
                "Qual período você quer consultar ou comparar?"
            )
        normalized_question = _normalize(question)
        comparison_requested = len(periods) > 1 and " entre " in f" {normalized_question} "
        comparison_requested = comparison_requested or bool(
            re.search(
                r"\b(?:compare|comparar|comparacao|cresceu|caiu|variacao|aumentou|reduziu)\b",
                normalized_question,
            )
        )
        if comparison_requested and len(periods) < 2:
            return self._clarify(
                "Qual período deve servir de base para essa comparação?"
            )
        if len(periods) > 1 and not comparison_requested:
            return self._clarify("Você mencionou mais de um período; quer compará-los?")
        if len(periods) > 1:
            period_phrase = question[periods[0][0] : periods[-1][1]]
        else:
            period_phrase = periods[0][2]

        filters: dict[str, str] = {}
        directions = _find_phrases(
            question,
            ("queda", "redução", "aumento", "subida", "crescimento"),
        )
        if directions:
            filters["direction_phrase"] = directions[0][2]
        threshold = re.search(
            r"(?<!\w)(?:acima de|abaixo de|mais de|menos de)\s+\d+(?:[.,]\d+)?\s*%",
            _normalize(question),
        )
        if threshold:
            filters["threshold_phrase"] = question[threshold.start() : threshold.end()]
        intent = AnalysisIntent(
            domain=domain,
            metric_phrase=selected_metric,
            period_phrase=period_phrase,
            geography_phrase=geography[-1][2] if geography else None,
            class_phrase=class_phrase[-1][2] if class_phrase else None,
            filters=filters,
        )
        return IntentInterpretation(status=InterpretationStatus.READY, intent=intent)

    @staticmethod
    def _clarify(question: str) -> IntentInterpretation:
        return IntentInterpretation(
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            clarification_question=question,
        )

    @staticmethod
    def _has_unresolved_multiple_values(
        question: str,
        matches: list[tuple[int, int, str]],
    ) -> bool:
        distinct = []
        for match in matches:
            if not distinct or _normalize(match[2]) != _normalize(distinct[-1][2]):
                distinct.append(match)
        if len(distinct) < 2:
            return False

        normalized_question = _normalize(question)
        for previous, current in zip(distinct, distinct[1:], strict=False):
            between = normalized_question[previous[1] : current[0]]
            if not re.search(r"\b(?:nao|na verdade|corrigindo)\b", between):
                return True
        return False

    @staticmethod
    def _has_unrecognized_capitalized_location(
        question: str,
        recognized: list[tuple[int, int, str]],
    ) -> bool:
        recognized_spans = [(start, end) for start, end, _ in recognized]
        pattern = re.compile(r"\b(?:em|no|na)\s+([A-ZÀ-ÖØ-Þ][\wÀ-ÿ-]*)")
        for match in pattern.finditer(question):
            start, end = match.span(1)
            if not any(
                recognized_start == start and recognized_end >= end
                for recognized_start, recognized_end in recognized_spans
            ):
                return True
        return False
