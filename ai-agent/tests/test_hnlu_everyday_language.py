"""Regressões da NLU Gold para termos cotidianos, calendário e continuação."""

from datetime import date

from app.agent.temporal import normalize_proposed_period_phrase
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.interpretation import IntentInterpretation
from app.schemas.questions import ConversationTurn
from tests.test_gold_question_filters import _setup


def _plan(question, *, context=(), competencies=None):
    core, request = _setup(question)
    if competencies is None:
        coverage = {
            item.metric_id: (item.kind, item.competencies)
            for item in request.temporal_coverage
        }
    else:
        coverage = {
            metric.id: ("monthly", competencies)
            for metric in GRID360_GOLD_PROFILE.metrics
            if not metric.accumulated_period_phrases
        }
    dimensions = {
        item.dimension_id: item.values for item in request.dimension_value_coverage
    }
    return core.question._analysis_planner.plan(
        question,
        list(context),
        request.access_scope.to_context("00000000000040008000000000000001"),
        temporal_coverage=coverage,
        dimension_value_coverage=dimensions,
    )


def test_bare_volume_means_measured_consumption_in_kwh():
    result = _plan("Qual foi o volume em Recife em março de 2025?")

    assert result.read_plan is not None
    assert result.read_plan.metric_id == "energy.consumption"
    assert result.read_plan.unit == "kWh"
    assert {item.dimension_id: item.values for item in result.read_plan.filters} == {
        "geography.municipality": ("Recife",),
    }


def test_residential_conversation_aliases_resolve_to_the_residential_class():
    aliases = (
        "casas", "famílias", "residências", "clientes residenciais",
        "unidades residenciais",
    )
    for alias in aliases:
        result = _plan(f"Qual foi a receita das {alias} em Recife em março de 2025?")
        assert result.read_plan is not None, alias
        filters = {item.dimension_id: item.values for item in result.read_plan.filters}
        assert filters["customer.consumption_class"] == ("RESIDENCIAL",), alias
        assert filters["geography.municipality"] == ("Recife",), alias


def test_short_residential_phrase_from_model_resolves_to_the_class_filter():
    question = "Qual foi a receita dos clientes residenciais em Recife em março de 2025?"
    core, request = _setup(question)
    coverage = {
        item.metric_id: (item.kind, item.competencies)
        for item in request.temporal_coverage
    }
    dimensions = {
        item.dimension_id: item.values for item in request.dimension_value_coverage
    }
    proposal = IntentInterpretation.model_validate({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "dimension_ids": ["geography.municipality"],
            "geography_phrase": "Recife",
            "class_phrase": "residenciais",
            "period_phrase": "março de 2025",
        },
    })

    result = core.question._analysis_planner.plan(
        question,
        request.context,
        request.access_scope.to_context("00000000000040008000000000000001"),
        temporal_coverage=coverage,
        dimension_value_coverage=dimensions,
        interpretation_override=proposal,
    )

    assert result.read_plan is not None
    filters = {item.dimension_id: item.values for item in result.read_plan.filters}
    assert filters["customer.consumption_class"] == ("RESIDENCIAL",)


def test_account_of_light_without_a_metric_requires_clarification():
    result = _plan("Quanto deu a conta de luz em Recife em março de 2025?")

    assert result.read_plan is None
    assert result.interpretation.clarification_reason.value == "ambiguous_metric"
    assert "consumo medido" in result.interpretation.clarification_question
    assert "valor faturado" in result.interpretation.clarification_question


def test_outage_language_without_dec_or_fec_requires_clarification():
    result = _plan("Teve falta de luz em Olinda em março de 2025?")

    assert result.read_plan is None
    assert result.interpretation.clarification_reason.value == "ambiguous_metric"
    assert "DEC" in result.interpretation.clarification_question
    assert "FEC" in result.interpretation.clarification_question


def test_semester_phrases_resolve_to_six_complete_months():
    competencies = tuple(
        f"{year:04d}-{month:02d}"
        for year in (2025, 2026)
        for month in range(1, 13)
    )
    expected = {
        "Qual foi a receita no primeiro semestre de 2026?":
            (date(2026, 1, 1), date(2026, 6, 30)),
        "Qual foi a receita no 2º semestre do ano de 2025?":
            (date(2025, 7, 1), date(2025, 12, 31)),
    }
    for question, bounds in expected.items():
        result = _plan(question, competencies=competencies)
        assert result.read_plan is not None, question
        assert (result.read_plan.window.start, result.read_plan.window.end) == bounds


def test_model_temporal_phrases_remove_prepositions_and_preserve_month_period():
    assert normalize_proposed_period_phrase("no mês 03 de 2025") == "2025-03"
    assert normalize_proposed_period_phrase("no ano anterior") == "ano anterior"


def test_relative_windows_use_the_latest_published_competency():
    competencies = tuple(
        f"{year:04d}-{month:02d}"
        for year in (2024, 2025, 2026)
        for month in range(1, 13)
        if (year, month) >= (2024, 7) and (year, month) <= (2026, 6)
    )
    expected = {
        "Quanto foi o faturamento nos últimos 12 meses?":
            (date(2025, 7, 1), date(2026, 6, 30)),
        "Quanto foi o faturamento no ano anterior?":
            (date(2025, 1, 1), date(2025, 12, 31)),
        "Quanto foi o faturamento no mês anterior?":
            (date(2026, 5, 1), date(2026, 5, 31)),
    }
    for question, bounds in expected.items():
        result = _plan(question, competencies=competencies)
        assert result.read_plan is not None, question
        assert (result.read_plan.window.start, result.read_plan.window.end) == bounds


def test_follow_up_changes_only_the_requested_period():
    previous = [
        ConversationTurn(role="user", content=(
            "Qual foi a receita residencial de Recife em junho de 2026?"
        )),
        ConversationTurn(role="assistant", content="Resposta fundamentada."),
    ]
    competencies = tuple(
        f"{year:04d}-{month:02d}"
        for year in (2025, 2026)
        for month in range(1, 13)
    )

    result = _plan("E no ano anterior?", context=previous, competencies=competencies)

    assert result.read_plan is not None
    assert result.read_plan.metric_id == "billing.revenue"
    assert (result.read_plan.window.start, result.read_plan.window.end) == (
        date(2025, 1, 1), date(2025, 12, 31),
    )
    filters = {item.dimension_id: item.values for item in result.read_plan.filters}
    assert filters == {
        "customer.consumption_class": ("RESIDENCIAL",),
        "geography.municipality": ("Recife",),
    }
