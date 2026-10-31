"""Catálogo lógico Gold (GENAI-03): perfil sem nomes físicos e núcleo composto com ele.

Tudo sintético: a fonte é a fixture demonstrativa existente, que não tem cenário Gold e por isso
responde sem evidência; o que se verifica é o plano lógico aprovado pelo núcleo.
"""

import asyncio
import json
import re
import tomllib
from pathlib import Path

import pytest

from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.agent.interpreter import QuestionInterpreter
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.profiles.grid360_gold_mapping_v1 import GRID360_GOLD_MAPPING
from app.profiles.grid360_gold_v1 import GOLD_PROFILE_ID, GRID360_GOLD_PROFILE
from app.readiness import CAPABILITY_REQUIREMENTS
from app.schemas.domain_profile import CatalogOperation, DomainProfile
from app.schemas.interpretation import InterpretationStatus
from app.schemas.questions import QuestionRequest
from app.schemas.read_plan import WindowKind
from app.tools.synthetic_analytics import SyntheticScenarioTool

from .conftest import FakeModelAdapter

GOLD_DICTIONARY_PATH = Path(__file__).parents[1] / "app" / "sql" / "dictionary_gold.toml"
GOLD_DATA_DICTIONARY = Path(__file__).resolve().parents[2] / "docs" / "dicionario_gold.md"
CORRELATION_ID = "b" * 32


def _physical_names() -> tuple[set[str], set[str]]:
    """Tabelas e colunas do dicionário Gold: (todas, só identificadores com sublinhado)."""

    raw = tomllib.loads(GOLD_DICTIONARY_PATH.read_text(encoding="utf-8"))
    names = set(raw["tables"])
    for spec in raw["tables"].values():
        names |= set(spec["columns"])
    return names, {name for name in names if "_" in name}


# --- perfil lógico ------------------------------------------------------------------------


def test_gold_profile_validates_and_keeps_the_demo_vocabulary_technique() -> None:
    profile = DomainProfile.model_validate(GRID360_GOLD_PROFILE.model_dump(mode="python"))

    assert profile == GRID360_GOLD_PROFILE
    assert profile.profile_id == GOLD_PROFILE_ID == "v-energy-grid-360-gold"
    assert profile.operations == (CatalogOperation.READ,)
    assert profile.comparison_terms == GRID360_DEMO_PROFILE.comparison_terms
    assert profile.out_of_scope_terms == GRID360_DEMO_PROFILE.out_of_scope_terms
    assert {metric.id for metric in profile.metrics} == {
        "billing.revenue",
        "energy.consumption",
        "billing.average_ticket",
        "billing.effective_tariff",
        "energy.average_consumption_per_uc",
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    }
    demo_ids = {metric.id for metric in GRID360_DEMO_PROFILE.metrics}
    assert {"billing.revenue", "energy.consumption"} <= demo_ids
    assert "network.interruptions" not in {metric.id for metric in profile.metrics}


def test_profile_exposes_no_physical_table_or_column_name() -> None:
    """Rótulos, aliases, limitações e ids falam a língua do negócio, não a do banco.

    Palavras simples que também nomeiam colunas (``bairro``, ``classe``, ``alimentador``)
    são vocabulário do negócio e podem aparecer em texto; identificadores com sublinhado e
    nomes de tabela, não. Ids e nomes de campo de evidência não podem coincidir com nenhum.
    """

    every_name, snake_names = _physical_names()
    text = json.dumps(GRID360_GOLD_PROFILE.model_dump(mode="json"), ensure_ascii=False)
    for name in sorted(snake_names):
        assert not re.search(rf"(?<![\w.]){re.escape(name)}(?![\w])", text, re.IGNORECASE), name

    identifiers = {GRID360_GOLD_PROFILE.profile_id}
    identifiers |= {domain.id for domain in GRID360_GOLD_PROFILE.domains}
    identifiers |= {dimension.id for dimension in GRID360_GOLD_PROFILE.dimensions}
    for metric in GRID360_GOLD_PROFILE.metrics:
        identifiers |= {metric.id, *(field.name for field in metric.evidence_fields)}
    parts = {part for identifier in identifiers for part in identifier.split(".")}
    assert not parts & every_name


def test_every_metric_declares_unit_dimensions_evidence_and_portuguese_limitations() -> None:
    dimension_ids = {dimension.id for dimension in GRID360_GOLD_PROFILE.dimensions}

    for metric in GRID360_GOLD_PROFILE.metrics:
        assert metric.unit and metric.accepted_unit_kinds, metric.id
        assert metric.dimension_ids and set(metric.dimension_ids) <= dimension_ids, metric.id
        roles = [field.role.value for field in metric.evidence_fields]
        assert roles[:3] == ["measure", "unit", "period"], metric.id
        assert len(metric.evidence_fields) == 3 + len(metric.dimension_ids), metric.id
        assert any("homologad" in text for text in metric.limitation_texts), metric.id


def test_billed_revenue_is_never_described_as_paid_and_consumption_as_billed_energy() -> None:
    metrics = {metric.id: metric for metric in GRID360_GOLD_PROFILE.metrics}
    revenue_aliases = {alias.casefold() for alias in metrics["billing.revenue"].aliases}
    consumption_aliases = {alias.casefold() for alias in metrics["energy.consumption"].aliases}

    assert not {"valor pago", "arrecadação", "pagamento"} & revenue_aliases
    assert "energia faturada" not in consumption_aliases
    assert any("não valor pago" in text for text in metrics["billing.revenue"].limitation_texts)
    assert any(
        "não energia faturada" in text for text in metrics["energy.consumption"].limitation_texts
    )


