"""Avaliação opt-in com onze perguntas artificiais e corpus conceitual aprovado."""

import asyncio
import json
import os
from datetime import UTC, datetime
from time import monotonic

from app.agent.documentation import DocumentationResponder, conceptual_question, lexical_scores
from app.agent.execution import ExecutionController
from app.config import Settings
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.document_selector import GeminiDocumentSelector
from app.schemas.access import AccessContext
from app.tools.documentation import IndicatorDocumentation

CASES = [
    ("Me explica o montante cobrado nas contas", "revenue"),
    ("O que significa quanto tempo em media uma unidade ficou sem luz?", "continuity"),
    ("Como entender a quantidade de vezes que faltou luz?", "continuity"),
    ("O que e a media cobrada por unidade consumidora?", "ticket"),
    ("Me explica a diferenca entre valor cobrado e dinheiro recebido", "revenue"),
    ("Como interpretar o custo observado de cada quilowatt-hora?", "price"),
    ("O que significa o registro historico de contatos com a central?", "attendance"),
    ("O que e a separacao do efeito de preco e da quantidade vendida?", "decomposition"),
    ("O que significa ter geracao propria e reduzir o consumo?", "gd"),
    ("O que e uma ocorrencia de falta de energia?", "events"),
    ("O que e a previsao do tempo?", None),
]


async def run():
    settings = Settings()
    if os.environ.get("GENAI_RUN_DOCUMENTATION_LIVE") != "1" or settings.gemini_api_key is None:
        raise SystemExit(
            "Ative GENAI_RUN_DOCUMENTATION_LIVE=1 e configure a chave privada "
            "antes da rodada autorizada."
        )
    identity = AccessContext(
        caller_ref="user.test",
        profile_id=GRID360_GOLD_PROFILE.profile_id,
        source_id="gold.local",
        correlation_id="a" * 32,
        allowed_operations={"read"},
        allowed_metric_ids={m.id for m in GRID360_GOLD_PROFILE.metrics},
        allowed_dimension_ids=set(),
    )
    source = IndicatorDocumentation()
    service = DocumentationResponder(
        source,
        GeminiDocumentSelector(
            api_key=settings.gemini_api_key.get_secret_value(), model=settings.gemini_model
        ),
    )
    correct, lexical_correct, supported_answers, retrieved_correct, clarifications = 0, 0, 0, 0, 0
    for question, expected in CASES:
        started = monotonic()
        result = await ExecutionController().run(
            lambda budget, text=question: service.respond(text, identity, budget)
        )
        actual = result.retrieved_id
        chunks = source.authorized_chunks(identity, datetime.now(UTC).date())
        lexical = sorted(
            lexical_scores(question, chunks),
            key=lambda x: -x[1],
        )
        lexical_id = (
            chunks[lexical[0][0]].id
            if lexical[0][1] > 0 and (len(lexical) == 1 or lexical[0][1] > lexical[1][1])
            else None
        )
        expected_statuses = (
            {"answered", "needs_clarification"}
            if expected == "gd"
            else {"answered"}
            if expected is not None
            else {"no_evidence"}
        )
        lexical_correct += lexical_id == expected
        supported = result.response.status.value != "answered" or result.response.answer == next(
            chunk.text for chunk in chunks if chunk.id == actual
        )
        supported_answers += result.response.status.value == "answered" and supported
        # O corpus descreve cadastro de GD/indicador de queda, não comprova geração própria.
        # Esta pergunta ampla pode esclarecer; isso não conta como recuperação correta.
        safe_clarification = (
            expected == "gd"
            and actual in {None, "gd"}
            and result.response.status.value == "needs_clarification"
        )
        correct += supported and (
            safe_clarification
            or actual == expected
            and result.response.status.value in expected_statuses
        )
        retrieved_correct += actual == expected
        clarifications += result.response.status.value == "needs_clarification"
        print(
            json.dumps(
                {
                    "question": question,
                    "expected": expected,
                    "actual": actual,
                    "status": result.response.status.value,
                    "concept": conceptual_question(question),
                    "seconds": round(monotonic() - started, 3),
                    "lexical": lexical[:2],
                    "supported": supported,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    print(
        json.dumps(
            {
                "cases": len(CASES),
                "correct": correct,
                "retrieved_correct": retrieved_correct,
                "clarifications": clarifications,
                "lexical_correct": lexical_correct,
                "supported_answers": supported_answers,
            }
        )
    )
    if correct != len(CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run())
