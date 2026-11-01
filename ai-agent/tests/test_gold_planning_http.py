"""Fronteiras reais do planejamento v2, sem modelo remoto ou dataset privado."""

import pytest

from app.api.application import create_api_application
from app.config import Settings
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.internal import QuestionSynthesisRequest, TemporalCoverage
from app.schemas.read_plan import LogicalReadPlan

from .conftest import InProcessClient
from .test_core_plan_synthesis import _lookup
from .test_gold_question_filters import _setup

TOKEN = "test-internal-gold-token-000000000000"
PLAN_PATH = "/api/v1/internal/question-plans"
SYNTHESIS_PATH = "/api/v1/internal/question-syntheses"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Correlation-ID": "a" * 32}


@pytest.mark.parametrize("label,metric", [
    ("receita", "billing.revenue"), ("consumo", "energy.consumption"),
])
@pytest.mark.parametrize("initial,final,expected", [
    (100, 120, "20.0 %"), (0, 120, "percentual indisponível"),
])
def test_fat09_con06_compare_only_the_two_requested_months(label, metric, initial, final, expected):
    core, request = _setup(f"Compare {label} entre janeiro de 2025 e março de 2025.")
    request = request.model_copy(update={"temporal_coverage": tuple(
        coverage.model_copy(update={"competencies": ("2025-01", "2025-03")})
        for coverage in request.temporal_coverage
    )})
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert planned["status"] == "planned", planned
        plan = LogicalReadPlan.model_validate(planned["plan"])
        assert plan.metric_id == metric
        assert plan.comparison_periods == ("2025-01", "2025-03")
        lookup = _lookup(plan, batch_ref=request.batch_ref, value=100)
        lookup.evidence.records = [
            {"period": "2025-01", "value": initial, "unit": plan.unit},
            {"period": "2025-03", "value": final, "unit": plan.unit},
        ]
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan,
            plan_fingerprint=planned["plan_fingerprint"], lookup=lookup,
            expected_batch_ref=request.batch_ref,
        )
        result = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
    assert result["status"] == "answered", result
    assert "Variação absoluta" in result["answer"]
    assert expected in result["answer"]


def test_con07_ranks_neighborhoods_by_change_instead_of_final_consumption():
    core, request = _setup(
        "Qual bairro de Olinda mais perdeu volume residencial "
        "entre janeiro de 2025 e março de 2025?"
    )
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert planned["status"] == "planned", planned
        plan = LogicalReadPlan.model_validate(planned["plan"])
        assert plan.group_by_dimension_ids == ("geography.neighborhood",)
        assert {item.dimension_id: item.values for item in plan.filters} == {
            "geography.municipality": ("Olinda",),
            "customer.consumption_class": ("RESIDENCIAL",),
        }
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {"period": month, "value": value, "unit": "kWh", "neighborhood": neighborhood}
            for neighborhood, month, value in [
                ("Casa Caiada", "2025-01", 100), ("Casa Caiada", "2025-03", 50),
                ("Bairro Alto", "2025-01", 1000), ("Bairro Alto", "2025-03", 990),
            ]
        ]
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
            dimension_value_coverage=[{
                "dimension_id": "geography.neighborhood", "values": ["Casa Caiada", "Bairro Alto"],
            }],
        )
        result = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert result["status"] == "answered", result
        assert "-50.0 kWh" in result["answer"]
        assert "Casa Caiada" in result["answer"]
        assert "Bairro Alto" not in result["answer"]
        # Uma ausência de grupo não pode ser convertida em base zero para ganhar o ranking.
        lookup.evidence.records.pop()
        synthesis = synthesis.model_copy(update={"lookup": lookup})
        incomplete = client.post(
            SYNTHESIS_PATH, json=synthesis.model_dump(mode="json"), headers=HEADERS,
        ).json()
        assert incomplete["status"] == "needs_clarification"
        assert not incomplete["evidence"]



def _application(core, *, token=TOKEN, mode="external"):
    # Borda real com o mesmo núcleo composto; não simula os handlers HTTP.
    return create_api_application(
        settings=Settings(_env_file=None, enable_demo_access=False, service_api_token=token),
        question_handler=core.question,
        insight_handler=core.insight,
        domain_profile=GRID360_GOLD_PROFILE,
        source_id="gold.local",
        source_mode=mode,
        access_context_resolver=None,
    )


