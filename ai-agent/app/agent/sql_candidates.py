"""Geração interna com orçamento/auditoria compartilhados; nenhuma fonte SQL."""

from typing import Protocol

from app.agent.execution import ExecutionController
from app.ports.events import EventCode, EventOutcome, EventSink, EventStage, EventTrace
from app.providers.protocols import (
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.sql_generation import (
    SqlGenerationCandidate,
    SqlGenerationRequest,
    SqlGenerationResponse,
)


class SqlCandidateGenerator(Protocol):
    async def generate(
        self,
        contents: str,
        *,
        context_version: str,
        timeout_seconds: float,
    ) -> SqlGenerationCandidate: ...


class SqlCandidateService:
    def __init__(
        self,
        generator: SqlCandidateGenerator,
        controller: ExecutionController,
        sink: EventSink,
    ):
        self.generator = generator
        self.controller = controller
        self.sink = sink
        controller.ensure_model_capacity(generator)

    async def generate(
        self,
        payload: SqlGenerationRequest,
        correlation_id: str,
    ) -> SqlGenerationResponse:
        trace = EventTrace(self.sink, "question", correlation_id, require_durable=True)

        async def action(budget):
            await trace.emit_async(EventStage.REQUEST, EventCode.STARTED, EventOutcome.STARTED)
            trace.model_calls = 1
            await trace.emit_async(EventStage.MODEL, EventCode.STARTED, EventOutcome.STARTED)
            try:
                result = await budget.model(
                    lambda: self.generator.generate(
                        payload.contents,
                        context_version=payload.context_version,
                        timeout_seconds=min(20, payload.remaining_timeout_ms / 1000),
                    )
                )
            except (ModelProviderUnavailable, ModelProviderRejected):
                await trace.emit_async(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
                raise
            if (
                not isinstance(result, SqlGenerationCandidate)
                or result.context_version != payload.context_version
            ):
                raise ModelProviderInvalidResponse("Contrato ou contexto de candidato divergente.")
            await trace.emit_async(EventStage.MODEL, EventCode.READY, EventOutcome.SUCCESS)
            await trace.emit_async(EventStage.RESPONSE, EventCode.COMPLETED, EventOutcome.SUCCESS)
            return SqlGenerationResponse(correlation_id=correlation_id, candidate=result)

        return await self.controller.run(
            action,
            timeout_seconds=payload.remaining_timeout_ms / 1000,
        )
