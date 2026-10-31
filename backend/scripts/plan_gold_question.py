"""Planeja uma pergunta Gold com escopo local confiável e sem exibir dados do lote."""

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
from app.schemas.ai import AIQuestionRequest
from app.schemas.genai_internal import AccessScope
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_planning import plan_gold_question


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", required=True, type=Path,
                        help="JSON privado no contrato público de pergunta, sem escopo.")
    parser.add_argument("--scope-file", required=True, type=Path,
                        help="Escopo AccessScope administrado localmente pelo Backend; não use entrada do portal.")
    args = parser.parse_args()
    url = os.getenv("GOLD_READINESS_DATABASE_URL")
    base = os.getenv("AI_AGENT_BASE_URL")
    token = os.getenv("AI_AGENT_SERVICE_API_TOKEN")
    if not url or not base or not token:
        print("Configure banco de leitura, URL GenAI e token de serviço.", file=sys.stderr)
        return 1
    engine = create_engine(url, hide_parameters=True, pool_timeout=5,
                           connect_args={"connect_timeout": 5})
    try:
        if engine.dialect.name != "postgresql" or engine.url.username != "venergy_gold_reader":
            raise ValueError("A operação exige PostgreSQL com papel somente leitura.")
        request = AIQuestionRequest.model_validate_json(args.request_file.read_text(encoding="utf-8"))

        def resolve_scope():
            # Relê a política atual após HTTP/consulta; alteração não herda acesso antigo.
            return AccessScope.model_validate_json(args.scope_file.read_text(encoding="utf-8"))

        async def run():
            async with httpx.AsyncClient(timeout=35, trust_env=False) as transport:
                client = GenAIQuestionClient(http_client=transport, base_url=base.rstrip("/"),
                                            service_token=token)
                return await plan_gold_question(
                    engine, client, request, resolve_scope=resolve_scope,
                    correlation_id=uuid4().hex,
                    expected_batch_ref=os.getenv("GOLD_READINESS_EXPECTED_BATCH_REF"),
                )
        result = asyncio.run(run())
    except (OSError, ValueError, SQLAlchemyError, GoldPublicationUnavailable,
            GenAIResponseInvalid, GenAIServiceUnavailable, GenAITimeout):
        print("Planejamento não comprovado. Confira acesso, publicação e serviço.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    # O consumidor de execução importa plan_gold_question e recebe plano/fonte/lote.
    # A CLI comprova a operação sem registrar pergunta, valores, UC ou referência privada.
    print(json.dumps({"status": result.response.status.value,
                      "plan_admitted": result.source is not None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
