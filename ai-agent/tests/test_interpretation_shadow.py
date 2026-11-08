import asyncio

from app.agent.interpretation_shadow import observe_interpretation
from app.schemas.analysis import AnalysisIntent
from app.schemas.interpretation import IntentInterpretation


def reference():
    return IntentInterpretation(
        status="ready", intent=AnalysisIntent(domain="energy", metric_id="revenue")
    )


def test_observation_identifies_lost_ranking_without_exposing_values():
    expected = reference()
    expected.intent.ranking_direction = "desc"
    expected.intent.ranking_limit = 1

    class Proposer:
        async def propose(self):
            return reference()

    result = asyncio.run(observe_interpretation(Proposer(), expected))
    assert result.status == "mismatch"
    assert result.differing_fields == ("intent.ranking_direction", "intent.ranking_limit")
    assert "revenue" not in result.model_dump_json()
    assert "intent" not in type(result).model_fields


def test_provider_failure_is_observed_without_disclosing_exception():
    class Proposer:
        async def propose(self):
            raise RuntimeError("private provider payload")

    result = asyncio.run(observe_interpretation(Proposer(), reference()))
    assert result.status == "proposal_error"
    assert "private" not in result.model_dump_json()


def test_timeout_is_distinct_from_semantic_mismatch():
    class Proposer:
        async def propose(self):
            await asyncio.Event().wait()

    result = asyncio.run(
        observe_interpretation(Proposer(), reference(), timeout_seconds=0.01)
    )
    assert result.status == "timeout"
    assert result.differing_fields == ()
