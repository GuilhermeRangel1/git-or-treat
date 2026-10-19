"""Coordena a geração de hipóteses a partir de contexto de tela estruturado."""

from pydantic import ValidationError

from app.agent.execution import ExecutionController, ExecutionLimitExceeded, RequestBudget
from app.providers.protocols import (
    GeneratedAnswer,
    ModelAdapter,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceReference, EvidenceResult
from app.schemas.insights import (
    InsightContextSummary,
    InsightObservation,
    ScreenContext,
    ScreenInsightResponse,
)
from app.schemas.questions import QuestionStatus
from app.schemas.responses import FailureCode, PublicError, map_failure

INSIGHT_PROMPT = (
    "Selecione em observation_ids as observações que merecem investigação. "
    "Use somente os IDs fornecidos. Não invente números, filtros ou causas; "
    "o serviço montará a hipótese pública a partir das observações selecionadas."
)
SYNTHETIC_INSIGHT_LIMITATIONS = [
    "O contexto e os valores são sintéticos; não representam dados reais da V-Energy.",
    "A hipótese é uma sugestão de investigação, não uma causa comprovada.",
]


class ScreenInsightOrchestrator:
    """Mantém observações do cliente separadas da hipótese gerada pelo modelo."""

    def __init__(
        self,
        model_adapter: ModelAdapter,
        execution_controller: ExecutionController | None = None,
    ) -> None:
        self._model_adapter = model_adapter
        self._execution = execution_controller or ExecutionController()

    async def generate(
        self, screen: ScreenContext, access_context: AccessContext | None = None
    ) -> ScreenInsightResponse:
        try:
            return await self._execution.run(
                lambda budget: self._generate_with_budget(screen, access_context, budget)
            )
        except ExecutionLimitExceeded:
            failure = map_failure(FailureCode.EXECUTION_LIMIT)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
                expose_context=access_context is not None,
            )

    async def _generate_with_budget(
        self,
        screen: ScreenContext,
        access_context: AccessContext | None,
        budget: RequestBudget,
    ) -> ScreenInsightResponse:
        if access_context is None:
            failure = map_failure(FailureCode.ACCESS_DENIED)
            return self._response(
                screen,
                status=QuestionStatus.REFUSED,
                message=failure.message,
                error=failure.error,
                expose_context=False,
            )
        records: list[dict[str, object]] = [
            {
                "metric": "Indicador demonstrativo da tela",
                "unit": screen.unit,
                "period": screen.period.model_dump(mode="json"),
                "filter_keys": sorted(screen.filters),
                "observations": [
                    {"observation_id": f"row_{index}", "value": item.value}
                    for index, item in enumerate(screen.observations, start=1)
                ],
            }
        ]
        evidence = EvidenceResult(
            reference=screen.reference.model_copy(
                update={"description": "Contexto sintético de tela fornecido pelo cliente."}
            ),
            records=records,
        )
        try:
            generated_result = await budget.model(
                lambda: self._model_adapter.generate(INSIGHT_PROMPT, [], evidence)
            )
            generated = GeneratedAnswer.model_validate(
                generated_result.model_dump()
                if isinstance(generated_result, GeneratedAnswer)
                else generated_result
            )
        except ModelProviderUnavailable:
            failure = map_failure(FailureCode.MODEL_UNAVAILABLE)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except (ModelProviderRejected, ModelProviderInvalidResponse) as exc:
            code = (
                FailureCode.MODEL_REJECTED
                if isinstance(exc, ModelProviderRejected)
                else FailureCode.INVALID_MODEL_OUTPUT
            )
            failure = map_failure(code)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except ExecutionLimitExceeded:
            raise
        except (ValidationError, TypeError, ValueError):
            failure = map_failure(FailureCode.INVALID_MODEL_OUTPUT)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except Exception:
            failure = map_failure(FailureCode.UNEXPECTED)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )

        observations = {
            f"row_{index}": item
            for index, item in enumerate(screen.observations, start=1)
        }
        if generated.status == "answered" and (
            not generated.observation_ids
            or len(set(generated.observation_ids)) != len(generated.observation_ids)
            or not set(generated.observation_ids) <= set(observations)
        ):
            failure = map_failure(FailureCode.UNGROUNDED_INSIGHT)
            return self._response(
                screen,
                status=QuestionStatus.REFUSED,
                message=failure.message,
                error=failure.error,
            )
        if generated.status == "answered":
            selected = ", ".join(
                f"{observations[item].label}: {observations[item].value} {screen.unit}"
                for item in generated.observation_ids
            )
            return self._response(
                screen,
                status=QuestionStatus.ANSWERED,
                hypothesis=(
                    f"Investigue o recorte de {screen.metric} a partir da observação "
                    f"demonstrativa: {selected}. Isso não estabelece uma causa."
                ),
            )
        if generated.status == "needs_clarification":
            return self._response(
                screen,
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message="Esclareça o recorte ou forneça série histórica para investigar a tela.",
            )
        return self._response(
            screen,
            status=QuestionStatus.REFUSED,
            message=map_failure(FailureCode.INSIGHT_REFUSAL).message,
            error=map_failure(FailureCode.INSIGHT_REFUSAL).error,
        )

    @staticmethod
    def _response(
        screen: ScreenContext,
        *,
        status: QuestionStatus,
        hypothesis: str | None = None,
        message: str | None = None,
        error: PublicError | None = None,
        expose_context: bool = True,
    ) -> ScreenInsightResponse:
        return ScreenInsightResponse(
            status=status,
            context=InsightContextSummary(
                metric=screen.metric if expose_context else "Indisponível",
                unit=screen.unit if expose_context else "Indisponível",
                period=screen.period,
                filters=screen.filters if expose_context else {},
            ),
            observation=InsightObservation(
                values=screen.observations if expose_context else []
            ),
            hypothesis=hypothesis,
            message=message,
            error=error,
            evidence=[
                EvidenceReference(
                    source=screen.reference.source,
                    description="Contexto sintético de tela fornecido pelo cliente.",
                    is_demo=True,
                )
            ] if expose_context else [],
            limitations=SYNTHETIC_INSIGHT_LIMITATIONS,
        )
