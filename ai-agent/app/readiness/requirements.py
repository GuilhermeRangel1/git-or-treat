"""Declaração estática do que cada capacidade exige da Gold; dados, não regra de avaliação.

Fontes: docs/dicionario_gold.md (tabelas e colunas) e docs/gold-coverage-v0.md (perguntas,
pendências de Dados e controles C01 a C13). `min_consecutive_months` fica None onde não há
janela mínima documentada; a avaliação ainda exige competências sem lacuna.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.readiness.models import ControlId, GoldTable
from app.schemas.analysis import LogicalIdentifier


class CaseDomain(StrEnum):
    """Domínios obrigatórios do case (IA-01); `apoio` reúne as capacidades complementares."""

    CONSUMO = "consumo"
    FATURAMENTO = "faturamento"
    INTERRUPCOES = "interrupcoes"
    ATENDIMENTO = "atendimento"
    APOIO = "apoio"


# Controles definidos na seção (g) de docs/gold-coverage-v0.md.
DOCUMENTED_CONTROLS: frozenset[str] = frozenset(f"C{number:02d}" for number in range(1, 14))

# Tabelas que têm a coluna `competencia` no dicionário Gold.
TABLES_WITH_COMPETENCIA: frozenset[GoldTable] = frozenset(
    {
        GoldTable.DIAGNOSTICO_RECEITA,
        GoldTable.INDICADORES_DEC_FEC,
        GoldTable.CONSUMO_RECEITA_BAIRRO,
        GoldTable.CONSUMO_MENSAL_UC,
    }
)


class CapabilityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: LogicalIdentifier
    domain: CaseDomain
    tables: tuple[GoldTable, ...] = ()
    temporal_column: Literal["competencia"] | None = None
    min_consecutive_months: int | None = Field(default=None, ge=1)
    required_controls: tuple[ControlId, ...] = ()
    definition_approved: bool
    source_not_in_gold: bool = False

    @model_validator(mode="after")
    def validate_declaration(self) -> Self:
        if self.source_not_in_gold:
            if self.tables or self.temporal_column or self.required_controls:
                raise ValueError("fonte fora da Gold não declara tabela, período nem controle")
        elif not self.tables:
            raise ValueError("capacidade da Gold exige ao menos uma tabela")
        if len(set(self.tables)) != len(self.tables):
            raise ValueError("tabela duplicada na capacidade")
        if self.temporal_column is not None and not set(self.tables) <= TABLES_WITH_COMPETENCIA:
            raise ValueError("coluna temporal exige tabelas com competência")
        if self.min_consecutive_months is not None and self.temporal_column is None:
            raise ValueError("janela mínima exige coluna temporal")
        if not set(self.required_controls) <= DOCUMENTED_CONTROLS:
            raise ValueError("controle não documentado")
        return self


CAPABILITY_REQUIREMENTS: tuple[CapabilityRequirement, ...] = (
    # P1, P4, P5: receita e energia faturadas por competência, município e classe.
    CapabilityRequirement(
        id="faturamento.receita",
        domain=CaseDomain.FATURAMENTO,
        tables=(GoldTable.DIAGNOSTICO_RECEITA,),
        temporal_column="competencia",
        required_controls=("C01", "C02", "C04"),
        definition_approved=True,
    ),
    # P3: recorte por bairro; C12 reconcilia com o diagnóstico e C13 detecta bairro duplicado.
    CapabilityRequirement(
        id="faturamento.receita_bairro",
        domain=CaseDomain.FATURAMENTO,
        tables=(GoldTable.CONSUMO_RECEITA_BAIRRO,),
        temporal_column="competencia",
        required_controls=("C12", "C13"),
        definition_approved=True,
    ),
    # P2: falta tarifa homologada e método de decomposição preço × volume aprovado (PRD §8).
    CapabilityRequirement(
        id="faturamento.preco_volume",
        domain=CaseDomain.FATURAMENTO,
        tables=(GoldTable.DIAGNOSTICO_RECEITA,),
        temporal_column="competencia",
        required_controls=("C01", "C02"),
        definition_approved=False,
    ),
    # P8: nenhuma tabela traz status de fatura, vencimento ou pagamento.
    CapabilityRequirement(
        id="faturamento.faturas_em_aberto",
        domain=CaseDomain.FATURAMENTO,
        definition_approved=False,
        source_not_in_gold=True,
    ),
    # P7, P20: série mensal por UC (valor faturado, não pago).
    CapabilityRequirement(
        id="consumo.mensal_uc",
        domain=CaseDomain.CONSUMO,
        tables=(GoldTable.CONSUMO_MENSAL_UC,),
        temporal_column="competencia",
        required_controls=("C03", "C10"),
        definition_approved=True,
    ),
    # P6: janelas P1/P2 fixas; janela e mínimo de meses da pergunta ainda abertos com Dados.
    CapabilityRequirement(
        id="consumo.variacao_uc",
        domain=CaseDomain.CONSUMO,
        tables=(GoldTable.VARIACAO_CONSUMO_UC,),
        required_controls=("C08", "C09"),
        definition_approved=False,
    ),
    # P16, P17, P21: DEC/FEC simplificados por alimentador e mês.
    CapabilityRequirement(
        id="interrupcoes.dec_fec",
        domain=CaseDomain.INTERRUPCOES,
        tables=(GoldTable.INDICADORES_DEC_FEC,),
        temporal_column="competencia",
        required_controls=("C11",),
        definition_approved=True,
    ),
    # P10: só total acumulado por UC, sem mês; sem controle independente do domínio.
    CapabilityRequirement(
        id="interrupcoes.uc_acumulado",
        domain=CaseDomain.INTERRUPCOES,
        tables=(GoldTable.VISAO_360_UC,),
        definition_approved=False,
    ),
    # P11: chamados e satisfação só como totais por UC, sem mês nem motivo; sem controle.
    CapabilityRequirement(
        id="atendimento.uc_acumulado",
        domain=CaseDomain.ATENDIMENTO,
        tables=(GoldTable.VISAO_360_UC,),
        definition_approved=False,
    ),
    # P14: mapeamento dos rótulos de inspeção da Silver pendente (issue #39).
    CapabilityRequirement(
        id="apoio.fila_inspecao",
        domain=CaseDomain.APOIO,
        tables=(GoldTable.FILA_INSPECAO,),
        required_controls=("C06", "C07"),
        definition_approved=False,
    ),
    # P9: nenhuma tabela de medidor.
    CapabilityRequirement(
        id="apoio.medidor_uc",
        domain=CaseDomain.APOIO,
        definition_approved=False,
        source_not_in_gold=True,
    ),
    # P15: nenhuma estimativa de energia recuperável.
    CapabilityRequirement(
        id="apoio.energia_recuperavel",
        domain=CaseDomain.APOIO,
        definition_approved=False,
        source_not_in_gold=True,
    ),
)
