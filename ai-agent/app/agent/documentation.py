"""Respostas conceituais extraídas do corpus autorizado, com citação verificável."""

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from app.agent.execution import ExecutionLimitExceeded, RequestBudget
from app.agent.safety import QuestionSafetyGate
from app.ports.documentation import (
    DocumentationSource,
    DocumentSelection,
    DocumentSelectionUnavailable,
    DocumentSelector,
)
from app.ports.events import EventCode, EventOutcome, EventStage, EventTrace, safe_reference_id
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceReference
from app.schemas.internal import DocumentationReference
from app.schemas.questions import QuestionResponse, QuestionStatus
from app.schemas.responses import FailureCode, map_failure

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentationResult:
    response: QuestionResponse
    reference: DocumentationReference | None = None
    retrieved_id: str | None = None


def normalize(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(char)
    )


def conceptual_question(question: str) -> bool:
    text = normalize(question)
    if re.search(
        r"\b\d{4}\b|\d+[/-]\d+|\balm[-_]|"
        r"\b(quanto(?! tempo em media)|quantos|quantas|qual foi|compare|comparar|"
        r"mes passado|top|ranking|"
        r"maiores|menores|janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro|ontem|hoje|trimestre|ano passado)\b|"
        r"\bem\s+(?!que\b|kwh\b|reais\b|horas\b|media\b)[a-z]+",
        text,
    ):
        return False
    return bool(
        re.search(
            r"\b(o que (?:e|sao|significa|entra|quer dizer)|qual (?:e )?a diferenca|"
            r"diferenca entre|explique|explica|explicar|defina|definicao|significado|"
            r"para que serve|significa|significam|me (?:explica|explique)|"
            r"pode (?:explicar|me explicar)|representam um mes|"
            r"(?:comprova|explica) (?:a )?causa|"
            r"(?:e|sao) (?:o mesmo|a mesma|(?:o )?valor pago|(?:a )?energia faturada|"
            r"(?:a )?tarifa)|como (?:entender|interpretar|funciona|e calculado))\b",
            text,
        )
    )


def lexical_scores(question, chunks):
    words = set(re.findall(r"[a-z]+", normalize(question)))
    words -= {"energia", "media", "faturada", "fatura", "variacao", "causa", "volume", "queda"}
    return [(index, len(words & set(chunk.keywords))) for index, chunk in enumerate(chunks)]


