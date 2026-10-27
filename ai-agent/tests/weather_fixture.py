"""Segundo domínio inteiramente artificial para provar composição sem mudanças no núcleo."""

from app.schemas.domain_profile import DomainProfile
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.read_plan import LogicalReadPlan, WindowKind

WEATHER_SOURCE_ID = "synthetic.weather"

WEATHER_PROFILE = DomainProfile.model_validate(
    {
        "profile_id": "weather-lab-demo",
        "domains": [{"id": "weather", "label": "Clima artificial"}],
        "metrics": [
            {
                "id": "weather.rainfall",
                "domain_id": "weather",
                "aliases": ["chuva", "precipitação"],
                "unit": "mm fictícios",
                "granularities": ["month"],
                "dimension_ids": ["weather.station"],
                "sensitivity": "internal",
                "evidence_fields": [
                    {
                        "name": "value",
                        "role": "measure",
                        "value_type": "number",
                        "sensitivity": "internal",
                    },
                    {
                        "name": "unit",
                        "role": "unit",
                        "value_type": "string",
                        "sensitivity": "internal",
                    },
                ],
                "limitation_texts": ["Medição inteiramente fictícia; não descreve clima real."],
            },
            {
                "id": "weather.temperature",
                "domain_id": "weather",
                "aliases": ["temperatura"],
                "unit": "graus fictícios",
                "granularities": ["month"],
                "dimension_ids": ["weather.station"],
                "sensitivity": "internal",
                "evidence_fields": [
                    {
                        "name": "value",
                        "role": "measure",
                        "value_type": "number",
                        "sensitivity": "internal",
                    },
                    {
                        "name": "unit",
                        "role": "unit",
                        "value_type": "string",
                        "sensitivity": "internal",
                    },
                ],
                "limitation_texts": ["Medição inteiramente fictícia; não descreve clima real."],
            },
        ],
        "dimensions": [
            {
                "id": "weather.station",
                "label": "Estação fictícia",
                "role": "geography",
                "aliases": ["estação", "posto"],
                "value_type": "string",
                "operators": ["eq"],
                "sensitivity": "internal",
                "values": [
                    {"value": "Arua", "aliases": ["Arua"]},
                    {"value": "Bela", "aliases": ["Bela"]},
                ],
            }
        ],
        "period_phrases": ["período de demonstração"],
        "comparison_terms": ["comparar"],
        "correction_terms": ["não", "corrigindo"],
        "follow_up_starters": ["e", "também"],
        "direction_terms": ["aumento", "queda"],
        "clarifications": {
            "missing_metric": "Qual indicador climático?",
            "multiple_domains": "Qual assunto climático primeiro?",
            "multiple_metrics": "Você quer chuva ou temperatura?",
            "unknown_geography": "Qual estação fictícia?",
            "multiple_geographies": "Qual estação fictícia primeiro?",
            "multiple_classes": "Qual classe?",
            "missing_period": "Qual período?",
            "comparison_baseline": "Qual período de base?",
            "multiple_periods": "Quer comparar os períodos?",
        },
        "operations": ["read"],
    }
)


class WeatherEvidenceSource:
    """Adaptador de teste: apenas o período e a estação Arua têm dados."""

    def __init__(self) -> None:
        self.plans: list[LogicalReadPlan] = []

    async def retrieve(self, plan: LogicalReadPlan, _access_context) -> EvidenceLookupResult:
        self.plans.append(plan)
        if (
            plan.window.kind is not WindowKind.CATALOG_PHRASE
            or plan.window.phrase != "período de demonstração"
            or any(item.values != ("Arua",) for item in plan.filters)
        ):
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NO_EVIDENCE,
                message="Sem medição artificial nesse recorte.",
            )

        values = {"weather.rainfall": 12, "weather.temperature": 23}
        value = values.get(plan.metric_id)
        if value is None:
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NO_EVIDENCE,
                message="Indicador artificial ausente.",
            )
        reference = EvidenceReference(
            source=WEATHER_SOURCE_ID,
            description="Fonte artificial de clima para teste de integração.",
            is_demo=True,
        )
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=reference,
                records=[{"value": value, "unit": plan.unit}],
                provenance=EvidenceProvenance(
                    source_id=plan.source_id,
                    reference_source=reference.source,
                    plan_fingerprint=plan.fingerprint(),
                    catalog_version=plan.catalog_version,
                    metric_id=plan.metric_id,
                    unit=plan.unit,
                    window=plan.window,
                    filters=plan.filters,
                    dimension_ids=plan.dimension_ids,
                ),
            ),
            limitations=["Medição inteiramente fictícia; não descreve clima real."],
        )
