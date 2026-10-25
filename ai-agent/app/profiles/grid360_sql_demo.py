"""Perfil de faturamento para o ensaio SQL com dados inteiramente fictícios."""

from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DomainProfile

SQL_DEMO_TRUNCATION_LIMITATION = "Resultado demonstrativo limitado às primeiras observações."


def _build_profile() -> DomainProfile:
    values = GRID360_DEMO_PROFILE.model_dump(mode="python")
    values["profile_id"] = "v-energy-grid-360-sql-demo"
    values["dimensions"][0]["values"] = [
        {"value": "Municipio Ficticio A", "aliases": ("Município Fictício A",)},
        {"value": "Municipio Ficticio B", "aliases": ("Município Fictício B",)},
    ]
    values["period_phrases"] = (
        "janeiro de 2025",
        "fevereiro de 2025",
        "março de 2025",
        "abril de 2025",
    )
    values["period_windows"] = (
        {
            "phrase": "janeiro de 2025", "start": "2025-01-01", "end": "2025-01-31",
            "granularity": "month",
        },
        {
            "phrase": "fevereiro de 2025", "start": "2025-02-01", "end": "2025-02-28",
            "granularity": "month",
        },
        {
            "phrase": "março de 2025", "start": "2025-03-01", "end": "2025-03-31",
            "granularity": "month",
        },
        {
            "phrase": "abril de 2025", "start": "2025-04-01", "end": "2025-04-30",
            "granularity": "month",
        },
    )
    values["default_period_phrase"] = None
    values["default_period_context_phrases"] = ()
    values["comparison_period_phrases"] = ()
    evidence_fields = [
        {"name": "value", "role": "measure", "value_type": "number", "sensitivity": "internal"},
        {"name": "unit", "role": "unit", "value_type": "string", "sensitivity": "internal"},
        {"name": "period", "role": "period", "value_type": "date", "sensitivity": "internal"},
        {
            "name": "category",
            "role": "dimension",
            "dimension_id": "geography.municipality",
            "value_type": "string",
            "sensitivity": "internal",
        },
    ]
    for metric in values["metrics"]:
        metric["evidence_fields"] = evidence_fields
        metric["limitation_texts"] = (
            *metric["limitation_texts"], SQL_DEMO_TRUNCATION_LIMITATION
        )
    values["metrics"][1]["unit"] = "kWh fictícios"
    values["metrics"][3]["unit"] = "atendimentos fictícios"
    return DomainProfile.model_validate(values)


GRID360_SQL_DEMO_PROFILE = _build_profile()
