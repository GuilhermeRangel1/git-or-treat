"""Interpretação determinística por vocabulário e catálogo injetados."""

import re
import unicodedata

from app.agent.documentation import conceptual_question
from app.agent.language_recovery import intent_question
from app.agent.ranking import ranking_reference
from app.agent.temporal import (
    has_incomplete_calendar_period,
    missing_year_question,
    yearless_month_spans,
)
from app.schemas.analysis import AnalysisIntent
from app.schemas.domain_profile import (
    DimensionDefinition,
    DimensionRole,
    DomainProfile,
    MetricDefinition,
    UnitDefinition,
)
from app.schemas.interpretation import (
    ClarificationReason,
    IntentInterpretation,
    InterpretationStatus,
)
from app.schemas.questions import ConversationTurn

_PERCENTAGE_THRESHOLD = re.compile(
    r"(?<!\w)(?:acima de|abaixo de|mais de|menos de)\s+\d+(?:[.,]\d+)?\s*%",
    re.IGNORECASE,
)
_LOCATION_AFTER_PREPOSITION = re.compile(r"\b(?:em|no|na)\s+([\wÀ-ÿ-]+)", re.IGNORECASE)
# Calendário não é lugar: "em 2026", "em jun" e "em jun/26" seguem para a
# validação de período em vez de pedir confirmação da geografia.
_MONTH_ABBREVIATIONS = frozenset(
    ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
)
_AFTER_MONTH_ABBREVIATION = re.compile(r"(?:\.|/[0-9]{2}(?:[0-9]{2})?)?(?![\w/-])")
# Sem preposição de lugar, só a grafia de nome próprio sinaliza local: "de Recife" e
# "do Recife" sim, "de energia" e "de 2025" não. Siglas e nomes com hífen ficam de fora.
_PROPER_NAME_AFTER_DE = re.compile(
    r"(?<!\w)(?i:de|do|da|dos|das)\s+([A-ZÀ-Ý][a-zà-ÿ]+)(?![\w-])"
)
_ENDS_WITH_EM = re.compile(r"(?:^|\W)em\s+$")
_QUESTION_START = re.compile(
    r"^(?:por favor[, ]+)?(?:qual|quais|quanto|quanta|quantos|quantas|como|onde|"
    r"me mostr[ae]|me diga|me diz|quero saber|quero consultar|gostaria de saber|"
    r"queria saber|pode mostrar|da pra ver)\b"
)
_EXCLUDED_VALUE_PREFIX = re.compile(
    r"\b(?:exceto|menos|excluindo|excluir|exclua|tirando|retirando|desconsiderando|"
    r"desconsidere|(?:com|a)\s+excecao\s+de|sem\s+contar(?:\s+com)?|"
    r"(?:sem|nao)(?:\s+(?:ser|seja|sejam|e|incluir|inclua|considerar|apenas|somente|so))?|"
    r"(?:fora|diferentes?)\s+(?:de|do|da|dos|das))\s+"
    r"(?:(?:a|o|os|as|de|do|da|dos|das|classe|consumo|municipio|cidade|bairro|"
    r"alimentador|subgrupo|clientes?|consumidores?|unidades?|consumidoras?|ucs?|"
    r"dados|valores|receita|faturamento|todos|todas)\s+)*$"
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _join_labels(items: list[str], conjunction: str) -> str:
    """Lista legível: "A", "A e B", "A, B e C"."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


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

    def __init__(self, profile: DomainProfile, *, max_rows: int = 100) -> None:
        self._profile = profile
        self._max_rows = max_rows
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
        *,
        pending_temporal_intent: AnalysisIntent | None = None,
    ) -> IntentInterpretation:
        turns = context or []
        if (self._profile.structured_dimension_filters and len(turns) >= 2
                and turns[-2].role == "user" and turns[-1].role == "assistant"):
            original = turns[-2].content
            previous = self._interpret(original, None)
            # Uma resposta com dois períodos completa a comparação pendente;
            # conserva indicador/filtros e substitui o mês isolado anterior.
            if (previous.clarification_question == self._profile.clarifications.comparison_baseline
                    and not self._metric_matches(question)
                    and len(_find_phrases(question, self._profile.period_phrases)) == 2):
                for start, end, _ in reversed(
                    _find_phrases(original, self._profile.period_phrases)
                ):
                    original = original[:start] + " " * (end - start) + original[end:]
                return self._interpret(f"{original} {question}", None)
            if previous.clarification_reason is ClarificationReason.CONFLICTING_RANKING:
                answer = _normalize(question).strip(" ?!.")
                choice = {"maiores": "mais", "maior": "mais", "mais": "mais",
                          "menores": "menos", "menor": "menos", "menos": "menos"}.get(answer)
                if choice:
                    original = re.sub(r"\b(?:mais|menos|maior|menor)\b", choice,
                                      original, flags=re.IGNORECASE)
                    return self._interpret(original, None)
            if previous.clarification_reason is ClarificationReason.AMBIGUOUS_METRIC:
                pending = next((r for r in self._profile.ambiguities
                                if _find_phrases(original, r.phrases)), None)
                phrase = pending.confirmation_phrase if pending else None
                if pending and phrase is None and len(pending.alternative_metric_ids) == 1:
                    phrase = next(m.aliases[0] for m in self._profile.metrics
                                  if m.id == pending.alternative_metric_ids[0])
                confirmed = _normalize(question).strip(" ?!.") in {
                    "sim", "isso", "isso mesmo", "pode ser", "pode consultar",
                    *([_normalize(phrase)] if phrase else []),
                }
                if pending and phrase and confirmed:
                    for start, end, _ in reversed(_find_phrases(original, pending.phrases)):
                        original = original[:start] + " " * (end-start) + original[end:]
                    for dimension in self._profile.dimensions:
                        if any(_normalize(phrase) == _normalize(alias)
                               for value in dimension.values for alias in value.aliases):
                            aliases = tuple(alias for value in dimension.values
                                            for alias in value.aliases)
                            for start, end, _ in reversed(_find_phrases(original, aliases)):
                                original = original[:start] + " " * (end-start) + original[end:]
                    return self._interpret(f"{original} {phrase}", None)
                if confirmed:
                    return previous
            if previous.clarification_reason is ClarificationReason.MULTIPLE_METRICS:
                options = self._ordered_metric_options(original)
                answer = _normalize(question).strip(" ?!.")
                ordinal = re.fullmatch(
                    r"(?:(?:o|a|opcao)\s+)?(primeir[oa]|segund[oa]|terceir[oa]|[1-3])", answer,
                )
                index = ({"primeiro": 0, "primeira": 0, "segundo": 1, "segunda": 1,
                          "terceiro": 2, "terceira": 2, "1": 0, "2": 1, "3": 2}
                         .get(ordinal[1])) if ordinal else None
                selected = options[index] if index is not None and index < len(options) else next(
                    (metric for metric in options if re.sub(r"^(?:o|a)\s+", "", answer)
                     in {_normalize(a) for a in (*metric.aliases, metric.label or "")}), None,
                )
                if selected is not None:
                    for start, end, surface in reversed(self._metric_matches(original)):
                        if _normalize(surface) not in {_normalize(a) for a in selected.aliases}:
                            original = original[:start] + " " * (end-start) + original[end:]
                    return self._interpret(original, None)
                if not _QUESTION_START.match(answer) and len(answer.split()) <= 4:
                    return previous
        if (
            self._profile.structured_dimension_filters and len(turns) >= 2
            and turns[-2].role == "user" and turns[-1].role == "assistant"
            and self._interpret(turns[-2].content, None).clarification_reason
            is ClarificationReason.AMBIGUOUS_DIMENSION
        ):
            selected = [dimension for dimension in self._profile.dimensions
                        if _normalize(question).strip(" ?!.")
                        in {_normalize(alias) for alias in dimension.aliases}]
            if len(selected) == 1:
                original = turns[-2].content
                matches = self._dimension_value_matches(original, (selected[0],))
                if len(matches) == 1:
                    start, _, _ = matches[0]
                    clarified = original[:start] + selected[0].aliases[0] + " " + original[start:]
                    return self._interpret(clarified, self._previous_intent(turns[:-2]))
        pending_period_question = self._pending_period_question(turns)
        current_question_has_metric = bool(self._metric_matches(question))
        if (
            self._profile.structured_dimension_filters and not current_question_has_metric
            and len(turns) >= 2 and turns[-1].role == "assistant"
        ):
            previous_intent = self._previous_intent(turns)
            metric = next((m for m in self._profile.metrics
                           if previous_intent and m.id == previous_intent.metric_id), None)
            if (metric and set(metric.required_filter_dimension_ids)
                    - previous_intent.filters.keys()):
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
                 if _find_phrases(turns[-2].content, rule.phrases)), None
            )
            # Uma nova pergunta completa não é uma resposta ao esclarecimento
            # anterior: juntar os textos criaria métricas e recortes indevidos.
            starts_new_question = _QUESTION_START.match(_normalize(question).strip())
            if pending is not None and not starts_new_question:
                original = turns[-2].content
                for start, end, _ in reversed(_find_phrases(original, pending.phrases)):
                    original = original[:start] + " " * (end - start) + original[end:]
                return self._interpret(f"{original} {question}", None)
        if pending_temporal_intent is not None and not current_question_has_metric:
            periods = _find_phrases(question, self._profile.period_phrases)
            coverage_message = self._profile.clarifications.temporal_coverage_unavailable
            if periods:
                return self._interpret(question, pending_temporal_intent)
            if coverage_message is not None:
                return self._clarify(coverage_message)
        if pending_period_question is not None and not current_question_has_metric:
            combined_question = f"{pending_period_question} {question}"
            return self._interpret(combined_question, self._previous_intent(turns[:-2]))

        previous_intent = self._previous_intent(turns)
        if previous_intent is not None and not self._is_follow_up(question, previous_intent):
            previous_intent = None
        if previous_intent is not None:
            for dimension in self._profile.dimensions:
                value = previous_intent.filters.get(dimension.id)
                if isinstance(value, str):
                    for alias in dimension.aliases:
                        question = re.sub(
                            rf"\b(?:nesse|neste|nessa|nesta)\s+{re.escape(alias)}\b",
                            lambda match, label=alias, name=value: f"no {label} {name}",
                            question, flags=re.IGNORECASE,
                        )
            question = re.sub(
                r"\b(?:no|nesse|neste)\s+mesmo\s+m[eê]s\b", "",
                question, flags=re.IGNORECASE,
            )
        return self._interpret(question, previous_intent)

    def _pending_period_question(self, context: list[ConversationTurn]) -> str | None:
        if len(context) < 2:
            return None

        previous_user, previous_assistant = context[-2:]
        if (
            previous_user.role == "user"
            and previous_assistant.role == "assistant"
            and self._interpret(previous_user.content, None).clarification_reason
            in {ClarificationReason.MISSING_PERIOD, ClarificationReason.MISSING_YEAR}
        ):
            return previous_user.content
        return None

    def _is_follow_up(self, question: str, previous_intent: AnalysisIntent) -> bool:
        normalized = _normalize(question).strip()
        starters = "|".join(
            re.escape(_normalize(item)) for item in self._profile.follow_up_starters
        )
        if starters and re.match(rf"^(?:{starters})\b", normalized):
            return True

        geography = self._dimension_value_matches(question, self._geography_dimensions)
        class_phrase = self._dimension_value_matches(question, self._classification_dimensions)
        metric_hits = self._metric_matches(question)
        if (
            self._profile.structured_dimension_filters
            and metric_hits
            and _QUESTION_START.match(normalized)
        ):
            return False
        explicit_domains = {
            metric.domain_id
            for metric, alias in self._metric_aliases
            if any(_normalize(alias) == _normalize(surface) for _, _, surface in metric_hits)
        }
        periods = _find_phrases(question, self._profile.period_phrases)
        has_comparison = self._has_comparison(normalized)
        corrections = "|".join(
            re.escape(_normalize(term)) for term in self._profile.correction_terms
        )
        if (
            corrections
            and re.match(rf"^(?:{corrections})\b", normalized)
            and not metric_hits
            and (periods or geography or class_phrase)
        ):
            return True
        if self._profile.structured_dimension_filters and periods and not metric_hits:
            remaining = question
            spans = [*periods, *(_find_phrases(question, self._profile.comparison_terms)
                                if has_comparison else [])]
            for start, end, _ in sorted(spans, reverse=True):
                remaining = remaining[:start] + " " * (end - start) + remaining[end:]
            remaining = re.sub(r"\b(?:em|no|na|so|somente|apenas)\b", "", _normalize(remaining))
            if has_comparison:
                remaining = re.sub(r"\b(?:entre|e|de|a|com|para)\b", "", remaining)
            if not re.search(r"\w", remaining):
                return True

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
        self, question: str, base_intent: AnalysisIntent | None,
    ) -> IntentInterpretation:
        result = self._interpret_core(question, base_intent)
        if result.status is InterpretationStatus.NEEDS_CLARIFICATION and len(question) <= 1000:
            if base_intent is not None:
                updates = dict(base_intent.filters)
                for dimension in self._profile.dimensions:
                    matches = self._dimension_value_matches(question, (dimension,))
                    if matches and not self._has_unresolved_multiple_values(question, matches):
                        start, _, surface = matches[-1]
                        if _EXCLUDED_VALUE_PREFIX.search(_normalize(question[:start])):
                            continue
                        values = {v.value for v in dimension.values
                                  if _normalize(surface) in {_normalize(a) for a in v.aliases}}
                        if len(values) == 1:
                            updates[dimension.id] = next(iter(values))
                patch = {"filters": updates,
                         "dimension_ids": sorted(set(base_intent.dimension_ids) | set(updates))}
                periods = _find_phrases(question, self._profile.period_phrases)
                if len(periods) == 1:
                    patch.update(period_phrase=periods[0][2], comparison_period_phrases=None)
                base = intent_question(base_intent.model_copy(update=patch), self._profile)
                draft = f"{base} {question}" if base else None
            else:
                draft = question
            if draft is not None and len(draft) <= 1000:
                return result.model_copy(update={"pending_question": draft})
        return result

    def _interpret_core(
        self,
        question: str,
        base_intent: AnalysisIntent | None,
    ) -> IntentInterpretation:
        if self._profile.structured_dimension_filters and conceptual_question(question):
            return self._clarify(
                "Para consultar definições e fórmulas aprovadas, abra “Entenda os indicadores” "
                "no topo do Assistente. Para buscar valores, informe o indicador, o período "
                "e o recorte desejados."
            )
        # Só o calendário decide se o intervalo está incompleto: "entre Recife, Olinda e ..."
        # introduz locais e "entre as classes" pede agrupamento, não um intervalo de meses.
        calendar_question = question
        if self._profile.structured_dimension_filters:
            for start, _, _ in self._dimension_value_matches(question, self._profile.dimensions):
                between = re.search(r"\bentre\s+$", question[:start], flags=re.IGNORECASE)
                if between is not None:
                    calendar_question = (calendar_question[:between.start()]
                                         + " " * (start - between.start())
                                         + calendar_question[start:])
            grouping = self._requested_breakdown(question)
            if grouping is not None:
                calendar_question = self._without_grouping_reference(calendar_question, grouping)
        if (self._profile.structured_dimension_filters
                and has_incomplete_calendar_period(calendar_question)):
            return self._clarify(
                "Informe o mês e o ano de ambos os extremos do intervalo; "
                "preciso dos dois períodos para fazer essa consulta."
            )
        if self._profile.structured_dimension_filters and re.search(
            r"\b(?:[0-9]{1,2}\s+de\s+[a-zç]+\s+(?:de\s+)?[0-9]{4}"
            r"|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\b",
            _normalize(question),
        ):
            return self._clarify(
                "Consigo consultar meses completos. "
                "Informe o mês e o ano, sem selecionar dias."
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
            return self._clarify(ambiguity.clarification, ClarificationReason.AMBIGUOUS_METRIC)

        metric_hits = self._metric_matches(question)
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
        if len(matched_metrics) > 1 and self._profile.structured_dimension_filters:
            options = self._ordered_metric_options(question)
            labels = "; ".join(f"{i}) {m.label or m.aliases[0]}"
                               for i, m in enumerate(options, 1))
            return self._clarify(
                f"Qual indicador você quer consultar primeiro: {labels}?",
                ClarificationReason.MULTIPLE_METRICS,
            )
        if len(matched_domains) > 1:
            return self._clarify(self._profile.clarifications.multiple_domains)
        if len(matched_metrics) > 1:
            return self._clarify(self._profile.clarifications.multiple_metrics)
        if not matched_domains and base_intent is None:
            return self._clarify(
                self._profile.clarifications.missing_metric, ClarificationReason.MISSING_METRIC,
            )

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
        ranking = ranking_reference(
            _normalize(detail_question),
            tuple(_normalize(alias) for alias in breakdown.aliases),
        ) if grouping_allowed else None
        if ranking is not None and re.search(r"\b(?:mais|maior)\b", _normalize(detail_question)) \
                and re.search(r"\b(?:menos|menor)\b", _normalize(detail_question)):
            return self._clarify(
                "Você pediu os maiores e os menores resultados. Qual ranking quer consultar "
                "primeiro: maiores ou menores?", ClarificationReason.CONFLICTING_RANKING,
            )
        if ranking is not None and ranking.limit is not None and not 1 <= ranking.limit <= 100:
            return self._clarify("Consulte entre 1 e 100 resultados por pergunta.")
        if breakdown is not None and breakdown_message is not None and not grouping_allowed:
            # Sem agrupamento no plano, responder o total seria um falso acerto.
            return self._clarify(
                breakdown_message.replace("{dimension}", breakdown.label.lower())
            )

        filter_question = detail_question
        value_question = question
        location_question = question
        if grouping_allowed:
            # O nome da dimensão no pedido de contribuição não é um valor de filtro.
            filter_question = self._without_grouping_reference(filter_question, breakdown)
            location_question = filter_question
        structured = self._profile.structured_dimension_filters
        dimension_filters: dict[str, str | tuple[str, str]] = {}
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
                label = dimension.label[:1].lower() + dimension.label[1:]
                if self._has_unresolved_dimension_reference(filter_question, dimension, matches):
                    groupable = {
                        dimension_id for metric in self._profile.metrics
                        for dimension_id in metric.grouping_dimension_ids or ()
                    }
                    if dimension.id not in groupable and re.search(
                        r"\b(?:quais|liste|listar|lista)\b", _normalize(filter_question)
                    ):
                        # Registro individual não é recorte publicado: oferece os totais.
                        totals = [item.label[:1].lower() + item.label[1:]
                                  for item in self._profile.dimensions if item.id in groupable]
                        offer = (f" Posso mostrar totais por {_join_labels(totals, 'ou')}."
                                 if totals else "")
                        return self._clarify(
                            f"Não apresento resultados individuais por {label}.{offer}"
                        )
                    return self._clarify(
                        f"Há um valor não reconhecido de {label}. "
                        "Informe somente os valores autorizados que deseja consultar."
                    )
                if self._has_unresolved_multiple_values(question, matches):
                    if any(_EXCLUDED_VALUE_PREFIX.search(_normalize(question[:start]))
                           for start, _, _ in matches):
                        return self._clarify(
                            "Este recorte pede exclusão; informe o valor que deseja incluir."
                        )
                    if (
                        len(matches) == 2
                        and selected_metric is not None
                        and self._profile.supports_grouping
                        and dimension.id in (selected_metric.grouping_dimension_ids or ())
                        and re.search(r"\bentre\s+$", _normalize(question[:matches[0][0]]))
                        and re.fullmatch(
                            r"\s+e\s+", _normalize(question[matches[0][1]:matches[1][0]])
                        )
                    ):
                        resolved_values = [
                            {value.value for value in dimension.values
                             if any(
                                 _normalize(surface) == _normalize(alias) for alias in value.aliases
                             )}
                            for _, _, surface in matches
                        ]
                        ambiguous = any(
                            _normalize(surface) == _normalize(other_surface)
                            and (start, end) == (other_start, other_end)
                            for start, end, surface in matches
                            for other_dimension in self._profile.dimensions
                            if other_dimension.id != dimension.id
                            for other_start, other_end, other_surface in
                            self._dimension_value_matches(value_question, (other_dimension,))
                        )
                        if not ambiguous and all(len(values) == 1 for values in resolved_values):
                            first, second = (next(iter(values)) for values in resolved_values)
                            if first != second:
                                dimension_filters[dimension.id] = (first, second)
                                if breakdown is None:
                                    breakdown = dimension
                                    grouping_allowed = True
                                continue
                    cited = list(dict.fromkeys(surface for _, _, surface in matches))
                    return self._clarify(
                        f"Consulto um valor de {label} por vez; você citou "
                        f"{_join_labels(cited, 'e')}. Qual quer primeiro?"
                    )
                if matches:
                    prefix = _normalize(question[:matches[-1][0]])
                    if _EXCLUDED_VALUE_PREFIX.search(prefix):
                        return self._clarify(
                            "Este recorte pede exclusão; informe o valor que deseja incluir."
                        )
                    surface = _normalize(matches[-1][2])
                    if surface in matched_surfaces:
                        choices = [item.label for item in self._profile.dimensions
                                   if any(surface == _normalize(alias)
                                          for value in item.values for alias in value.aliases)]
                        return self._clarify(
                            f"Você quer consultar {matches[-1][2]} como "
                            f"{_join_labels(choices, 'ou')}? Responda com uma dessas opções.",
                            ClarificationReason.AMBIGUOUS_DIMENSION,
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
        if self._has_unrecognized_location_phrase(location_question, geography):
            return self._clarify(self._profile.clarifications.unknown_geography)
        unit_surface = self._incompatible_unit(question, selected_metric)
        unit_message = self._profile.clarifications.unit_mismatch
        if unit_surface is not None and unit_message is not None:
            return self._clarify(unit_message.replace("{unit}", unit_surface))
        detail_clarification = self._unsupported_detail(filter_question)
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
        metric_changed = (
            base_intent is not None and selected_metric is not None
            and base_intent.metric_id != selected_metric.id
        )
        if (self._profile.structured_dimension_filters and metric_changed
                and base_intent.group_by_dimension_ids and breakdown is None):
            return self._clarify(
                "A consulta anterior separava o resultado por grupos. "
                "Informe a abertura desejada para o novo indicador."
            )
        default_period_context_requested = bool(
            _find_phrases(question, self._profile.default_period_context_phrases)
        )
        configured_comparison_window = any(
            _normalize(surface) in self._comparison_period_phrases
            for _, _, surface in periods
        )
        normalized_question = _normalize(question)
        paired_filter = any(isinstance(value, tuple) for value in dimension_filters.values())
        comparison_requested = len(periods) > 1 and (
            bool(re.search(r"\bentre\s+$", _normalize(question[:periods[0][0]])))
            if paired_filter else " entre " in f" {normalized_question} "
        )
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
            year_question = missing_year_question(question, comparison=comparison_requested)
            if self._profile.structured_dimension_filters and year_question is not None:
                return self._clarify(year_question, ClarificationReason.MISSING_YEAR)
            return self._clarify(
                self._profile.clarifications.missing_period, ClarificationReason.MISSING_PERIOD,
            )
        if not periods and comparison_requested:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if comparison_requested and len(periods) < 2 and not configured_comparison_window:
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if len(periods) > 1 and not comparison_requested:
            return self._clarify(self._profile.clarifications.multiple_periods)
        comparison_phrases = (
            base_intent.comparison_period_phrases
            if base_intent is not None and not periods and selected_metric is not None
            else None
        )
        if (comparison_phrases is not None and selected_metric is not None
                and not selected_metric.supports_comparison):
            return self._clarify(self._profile.clarifications.comparison_baseline)
        if self._profile.structured_dimension_filters and comparison_requested:
            from app.agent.temporal import explicit_monthly_phrases
            explicit = explicit_monthly_phrases(question)
            if (
                selected_metric is None or not selected_metric.supports_comparison
                or len(explicit) != 2 or len(periods) != 2
            ):
                return self._clarify(self._profile.clarifications.comparison_baseline)
            comparison_phrases = (explicit[0], explicit[1])
            connector = _normalize(question[periods[0][1]:periods[1][0]])
            if re.search(r"\bem\s+(?:comparacao\s+com|relacao\s+ao?)\s+$", connector):
                comparison_phrases = (explicit[1], explicit[0])
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
        filters = dict(base_intent.filters) if base_intent else {}
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
        inherited_limit = base_intent.ranking_limit if same_metric_context else None
        intent_values = {
            "comparison_period_phrases": comparison_phrases,
            "group_by_dimension_ids": [breakdown.id] if grouping_allowed else inherited_groups,
            "ranking_direction": (
                "asc" if grouping_allowed and re.search(
                    r"\b(?:perdeu|caiu|reduziu|menor|menos)\b", _normalize(detail_question)
                ) else "desc" if grouping_allowed and re.search(
                    r"\b(?:mais|maior)\b", _normalize(detail_question)
                ) else "desc" if ranking is not None else inherited_order
            ),
            "ranking_limit": (
                (ranking.limit if ranking.limit is not None else self._max_rows)
                if ranking is not None
                and (comparison_phrases is None or ranking.explicit_count)
                else inherited_limit if same_metric_context else None
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

    def _metric_matches(self, question: str) -> list[tuple[int, int, str]]:
        matches = _find_phrases(question, tuple(alias for _, alias in self._metric_aliases))
        if not self._profile.structured_dimension_filters:
            return matches
        dimensions = _find_phrases(
            question, tuple(alias for d in self._profile.dimensions for alias in d.aliases)
        )
        # "Consumo" dentro do rótulo "classe de consumo" não pede outra métrica.
        return [match for match in matches if not any(
            start <= match[0] and match[1] <= end for start, end, _ in dimensions
        )]

    def _ordered_metric_options(self, question: str) -> list[MetricDefinition]:
        options = []
        for _, _, surface in self._metric_matches(question):
            for metric in self._profile.metrics:
                if (metric not in options and _normalize(surface)
                        in {_normalize(alias) for alias in metric.aliases}):
                    options.append(metric)
        return options

    @staticmethod
    def _without_grouping_reference(question: str, dimension: DimensionDefinition) -> str:
        normalized = _normalize(question)
        ranking = ranking_reference(normalized, tuple(_normalize(a) for a in dimension.aliases))
        if ranking is not None:
            tail = normalized[ranking.end:].lstrip()
            if not tail or re.match(
                r"^(?:[?.,;:]|(?:por|que|entre|em|no|na|nos|nas|com|sem|de|do|da|teve|tiveram|tem|"
                r"foi|foram|e|mais|menos|maior|menor|cresceu|caiu|perdeu|reduziu|aumentou)\b)",
                tail,
            ):
                question = (question[:ranking.start] + " " * (ranking.end - ranking.start)
                            + question[ranking.end:])
        for start, end, _ in reversed(_find_phrases(question, dimension.aliases)):
            prefix = re.search(
                r"\b(?:(?:em\s+)?qual\s+(?:(?:foi|é|e)\s+)?(?:(?:o|a)\s+)?"
                r"|por\s+(?:cada\s+)?|entre\s+(?:(?:as?|os?)\s+)?)$",
                question[:start], re.IGNORECASE,
            )
            tail = _normalize(question[end:]).lstrip()
            tail = re.sub(r"^(?:a|o)\s+", "", tail)
            # Um valor desconhecido depois de "por município" ainda é um filtro
            # não reconhecido; não o apagamos para responder todos os municípios.
            if prefix and (not tail or re.match(
                r"^(?:[?.,;:]|(?:em|no|na|nos|nas|com|sem|de|do|da|teve|tem|foi|e|"
                r"mais|menos|maior|menor|cresceu|caiu|perdeu|reduziu|aumentou)\b)", tail,
            )):
                question = question[:prefix.start()] + " " * (end - prefix.start()) + question[end:]
        return question

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
            # Uma localização introduzida por "em/de/do/da" usa o município quando o
            # nome também existe como bairro. Qualificadores explícitos prevalecem.
            if not qualified and re.search(r"\b(?:em|de|do|da)\s+$", prefix):
                parent_ids = {
                    dimension.parent_dimension_id for dimension in self._profile.dimensions
                    if dimension.parent_dimension_id and any(
                        _normalize(match[2]) == _normalize(alias)
                        for value in dimension.values for alias in value.aliases
                    )
                }
                qualified = {
                    dimension.id for dimension in self._profile.dimensions
                    if dimension.id in parent_ids and any(
                        _normalize(match[2]) == _normalize(alias)
                        for value in dimension.values for alias in value.aliases
                    )
                }
            for dimension in self._profile.dimensions:
                if dimension.parent_dimension_id and any(re.search(
                    rf"\bqual\s+(?:(?:o|a)\s+)?{re.escape(_normalize(alias))}\s+de\s+$",
                    prefix,
                ) for alias in dimension.aliases):
                    qualified = {dimension.parent_dimension_id}
                if dimension.parent_dimension_id:
                    aliases = "|".join(re.escape(_normalize(alias)) for alias in dimension.aliases)
                    reference = re.search(
                        rf"\b(?:{aliases})\s+(?P<value>.+?)\s+(?:de|do|da)\s+$", prefix,
                    )
                    if reference and reference["value"] in {
                        _normalize(alias) for value in dimension.values for alias in value.aliases
                    }:
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
        """Agrupamento por/entre dimensões, exceto quando um valor vem logo depois."""

        normalized = _normalize(question)
        for dimension in self._profile.dimensions:
            aliases = sorted(
                {_normalize(item) for item in dimension.aliases}, key=len, reverse=True
            )
            alternatives = "|".join(re.escape(alias) for alias in aliases)
            pattern = (rf"(?<!\w)(?:por\s+(?:cada\s+)?|entre\s+(?:(?:as?|os?)\s+)?)"
                       rf"(?:{alternatives})(?!\w)")
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
        for dimension in self._profile.dimensions:
            if ranking_reference(normalized, tuple(_normalize(a) for a in dimension.aliases)):
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

        if self._profile.structured_dimension_filters and re.search(
            r"(?:[<>]=?|!=)\s*(?:r\$\s*)?[+-]?[0-9]", question, re.IGNORECASE,
        ):
            return "Esse filtro por valor ainda não está disponível. Informe um recorte sem ele."
        period_spans = [
            (start, end)
            for start, end, _ in _find_phrases(question, self._profile.period_phrases)
        ]
        if self._profile.structured_dimension_filters:
            period_spans.extend(yearless_month_spans(question))
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
        # Um segundo local não pode desaparecer porque só o primeiro foi
        # reconhecido: "em Recife e Atlantis" não significa apenas Recife.
        for _, end, _ in recognized:
            joined = re.match(r"\s+(?:e|ou)\s+(?:(?:em|no|na)\s+)?(?P<name>\w+)",
                              question[end:], flags=re.IGNORECASE)
            if joined is not None:
                start = end + joined.start("name")
                stop = end + joined.end("name")
                word = _normalize(joined["name"])
                connectors = {"como", "quanto", "qual", "quais", "compare", "comparar",
                              "comparando", "quero", "queria", "gostaria", "preciso",
                              "teve", "tiveram", "foi", "foram", "somente", "apenas"}
                if word not in connectors and not any(
                    a <= start and stop <= b for a, b in recognized_spans
                ):
                    return True
        for match in _LOCATION_AFTER_PREPOSITION.finditer(question):
            start, end = match.span(1)
            word = _normalize(match.group(1))
            # Só ano completo: "em 10 março" é data diária e precisa continuar bloqueada.
            if (
                re.fullmatch(r"[0-9]{4}", word)
                or (word in _MONTH_ABBREVIATIONS
                    and _AFTER_MONTH_ABBREVIATION.match(question, end))
            ):
                continue
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
    def _clarify(
        question: str, reason: ClarificationReason | None = None,
    ) -> IntentInterpretation:
        return IntentInterpretation(
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            clarification_question=question,
            clarification_reason=reason,
        )