def test_http_plan_preserves_canonical_filters_and_partial_calendar():
    core, request = _setup("Receita residencial em Olinda este ano?")
    with InProcessClient(_application(core)) as client:
        response = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "a" * 32
    result = response.json()
    assert result["status"] == "planned"
    assert result["correlation_id"] == "a" * 32
    plan = result["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["window"]["start"] == "2025-01-01"
    assert plan["window"]["end"] == "2025-03-31"
    assert plan["limit"] == 100
    assert plan["order"] is None
    assert plan["group_by_dimension_ids"] == []
    assert {f["dimension_id"]: f["values"] for f in plan["filters"]} == {
        "geography.municipality": ["Olinda"],
        "customer.consumption_class": ["RESIDENCIAL"],
    }


@pytest.mark.parametrize("path", [PLAN_PATH, SYNTHESIS_PATH])
def test_internal_operations_require_token_and_external_composition(path):
    core, request = _setup("Receita em Olinda em março de 2025?")
    payload = request.model_dump(mode="json")
    with InProcessClient(_application(core)) as client:
        assert client.post(path, json=payload).status_code == 401
    for options in ({"token": None}, {"mode": "demo"}):
        with InProcessClient(_application(core, **options)) as client:
            assert client.post(path, json=payload, headers=HEADERS).status_code == 503


def test_http_plan_reapplies_scope_and_returns_specific_clarification():
    core, request = _setup("Receita residencial em Olinda em março de 2025?")
    with InProcessClient(_application(core)) as client:
        payload = request.model_dump(mode="json")
        payload["access_scope"]["allowed_dimension_ids"].remove("generation.distributed")
        payload["question"] = "Receita com GD em março de 2025?"
        denied = client.post(PLAN_PATH, json=payload, headers=HEADERS)
        assert denied.json()["status"] == "refused"
        payload = request.model_dump(mode="json")
        payload["question"] = "Receita em Olinda em junho de 2025?"
        absent = client.post(PLAN_PATH, json=payload, headers=HEADERS)
        assert absent.json()["status"] == "needs_clarification"
        assert absent.json()["plan"] is None


def test_http_synthesis_preserves_zero_and_rejects_changed_publication():
    core, request = _setup("Receita residencial em Olinda em março de 2025?")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref, value=0)
        lookup.evidence.records[0]["period"] = "2025-03"
        lookup.evidence.records[0]["municipality"] = "Olinda"
        lookup.evidence.records[0]["consumption_class"] = "RESIDENCIAL"
        synthesis = QuestionSynthesisRequest(
            question=request.question,
            access_scope=request.access_scope,
            remaining_timeout_ms=35000,
            plan=plan,
            plan_fingerprint=planned["plan_fingerprint"],
            lookup=lookup,
            expected_batch_ref=request.batch_ref,
        ).model_dump(mode="json")
        result = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert result.status_code == 200
        assert result.json()["status"] == "answered"
        assert "R$ 0,00 em março de 2025" in result.json()["answer"]
        assert "billing.revenue" not in result.json()["answer"]
        assert result.json()["analysis_context"]["batch_reference"] == request.batch_ref
        assert result.json()["analysis_context"]["period"] == "2025-03-01 a 2025-03-31"
        assert result.json()["analysis_context"]["metric"] == "billing.revenue"
        assert result.json()["analysis_context"]["metric_label"] == "Receita faturada"
        assert result.json()["analysis_context"]["metric_definition"]
        # Ausência de medida não pode virar o zero observado acima.
        record = synthesis["lookup"]["evidence"]["records"][0]
        for missing_value in (None, "absent"):
            if missing_value is None:
                record["value"] = None
            else:
                record.pop("value")
            missing = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
            assert missing.status_code == 200
            assert missing.json()["status"] == "recoverable_error"
            assert missing.json()["evidence"] == []
        record["value"] = 0
        comparison = request.model_dump(mode="json")
        comparison["question"] = (
            "Compare a receita residencial em Olinda de fevereiro de 2025 "
            "com março de 2025, com base zero."
        )
        unsupported = client.post(PLAN_PATH, json=comparison, headers=HEADERS)
        assert unsupported.status_code == 200
        assert unsupported.json()["status"] == "planned"
        assert unsupported.json()["plan"]["comparison_periods"] == ["2025-02", "2025-03"]
        synthesis["lookup"]["evidence"]["records"][0]["municipality"] = "Recife"
        outside = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert outside.json()["status"] == "recoverable_error"
        synthesis["lookup"]["evidence"]["records"][0]["municipality"] = "Olinda"
        synthesis["expected_batch_ref"] = request.batch_ref.replace("12345678", "87654321")
        changed = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS)
        assert changed.json()["status"] == "recoverable_error"


