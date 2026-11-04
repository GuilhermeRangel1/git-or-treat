"""Confere, com uma chamada real e mínima por modelo, a cadeia de modelos configurada.

A cadeia vem da mesma ``Settings`` e da mesma factory do serviço: modelo principal, modelos
secundários do Gemini e provedores de ``GENAI_MODEL_FALLBACK_PROVIDERS``. Cada modelo recebe
uma pergunta trivial sobre uma evidência sintética e consome uma requisição da cota.

O resultado vem do log ``genai_provider_failure`` emitido pelo próprio adaptador: ``ok``,
``quota``, ``model_not_found``, ``overloaded``, ``rejected``, ``timeout_or_network`` ou
``invalid_response``. Nunca imprime chave, cabeçalhos, texto de exceção nem a resposta do
modelo. Sai com código 0 somente se todos os modelos responderem ``ok``.

Uso, em ``ai-agent/``:
    python scripts/check_models.py --list   # só mostra a cadeia, sem chamadas
    python scripts/check_models.py [--yes]  # chama cada modelo uma vez
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from app.config import Settings  # noqa: E402
from app.providers.factory import ModelConfigurationError, build_model_adapter  # noqa: E402
from app.schemas.evidence import EvidenceResult  # noqa: E402
from app.schemas.questions import EvidenceReference  # noqa: E402
from app.telemetry import logger as telemetry_logger  # noqa: E402

QUESTION = "Qual é o valor da evidência sintética?"
EVIDENCE = EvidenceResult(
    reference=EvidenceReference(
        source="synthetic_fixture:check_models",
        description="Valor inventado para conferir a disponibilidade do modelo.",
        is_demo=True,
    ),
    records=[{"metric": "valor_demo", "value": 1, "unit": "unidades fictícias"}],
)
FAILURE_PREFIX = "genai_provider_failure "


class _FailureCapture(logging.Handler):
    """Guarda só ``kind`` e ``status`` da linha estruturada do adaptador."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.kind: str | None = None
        self.status: int | None = None

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith(FAILURE_PREFIX):
            fields = json.loads(message.removeprefix(FAILURE_PREFIX))
            self.kind, self.status = fields.get("kind"), fields.get("status")


def _chain(settings: Settings, client, groq_client) -> list:
    """Adaptadores individuais na ordem da cadeia, sem cache para não esconder a chamada."""
    adapter = build_model_adapter(
        settings.model_copy(update={"model_cache_ttl_seconds": 0}),
        client=client, groq_client=groq_client,
    )
    return list(getattr(adapter, "_adapters", (adapter,)))


def _describe(adapter) -> str:
    provider = type(adapter).__name__.removesuffix("ModelAdapter").lower()
    return f"{provider} {getattr(adapter, '_model_name', '?')}"


async def _check(adapter) -> tuple[str, int]:
    capture = _FailureCapture()
    telemetry_logger.addHandler(capture)
    # Sem propagar: a linha de falha não deve ir para o console junto com o resumo.
    propagate, telemetry_logger.propagate = telemetry_logger.propagate, False
    started = time.perf_counter()
    try:
        await adapter.generate(QUESTION, [], EVIDENCE)
        result = "ok"
    except Exception:  # noqa: BLE001 - o texto da exceção nunca é exibido
        result = capture.kind or "rejected"
    finally:
        telemetry_logger.removeHandler(capture)
        telemetry_logger.propagate = propagate
    return result, round((time.perf_counter() - started) * 1000)


def _configuration_error(exc: Exception) -> str:
    message = str(exc)
    if "API_KEY" in message:
        return "chave não configurada"
    if "dependência opcional" in message:
        return "dependência opcional do provedor não instalada"
    return "configuração de modelos inválida"


def main(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    client=None,
    groq_client=None,
    ask: Callable[[str], str] = input,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="só mostra a cadeia configurada")
    parser.add_argument("--yes", action="store_true", help="não pede confirmação")
    args = parser.parse_args(argv)

    try:
        settings = settings or Settings()
        if settings.model_provider == "unavailable":
            print("Nenhum provedor de modelo configurado.")
            return 1
        adapters = _chain(settings, client, groq_client)
    except (ModelConfigurationError, ValidationError, ValueError) as exc:
        print(f"Erro de configuração: {_configuration_error(exc)}.")
        return 1

    print("Cadeia de modelos configurada:")
    for position, adapter in enumerate(adapters, start=1):
        print(f"  {position}. {_describe(adapter)}")
    if args.list:
        return 0

    print(f"Cada modelo consome 1 requisição da cota ({len(adapters)} no total).")
    if not args.yes:
        try:
            answer = ask("Continuar? [S/n] ").strip().casefold()
        except EOFError:
            answer = "n"
        if answer not in {"", "s", "sim", "y", "yes"}:
            print("Cancelado; nenhuma chamada foi feita.")
            return 1

    all_ok = True
    for adapter in adapters:
        result, latency_ms = asyncio.run(_check(adapter))
        all_ok = all_ok and result == "ok"
        print(f"{_describe(adapter)}: {result} ({latency_ms} ms)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
