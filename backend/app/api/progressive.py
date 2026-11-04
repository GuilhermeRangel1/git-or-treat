"""Negociação opcional de dados prontos, sem duplicar a consulta conversacional."""

import asyncio
import json
from collections.abc import Awaitable, Callable

from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response, StreamingResponse

STREAM_TYPE = "application/x-ndjson"


def progressive_handler(handler: Callable[[Request], Awaitable[Response]]):
    async def handle(request: Request):
        if (
            request.method != "POST"
            or not request.url.path.endswith("/questions")
            or STREAM_TYPE not in request.headers.get("accept", "")
        ):
            return await handler(request)
        # Armazenar o corpo antes de observar disconnect: só um consumidor recebe
        # eventos ASGI; o handler reutiliza o corpo armazenado no mesmo Request.
        await request.body()
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def publish(response):
            await queue.put(("data", response.model_dump(mode="json")))

        request.state.publish_visual = publish

        async def run():
            try:
                response = await handler(request)
            except Exception:  # noqa: BLE001 — última fronteira HTTP; nunca envia o erro interno.
                response = JSONResponse(
                    {
                        "message": "O serviço de resposta está temporariamente indisponível."
                    },
                    status_code=503,
                )
            await queue.put(("complete", response))

        task = asyncio.create_task(run())

        async def stop():
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        async def disconnected():
            while True:
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    return

        first_task = asyncio.create_task(queue.get())
        disconnect_task = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait(
                {first_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if disconnect_task in done:
                raise ClientDisconnect
            first = first_task.result()
        except BaseException:
            await stop()
            raise
        finally:
            for pending in (first_task, disconnect_task):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(first_task, disconnect_task, return_exceptions=True)
        if first[0] == "complete":
            await task
            return first[1]

        def encode(kind, data, status=200):
            return (
                json.dumps(
                    {"type": kind, "status": status, "data": data},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

        async def content():
            try:
                yield encode(*first)
                while True:
                    kind, value = await queue.get()
                    if kind == "data":
                        yield encode(kind, value)
                        continue
                    body = json.loads(value.body)
                    yield encode(
                        "complete" if value.status_code < 400 else "error",
                        body,
                        value.status_code,
                    )
                    break
            finally:
                await stop()

        return StreamingResponse(
            content(),
            media_type=STREAM_TYPE,
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
                "X-Correlation-ID": request.state.correlation_id,
            },
        )

    return handle
