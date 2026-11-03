import pytest

from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_evidence import EvidenceLookupResult
from app.schemas.genai_plan import LogicalReadPlan
from app.services.chat_visualization import build_chat_visualization
from app.services.genai_client import GenAIResponseInvalid

BATCH = (
    "gold-csv-v2:GOLD_20261031T020143Z_fd69c375:82ff37de-0266-421c-8674-9ba4e191b20b"
)


@pytest.fixture
def scenario():
    plan = LogicalReadPlan.model_validate(
        {
            "catalog_version": "v1",
            "operation": "read",
            "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local",
            "domain_id": "revenue",
            "metric_id": "billing.revenue",
            "unit": "R$",
            "dimension_ids": ["geography.municipality"],
            "window": {
                "kind": "bounded",
                "start": "2026-06-01",
                "end": "2026-08-31",
                "granularity": "month",
            },
            "filters": [
                {
                    "dimension_id": "geography.municipality",
                    "operator": "eq",
                    "values": ["Recife"],
                }
            ],
            "limit": 100,
        }
    )
    reference = {
        "source": "gold.local",
        "description": "Agregado autorizado.",
        "is_demo": False,
    }
    lookup = EvidenceLookupResult.model_validate(
        {
            "status": "available",
            "evidence": {
                "reference": reference,
                "records": [
                    {"value": value, "unit": "R$", "period": f"2026-{month:02d}"}
                    for month, value in [(6, 100), (7, 120), (8, 110)]
                ],
                "provenance": {
                    "source_id": "gold.local",
                    "reference_source": "gold.local",
                    "plan_fingerprint": plan.fingerprint(),
                    "catalog_version": "v1",
                    "metric_id": plan.metric_id,
                    "unit": "R$",
                    "window": plan.window.model_dump(mode="json"),
                    "filters": [f.model_dump(mode="json") for f in plan.filters],
                    "batch_ref": BATCH,
                },
            },
        }
    )
    response = AIQuestionResponse.model_validate(
        {
            "status": "answered",
            "answer": "Resultado fundamentado.",
            "evidence": [reference],
            "analysis_context": {
                "metric": plan.metric_id,
                "metric_label": "Receita faturada",
                "unit": "R$",
                "period": "2026-06-01 a 2026-08-31",
                "filters": {"geography.municipality": "Recife"},
                "batch_reference": BATCH,
            },
        }
    )
    return plan, lookup, response


def test_public_points_and_line_are_copied_from_authorized_evidence(scenario):
    plan, lookup, response = scenario
    visual = build_chat_visualization(plan, lookup, response)
    assert visual.kind == "line"
    assert [p.value for p in visual.points] == [100, 120, 110]
    assert [p.observation_id for p in visual.plot_points] == ["row_1", "row_2", "row_3"]
    published = AIQuestionResponse.model_validate(
        {**response.model_dump(), "visualization": visual.model_dump()}
    )
    assert published.visualization.dimension_ids == ("geography.municipality",)
    assert all("municipality" not in p.label for p in published.visualization.points)
    assert published.visualization.title == "Receita faturada"


@pytest.mark.parametrize(
    "row_patch",
    [{"unit": "kWh"}, {"value": True}, {"value": float("inf")}, {"period": "2026-05"}],
)
def test_incompatible_measure_or_period_is_not_published(scenario, row_patch):
    plan, lookup, response = scenario
    lookup.evidence.records[0].update(row_patch)
    with pytest.raises(GenAIResponseInvalid):
        build_chat_visualization(plan, lookup, response)


def test_visualization_is_absent_for_clarification_and_old_responses_remain_compatible(
    scenario,
):
    plan, lookup, response = scenario
    assert "visualization" not in response.model_dump()
    stopped = AIQuestionResponse(status="needs_clarification", message="Qual período?")
    assert build_chat_visualization(plan, lookup, stopped) is None


def test_broken_series_is_not_connected_as_continuous(scenario):
    plan, lookup, response = scenario
    lookup.evidence.records.pop(1)
    assert build_chat_visualization(plan, lookup, response).kind == "bars"


