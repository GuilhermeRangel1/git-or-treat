"""Ponta a ponta das regras da revisão do PR #42: pergunta → create_app → plano → fonte.

Usa a mesma composição do harness de regressão (`create_app` com fonte sintética que registra
o plano aprovado e modelo fixo). Esclarecimentos não podem chegar à fonte nem ao modelo.
"""

import pytest

from app.api.access import SYNTHETIC_SOURCE_ID
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from tests.conftest import InProcessClient
from tests.test_genai_regression import CaseModelAdapter, RecordingEvidenceSource, summarize_plan

CLARIFICATIONS = GRID360_DEMO_PROFILE.clarifications
PERIOD_DETAIL = GRID360_DEMO_PROFILE.detail_rules[0].clarification
AVERAGE_DETAIL = GRID360_DEMO_PROFILE.detail_rules[1].clarification


def _ask(question: str, context: list[dict] | None = None):
    source = RecordingEvidenceSource()
    model = CaseModelAdapter(
        {"model_answer": "O consumo demonstrativo foi 420 unidades fictícias.",
         "model_observation_ids": ["row_1"]}
    )
    application = create_app(
        settings=Settings(
            _env_file=None,
            environment="local",
            enable_demo_access=True,
            model_routing_enabled=False,
        ),
        domain_profile=GRID360_DEMO_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        evidence_source=source,
        model_adapter=model,
    )
    with InProcessClient(application) as client:
        response = client.post(
            "/api/v1/questions", json={"question": question, "context": context or []}
        )
    assert response.status_code == 200
    return response.json(), source, model


@pytest.mark.parametrize(
    ("question", "expected_message"),
    [
        (
            "Interrupções por município no período de demonstração",
            CLARIFICATIONS.unsupported_breakdown.replace("{dimension}", "município"),
        ),
        (
            "Qual o consumo por classe no período de demonstração?",
            CLARIFICATIONS.unsupported_breakdown.replace("{dimension}", "classe de consumo"),
        ),
        (
            "Qual o faturamento em kWh no período de demonstração?",
            CLARIFICATIONS.unit_mismatch.replace("{unit}", "kWh"),
        ),
        (
            "Qual o consumo em R$ no período de demonstração?",
            CLARIFICATIONS.unit_mismatch.replace("{unit}", "R$"),
        ),
        (
            "Qual a duração das interrupções em horas no período de demonstração?",
            CLARIFICATIONS.unit_mismatch.replace("{unit}", "horas"),
        ),
        ("Qual o consumo em média no período de demonstração?", AVERAGE_DETAIL),
        ("Qual o consumo de Janeiro?", PERIOD_DETAIL),
        ("Qual o consumo em março?", PERIOD_DETAIL),
        ("Qual o consumo de março de 2026?", PERIOD_DETAIL),
        (
            "Qual o consumo do Recife no período de demonstração?",
            CLARIFICATIONS.unknown_geography,
        ),
    ],
)
def test_review_clarifications_reach_the_user_without_source_or_model(
    question: str, expected_message: str
) -> None:
    body, source, model = _ask(question)

    assert body["status"] == "needs_clarification"
    assert body["message"] == expected_message
    assert body["answer"] is None and body["evidence"] == []
    assert source.plans == []
    assert model.calls == []


def test_month_in_follow_up_asks_for_the_period() -> None:
    body, source, _model = _ask(
        "E em março?",
        [{"role": "user", "content": "Qual o consumo no período de demonstração?"}],
    )

    assert body["message"] == PERIOD_DETAIL
    assert source.plans == []


def test_correction_na_verdade_reaches_the_source_with_the_last_place() -> None:
    body, source, model = _ask(
        "Qual o consumo em Olinda, na verdade em Jaboatão, no período de demonstração?"
    )

    [plan] = source.plans
    assert summarize_plan(plan)["filters"] == [
        {"dimension_id": "geography.municipality", "values": ["Jaboatão dos Guararapes"]}
    ]
    # A fonte sintética não tem esse recorte: sem evidência e sem chamar o modelo.
    assert body["status"] == "no_evidence"
    assert model.calls == []


@pytest.mark.parametrize(
    "question",
    [
        "Qual o consumo, por favor, no período de demonstração?",
        "Qual o consumo no total no período de demonstração?",
        "Qual o consumo em kWh no período de demonstração?",
    ],
)
def test_near_misses_are_answered_from_the_source(question: str) -> None:
    body, source, model = _ask(question)

    [plan] = source.plans
    assert summarize_plan(plan) == {
        "domain_id": "consumption",
        "metric_id": "energy.consumption",
        "dimension_ids": [],
        "window": {"phrase": "período de demonstração"},
        "filters": [],
    }
    assert body["status"] == "answered"
    assert "420 unidades fictícias" in body["answer"]
    assert len(model.calls) == 1
