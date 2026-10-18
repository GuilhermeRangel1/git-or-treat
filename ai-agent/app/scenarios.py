"""Cenários artificiais para desenvolver e demonstrar contratos do agente."""

from app.schemas.questions import EvidenceReference
from app.schemas.analysis import AnalysisDomain, AnalysisIntent
from app.schemas.scenarios import SyntheticScenario
from app.tools.evidence import EvidenceResult

SYNTHETIC_SCENARIOS = (
    SyntheticScenario(
        scenario_id="revenue_comparison_demo",
        question="Compare o indicador fictício de receita entre dois períodos de demonstração.",
        intent=AnalysisIntent(
            domain=AnalysisDomain.REVENUE,
            metric_phrase="receita",
            period_phrase="dois períodos de demonstração",
        ),
        evidence=EvidenceResult(
            reference=EvidenceReference(
                source="synthetic_fixture:revenue_comparison_demo",
                description="Índice artificial criado somente para testar o contrato do agente.",
                is_demo=True,
            ),
            records=[
                {"period_label": "período A", "value": 100, "unit": "unidades fictícias"},
                {"period_label": "período B", "value": 95, "unit": "unidades fictícias"},
            ],
        ),
        limitations=[
            "Valores inventados; não representam faturamento, receita ou fórmula oficial "
            "da V-Energy."
        ],
    ),
    SyntheticScenario(
        scenario_id="consumption_demo",
        question="Qual é o indicador sintético de consumo no cenário de demonstração?",
        intent=AnalysisIntent(
            domain=AnalysisDomain.CONSUMPTION,
            metric_phrase="consumo",
        ),
        evidence=EvidenceResult(
            reference=EvidenceReference(
                source="synthetic_fixture:consumption_demo",
                description="Medida artificial sem vínculo com uma unidade consumidora real.",
                is_demo=True,
            ),
            records=[{"value": 420, "unit": "unidades fictícias"}],
        ),
        limitations=[
            "Valor inventado; não representa leitura, consumo ou unidade consumidora da V-Energy."
        ],
    ),
    SyntheticScenario(
        scenario_id="network_interruptions_demo",
        question="Quantas interrupções existem no cenário de demonstração?",
        intent=AnalysisIntent(
            domain=AnalysisDomain.NETWORK,
            metric_phrase="interrupções",
        ),
        evidence=EvidenceResult(
            reference=EvidenceReference(
                source="synthetic_fixture:network_interruptions_demo",
                description="Contagem artificial criada para testar referência de evidência.",
                is_demo=True,
            ),
            records=[{"value": 2, "unit": "ocorrências fictícias"}],
        ),
        limitations=[
            "Contagem inventada; não descreve ocorrências de rede nem indicador DEC/FEC real."
        ],
    ),
    SyntheticScenario(
        scenario_id="service_attendance_demo",
        question="Quantos atendimentos aparecem no cenário sintético?",
        intent=AnalysisIntent(
            domain=AnalysisDomain.SERVICE,
            metric_phrase="atendimentos",
        ),
        evidence=EvidenceResult(
            reference=EvidenceReference(
                source="synthetic_fixture:service_attendance_demo",
                description="Contagem artificial sem dados de clientes ou chamados reais.",
                is_demo=True,
            ),
            records=[{"value": 1, "unit": "atendimento fictício"}],
        ),
        limitations=[
            "Contagem inventada; não representa atendimento, satisfação ou chamado da V-Energy."
        ],
    ),
)