def test_response_cannot_relabel_authorized_points_as_another_period(scenario):
    plan, lookup, response = scenario
    response.analysis_context.period = "2025-01-01 a 2025-03-31"
    with pytest.raises(GenAIResponseInvalid):
        build_chat_visualization(plan, lookup, response)


def test_altered_context_or_plot_ids_are_refused(scenario):
    plan, lookup, response = scenario
    visual = build_chat_visualization(plan, lookup, response).model_dump()
    visual["plot_points"][0]["value"] = 999
    with pytest.raises(ValueError):
        AIQuestionResponse.model_validate(
            {**response.model_dump(), "visualization": visual}
        )
    response.analysis_context.filters = {"geography.municipality": "Olinda"}
    with pytest.raises(GenAIResponseInvalid):
        build_chat_visualization(plan, lookup, response)


def test_upstream_cannot_supply_public_chart(scenario):
    import asyncio

    import httpx

    from app.schemas.ai import AIQuestionRequest
    from app.services.genai_client import GenAIQuestionClient

    plan, lookup, response = scenario
    correlation = "a" * 32
    visual = build_chat_visualization(plan, lookup, response)
    body = {
        **response.model_dump(mode="json"),
        "correlation_id": correlation,
        "visualization": visual.model_dump(mode="json"),
    }

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json=body, headers={"x-correlation-id": correlation}
                )
            )
        ) as http:
            client = GenAIQuestionClient(
                http_client=http,
                base_url="http://genai.invalid",
                service_token="s" * 40,
            )
            with pytest.raises(GenAIResponseInvalid):
                await client.ask(
                    AIQuestionRequest(question="Qual a receita?"),
                    correlation_id=correlation,
                )

    asyncio.run(run())


def test_coordinator_attaches_points_after_existing_synthesis(scenario, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    from app.schemas.ai import AIQuestionRequest
    from app.schemas.genai_internal import QuestionPlanResponse
    from app.schemas.gold_readiness import GoldReadinessReport
    from app.services import genai_coordination as flow
    from app.services.genai_deadline import GenAIRequestDeadline
    from app.services.genai_planning import GoldPlanningResult
    from app.services.gold_catalog import load_gold_catalog
    from tests.test_genai_continuation import SCOPE

    plan, lookup, response = scenario
    metric = next(
        m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id
    )
    publication = SimpleNamespace(batch_ref=BATCH, assert_current=lambda engine: None)
    planned = GoldPlanningResult(
        QuestionPlanResponse(
            correlation_id="a" * 32,
            status="planned",
            plan=plan,
            plan_fingerprint=plan.fingerprint(),
        ),
        publication,
        metric.sources[0],
        SCOPE,
        GenAIRequestDeadline.start(60),
    )

    async def planning(*args, **kwargs):
        return planned

    async def readiness(*args):
        return GoldReadinessReport(
            readiness_version="gold-readiness-v2",
            batch_ref=BATCH,
            lot_state="ready",
            capabilities={"faturamento.receita": {"status": "available"}},
        )

    calls = []

    async def synthesis(payload, **kwargs):
        calls.append(payload)
        return response

    events = []

    def audit(event, **kwargs):
        events.append(event.stage)
        return uuid4().hex

    monkeypatch.setattr(flow, "plan_gold_question", planning)
    monkeypatch.setattr(flow, "execute_gold_plan", lambda *args, **kwargs: lookup)
    result = asyncio.run(
        flow.answer_gold_question(
            None,
            SimpleNamespace(synthesize=synthesis),
            AIQuestionRequest(question="Receita de junho a agosto em Recife?"),
            resolve_scope=lambda: SCOPE,
            correlation_id="a" * 32,
            readiness_gate=readiness,
            audit_store=SimpleNamespace(record=audit),
        )
    )
    assert len(calls) == 1
    assert [point.value for point in result.visualization.points] == [100, 120, 110]
    assert events == ["request", "plan", "source", "response"]