def test_only_closed_or_documented_dimension_values_are_declared() -> None:
    """Sem valores de município, bairro, subgrupo, bandeira, alimentador nem UC do lote."""

    dimensions = {dimension.id: dimension for dimension in GRID360_GOLD_PROFILE.dimensions}
    documented = GOLD_DATA_DICTIONARY.read_text(encoding="utf-8")

    assert {dimension_id for dimension_id, dimension in dimensions.items() if dimension.values} == {
        "generation.distributed",
        "customer.consumption_class",
    }
    assert [value.value for value in dimensions["generation.distributed"].values] == [
        "Sim",
        "Não",
    ]
    for value in dimensions["customer.consumption_class"].values:
        assert f"`{value.value}`" in documented, value.value


def test_metrics_of_unavailable_capabilities_are_not_in_the_profile() -> None:
    unavailable = {item.capability_id for item in GRID360_GOLD_MAPPING.unavailable}
    approved = {
        requirement.id
        for requirement in CAPABILITY_REQUIREMENTS
        if requirement.definition_approved and not requirement.source_not_in_gold
    }
    used = {
        source.capability_id for metric in GRID360_GOLD_MAPPING.metrics for source in metric.sources
    }

    assert (
        used
        == approved
        == {
            "faturamento.receita",
            "faturamento.receita_bairro",
            "consumo.mensal_uc",
            "interrupcoes.dec_fec",
        }
    )
    assert unavailable == {requirement.id for requirement in CAPABILITY_REQUIREMENTS} - approved
    assert {domain.id for domain in GRID360_GOLD_PROFILE.domains} == {
        "revenue",
        "consumption",
        "network",
    }
    interpreter = QuestionInterpreter(profile=GRID360_GOLD_PROFILE)
    for question in (
        "Quantos chamados tivemos no último trimestre?",
        "Quais faturas estão em aberto no mês passado?",
        "Qual o número do medidor no último ano?",
    ):
        result = interpreter.interpret(question)
        assert result.status is InterpretationStatus.NEEDS_CLARIFICATION, question
        assert result.intent is None, question


# --- núcleo composto ----------------------------------------------------------------------


class RecordingSource:
    def __init__(self) -> None:
        self.plans = []
        self._inner = SyntheticScenarioTool()

    async def retrieve(self, plan, access_context):
        self.plans.append(plan)
        return await self._inner.retrieve(plan, access_context)


def _ask(question: str):
    source = RecordingSource()
    core = compose_core(
        profile=GRID360_GOLD_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        evidence_source=source,
        model_adapter=FakeModelAdapter(),
        execution_controller=ExecutionController(),
    )
    response = asyncio.run(
        core.question.answer(
            QuestionRequest(question=question),
            demo_access_context(GRID360_GOLD_PROFILE, CORRELATION_ID),
        )
    )
    return response, source.plans


@pytest.mark.parametrize(
    ("question", "metric_id", "unit", "period", "filters"),
    [
        (
            "Qual foi a receita no último trimestre?",
            "billing.revenue",
            "R$",
            "último trimestre",
            {},
        ),
        (
            "Qual foi a receita residencial no último trimestre?",
            "billing.revenue",
            "R$",
            "último trimestre",
            {"customer.consumption_class": ("RESIDENCIAL",)},
        ),
        (
            "Qual foi o consumo nos últimos 12 meses?",
            "energy.consumption",
            "kWh",
            "últimos 12 meses",
            {},
        ),
        (
            "Qual foi o DEC no mês passado?",
            "network.equivalent_interruption_duration",
            "horas por UC",
            "mês passado",
            {},
        ),
    ],
)
def test_simple_questions_become_the_expected_logical_plan(
    question, metric_id, unit, period, filters
) -> None:
    response, plans = _ask(question)

    assert len(plans) == 1
    plan = plans[0]
    assert plan.profile_id == GOLD_PROFILE_ID
    assert plan.metric_id == metric_id
    assert plan.unit == unit
    assert plan.window.kind is WindowKind.CATALOG_PHRASE
    assert plan.window.phrase == period
    assert {item.dimension_id: item.values for item in plan.filters} == filters
    assert response.status == "no_evidence"


def test_dec_plan_without_feeder_has_no_physical_source_in_the_mapping() -> None:
    """O plano lógico é aprovado, mas DEC só é lido com alimentador fixado."""

    from app.profiles.grid360_gold_mapping_v1 import select_source

    _response, plans = _ask("Qual foi o DEC no mês passado?")
    approved = {
        source.capability_id for metric in GRID360_GOLD_MAPPING.metrics for source in metric.sources
    }

    dec = GRID360_GOLD_MAPPING.metric(plans[0].metric_id)
    assert select_source(dec, set(plans[0].dimension_ids), approved) is None
    assert select_source(dec, {"network.feeder"}, approved).table.value == "indicadores_dec_fec"


@pytest.mark.parametrize(
    "question",
    ["Houve falta de luz no mês passado?", "Quanto foi a conta de luz no último trimestre?"],
)
def test_ambiguous_question_asks_for_clarification_without_reading_the_source(question) -> None:
    response, plans = _ask(question)

    assert response.status == "needs_clarification"
    assert plans == []
