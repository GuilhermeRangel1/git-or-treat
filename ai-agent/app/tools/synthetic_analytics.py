"""Ferramentas analíticas estritamente sintéticas para validar contratos locais."""

from enum import StrEnum
from math import isfinite
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scenarios import SYNTHETIC_SCENARIOS
from app.schemas.questions import EvidenceReference
from app.schemas.scenarios import AnalysisIntent, SyntheticScenario
from app.tools.evidence import EvidenceResult


class ToolStatus(StrEnum):
    SUCCESS = "success"
    NO_EVIDENCE = "no_evidence"
    NEEDS_CLARIFICATION = "needs_clarification"


class SyntheticToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ToolStatus
    evidence: EvidenceResult | None = None
    message: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is ToolStatus.SUCCESS:
            if self.evidence is None or not self.evidence.records:
                raise ValueError("resultado de sucesso exige evidências com registros")
            if not self.evidence.reference.is_demo:
                raise ValueError("ferramenta sintética exige referência marcada como demonstração")
        elif self.evidence is not None or not self.message:
            raise ValueError("resultado sem evidência exige mensagem e não pode conter dados")
        return self


class SyntheticScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str | None = None
    intent: AnalysisIntent | None = None

    @model_validator(mode="after")
    def require_one_selector(self) -> Self:
        if (self.scenario_id is None) == (self.intent is None):
            raise ValueError("informe scenario_id ou intent, mas não ambos")
        return self


class SyntheticScenarioTool:
    """Busca uma fixture pelo ID ou domínio sem aplicar filtros não representados."""

    def __init__(
        self,
        catalog: tuple[SyntheticScenario, ...] = SYNTHETIC_SCENARIOS,
    ) -> None:
        self._catalog = catalog

    def execute(self, request: SyntheticScenarioRequest) -> SyntheticToolResult:
        if request.scenario_id is not None:
            scenario = next(
                (item for item in self._catalog if item.scenario_id == request.scenario_id),
                None,
            )
        else:
            intent = request.intent
            assert intent is not None
            if intent.geography_phrase or intent.class_phrase or intent.filters:
                return SyntheticToolResult(
                    status=ToolStatus.NO_EVIDENCE,
                    message="A fixture sintética não contém os filtros solicitados.",
                )
            if intent.period_phrase and "demonstração" not in intent.period_phrase.casefold():
                return SyntheticToolResult(
                    status=ToolStatus.NO_EVIDENCE,
                    message="A fixture não representa o período solicitado.",
                )
            scenario = next(
                (item for item in self._catalog if item.intent.domain is intent.domain),
                None,
            )

        if scenario is None:
            return SyntheticToolResult(
                status=ToolStatus.NO_EVIDENCE,
                message="Não há cenário sintético correspondente à solicitação.",
            )
        if not scenario.evidence.records:
            return SyntheticToolResult(
                status=ToolStatus.NO_EVIDENCE,
                message="O cenário não contém registros para responder.",
                limitations=scenario.limitations,
            )
        return SyntheticToolResult(
            status=ToolStatus.SUCCESS,
            evidence=scenario.evidence,
            limitations=scenario.limitations,
        )


class PeriodGranularity(StrEnum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class SyntheticObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_label: str = Field(min_length=1, max_length=100)
    granularity: PeriodGranularity
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=60)


class SyntheticComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[SyntheticObservation] = Field(default_factory=list, max_length=2)
    reference: EvidenceReference

    @model_validator(mode="after")
    def require_demo_reference(self) -> Self:
        if not self.reference.is_demo:
            raise ValueError(
                "comparação sintética exige EvidenceReference marcada como demonstração"
            )
        return self


class SyntheticPeriodComparisonTool:
    """Compara dois valores artificiais; não implementa fórmula oficial do negócio."""

    def compare(self, request: SyntheticComparisonRequest) -> SyntheticToolResult:
        if len(request.observations) != 2:
            return SyntheticToolResult(
                status=ToolStatus.NO_EVIDENCE,
                message="A comparação requer dois períodos com valores disponíveis.",
            )

        baseline, current = request.observations
        if baseline.granularity is not current.granularity or baseline.unit != current.unit:
            return SyntheticToolResult(
                status=ToolStatus.NEEDS_CLARIFICATION,
                message="Os períodos e as unidades precisam ser comparáveis.",
            )
        if baseline.value == 0:
            return SyntheticToolResult(
                status=ToolStatus.NO_EVIDENCE,
                message="Não é possível calcular variação percentual com denominador zero.",
            )

        absolute_change = current.value - baseline.value
        percentage_change = absolute_change / baseline.value * 100
        if not isfinite(absolute_change) or not isfinite(percentage_change):
            return SyntheticToolResult(
                status=ToolStatus.NO_EVIDENCE,
                message="A comparação não produziu um resultado numérico válido.",
            )

        return SyntheticToolResult(
            status=ToolStatus.SUCCESS,
            evidence=EvidenceResult(
                reference=request.reference,
                records=[
                    {
                        "baseline_period": baseline.period_label,
                        "current_period": current.period_label,
                        "baseline_value": baseline.value,
                        "current_value": current.value,
                        "absolute_change": absolute_change,
                        "percentage_change": percentage_change,
                        "unit": baseline.unit,
                    }
                ],
            ),
            limitations=[
                "Valores e comparação são sintéticos; a variação percentual é uma operação "
                "aritmética de demonstração, não uma fórmula oficial da V-Energy."
            ],
        )