class DocumentationResponder:
    def __init__(self, source: DocumentationSource, selector: DocumentSelector | None = None):
        self.source, self.selector = source, selector
        self.safety = QuestionSafetyGate()

    async def respond(
        self,
        question: str,
        access: AccessContext,
        budget: RequestBudget,
        trace: EventTrace | None = None,
    ) -> DocumentationResult:
        today = datetime.now(UTC).date()
        try:
            if trace is not None:
                trace.source_calls += 1
                await trace.emit_async(EventStage.SOURCE, EventCode.STARTED, EventOutcome.STARTED)
            chunks = await budget.source(
                lambda: asyncio.to_thread(self.source.authorized_chunks, access, today)
            )
            # Metadados e conteúdo são dados não confiáveis, inclusive antes da seleção semântica.
            chunks = tuple(
                chunk
                for chunk in chunks
                if self.safety.refusal_code(
                    f"{chunk.title}\n{chunk.section}\n{chunk.owner}\n{chunk.text}"
                )
                is None
            )
            if not chunks:
                return self.absent()
            texts = (question, *(f"{chunk.section}\n{chunk.text}" for chunk in chunks))
            if len(chunks) > 24 or sum(len(text.encode("utf-8")) for text in texts) > 16384:
                return self.failure(FailureCode.EXECUTION_LIMIT)
            lexical = sorted(lexical_scores(question, chunks), key=lambda item: -item[1])
            selected = None
            sufficient = True
            strategy = "lexical"
            # Um único tópico nomeado de forma inequívoca dispensa chamada remota.
            positive = [item for item in lexical if item[1] > 0]
            exact = [
                index
                for index, chunk in enumerate(chunks)
                if normalize(question).strip(" .?!") == normalize(chunk.section).strip(" .?!")
            ]
            if len(exact) == 1:
                selected = exact[0]
            elif len(positive) == 1 and any(
                re.fullmatch(
                    r"(?:o que e|o que significa|explique|defina) (?:a |o )?"
                    + re.escape(normalize(line.split(":", 1)[0]))
                    + r"[.!?]*",
                    normalize(question).strip(),
                )
                for line in chunks[positive[0][0]].text.splitlines()
            ):
                selected = positive[0][0]
            elif self.selector is not None:
                strategy = "semantic"
                if trace is not None:
                    trace.model_calls += 1
                    await trace.emit_async(
                        EventStage.MODEL, EventCode.STARTED, EventOutcome.STARTED
                    )
                async with asyncio.timeout(20):
                    selection = await budget.model(lambda: self.selector.select(question, chunks))
                if (
                    not isinstance(selection, DocumentSelection)
                    or type(selection.sufficient) is not bool
                ):
                    raise ValueError("seleção documental inválida")
                if trace is not None:
                    await trace.emit_async(
                        EventStage.MODEL, EventCode.COMPLETED, EventOutcome.SUCCESS
                    )
                sufficient = selection.sufficient
                if selection.id is not None:
                    indices = [i for i, chunk in enumerate(chunks) if chunk.id == selection.id]
                    if len(indices) != 1:
                        raise ValueError("seleção fora do corpus autorizado")
                    selected = indices[0]
            else:
                return self.failure(FailureCode.MODEL_UNAVAILABLE)
            if selected is None:
                return self.absent(ambiguous=bool(positive))
            chunk = chunks[selected]
            # Mudança/retirada/revogação no corpus durante a chamada invalida a citação.
            current = await asyncio.to_thread(self.source.authorized_chunks, access, today)
            if chunk not in current:
                return self.absent()
            if not sufficient:
                return DocumentationResult(
                    QuestionResponse(
                        status=QuestionStatus.NEEDS_CLARIFICATION,
                        message=f"Encontrei a definição “{chunk.section}”, mas ela não cobre toda "
                        "a sua dúvida. Para consultar essa definição, "
                        f"pergunte: “{chunk.section}”.",
                    ),
                    retrieved_id=chunk.id,
                )
            if trace is not None:
                trace.evidence_ref = safe_reference_id(f"documentation:{chunk.id}:{chunk.version}")
                trace.row_count = 1
                await trace.emit_async(
                    EventStage.EVIDENCE, EventCode.AVAILABLE, EventOutcome.SUCCESS
                )
            logger.info(
                "Busca documental: estratégia=%s, trecho=%s, versão=%s.",
                strategy,
                chunk.id,
                chunk.version,
            )
            return DocumentationResult(
                QuestionResponse(
                    status=QuestionStatus.ANSWERED,
                    answer=chunk.text,
                    evidence=[
                        EvidenceReference(
                            source="documentation.indicators",
                            description=(
                                f"{chunk.title} · {chunk.section} · "
                                f"versão {chunk.version} · trecho {chunk.id}."
                            ),
                            is_demo=False,
                        )
                    ],
                    limitations=[
                        "Explicação conceitual; valores por período ou local "
                        "exigem uma consulta aos dados."
                    ],
                ),
                DocumentationReference(id=chunk.id, version=chunk.version),
                retrieved_id=chunk.id,
            )
        except (TimeoutError, ExecutionLimitExceeded, DocumentSelectionUnavailable):
            return self.failure(FailureCode.MODEL_UNAVAILABLE)
        except (OSError, ValueError, TypeError, KeyError):
            return self.failure(FailureCode.SOURCE_UNAVAILABLE)

    @staticmethod
    def absent(*, ambiguous=False):
        return DocumentationResult(
            QuestionResponse(
                status=QuestionStatus.NEEDS_CLARIFICATION
                if ambiguous
                else QuestionStatus.NO_EVIDENCE,
                message=(
                    "Qual indicador você quer entender primeiro? "
                    "Indique um dos conceitos ou detalhe a diferença que deseja esclarecer."
                    if ambiguous
                    else "Não encontrei uma definição autorizada suficiente para responder. "
                    "Indique o nome do indicador ou reformule a dúvida."
                ),
            )
        )

    @staticmethod
    def failure(code):
        failure = map_failure(code)
        return DocumentationResult(
            QuestionResponse(
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        )
