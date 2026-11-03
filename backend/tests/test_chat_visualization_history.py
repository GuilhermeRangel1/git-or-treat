from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints import ai_conversations as routes
from app.schemas.ai import AIQuestionResponse
from app.services.ai_conversations import ConversationStore
from app.services.chat_visualization import build_chat_visualization
from tests import test_ai_history_http as history_fixtures
from tests import test_ai_history_store as store_fixtures
from tests import test_chat_visualization as visual_fixtures
from tests.test_genai_continuation import SCOPE

client = history_fixtures.client
storage = store_fixtures.storage
scenario = visual_fixtures.scenario


@pytest.mark.parametrize(
    "publication,expected",
    [
        (visual_fixtures.BATCH, True),
        (visual_fixtures.BATCH.replace("fd69c375", "aaaaaaaa"), False),
        (None, False),
    ],
)
def test_saved_chart_requires_current_publication(
    client, scenario, monkeypatch, publication, expected
):
    web, db, _ = client
    monkeypatch.setattr(routes, "current_scope", lambda *args: SCOPE)
    conversation = history_fixtures.create(web)
    owner = ConversationStore(db, "one")
    request_id = str(uuid4())
    _, _, attempt = owner.reserve(
        conversation, request_id, "fixture", routes.history_scope(SCOPE)
    )
    plan, lookup, response = scenario
    visual = build_chat_visualization(plan, lookup, response)
    answer = AIQuestionResponse.model_validate(
        {**response.model_dump(), "visualization": visual.model_dump()}
    )
    owner.finish(
        conversation,
        request_id,
        attempt,
        "Receita no período?",
        answer,
        "Receita no período?",
        visual_fixtures.BATCH,
    )

    def engine(scope):
        if publication is None:
            raise ValueError("Fonte indisponível")
        return SimpleNamespace(connect=lambda: nullcontext(None), dispose=lambda: None)

    monkeypatch.setattr(routes, "create_genai_gold_engine", engine)
    monkeypatch.setattr(
        routes,
        "current_publication",
        lambda connection: SimpleNamespace(batch_ref=publication),
    )
    result = web.get(f"/api/v1/ai/conversations/{conversation}")
    assert result.status_code == 200, result.text
    saved = result.json()["exchanges"][0]["response"]
    assert bool(saved.get("visualization")) is expected
    assert saved["answer"] == response.answer
