"""Interpretação determinística e conservadora de perguntas em português."""

import re
import unicodedata

from app.schemas.analysis import AnalysisDomain, AnalysisIntent
from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.questions import ConversationTurn

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

    def interpret(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
    ) -> IntentInterpretation:
        previous_intent = self._previous_intent(context or [])
        if previous_intent is not None and not self._is_follow_up(question, previous_intent):
            previous_intent = None
        return self._interpret(question, previous_intent)

    @staticmethod
    def _is_follow_up(question: str, previous_intent: AnalysisIntent) -> bool:
        normalized = _normalize(question).strip()
        if re.match(r"^(?:e\b|tambem\b|nesse\b|neste\b|entao\b|agora\b)", normalized):
            return True

        geography = _find_phrases(question, GEOGRAPHIES)
        class_phrase = _find_phrases(question, CLASSES)
        metric_aliases = tuple(alias for _, phrases in METRIC_ALIASES for alias in phrases)
        metric_hits = _find_phrases(question, metric_aliases)
        explicit_domains = {
            domain
            for domain, phrases in METRIC_ALIASES
            if any(
                _normalize(alias) == _normalize(surface)
                for alias in phrases
                for _, _, surface in metric_hits
            )
        }
        periods = _find_phrases(question, PERIOD_PHRASES)
        has_comparison = bool(
            re.search(
                r"\b(?:compare|comparar|comparacao|cresceu|caiu|variacao|aumentou|reduziu)\b",
                normalized,
            )
        )

        # A filter-only continuation can inherit the last complete user intent.
        if (
            (geography or class_phrase)
            and not explicit_domains
            and not periods
            and not has_comparison
        ):
            return True
        # An explicit metric of the same domain plus a new filter is also a clear continuation.
        return bool(
            (geography or class_phrase)
            and explicit_domains == {previous_intent.domain}
            and not periods
            and not has_comparison
        )

    def _previous_intent(self, context: list[ConversationTurn]) -> AnalysisIntent | None:
        for turn in reversed(context):
            if turn.role != "user":
                continue
            previous = self._interpret(turn.content, None)
            if previous.status is InterpretationStatus.READY:
                return previous.intent
            # Do not jump over a more recent ambiguous user message to older context.
            return None
        return None

    def _interpret(
        self,
        question: str,
        base_intent: AnalysisIntent | None,
    ) -> IntentInterpretation:
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
        if not matched_domains and base_intent is None:
            return self._clarify(
                "Qual indicador ou assunto você quer consultar?"
            )

        domain = next(iter(matched_domains)) if matched_domains else base_intent.domain
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
        selected_metric = (
            next(
                surface
                for _, _, surface in metric_hits
                if any(
                    candidate_domain is domain and _normalize(candidate) == _normalize(surface)
                    for candidate_domain, candidate in aliases
                )
            )
            if metric_hits
            else base_intent.metric_phrase
        )
        periods = _find_phrases(question, PERIOD_PHRASES)
        normalized_question = _normalize(question)
        comparison_requested = len(periods) > 1 and " entre " in f" {normalized_question} "
        comparison_requested = comparison_requested or bool(
            re.search(
                r"\b(?:compare|comparar|comparacao|cresceu|caiu|variacao|aumentou|reduziu)\b",
                normalized_question,
            )
        )
        if not periods and base_intent is None:
            return self._clarify(
                "Qual período você quer consultar ou comparar?"
            )
        if not periods and comparison_requested:
            return self._clarify(
                "Qual período deve servir de base para essa comparação?"
            )
        if comparison_requested and len(periods) < 2:
            return self._clarify(
                "Qual período deve servir de base para essa comparação?"
            )
        if len(periods) > 1 and not comparison_requested:
            return self._clarify("Você mencionou mais de um período; quer compará-los?")
        if len(periods) > 1:
            period_phrase = question[periods[0][0] : periods[-1][1]]
        elif periods:
            period_phrase = periods[0][2]
        else:
            assert base_intent is not None
            period_phrase = base_intent.period_phrase

        filters: dict[str, str] = dict(base_intent.filters) if base_intent else {}
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
        intent_values = {
            "domain": domain,
            "metric_phrase": selected_metric,
            "period_phrase": period_phrase,
            "geography_phrase": (
                geography[-1][2]
                if geography
                else (base_intent.geography_phrase if base_intent else None)
            ),
            "class_phrase": (
                class_phrase[-1][2]
                if class_phrase
                else (base_intent.class_phrase if base_intent else None)
            ),
            "filters": filters,
        }
        intent = AnalysisIntent(
            **{name: value for name, value in intent_values.items() if value is not None}
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
