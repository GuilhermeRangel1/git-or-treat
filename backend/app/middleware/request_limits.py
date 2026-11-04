import json
import math

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

MAX_BODY_BYTES = 65_536
MAX_JSON_DEPTH = 32


def too_deep(body: bytes) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for char in body:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return True
        elif char in (93, 125):
            depth -= 1
    return False


def finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Número JSON não finito.")
    return result


def reject_constant(value: str):
    raise ValueError("Constante não permitida em JSON.")


def validate_json_strings(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if "\x00" in item:
                raise ValueError("Byte nulo não permitido.")
            item.encode("utf-8")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


class RequestLimitsMiddleware:
    """Bound body memory and JSON depth before FastAPI invokes its parser."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length", b"")
        normalized_length = length.lstrip(b"0") or b"0"
        if length.isdigit() and (len(normalized_length) > len(str(MAX_BODY_BYTES)) or int(normalized_length) > MAX_BODY_BYTES):
            return await self._reject(scope, receive, send, "Corpo da requisição excede o limite.")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return await self._reject(scope, receive, send, "Corpo da requisição excede o limite.")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        content_type = headers.get(b"content-type", b"").split(b";")[0].strip().lower()
        is_json = not content_type or content_type == b"application/json" or content_type.endswith(b"+json")
        if body and scope.get("method") in {"POST", "PUT", "PATCH"} and not is_json:
            return await self._reject(scope, receive, send, "Envie o corpo como JSON.", 415)
        if is_json:
            try:
                body.decode("utf-8")
            except UnicodeDecodeError:
                return await self._reject(scope, receive, send, "JSON deve usar UTF-8.", 400)
            if b"\x00" in body:
                return await self._reject(scope, receive, send, "JSON deve usar UTF-8 sem bytes nulos.", 400)
            if too_deep(body):
                return await self._reject(scope, receive, send, "JSON excede o limite de profundidade.")
            if body:
                try:
                    parsed = json.loads(body, parse_float=finite_float, parse_constant=reject_constant)
                    validate_json_strings(parsed)
                except json.JSONDecodeError:
                    pass  # Preserve FastAPI's field-level response for malformed JSON.
                except (ValueError, OverflowError):
                    return await self._reject(scope, receive, send, "Conteúdo JSON inválido ou excessivo.", 400)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope, receive, send, message, status_code=413):
        response = JSONResponse({"detail": message}, status_code=status_code)
        await response(scope, receive, send)