def test_fat10_revenue_contribution_groups_and_orders_classes():
    core, request = _setup("Qual classe mais contribuiu para a receita em Olinda em março de 2025?")
    with InProcessClient(_application(core)) as client:
        response = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS)
    body = response.json()
    assert body["status"] == "planned"
    plan = body["plan"]
    assert plan["metric_id"] == "billing.revenue"
    assert plan["group_by_dimension_ids"] == ["customer.consumption_class"]
    assert plan["limit"] == 1
    assert plan["order"] == {"field_id": "billing.revenue", "direction": "desc"}
    assert plan["window"]["start"] == "2025-03-01"
    assert plan["window"]["end"] == "2025-03-31"
    assert plan["filters"] == [{"dimension_id": "geography.municipality",
                                "operator": "eq", "values": ["Olinda"]}]


@pytest.mark.parametrize("question,metric", [
    ("Quantos chamados de atendimento existem no histórico acumulado?",
     "service.accumulated_attendance"),
    ("Qual é a satisfação média do atendimento no histórico acumulado?",
     "service.accumulated_satisfaction"),
])
def test_ate03_ate04_select_accumulated_metric_without_inventing_calendar(question, metric):
    core, request = _setup(question)
    request = request.model_copy(update={"temporal_coverage": (
        *request.temporal_coverage, TemporalCoverage(metric_id=metric, kind="none"),
    )})
    with InProcessClient(_application(core)) as client:
        body = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS).json()
    assert body["status"] == "planned"
    assert body["plan"]["metric_id"] == metric
    assert body["plan"]["window"]["phrase"] == "histórico acumulado"


def test_ate03_accumulated_observation_survives_synthesis_without_inventing_date():
    core, request = _setup("Quantos chamados de atendimento existem no histórico acumulado?")
    request = request.model_copy(update={"temporal_coverage": (
        *request.temporal_coverage,
        TemporalCoverage(metric_id="service.accumulated_attendance", kind="none"),
    )})
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS
        ).json()
        assert planned["status"] == "planned"
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref, value=5)
        lookup.evidence.records[0]["period"] = "histórico acumulado"
        synthesis = QuestionSynthesisRequest(
            question=request.question, access_scope=request.access_scope,
            remaining_timeout_ms=35000, plan=plan, plan_fingerprint=plan.fingerprint(),
            lookup=lookup, expected_batch_ref=request.batch_ref,
        ).model_dump(mode="json")
        response = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS).json()
        assert response["status"] == "answered"
        assert response["analysis_context"]["period"] == "histórico acumulado"
        assert "5 protocolos" in response["answer"]
        synthesis["lookup"]["evidence"]["records"][0]["period"] = "2025-03"
        wrong = client.post(SYNTHESIS_PATH, json=synthesis, headers=HEADERS).json()
        assert wrong["status"] == "recoverable_error"
        assert not wrong["evidence"]


def test_fat10_does_not_rank_months_as_if_they_were_period_contributions():
    core, request = _setup(
        "Qual classe mais contribuiu para a receita em Olinda no último trimestre?"
    )
    with InProcessClient(_application(core)) as client:
        body = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS).json()
    assert body["status"] == "needs_clarification"
    assert body["plan"] is None


def test_fat10_followup_keeps_grouping_and_ranking_when_changing_municipality():
    from app.schemas.questions import ConversationTurn
    question = "Qual classe mais contribuiu para a receita em Olinda em março de 2025?"
    core, request = _setup("E em Recife?")
    request = request.model_copy(update={
        "context": [ConversationTurn(role="user", content=question)],
    })
    with InProcessClient(_application(core)) as client:
        body = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS).json()
    assert body["status"] == "planned"
    assert body["plan"]["group_by_dimension_ids"] == ["customer.consumption_class"]
    assert body["plan"]["order"] == {"field_id": "billing.revenue", "direction": "desc"}
    assert body["plan"]["limit"] == 1
    assert body["plan"]["filters"][0]["values"] == ["Recife"]


