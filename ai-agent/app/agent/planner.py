"""Liga a interpretação à ferramenta sintética sem gerar resposta de linguagem natural."""

from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.agent.interpreter import QuestionInterpreter
from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.questions import ConversationTurn
from app.tools.synthetic_analytics import (
    SyntheticScenarioRequest,
    SyntheticToolResult,
    ToolStatus,
)


class ScenarioTool(Protocol):
    def execute(self, request: SyntheticScenarioRequest) -> SyntheticToolResult: ...


class ScenarioToolUnavailable(Exception):
    """Sinaliza indisponibilidade temporária da ferramenta analítica."""


class AnalysisPlanStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    NO_EVIDENCE = "no_evidence"


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AnalysisPlanStatus
    interpretation: IntentInterpretation
    tool_result: SyntheticToolResult | None = None

    @model_validator(mode="after")
    def validate_tool_was_called_only_for_ready_intent(self) -> Self:
        if self.interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            if (
                self.status is not AnalysisPlanStatus.NEEDS_CLARIFICATION
                or self.tool_result is not None
            ):
                raise ValueError("pergunta ambígua deve parar antes da ferramenta")
        elif self.tool_result is None:
            raise ValueError("intenção pronta exige resultado da ferramenta")
        elif (
            self.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
            and self.tool_result.status is not ToolStatus.NEEDS_CLARIFICATION
        ):
            raise ValueError("esclarecimento da ferramenta precisa ser preservado no plano")
        elif (
            self.status is AnalysisPlanStatus.READY
            and self.tool_result.status is not ToolStatus.SUCCESS
        ):
            raise ValueError("plano pronto exige evidência da ferramenta")
        elif (
            self.status is AnalysisPlanStatus.NO_EVIDENCE
            and self.tool_result.status is not ToolStatus.NO_EVIDENCE
        ):
            raise ValueError("plano sem evidência exige resultado correspondente da ferramenta")
        return self


class QuestionAnalysisPlanner:
    """Prepara a interpretação e consulta a fixture só após resolver ambiguidades."""

    def __init__(self, interpreter: QuestionInterpreter, scenario_tool: ScenarioTool) -> None:
        self._interpreter = interpreter
        self._scenario_tool = scenario_tool

    def prepare(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
    ) -> AnalysisPlan:
        interpretation = self._interpreter.interpret(question, context)
        if interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            return AnalysisPlan(
                status=AnalysisPlanStatus.NEEDS_CLARIFICATION,
                interpretation=interpretation,
            )

        assert interpretation.intent is not None
        tool_result = self._scenario_tool.execute(
            SyntheticScenarioRequest(intent=interpretation.intent)
        )
        if tool_result.status is ToolStatus.SUCCESS:
            status = AnalysisPlanStatus.READY
        elif tool_result.status is ToolStatus.NEEDS_CLARIFICATION:
            status = AnalysisPlanStatus.NEEDS_CLARIFICATION
        else:
            status = AnalysisPlanStatus.NO_EVIDENCE
        return AnalysisPlan(
            status=status,
            interpretation=interpretation,
            tool_result=tool_result,
        )
