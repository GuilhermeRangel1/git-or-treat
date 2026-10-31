"""Conferência interna somente leitura: Backend / GenAI / prontidão, sem valores do lote."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.repositories.gold_publication import GoldPublicationUnavailable
from app.services.genai_client import (
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.gold_readiness import (
    evaluate_attendance_readiness,
    evaluate_domain_readiness,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", action="append", required=True,
                        help="Competência solicitada YYYY-MM; repetir para mais meses.")
    parser.add_argument("--scope", choices=["attendance", "domains"], default="attendance",
                        help="Atendimento compatível ou avaliação dos quatro domínios.")
    parser.add_argument("--approve-control", action="append", choices=["C01","C02","C03","C04","C10","C11","C12","C13","C14","C15"], default=[],
                        help="Aceite explícito da regra do controle; não força resultado passado.")
    args = parser.parse_args()
    url = os.getenv("GOLD_READINESS_DATABASE_URL")
    base = os.getenv("AI_AGENT_BASE_URL")
    token = os.getenv("AI_AGENT_SERVICE_API_TOKEN")
    if not url or not base or not token:
        print("Configure banco de leitura, URL GenAI e token de serviço no ambiente.", file=sys.stderr)
        return 1
    options = {"connect_args": {"connect_timeout": 5}, "pool_timeout": 5} if url.startswith("postgresql") else {}
    engine = create_engine(url, hide_parameters=True, **options)
    if engine.dialect.name == "sqlite":
        engine = engine.execution_options(schema_translate_map={"gold": None, "gold_v2": None})

    evaluate = evaluate_domain_readiness if args.scope == "domains" else evaluate_attendance_readiness

    async def run():
        async with httpx.AsyncClient(timeout=35, trust_env=False) as client:
            return await evaluate(
                engine, http_client=client, base_url=base, service_token=token,
                requested_periods=tuple(args.period),
                approved_controls=frozenset(args.approve_control), correlation_id=uuid4().hex,
                expected_batch_ref=os.getenv("GOLD_READINESS_EXPECTED_BATCH_REF"))
    try:
        report = asyncio.run(run())
    except (ValueError, SQLAlchemyError, GoldPublicationUnavailable, GenAIResponseInvalid,
            GenAIServiceUnavailable, GenAITimeout):
        print("Não foi possível comprovar prontidão. Confira publicação, controles e serviço.",
              file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    # Saída operacional sem referência do lote, períodos, identificadores ou contagens.
    print(json.dumps({"readiness_version":report.readiness_version, "lot_state":report.lot_state,
                      "capabilities":{key:value.model_dump() for key,value in report.capabilities.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