def test_comparison_numeric_overflow_is_a_sanitized_clarification():
    core, request = _setup("Compare a receita entre janeiro de 2025 e março de 2025.")
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS
        ).json()
        plan = LogicalReadPlan.model_validate(planned["plan"])
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.records = [
            {"period": "2025-01", "value": 0.01, "unit": "R$"},
            {"period": "2025-03", "value": 1e25, "unit": "R$"},
        ]
        payload = QuestionSynthesisRequest(
            question=request.question,
            access_scope=request.access_scope,
            remaining_timeout_ms=35000,
            plan=plan,
            plan_fingerprint=plan.fingerprint(),
            lookup=lookup,
            expected_batch_ref=request.batch_ref,
        )
        response = client.post(
            SYNTHESIS_PATH, json=payload.model_dump(mode="json"), headers=HEADERS
        )
        assert response.status_code == 200
        assert response.json()["status"] == "needs_clarification"
        assert not response.json()["evidence"]


def test_con08_uses_the_documented_fixed_windows_instead_of_inventing_current_month():
    core, request = _setup(
        "Quantas UCs com geração distribuída em Olinda tiveram queda de consumo acima de 30%?"
    )
    request = request.model_copy(
        update={
            "temporal_coverage": (
                *request.temporal_coverage,
                TemporalCoverage(metric_id="energy.gd_consumption_drop", kind="none"),
            )
        }
    )
    with InProcessClient(_application(core)) as client:
        body = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS).json()
    assert body["status"] == "planned", body
    assert body["plan"]["metric_id"] == "energy.gd_consumption_drop"
    assert body["plan"]["window"]["kind"] == "catalog_phrase"
    assert "2022-07" in body["plan"]["window"]["phrase"]
    assert "2026-06" in body["plan"]["window"]["phrase"]


def test_int03_distinguishes_count_of_events_from_dec_and_fec():
    core, request = _setup("Quantas interrupções houve no alimentador AL-01 em março de 2025?")
    with InProcessClient(_application(core)) as client:
        body = client.post(PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS).json()
    assert body["status"] == "planned", body
    assert body["plan"]["metric_id"] == "network.interruption_events"
    assert body["plan"]["unit"] == "ocorrências"


def test_fat11_keeps_all_components_and_the_actual_published_windows():
    from app.schemas.evidence import PublishedWindows

    core, request = _setup(
        "Quanto da variação da receita residencial foi efeito preço e quanto foi efeito volume?"
    )
    request = request.model_copy(
        update={
            "temporal_coverage": (
                *request.temporal_coverage,
                TemporalCoverage(metric_id="billing.price_volume", kind="none"),
            )
        }
    )
    with InProcessClient(_application(core)) as client:
        planned = client.post(
            PLAN_PATH, json=request.model_dump(mode="json"), headers=HEADERS
        ).json()
        assert planned["status"] == "planned", planned
        plan = LogicalReadPlan.model_validate(planned["plan"])
        metric = next(m for m in GRID360_GOLD_PROFILE.metrics if m.id == "billing.price_volume")
        lookup = _lookup(plan, batch_ref=request.batch_ref)
        lookup.evidence.provenance = lookup.evidence.provenance.model_copy(
            update={
                "published_windows": PublishedWindows(
                    p0_start="2000-01",
                    p0_end="2000-12",
                    p1_start="2001-01",
                    p1_end="2001-12",
                    method="PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
                ),
            }
        )
        lookup.evidence.records = [
            {"label": label, "value": index, "unit": unit, "period": plan.window.phrase}
            for index, (label, unit) in enumerate(metric.observation_labels.items())
        ]
        payload = QuestionSynthesisRequest(
            question=request.question,
            access_scope=request.access_scope,
            remaining_timeout_ms=35000,
            plan=plan,
            plan_fingerprint=plan.fingerprint(),
            lookup=lookup,
            expected_batch_ref=request.batch_ref,
        )
        body = client.post(
            SYNTHESIS_PATH, json=payload.model_dump(mode="json"), headers=HEADERS
        ).json()
        assert body["status"] == "answered", body
        assert body["analysis_context"]["period"] == "P0 2000-01 a 2000-12; P1 2001-01 a 2001-12"
        assert all(label in body["answer"] for label in metric.observation_labels)
        lookup.evidence.records.pop()
        body = client.post(
            SYNTHESIS_PATH, json=payload.model_dump(mode="json"), headers=HEADERS
        ).json()
        assert body["status"] == "recoverable_error"
        assert not body["evidence"]
