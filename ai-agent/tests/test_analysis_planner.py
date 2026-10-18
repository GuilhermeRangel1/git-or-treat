from app.agent.interpreter import QuestionInterpreter
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner
from app.schemas.scenarios import AnalysisIntent
from app.tools.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.tools.synthetic_analytics import SyntheticScenarioTool


class CountingScenarioTool:
    def __init__(self) -> None:
        self.calls: list[AnalysisIntent] = []

    def retrieve(self, intent: AnalysisIntent) -> EvidenceLookupResult:
        self.calls.append(intent)
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Fixture sem correspondência para este teste.",
        )


def test_ambiguous_question_is_clarified_before_any_tool_is_called() -> None:
    tool = CountingScenarioTool()
    planner = QuestionAnalysisPlanner(QuestionInterpreter(), tool)

    plan = planner.prepare("Minha conta de luz subiu?")

    assert plan.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
    assert plan.evidence_result is None
    assert tool.calls == []


def test_corrected_filter_is_the_only_filter_sent_to_the_tool() -> None:
    tool = CountingScenarioTool()
    planner = QuestionAnalysisPlanner(QuestionInterpreter(), tool)

    plan = planner.prepare(
        "Qual foi a receita em Olinda, não, em Jaboatão entre o ano passado e este ano?"
    )

    assert plan.status is AnalysisPlanStatus.NO_EVIDENCE
    assert plan.interpretation.intent is not None
    assert plan.interpretation.intent.geography_phrase == "Jaboatão"
    assert len(tool.calls) == 1
    assert tool.calls[0].geography_phrase == "Jaboatão"


def test_planner_accepts_an_evidence_source_without_synthetic_request_types() -> None:
    planner = QuestionAnalysisPlanner(QuestionInterpreter(), SyntheticScenarioTool())

    plan = planner.prepare("Qual foi o consumo no período de demonstração?")

    assert plan.status is AnalysisPlanStatus.READY
    assert plan.evidence_result is not None
    assert plan.evidence_result.evidence is not None
    assert plan.evidence_result.evidence.reference.is_demo is True


def test_explicit_demo_question_reaches_synthetic_tool_and_returns_evidence() -> None:
    planner = QuestionAnalysisPlanner(QuestionInterpreter(), SyntheticScenarioTool())

    plan = planner.prepare("Qual foi o consumo no período de demonstração?")

    assert plan.status is AnalysisPlanStatus.READY
    assert plan.evidence_result is not None
    assert plan.evidence_result.evidence is not None
    assert plan.evidence_result.evidence.records == [
        {"value": 420, "unit": "unidades fictícias"}
    ]
