"""Interpretação determinística por vocabulário e catálogo injetados."""

import re
import unicodedata

from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import (
    DimensionDefinition,
    DimensionRole,
    DomainProfile,
    MetricDefinition,
)
from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.questions import ConversationTurn

_PERCENTAGE_THRESHOLD = re.compile(
    r"(?<!\w)(?:acima de|abaixo de|mais de|menos de)\s+\d+(?:[.,]\d+)?\s*%",
    re.IGNORECASE,
)


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
    """Mapeia frases usando um perfil explícito, sem normalizar regras de negócio."""

    def __init__(self, profile: DomainProfile) -> None:
        self._profile = profile
        self._metric_aliases = tuple(
            (metric, alias) for metric in profile.metrics for alias in metric.aliases
        )
        self._geography_dimensions = tuple(
            dimension
            for dimension in profile.dimensions
            if dimension.role is DimensionRole.GEOGRAPHY
        )
        self._classification_dimensions = tuple(
            dimension
            for dimension in profile.dimensions
            if dimension.role is DimensionRole.CLASSIFICATION
        )

    def interpret(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
    ) -> IntentInterpretation:
        previous_intent = self._previous_intent(context or [])
        if previous_intent is not None and not self._is_follow_up(question, previous_intent):
            previous_intent = None
        return self._interpret(question, previous_intent)

    def _is_follow_up(self, question: str, previous_intent: AnalysisIntent) -> bool:
        normalized = _normalize(question).strip()
        starters = "|".join(
            re.escape(_normalize(item)) for item in self._profile.follow_up_starters
        )
        if starters and re.match(rf"^(?:{starters})\b", normalized):
            return True

        geography = self._dimension_value_matches(question, self._geography_dimensions)
        class_phrase = self._dimension_value_matches(question, self._classification_dimensions)
        metric_hits = _find_phrases(question, tuple(alias for _, alias in self._metric_aliases))
        explicit_domains = {
            metric.domain_id
            for metric, alias in self._metric_aliases
            if any(_normalize(alias) == _normalize(surface) for _, _, surface in metric_hits)
        }
        periods = _find_phrases(question, self._profile.period_phrases)
        has_comparison = self._has_comparison(normalized)

        if (
            (geography or class_phrase)
            and not explicit_domains
            and not periods
            and not has_comparison
        ):
            return True
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
            return None
        return None

    def _interpret(
        self,
        question: str,
        base_intent: AnalysisIntent | None,
    ) -> IntentInterpretation:
        ambiguity = next(
            (rule for rule in self._profile.ambiguities if _find_phrases(question, rule.phrases)),
            None,
        )
        if ambiguity is not None:
            return self._clarify(ambiguity.clarification)

        metric_hits = _find_phrases(question, tuple(alias for _, alias in self._metric_aliases))
        matched_metrics = {
            metric.id: metric
            for metric, alias in self._metric_aliases
            if any(_normalize(alias) == _normalize(surface) for _, _, surface in metric_hits)
        }
        matched_domains = {metric.domain_id for metric in matched_metrics.values()}
        if len(matched_domains) > 1:
            return self._clarify(self._profile.clarifications.multiple_domains)
        if len(matched_metrics) > 1:
            return self._clarify(self._profile.clarifications.multiple_metrics)
        if not matched_domains and base_intent is None:
            return self._clarify(self._profile.clarifications.missing_metric)

        selected_metric = self._select_metric(matched_metrics, base_intent)
        domain = next(iter(matched_domains)) if matched_domains else base_intent.domain

        geography = self._dimension_value_matches(question, self._geography_dimensions)
        if self._has_unrecognized_location_phrase(question, geography):
            return self._clarify(self._profile.clarifications.unknown_geography)
        class_phrase = self._dimension_value_matches(question, self._classification_dimensions)
        if self._has_unresolved_multiple_values(question, geography):
            return self._clarify(self._profile.clarifications.multiple_geographies)
        if self._has_unresolved_multiple_values(question, class_phrase):
            return self._clarify(self._profile.clarifications.multiple_classes)

        selected_alias = next(
            (
                surface
                for _, _, surface in metric_hits
                if selected_metric is not None
                and any(
                    metric.id == selected_metric.id and _normalize(alias) == _normalize(surface)
                    for metric, alias in self._metric_aliases
                )
            ),
            base_intent.metric_phrase if base_intent else None,
        )
        periods = _find_phrases(question, self._profile.period_phrases)
        normalized_question = _normalize(question)
        comparison_requested = len(periods) > 1 and " entre " in f" {normalized_question} "
        comparison_requested = comparison_requested or self._has_comparison(normalized_question)
        if not periods and base_intent is None:
            return self._clarify(self._profile.clarifications.missing_period)
        if not periods and comparison_requested:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if comparison_requested and len(periods) < 2:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if len(periods) > 1 and not comparison_requested:
            return self._clarify(self._profile.clarifications.multiple_periods)
        if len(periods) > 1:
            period_phrase = question[periods[0][0] : periods[-1][1]]
        elif periods:
            period_phrase = periods[0][2]
        else:
            assert base_intent is not None
            period_phrase = base_intent.period_phrase

        filters: dict[str, str] = dict(base_intent.filters) if base_intent else {}
        directions = _find_phrases(question, self._profile.direction_terms)
        if directions:
            filters["direction_phrase"] = directions[0][2]
        threshold = _PERCENTAGE_THRESHOLD.search(question)
        if threshold:
            filters["threshold_phrase"] = question[threshold.start() : threshold.end()]

        selected_dimension_ids = self._matched_dimension_ids(geography, class_phrase)
        intent_values = {
            "domain": domain,
            "metric_id": selected_metric.id if selected_metric else None,
            "metric_phrase": selected_alias,
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
            "dimension_ids": selected_dimension_ids
            or (base_intent.dimension_ids if base_intent else []),
            "filters": filters,
        }
        intent = AnalysisIntent(
            **{name: value for name, value in intent_values.items() if value is not None}
        )
        return IntentInterpretation(status=InterpretationStatus.READY, intent=intent)

    def _select_metric(
        self,
        matched: dict[str, MetricDefinition],
        base_intent: AnalysisIntent | None,
    ) -> MetricDefinition | None:
        if matched:
            return next(iter(matched.values()))
        if base_intent is None:
            return None
        return next(
            (
                metric
                for metric in self._profile.metrics
                if metric.id == base_intent.metric_id
                or (
                    metric.domain_id == base_intent.domain
                    and _normalize(base_intent.metric_phrase or "")
                    in {_normalize(alias) for alias in metric.aliases}
                )
            ),
            None,
        )

    def _matched_dimension_ids(
        self,
        geography: list[tuple[int, int, str]],
        classification: list[tuple[int, int, str]],
    ) -> list[str]:
        matched_surfaces = {_normalize(item[2]) for item in (*geography, *classification)}
        ids: list[str] = []
        for dimension in (*self._geography_dimensions, *self._classification_dimensions):
            aliases = {_normalize(alias) for value in dimension.values for alias in value.aliases}
            if aliases & matched_surfaces:
                ids.append(dimension.id)
        return ids

    @staticmethod
    def _dimension_value_matches(
        question: str,
        dimensions: tuple[DimensionDefinition, ...],
    ) -> list[tuple[int, int, str]]:
        phrases = tuple(
            alias
            for dimension in dimensions
            for value in dimension.values
            for alias in value.aliases
        )
        return _find_phrases(question, phrases)

    def _has_comparison(self, normalized_question: str) -> bool:
        return bool(_find_phrases(normalized_question, self._profile.comparison_terms))

    def _has_unresolved_multiple_values(
        self,
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
        correction_pattern = "|".join(
            re.escape(_normalize(term)) for term in self._profile.correction_terms
        )
        for previous, current in zip(distinct, distinct[1:], strict=False):
            between = normalized_question[previous[1] : current[0]]
            if not re.search(rf"\b(?:{correction_pattern})\b", between):
                return True
        return False

    def _has_unrecognized_location_phrase(
        self,
        question: str,
        recognized: list[tuple[int, int, str]],
    ) -> bool:
        protected = [
            *recognized,
            *self._dimension_value_matches(question, self._classification_dimensions),
            *_find_phrases(
                question,
                (
                    *self._profile.period_phrases,
                    *self._profile.comparison_terms,
                    *self._profile.direction_terms,
                    *(alias for _, alias in self._metric_aliases),
                    *(
                        alias
                        for dimension in self._profile.dimensions
                        for alias in dimension.aliases
                    ),
                ),
            ),
        ]
        recognized_spans = [(start, end) for start, end, _ in protected]
        pattern = re.compile(r"\b(?:em|no|na)\s+([\wÀ-ÿ-]+)", re.IGNORECASE)
        for match in pattern.finditer(question):
            start, end = match.span(1)
            if not any(
                recognized_start == start and recognized_end >= end
                for recognized_start, recognized_end in recognized_spans
            ):
                return True
        return False

    @staticmethod
    def _clarify(question: str) -> IntentInterpretation:
        return IntentInterpretation(
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            clarification_question=question,
        )
