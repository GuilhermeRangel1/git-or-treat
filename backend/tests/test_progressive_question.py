import asyncio
import json

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from app.api.progressive import progressive_handler
from app.services.chat_visualization import build_visual_preview
from tests import test_chat_visualization as visual_fixtures

scenario = visual_fixtures.scenario


def request():
    value = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/ai/questions",
            "headers": [(b"accept", b"application/x-ndjson")],
            "query_string": b"",
            "scheme": "http",
            "server": ("localhost", 80),
        }
    )
    value.state.correlation_id = "a" * 32
    value._body = b"{}"

    async def receive():
        await asyncio.Event().wait()

    value._receive = receive
    return value


@pytest.mark.parametrize("finish", ["success", "model_failure", "disconnect"])
def test_real_data_precedes_synthesis_and_disconnect_cancels_task(scenario, finish):
    async def run():
        release = asyncio.Event()
        stopped = asyncio.Event()
        plan, lookup, _ = scenario
        preview = build_visual_preview(plan, lookup)

        async def original(req):
            try:
                await req.state.publish_visual(preview)
                await release.wait()
                return JSONResponse(
                    {"result": "done"}, status_code=200 if finish == "success" else 503
                )
            finally:
                stopped.set()

        result = await progressive_handler(original)(request())
        assert isinstance(result, StreamingResponse)
        stream = result.body_iterator
        first = json.loads(await anext(stream))
        assert first["type"] == "data"
        assert [p["value"] for p in first["data"]["visualization"]["points"]] == [
            100,
            120,
            110,
        ]
        assert not stopped.is_set()  # Interpretation has not finished.
        if finish != "disconnect":
            release.set()
            final = json.loads(await anext(stream))
            assert final["type"] == ("complete" if finish == "success" else "error")
        await stream.aclose()
        assert stopped.is_set()

    asyncio.run(run())


def test_denial_before_data_preserves_http_status():
    async def original(req):
        return JSONResponse({"message": "Acesso negado."}, status_code=403)

    result = asyncio.run(progressive_handler(original)(request()))
    assert not isinstance(result, StreamingResponse)
    assert result.status_code == 403


def test_disconnect_before_first_data_stops_the_coordinator():
    from starlette.requests import ClientDisconnect

    async def run():
        stopped = asyncio.Event()
        started = asyncio.Event()

        async def original(req):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        req = request()

        async def receive():
            await started.wait()
            return {"type": "http.disconnect"}

        req._receive = receive
        with pytest.raises(ClientDisconnect):
            await progressive_handler(original)(req)
        assert stopped.is_set()

    asyncio.run(run())
