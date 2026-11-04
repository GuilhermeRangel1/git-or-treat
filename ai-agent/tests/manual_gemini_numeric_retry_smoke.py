"""Smoke test manual da escalada numérica com chamadas reais ao Gemini."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from app.config import Settings
from app.main import create_app
from app.ports.events import EventStage
from app.providers.factory import build_model_adapter, build_model_router
from app.providers.protocols import GeneratedAnswer
from app.providers.routing import ModelRouter, ModelTier, RoutingPolicy


class FaultInjectingLightAdapter:
    """Usa Gemini no nível leve e injeta um número inválido para exercitar a escalada."""

    def __init__(self, adapter) -> None:
        self._adapter = adapter
        self.live_calls = 0

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        await self._adapter.generate(question, context, evidence)
        self.live_calls += 1
        observation_id = evidence.records[0]["observation_id"]
        return GeneratedAnswer(
            status="answered",
            answer="O consumo informado foi 999 unidades fictícias.",
            observation_ids=(observation_id,),
        )


class CountingAdapter:
    def __init__(self, adapter) -> None:
        self._adapter = adapter
        self.live_calls = 0

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        result = await self._adapter.generate(question, context, evidence)
        self.live_calls += 1
        return result


class RecordingSink:
    durable = False

    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="arquivo local com GENAI_GEMINI_API_KEY (padrão: .env)",
    )
    parser.add_argument(
        "--strong-model",
        default=None,
        help="modelo Gemini forte (padrão: GENAI_GEMINI_MODEL do ambiente/.env)",
    )
    parser.add_argument(
        "--light-model",
        default="gemini-3.5-flash-lite",
        help="modelo Gemini leve (padrão: gemini-3.5-flash-lite)",
    )
    parser.add_argument(
        "--run-live",
        action="store_true",
        help="confirma duas chamadas reais e possivelmente faturáveis ao Gemini",
    )
    args = parser.parse_args()
    if not args.run_live:
        parser.error("adicione --run-live para confirmar chamadas externas ao Gemini")
    return args


async def _run(settings: Settings) -> dict[str, object]:
    strong_adapter = build_model_adapter(settings)
    strong = CountingAdapter(strong_adapter)
    configured_router = build_model_router(settings, strong_adapter)
    if configured_router is None:
        raise RuntimeError("Não foi possível montar o roteador Gemini.")

    light = FaultInjectingLightAdapter(configured_router.adapter_for(ModelTier.LIGHT))
    router = ModelRouter(
        {ModelTier.LIGHT: light, ModelTier.STRONG: strong},
        RoutingPolicy(
            light_intents=frozenset(settings.model_light_intents),
            max_light_evidence_records=settings.model_light_max_evidence_records,
            max_light_evidence_chars=settings.model_light_max_evidence_chars,
        ),
    )
    sink = RecordingSink()
    application = create_app(
        settings=settings,
        model_adapter=strong,
        model_router=router,
        event_sink=sink,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://smoke.test",
        timeout=settings.request_timeout_ms / 1000 + 10,
    ) as client:
        response = await client.post(
            "/api/v1/questions",
            json={
                "contract_version": "v1",
                "question": "Qual foi o consumo no período de demonstração?",
            },
        )

    body = response.json()
    model_events = [
        {"code": event.code.value, "model_calls": event.model_calls}
        for event in sink.events
        if event.stage is EventStage.MODEL
    ]
    result: dict[str, object] = {
        "http_status": response.status_code,
        "response_status": body.get("status"),
        "model_tier": body.get("model_tier"),
        "answer": body.get("answer"),
        "real_light_call_completed": light.live_calls == 1,
        "real_strong_call_completed": strong.live_calls == 1,
        "model_events": model_events,
        "source": "synthetic.fixture",
        "fault_injection": "999 foi inserido no rascunho após a chamada real do Gemini light",
    }
    print(json.dumps(result, ensure_ascii=True))

    assert response.status_code == 200
    assert light.live_calls == 1
    assert strong.live_calls == 1
    assert body.get("status") == "answered"
    assert body.get("model_tier") == ModelTier.STRONG.value
    assert "999" not in (body.get("answer") or "")
    assert any(
        event["code"] == "escalated" and event["model_calls"] == 2
        for event in model_events
    )
    return result


def main() -> None:
    args = _parse_args()
    env_settings = Settings(_env_file=args.env_file)
    settings = Settings(
        _env_file=args.env_file,
        environment="local",
        enable_demo_access=True,
        model_provider="gemini",
        gemini_model=args.strong_model or env_settings.gemini_model,
        model_routing_enabled=True,
        model_light_model=args.light_model,
        model_light_intents=["consumption"],
        model_cache_ttl_seconds=0,
        model_timeout_ms=60_000,
        model_total_timeout_ms=120_000,
        request_timeout_ms=120_000,
        model_max_calls=3,
    )
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        raise SystemExit("Configure GENAI_GEMINI_API_KEY no ambiente ou no arquivo --env-file.")
    if settings.gemini_model == settings.model_light_model:
        raise SystemExit("Os modelos light e strong precisam ter IDs distintos.")
    asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
