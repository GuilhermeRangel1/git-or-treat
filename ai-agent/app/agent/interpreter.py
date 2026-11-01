"""Interpretação determinística por vocabulário e catálogo injetados."""

import re
import unicodedata

from app.agent.temporal import has_incomplete_calendar_period
from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import (
    DimensionDefinition,
    DimensionRole,
    DomainProfile,
    MetricDefinition,
    UnitDefinition,
)
from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.questions import ConversationTurn

_PERCENTAGE_THRESHOLD = re.compile(
    r"(?<!\w)(?:acima de|abaixo de|mais de|menos de)\s+\d+(?:[.,]\d+)?\s*%",
    re.IGNORECASE,
)
_LOCATION_AFTER_PREPOSITION = re.compile(r"\b(?:em|no|na)\s+([\wÀ-ÿ-]+)", re.IGNORECASE)
# Sem preposição de lugar, só a grafia de nome próprio sinaliza local: "de Recife" e
# "do Recife" sim, "de energia" e "de 2025" não. Siglas e nomes com hífen ficam de fora.
_PROPER_NAME_AFTER_DE = re.compile(
    r"(?<!\w)(?i:de|do|da|dos|das)\s+([A-ZÀ-Ý][a-zà-ÿ]+)(?![\w-])"
)
_ENDS_WITH_EM = re.compile(r"(?:^|\W)em\s+$")


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _find_phrases(text: str, phrases: tuple[str, ...]) -> list[tuple[int, int, str]]:
    normalized_chars: list[str] = []
    original_positions: list[int] = []
    for original_index, original_char in enumerate(text):
        decomposed = unicodedata.normalize("NFD", original_char.casefold())
        for normalized_char in decomposed:
            if not unicodedata.combining(normalized_char):
                normalized_chars.append(normalized_char)
                original_positions.append(original_index)
    normalized = "".join(normalized_chars)
    found: list[tuple[int, int, str]] = []
    for phrase in phrases:
        pattern = re.compile(rf"(?<!\w){re.escape(_normalize(phrase))}(?!\w)")
        for match in pattern.finditer(normalized):
            start = original_positions[match.start()]
            end = original_positions[match.end() - 1] + 1
            found.append((start, end, text[start:end]))
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
        self._comparison_period_phrases = frozenset(
            _normalize(item) for item in profile.comparison_period_phrases
        )
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
        # Em "queda de energia" o termo de direção nomeia o próprio evento; em "queda de
        # consumo" ele qualifica outro sinônimo da mesma métrica e continua sendo direção.
        self._aliases_absorbing_direction = frozenset(
            _normalize(alias)
            for metric, alias in self._metric_aliases
            if _find_phrases(alias, profile.direction_terms)
            and not any(
                _find_phrases(alias, (other,))
                for other in metric.aliases
                if _normalize(other) != _normalize(alias)
            )
        )
        self._unit_aliases = tuple(alias for unit in profile.units for alias in unit.aliases)
        self._units_by_alias: dict[str, UnitDefinition] = {
            _normalize(alias): unit for unit in profile.units for alias in unit.aliases
        }
        self._detail_phrases = tuple(
            phrase for rule in profile.detail_rules for phrase in rule.phrases
        )
        # Palavra já usada em alguma frase do perfil ("Energia" de "falta de energia")
        # não é tratada como nome de lugar desconhecido.
        self._profile_words = frozenset(
            word
            for phrase in (
                *(alias for _, alias in self._metric_aliases),
                *profile.period_phrases,
                *profile.comparison_terms,
                *profile.direction_terms,
                *profile.correction_terms,
                *self._unit_aliases,
                *self._detail_phrases,
                *(
                    alias
                    for dimension in profile.dimensions
                    for alias in (
                        *dimension.aliases,
                        *(item for value in dimension.values for item in value.aliases),
                    )
                ),
            )
            for word in re.findall(r"\w+", _normalize(phrase))
        )

    def interpret(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
    ) -> IntentInterpretation:
        turns = context or []
        pending_period_question = self._pending_period_question(turns)
        current_question_has_metric = bool(
            _find_phrases(question, tuple(alias for _, alias in self._metric_aliases))
        )
        if (
            self._profile.structured_dimension_filters and not current_question_has_metric
            and len(turns) >= 2 and turns[-1].role == "assistant"
        ):
            dimensions = {dimension.id: dimension for dimension in self._profile.dimensions}
            messages = {
                "Informe o filtro obrigatório: "
                + ", ".join(dimensions[key].label.lower()
                            for key in sorted(metric.required_filter_dimension_ids)) + "."
                for metric in self._profile.metrics if metric.required_filter_dimension_ids
            }
            if turns[-1].content in messages:
                previous_intent = self._previous_intent(turns)
                if previous_intent is not None:
                    return self._interpret(question, previous_intent)
        if (
            self._profile.structured_dimension_filters
            and current_question_has_metric
            and len(turns) >= 2
            and turns[-2].role == "user"
            and turns[-1].role == "assistant"
        ):
            pending = next(
                (rule for rule in self._profile.ambiguities
                 if rule.clarification == turns[-1].content), None
            )
            if pending is not None:
                original = turns[-2].content
                for start, end, _ in reversed(_find_phrases(original, pending.phrases)):
                    original = original[:start] + " " * (end - start) + original[end:]
                return self._interpret(f"{original} {question}", None)
        if (
            self._pending_period_coverage_answer(turns)
            and not current_question_has_metric
        ):
            previous_intent = self._previous_intent(turns)
            periods = _find_phrases(question, self._profile.period_phrases)
            coverage_message = self._profile.clarifications.temporal_coverage_unavailable
            if previous_intent is not None and periods:
                return self._interpret(question, previous_intent)
            if coverage_message is not None:
                return self._clarify(coverage_message)
        if pending_period_question is not None and not current_question_has_metric:
            combined_question = f"{pending_period_question} {question}"
            return self._interpret(combined_question, None)

        previous_intent = self._previous_intent(turns)
        if previous_intent is not None and not self._is_follow_up(question, previous_intent):
            previous_intent = None
        return self._interpret(question, previous_intent)

    def _pending_period_question(self, context: list[ConversationTurn]) -> str | None:
        if len(context) < 2:
            return None

        previous_user, previous_assistant = context[-2:]
        if (
            previous_user.role == "user"
            and previous_assistant.role == "assistant"
            and previous_assistant.content == self._profile.clarifications.missing_period
        ):
            return previous_user.content
        return None

    def _pending_period_coverage_answer(self, context: list[ConversationTurn]) -> bool:
        if len(context) < 2:
            return False

        previous_assistant = context[-1]
        message = self._profile.clarifications.temporal_coverage_unavailable
        return (
            message is not None
            and context[-2].role == "user"
            and previous_assistant.role == "assistant"
            and previous_assistant.content == message
        )

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
        if self._profile.structured_dimension_filters:
            # Reinterpreta a última fala com o trecho anterior que ainda cabe no
            # contrato. O prefixo diminui a cada chamada; histórico não vira estado
            # confiável e a política atual continuará aprovando o plano resultante.
            for index in range(len(context) - 1, -1, -1):
                if context[index].role != "user":
                    continue
                previous = self.interpret(context[index].content, context[:index])
                return previous.intent if previous.status is InterpretationStatus.READY else None
            return None
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
        if self._profile.structured_dimension_filters and has_incomplete_calendar_period(question):
            return self._clarify(
                "Informe o mês e o ano de ambos os extremos do intervalo; "
                "não vou reduzir a consulta ao único mês reconhecido."
            )
        if self._profile.structured_dimension_filters and re.search(
            r"\b(?:[0-9]{1,2}\s+de\s+[a-zç]+\s+(?:de\s+)?[0-9]{4}"
            r"|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\b",
            _normalize(question),
        ):
            return self._clarify(
                "Este planejamento aceita competências mensais; "
                "informe o mês e o ano completos, sem selecionar dias."
            )
        ambiguity = next(
            (rule for rule in self._profile.ambiguities
             if _find_phrases(question, rule.phrases)
             and not any(metric.id in rule.resolved_metric_ids
                         and _find_phrases(question, metric.aliases)
                         for metric in self._profile.metrics)),
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
        if len(matched_metrics) > 1:
            candidates = [metric for metric in matched_metrics.values()
                          if set(matched_metrics) - {metric.id} <= set(metric.absorbed_metric_ids)]
            if len(candidates) == 1:
                matched_metrics = {candidates[0].id: candidates[0]}
        matched_domains = {metric.domain_id for metric in matched_metrics.values()}
        if len(matched_domains) > 1:
            return self._clarify(self._profile.clarifications.multiple_domains)
        if len(matched_metrics) > 1:
            return self._clarify(self._profile.clarifications.multiple_metrics)
        if not matched_domains and base_intent is None:
            return self._clarify(self._profile.clarifications.missing_metric)

        selected_metric = self._select_metric(matched_metrics, base_intent)
        if selected_metric is not None and selected_metric.accumulated_metric_id:
            accumulated = next((item for item in self._profile.metrics
                                if item.id == selected_metric.accumulated_metric_id), None)
            if accumulated is not None and _find_phrases(
                question, accumulated.accumulated_period_phrases
            ):
                selected_metric = accumulated
        domain = next(iter(matched_domains)) if matched_domains else base_intent.domain

        # O nome cadastrado da métrica não é um pedido adicional de agregação:
        # "consumo médio por UC" não solicita uma abertura por UC nem média do total.
        # Qualificadores fora do nome continuam sujeitos às regras do perfil.
        detail_question = question
        for start, end, _ in reversed(metric_hits):
            detail_question = detail_question[:start] + " " * (end - start) + detail_question[end:]
        if selected_metric is not None:
            for alias in selected_metric.aggregate_subject_aliases:
                detail_question = re.sub(
                    rf"\bquant[oa]s?\s+{re.escape(alias)}\b",
                    lambda match: " " * len(match.group()), detail_question, flags=re.IGNORECASE,
                )
        breakdown = self._requested_breakdown(detail_question)
        breakdown = breakdown or self._requested_ranking_dimension(detail_question)
        breakdown_message = self._profile.clarifications.unsupported_breakdown
        grouping_allowed = (
            breakdown is not None and selected_metric is not None
            and self._profile.supports_grouping
            and selected_metric.grouping_dimension_ids is not None
            and breakdown.id in selected_metric.grouping_dimension_ids
        )
        if breakdown is not None and breakdown_message is not None and not grouping_allowed:
            # Sem agrupamento no plano, responder o total seria um falso acerto.
            return self._clarify(
                breakdown_message.replace("{dimension}", breakdown.label.lower())
            )

        filter_question = detail_question
        value_question = question
        if grouping_allowed:
            # O nome da dimensão no pedido de contribuição não é um valor de filtro.
            aliases = "|".join(re.escape(alias) for alias in breakdown.aliases)
            filter_question = re.sub(
                rf"\bqual\s+(?:(?:o|a)\s+)?(?:{aliases})\b",
                lambda match: " " * len(match.group()), filter_question,
                flags=re.IGNORECASE,
            )
        structured = self._profile.structured_dimension_filters
        dimension_filters: dict[str, str] = {}
        if structured:
            matched_surfaces: dict[str, str] = {}
            known_spans = self._dimension_value_matches(value_question, self._profile.dimensions)
            for dimension in self._profile.dimensions:
                matches = self._dimension_value_matches(value_question, (dimension,))
                # Um valor completo (AL-TESTE) absorve um fragmento conhecido
                # de outra dimensão (classe TESTE), sem apagar menção separada.
                matches = [match for match in matches if not any(
                    start <= match[0] and match[1] <= end
                    and (start, end) != match[:2]
                    for start, end, _ in known_spans
                )]
                if self._has_unresolved_dimension_reference(filter_question, dimension, matches):
                    return self._clarify(
                        f"Há um valor não reconhecido de {dimension.label.lower()}. "
                        "Informe somente os valores autorizados que deseja consultar."
                    )
                if self._has_unresolved_multiple_values(question, matches):
                    return self._clarify(
                        f"Informe um único valor de {dimension.label.lower()} "
                        "ou uma correção explícita."
                    )
                if matches:
                    prefix = _normalize(question[:matches[-1][0]])
                    if re.search(
                        r"\b(?:exceto|sem|menos|nao)\s+"
                        r"(?:(?:a|o|classe|municipio|bairro)\s+)*$", prefix
                    ):
                        return self._clarify(
                            "Este recorte pede exclusão; informe o valor que deseja incluir."
                        )
                    surface = _normalize(matches[-1][2])
                    if surface in matched_surfaces:
                        return self._clarify(
                            "O mesmo nome corresponde a mais de uma dimensão; "
                            "especifique outro recorte sem ambiguidade."
                        )
                    matched_surfaces[surface] = dimension.id
                    candidates = {
                        value.value for value in dimension.values
                        if surface in {_normalize(alias) for alias in value.aliases}
                    }
                    if len(candidates) != 1:
                        return self._clarify("O filtro informado é ambíguo neste catálogo.")
                    dimension_filters[dimension.id] = next(iter(candidates))
                elif _find_phrases(filter_question, dimension.aliases):
                    return self._clarify(
                        f"Informe um valor autorizado de {dimension.label.lower()}; "
                        "o filtro solicitado não foi reconhecido."
                    )
        geography = self._dimension_value_matches(question, self._geography_dimensions)
        if self._has_unrecognized_location_phrase(question, geography):
            return self._clarify(self._profile.clarifications.unknown_geography)
        unit_surface = self._incompatible_unit(question, selected_metric)
        unit_message = self._profile.clarifications.unit_mismatch
        if unit_surface is not None and unit_message is not None:
            return self._clarify(unit_message.replace("{unit}", unit_surface))
        detail_clarification = self._unsupported_detail(detail_question)
        if detail_clarification is not None:
            return self._clarify(detail_clarification)
        class_phrase = self._dimension_value_matches(question, self._classification_dimensions)
        if not structured and self._has_unresolved_multiple_values(question, geography):
            return self._clarify(self._profile.clarifications.multiple_geographies)
        if not structured and self._has_unresolved_multiple_values(question, class_phrase):
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
        default_period_context_requested = bool(
            _find_phrases(question, self._profile.default_period_context_phrases)
        )
        configured_comparison_window = any(
            _normalize(surface) in self._comparison_period_phrases
            for _, _, surface in periods
        )
        normalized_question = _normalize(question)
        comparison_requested = len(periods) > 1 and " entre " in f" {normalized_question} "
        comparison_requested = comparison_requested or self._has_comparison(normalized_question)
        comparison_requested = comparison_requested or configured_comparison_window
        if (selected_metric is not None and selected_metric.requires_published_windows
                and not periods):
            comparison_requested = False
        metric_default_period = selected_metric.default_period_phrase if selected_metric else None
        if (
            not periods
            and metric_default_period is None
            and base_intent is None
            and (
                self._profile.default_period_phrase is None
                or (
                    self._profile.default_period_context_phrases
                    and not default_period_context_requested
                )
            )
        ):
            return self._clarify(self._profile.clarifications.missing_period)
        if not periods and comparison_requested:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if comparison_requested and len(periods) < 2 and not configured_comparison_window:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if len(periods) > 1 and not comparison_requested:
            return self._clarify(self._profile.clarifications.multiple_periods)
        comparison_phrases = (
            base_intent.comparison_period_phrases
            if base_intent is not None and not periods and selected_metric is not None
            and base_intent.metric_id == selected_metric.id else None
        )
        if self._profile.structured_dimension_filters and comparison_requested:
            from app.agent.temporal import explicit_monthly_phrases
            explicit = explicit_monthly_phrases(question)
            if (
                selected_metric is None or not selected_metric.supports_comparison
                or len(explicit) != 2 or len(periods) != 2
            ):
                return self._clarify(self._profile.clarifications.comparison_baseline)
            comparison_phrases = (explicit[0], explicit[1])
        if len(periods) > 1:
            period_phrase = question[periods[0][0] : periods[-1][1]]
        elif periods:
            period_phrase = (
                self._profile.comparison_period_phrases[0]
                if configured_comparison_window
                else periods[0][2]
            )
        elif base_intent is None:
            period_phrase = metric_default_period or self._profile.default_period_phrase
            assert period_phrase is not None
        else:
            assert base_intent is not None
            period_phrase = base_intent.period_phrase

        if comparison_phrases is not None:
            period_phrase = comparison_phrases[0]
        filters: dict[str, str] = dict(base_intent.filters) if base_intent else {}
        filters.update(dimension_filters)
        directions = [
            direction
            for direction in _find_phrases(question, self._profile.direction_terms)
            if not any(
                start <= direction[0] and direction[1] <= end
                and _normalize(surface) in self._aliases_absorbing_direction
                for start, end, surface in metric_hits
            )
        ]
        if directions and comparison_phrases is None:
            filters["direction_phrase"] = directions[0][2]
        threshold = _PERCENTAGE_THRESHOLD.search(question)
        if threshold and not any(
            start <= threshold.start() and threshold.end() <= end for start, end, _ in metric_hits
        ):
            filters["threshold_phrase"] = question[threshold.start() : threshold.end()]

        selected_dimension_ids = self._matched_dimension_ids(geography, class_phrase)
        same_metric_context = (
            base_intent is not None and selected_metric is not None
            and base_intent.metric_id == selected_metric.id
        )
        inherited_groups = base_intent.group_by_dimension_ids if same_metric_context else []
        inherited_order = base_intent.ranking_direction if same_metric_context else None
        intent_values = {
            "comparison_period_phrases": comparison_phrases,
            "group_by_dimension_ids": [breakdown.id] if grouping_allowed else inherited_groups,
            "ranking_direction": (
                "asc" if grouping_allowed and re.search(
                    r"\b(?:perdeu|caiu|reduziu|menor|menos)\b", _normalize(detail_question)
                ) else "desc" if grouping_allowed and re.search(
                    r"\b(?:mais|maior)\b", _normalize(detail_question)
                ) else inherited_order
            ),
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
        if structured:
            intent_values["geography_phrase"] = None
            intent_values["class_phrase"] = None
            intent_values["dimension_ids"] = sorted(
                set(base_intent.dimension_ids if base_intent else ()) | set(dimension_filters)
            )
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
    def _has_unresolved_dimension_reference(
        question: str,
        dimension: DimensionDefinition,
        values: list[tuple[int, int, str]],
    ) -> bool:
        for start, end, _ in _find_phrases(question, dimension.aliases):
            if any(value_start <= start and end <= value_end
                   for value_start, value_end, _ in values):
                continue
            if not any(
                value_start >= end
                and re.fullmatch(r"\s*(?:(?:de|da|do)\s+)?[:=]?\s*",
                                 _normalize(question[end:value_start]))
                for value_start, _, _ in values
            ):
                return True
        return False

    def _dimension_value_matches(
        self,
        question: str,
        dimensions: tuple[DimensionDefinition, ...],
    ) -> list[tuple[int, int, str]]:
        phrases = tuple(
            alias
            for dimension in dimensions
            for value in dimension.values
            for alias in value.aliases
        )
        matches = _find_phrases(question, phrases)
        selected = []
        for match in matches:
            prefix = _normalize(question[:match[0]])
            qualified = {
                dimension.id for dimension in self._profile.dimensions
                if any(_normalize(match[2]) == _normalize(alias)
                       for value in dimension.values for alias in value.aliases)
                and any(re.search(
                    rf"\b{re.escape(_normalize(alias))}\s+(?:(?:de|do|da)\s+)?$", prefix
                ) for alias in dimension.aliases)
            }
            for dimension in self._profile.dimensions:
                if dimension.parent_dimension_id and any(re.search(
                    rf"\bqual\s+(?:(?:o|a)\s+)?{re.escape(_normalize(alias))}\s+de\s+$",
                    prefix,
                ) for alias in dimension.aliases):
                    qualified = {dimension.parent_dimension_id}
            if not qualified or any(
                dimension.id in qualified and any(
                    _normalize(match[2]) == _normalize(alias)
                    for value in dimension.values for alias in value.aliases
                ) for dimension in dimensions
            ):
                selected.append(match)
        return selected

    def _requested_breakdown(self, question: str) -> DimensionDefinition | None:
        """Dimensão pedida em "por <alias>", exceto quando um valor dela vem logo depois."""

        normalized = _normalize(question)
        for dimension in self._profile.dimensions:
            aliases = sorted(
                {_normalize(item) for item in dimension.aliases}, key=len, reverse=True
            )
            alternatives = "|".join(re.escape(alias) for alias in aliases)
            pattern = rf"(?<!\w)por\s+(?:cada\s+)?(?:{alternatives})(?!\w)"
            values = {_normalize(item) for value in dimension.values for item in value.aliases}
            for match in re.finditer(pattern, normalized):
                # "por classe residencial" e "por município de Olinda" são filtros.
                rest = normalized[match.end() :]
                if any(
                    re.match(rf"\s+(?:(?:de|da|do)\s+)?{re.escape(value)}(?!\w)", rest)
                    for value in values
                ):
                    continue
                return dimension
        return None

    def _requested_ranking_dimension(self, question: str) -> DimensionDefinition | None:
        """Detecta perguntas de maior/menor por dimensão que exigiriam agrupamento e ordem."""

        normalized = _normalize(question)
        ranking = r"(?:mais|menos|maior|menor|cresceu|caiu|perdeu|reduziu|aumentou)"
        for dimension in self._profile.dimensions:
            aliases = sorted(
                {_normalize(item.rstrip("s")) for item in dimension.aliases},
                key=len,
                reverse=True,
            )
            alternatives = "|".join(re.escape(alias) for alias in aliases)
            pattern = (
                rf"\b(?:qual|quais)\s+(?:(?:foi|foram|e)\s+)?"
                rf"(?:o|a|os|as)?\s*(?:{alternatives})\b[^?]*\b{ranking}\b"
            )
            if re.search(pattern, normalized):
                return dimension
        return None

    def _incompatible_unit(self, question: str, metric: MetricDefinition | None) -> str | None:
        """Unidade citada em "em <unidade>" cujo tipo a métrica não aceita."""

        if metric is None or not metric.accepted_unit_kinds:
            return None
        for start, _end, surface in _find_phrases(question, self._unit_aliases):
            if not _ENDS_WITH_EM.search(_normalize(question[:start])):
                continue
            if self._units_by_alias[_normalize(surface)].kind not in metric.accepted_unit_kinds:
                return surface
        return None

    def _unsupported_detail(self, question: str) -> str | None:
        """Pedido de detalhe que o perfil não atende, fora de um período do catálogo."""

        period_spans = [
            (start, end)
            for start, end, _ in _find_phrases(question, self._profile.period_phrases)
        ]
        for rule in self._profile.detail_rules:
            if rule.clarification is None:
                continue
            for start, end, _ in _find_phrases(question, rule.phrases):
                if not any(
                    period_start <= start and end <= period_end
                    for period_start, period_end in period_spans
                ):
                    return rule.clarification
        return None

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
            *self._dimension_value_matches(
                question, self._profile.dimensions
            ),
            *self._dimension_value_matches(question, self._classification_dimensions),
            *_find_phrases(question, self._profile.non_location_phrases),
            *_find_phrases(
                question,
                (
                    *self._profile.period_phrases,
                    *self._profile.comparison_terms,
                    *self._profile.direction_terms,
                    *self._profile.correction_terms,
                    *(alias for _, alias in self._metric_aliases),
                    *(
                        alias
                        for dimension in self._profile.dimensions
                        for alias in dimension.aliases
                    ),
                    *self._unit_aliases,
                    *self._detail_phrases,
                ),
            ),
        ]
        recognized_spans = [(start, end) for start, end, _ in protected]
        for match in _LOCATION_AFTER_PREPOSITION.finditer(question):
            start, end = match.span(1)
            # O trecho conhecido pode começar na palavra ou na própria preposição ("na verdade").
            if not any(
                recognized_start in (start, match.start()) and recognized_end >= end
                for recognized_start, recognized_end in recognized_spans
            ):
                return True
        # Contido em qualquer trecho conhecido: "Falta de Luz" e "período de Demonstração"
        # não são nomes de lugar.
        for match in _PROPER_NAME_AFTER_DE.finditer(question):
            start, end = match.span(1)
            if _normalize(match.group(1)) in self._profile_words:
                continue
            if not any(
                recognized_start <= start and end <= recognized_end
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
