"""Mapeamento físico versionado do catálogo Gold: id lógico -> tabela, coluna e fórmula.

Usado pelo executor do Backend no futuro; o núcleo (interpretação e planejamento) só conhece
``GRID360_GOLD_PROFILE``. Não importa a camada SQL de execução: a validação recebe o dicionário
como ``DictionarySchema``, montado por quem chama a partir de ``dictionary_gold.toml``.

A referência atual é o schema físico `gold_v2` do Backend, com quinze tabelas e
colunas `DEC`/`FEC` preservadas. O dicionário SQL v1 do PR #46 é legado e não valida
esta versão. Este módulo não executa SQL e não é importado pelo planejador lógico.

Regras fixas:
- uma consulta usa uma única fonte: a primeira de ``sources`` cujas dimensões cobrem a consulta
  e cuja capacidade está disponível; nunca soma duas tabelas nem junta fatos de tabelas;
- ``sum`` soma a medida no recorte; ``ratio_of_sums`` divide a soma do numerador pela soma do
  denominador no mesmo recorte e nunca soma nem tira média de razões já calculadas;
- ``key_grain_read`` (DEC/FEC) só lê linhas no grão da chave, com alimentador fixado, sem
  agregar entre alimentadores nem entre meses.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.readiness import V2_CAPABILITY_REQUIREMENTS, CapabilityRequirement, GoldTable, ReasonCode
from app.readiness.models import ReadinessVersion
from app.schemas.analysis import LogicalIdentifier
from app.schemas.domain_profile import DomainProfile, UnitKind

MAPPING_VERSION = "gold-catalog-v2"
# Versão do contrato físico Backend; validada contra suas tabelas em processo separado.
DICTIONARY_VERSION = "gold-csv-v2"

PhysicalColumn = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
OpenPoint = Annotated[str, StringConstraints(min_length=1, max_length=300)]

_NUMERIC_TYPES = {"bigint": "bigint", "double": "double", "decimal": "decimal"}


class CatalogMappingError(ValueError):
    """O mapeamento contradiz o perfil, a prontidão ou o dicionário Gold."""


class Aggregation(StrEnum):
    SUM = "sum"
    RATIO_OF_SUMS = "ratio_of_sums"
    KEY_GRAIN_READ = "key_grain_read"


class ColumnType(StrEnum):
    """Família do tipo no dicionário; ``decimal`` cobre ``decimal(p,s)``."""

    BIGINT = "bigint"
    DOUBLE = "double"
    DECIMAL = "decimal"


class NullRule(StrEnum):
    # Nulo é ausência: a soma ignora nulos e, sem nenhum valor, o resultado é ausente (sem
    # evidência), nunca zero.
    SUM_IGNORES_NULL_ALL_NULL_IS_ABSENT = "sum_ignores_null_all_null_is_absent"
    # Numerador ou denominador ausente, ou denominador zero: resultado ausente.
    RATIO_ABSENT_ON_NULL_OR_ZERO_DENOMINATOR = "ratio_absent_on_null_or_zero_denominator"
    # Linha ausente não vira zero; valor nulo na linha é ausência.
    READ_NULL_IS_ABSENT = "read_null_is_absent"


class Rounding(BaseModel):
    """Arredondamento só na apresentação, depois do cálculo; proposta a confirmar com Dados."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decimals: int = Field(ge=0, le=6)
    mode: Literal["half_even"] = "half_even"


class SourceMapping(BaseModel):
    """Uma tabela candidata para a métrica, sempre lida sozinha."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: LogicalIdentifier
    table: GoldTable
    temporal_column: PhysicalColumn | None
    grain: tuple[PhysicalColumn, ...] = Field(min_length=1)
    measure_column: PhysicalColumn | None = None
    numerator_column: PhysicalColumn | None = None
    denominator_column: PhysicalColumn | None = None
    nullable_columns: tuple[PhysicalColumn, ...] = ()
    dimension_columns: dict[LogicalIdentifier, PhysicalColumn] = Field(default_factory=dict)

    def measure_columns(self) -> tuple[str, ...]:
        return tuple(
            column
            for column in (self.measure_column, self.numerator_column, self.denominator_column)
            if column is not None
        )

    def referenced_columns(self) -> set[str]:
        columns = {*self.grain, *self.measure_columns(), *self.dimension_columns.values()}
        if self.temporal_column is not None:
            columns.add(self.temporal_column)
        return columns


class MetricMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: LogicalIdentifier
    # Capacidade da fonte padrão (a primeira); cada fonte declara a sua.
    capability_id: LogicalIdentifier
    required_capability_ids: tuple[LogicalIdentifier, ...] = Field(min_length=1)
    aggregation: Aggregation
    unit: str = Field(min_length=1, max_length=200)
    unit_kind: UnitKind
    measure_type: ColumnType | None = None
    numerator_type: ColumnType | None = None
    denominator_type: ColumnType | None = None
    rounding: Rounding
    null_rule: NullRule
    # Dimensões que a consulta precisa fixar (DEC/FEC: alimentador).
    required_dimension_ids: tuple[LogicalIdentifier, ...] = ()
    sources: tuple[SourceMapping, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        ratio = self.aggregation is Aggregation.RATIO_OF_SUMS
        for source in self.sources:
            has_measure = source.measure_column is not None
            has_ratio = (source.numerator_column, source.denominator_column) != (None, None)
            if ratio != has_ratio or ratio == has_measure:
                raise ValueError(f"{self.metric_id}: fonte não combina com a agregação")
            if ratio and None in (source.numerator_column, source.denominator_column):
                raise ValueError(f"{self.metric_id}: razão exige numerador e denominador")
            if not set(self.required_dimension_ids) <= set(source.dimension_columns):
                raise ValueError(f"{self.metric_id}: fonte sem dimensão obrigatória")
        if ratio != (self.numerator_type is not None and self.denominator_type is not None):
            raise ValueError(f"{self.metric_id}: razão declara tipos do numerador e denominador")
        if ratio == (self.measure_type is not None):
            raise ValueError(f"{self.metric_id}: tipo da medida incompatível com a agregação")
        expected_null = {
            Aggregation.SUM: NullRule.SUM_IGNORES_NULL_ALL_NULL_IS_ABSENT,
            Aggregation.RATIO_OF_SUMS: NullRule.RATIO_ABSENT_ON_NULL_OR_ZERO_DENOMINATOR,
            Aggregation.KEY_GRAIN_READ: NullRule.READ_NULL_IS_ABSENT,
        }[self.aggregation]
        if self.null_rule is not expected_null:
            raise ValueError(f"{self.metric_id}: regra de nulidade incompatível")
        if self.sources[0].capability_id != self.capability_id:
            raise ValueError(f"{self.metric_id}: capacidade difere da fonte padrão")
        if len({source.table for source in self.sources}) != len(self.sources):
            raise ValueError(f"{self.metric_id}: tabela repetida entre as fontes")
        return self

    def dimension_ids(self) -> set[str]:
        return {dimension for source in self.sources for dimension in source.dimension_columns}


class UnavailableCapability(BaseModel):
    """Capacidade fora do catálogo, com o motivo estático da prontidão."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: LogicalIdentifier
    reasons: tuple[ReasonCode, ...] = Field(min_length=1)
    note: str = Field(min_length=1, max_length=300)


class GoldCatalogMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_version: Literal["gold-catalog-v2"] = MAPPING_VERSION
    physical_schema: Literal["gold_v2"] = "gold_v2"
    profile_id: LogicalIdentifier
    dictionary_version: str = Field(min_length=1, max_length=100)
    readiness_version: ReadinessVersion = "gold-readiness-v2"
    metrics: tuple[MetricMapping, ...] = Field(min_length=1)
    unavailable: tuple[UnavailableCapability, ...] = ()
    open_points: tuple[OpenPoint, ...] = ()

    @model_validator(mode="after")
    def validate_unique(self) -> Self:
        metric_ids = [metric.metric_id for metric in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("métrica duplicada no mapeamento")
        unavailable = [item.capability_id for item in self.unavailable]
        if len(unavailable) != len(set(unavailable)):
            raise ValueError("capacidade indisponível duplicada")
        return self

    def metric(self, metric_id: str) -> MetricMapping:
        return next(item for item in self.metrics if item.metric_id == metric_id)


class DictionaryTable(BaseModel):
    """O que a validação precisa de ``[tables.<nome>]`` do dicionário Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    columns: dict[str, str]
    key: tuple[str, ...]
    period_column: str | None = None


class DictionarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    tables: dict[str, DictionaryTable]
    sensitive_columns: frozenset[str]


def select_source(
    metric: MetricMapping,
    dimension_ids: set[str] | frozenset[str],
    available_capabilities: set[str] | frozenset[str],
) -> SourceMapping | None:
    """Única fonte para a consulta: a primeira que cobre as dimensões e está disponível.

    ``None`` quando nenhuma fonte serve ou falta dimensão obrigatória; nunca combina fontes.
    """

    if not set(metric.required_capability_ids) <= set(available_capabilities):
        return None
    if not set(metric.required_dimension_ids) <= set(dimension_ids):
        return None
    return next(
        (
            source
            for source in metric.sources
            if set(dimension_ids) <= set(source.dimension_columns)
            and source.capability_id in available_capabilities
        ),
        None,
    )


def validate_mapping(
    mapping: GoldCatalogMapping,
    *,
    profile: DomainProfile,
    dictionary: DictionarySchema,
    requirements: tuple[CapabilityRequirement, ...] = V2_CAPABILITY_REQUIREMENTS,
) -> None:
    """Falha com ``CatalogMappingError`` em qualquer divergência; nunca aprova em silêncio."""

    errors: list[str] = []
    if mapping.readiness_version != "gold-readiness-v2":
        errors.append("catálogo v2 exige prontidão v2")
    capabilities = {requirement.id: requirement for requirement in requirements}
    if mapping.profile_id != profile.profile_id:
        errors.append("perfil do mapeamento difere do perfil lógico")
    if mapping.dictionary_version != dictionary.version:
        errors.append(
            f"versão do dicionário {dictionary.version!r} difere de {mapping.dictionary_version!r}"
        )
    profile_metrics = {metric.id: metric for metric in profile.metrics}
    mapped = {metric.metric_id for metric in mapping.metrics}
    for missing in sorted(set(profile_metrics) - mapped):
        errors.append(f"{missing}: métrica do perfil sem mapeamento")
    for extra in sorted(mapped - set(profile_metrics)):
        errors.append(f"{extra}: mapeamento sem métrica no perfil")

    used_capabilities: set[str] = set()
    for metric in mapping.metrics:
        for dependency in metric.required_capability_ids:
            requirement = capabilities.get(dependency)
            if (
                requirement is None
                or requirement.source_not_in_gold
                or not requirement.definition_approved
            ):
                errors.append(
                    f"{metric.metric_id}: dependência {dependency} inexistente ou não aprovada"
                )
        logical = profile_metrics.get(metric.metric_id)
        if logical is not None:
            if logical.unit != metric.unit:
                errors.append(f"{metric.metric_id}: unidade difere do perfil")
            if metric.dimension_ids() != set(logical.dimension_ids):
                errors.append(f"{metric.metric_id}: dimensões diferem das sustentadas pelas fontes")
        for source in metric.sources:
            used_capabilities.add(source.capability_id)
            errors.extend(_source_errors(metric, source, capabilities, dictionary))

    declared_unavailable = {item.capability_id: item for item in mapping.unavailable}
    for capability_id in sorted(used_capabilities & set(declared_unavailable)):
        errors.append(f"{capability_id}: capacidade usada e declarada indisponível")
    for requirement in requirements:
        if requirement.id in used_capabilities:
            continue
        expected = _static_reasons(requirement)
        declared = declared_unavailable.get(requirement.id)
        if declared is None:
            errors.append(f"{requirement.id}: capacidade sem métrica nem motivo de indisponível")
        elif expected and set(declared.reasons) != set(expected):
            errors.append(f"{requirement.id}: motivo difere da prontidão")
    for capability_id in sorted(set(declared_unavailable) - set(capabilities)):
        errors.append(f"{capability_id}: capacidade indisponível inexistente na prontidão")
    if errors:
        raise CatalogMappingError("; ".join(errors))


def _static_reasons(requirement: CapabilityRequirement) -> tuple[ReasonCode, ...]:
    reasons = []
    if not requirement.definition_approved:
        reasons.append(ReasonCode.DEFINITION_PENDING)
    if requirement.source_not_in_gold:
        reasons.append(ReasonCode.SOURCE_NOT_IN_GOLD)
    return tuple(reasons)


def _source_errors(
    metric: MetricMapping,
    source: SourceMapping,
    capabilities: dict[str, CapabilityRequirement],
    dictionary: DictionarySchema,
) -> list[str]:
    where = f"{metric.metric_id}/{source.table.value}"
    errors: list[str] = []
    requirement = capabilities.get(source.capability_id)
    if requirement is None:
        errors.append(f"{where}: capacidade {source.capability_id} inexistente na prontidão")
    elif requirement.source_not_in_gold or not requirement.definition_approved:
        errors.append(f"{where}: capacidade {source.capability_id} não está aprovada")
    elif source.table not in requirement.tables:
        errors.append(f"{where}: tabela fora das tabelas da capacidade {source.capability_id}")
    elif requirement.temporal_column != source.temporal_column:
        errors.append(f"{where}: coluna temporal difere da prontidão")

    table = dictionary.tables.get(source.table.value)
    if table is None:
        return [*errors, f"{where}: tabela ausente do dicionário"]
    for column in sorted(source.referenced_columns() | set(source.nullable_columns)):
        if column not in table.columns:
            errors.append(f"{where}: coluna {column} ausente do dicionário")
        elif column in dictionary.sensitive_columns:
            errors.append(f"{where}: coluna {column} é sensível")
    if tuple(source.grain) != tuple(table.key):
        errors.append(f"{where}: grão difere da chave do dicionário")
    if source.temporal_column != table.period_column:
        errors.append(f"{where}: coluna temporal difere do period_column do dicionário")
    expected_types = (
        ((source.measure_column, metric.measure_type),)
        if metric.aggregation is not Aggregation.RATIO_OF_SUMS
        else (
            (source.numerator_column, metric.numerator_type),
            (source.denominator_column, metric.denominator_type),
        )
    )
    for column, expected in expected_types:
        actual = table.columns.get(column or "")
        if actual is None or expected is None:
            continue
        family = _NUMERIC_TYPES.get(actual.split("(", 1)[0].strip().casefold())
        if family != expected.value:
            errors.append(f"{where}: coluna {column} tem tipo {actual}, esperado {expected.value}")
    if (
        metric.aggregation is Aggregation.SUM
        and metric.measure_type is not None
        and _SUM_TYPE_BY_KIND.get(metric.unit_kind) != metric.measure_type
    ):
        errors.append(f"{where}: tipo da medida incompatível com a unidade")
    return errors


_SUM_TYPE_BY_KIND = {
    UnitKind.CURRENCY: ColumnType.DECIMAL,
    UnitKind.ENERGY: ColumnType.DOUBLE,
    UnitKind.COUNT: ColumnType.BIGINT,
}

# --- Mapeamento v2 -----------------------------------------------------------------------

_DIAGNOSTICO_DIMENSIONS = {
    "geography.municipality": "municipio",
    "customer.consumption_class": "classe_consumo",
    "tariff.subgroup": "subgrupo_tarifario",
    "tariff.flag": "bandeira_tarifaria",
    "generation.distributed": "possui_gd",
}
_BAIRRO_DIMENSIONS = {
    "geography.municipality": "municipio",
    "geography.neighborhood": "bairro",
    "customer.consumption_class": "classe_consumo",
}
_MENSAL_DIMENSIONS = {"customer.consumer_unit": "id_uc"}
_DIAGNOSTICO_GRAIN = (
    "competencia",
    "municipio",
    "classe_consumo",
    "subgrupo_tarifario",
    "bandeira_tarifaria",
    "possui_gd",
)
_BAIRRO_GRAIN = ("competencia", "municipio", "bairro", "classe_consumo")
_MENSAL_GRAIN = ("id_uc", "competencia")


def _diagnostico(**columns: str) -> SourceMapping:
    return SourceMapping(
        capability_id="faturamento.receita",
        table=GoldTable.DIAGNOSTICO_RECEITA,
        temporal_column="competencia",
        grain=_DIAGNOSTICO_GRAIN,
        nullable_columns=tuple(columns.values()),
        dimension_columns=_DIAGNOSTICO_DIMENSIONS,
        **columns,
    )


def _bairro(**columns: str) -> SourceMapping:
    return SourceMapping(
        capability_id="faturamento.receita_bairro",
        table=GoldTable.CONSUMO_RECEITA_BAIRRO,
        temporal_column="competencia",
        grain=_BAIRRO_GRAIN,
        nullable_columns=tuple(columns.values()),
        dimension_columns=_BAIRRO_DIMENSIONS,
        **columns,
    )


def _mensal(**columns: str) -> SourceMapping:
    return SourceMapping(
        capability_id="consumo.mensal_uc",
        table=GoldTable.CONSUMO_MENSAL_UC,
        temporal_column="competencia",
        grain=_MENSAL_GRAIN,
        nullable_columns=tuple(columns.values()),
        dimension_columns=_MENSAL_DIMENSIONS,
        **columns,
    )


def _dec_fec(column: str) -> SourceMapping:
    return SourceMapping(
        capability_id="interrupcoes.dec_fec",
        table=GoldTable.INDICADORES_DEC_FEC,
        temporal_column="competencia",
        grain=("id_alimentador", "competencia"),
        measure_column=column,
        nullable_columns=(column,),
        dimension_columns={
            "network.feeder": "id_alimentador",
            "geography.municipality": "municipio",
        },
    )


_SUM_NULLS = NullRule.SUM_IGNORES_NULL_ALL_NULL_IS_ABSENT
_RATIO_NULLS = NullRule.RATIO_ABSENT_ON_NULL_OR_ZERO_DENOMINATOR

GRID360_GOLD_MAPPING = GoldCatalogMapping(
    profile_id="v-energy-grid-360-gold",
    dictionary_version=DICTIONARY_VERSION,
    metrics=(
        MetricMapping(
            metric_id="billing.revenue",
            required_capability_ids=("faturamento.receita",),
            capability_id="faturamento.receita",
            aggregation=Aggregation.SUM,
            unit="R$",
            unit_kind=UnitKind.CURRENCY,
            measure_type=ColumnType.DECIMAL,
            rounding=Rounding(decimals=2),
            null_rule=_SUM_NULLS,
            sources=(
                _diagnostico(measure_column="receita_total_reais"),
                _bairro(measure_column="receita_total_reais"),
                _mensal(measure_column="receita_reais"),
            ),
        ),
        MetricMapping(
            metric_id="energy.consumption",
            required_capability_ids=("consumo.mensal_uc",),
            capability_id="faturamento.receita",
            aggregation=Aggregation.SUM,
            unit="kWh",
            unit_kind=UnitKind.ENERGY,
            measure_type=ColumnType.DOUBLE,
            rounding=Rounding(decimals=2),
            null_rule=_SUM_NULLS,
            sources=(
                _diagnostico(measure_column="consumo_total_kwh"),
                _bairro(measure_column="consumo_total_kwh"),
                _mensal(measure_column="consumo_kwh"),
            ),
        ),
        MetricMapping(
            metric_id="billing.average_ticket",
            required_capability_ids=("faturamento.receita",),
            capability_id="faturamento.receita",
            aggregation=Aggregation.RATIO_OF_SUMS,
            unit="R$ por UC faturada no mês",
            unit_kind=UnitKind.CURRENCY,
            numerator_type=ColumnType.DECIMAL,
            denominator_type=ColumnType.BIGINT,
            rounding=Rounding(decimals=2),
            null_rule=_RATIO_NULLS,
            sources=(
                _diagnostico(
                    numerator_column="receita_total_reais",
                    denominator_column="qtd_ucs_distintas_faturadas_no_mes",
                ),
                _bairro(
                    numerator_column="receita_total_reais",
                    denominator_column="qtd_ucs_distintas_faturadas_no_mes",
                ),
            ),
        ),
        MetricMapping(
            metric_id="billing.effective_tariff",
            required_capability_ids=("faturamento.receita", "consumo.mensal_uc"),
            capability_id="faturamento.receita",
            aggregation=Aggregation.RATIO_OF_SUMS,
            unit="R$/kWh",
            unit_kind=UnitKind.CURRENCY,
            numerator_type=ColumnType.DECIMAL,
            denominator_type=ColumnType.DOUBLE,
            rounding=Rounding(decimals=4),
            null_rule=_RATIO_NULLS,
            sources=(
                _diagnostico(
                    numerator_column="receita_base_comparavel_reais",
                    denominator_column="consumo_base_comparavel_kwh",
                ),
                _bairro(
                    numerator_column="receita_base_comparavel_reais",
                    denominator_column="consumo_base_comparavel_kwh",
                ),
                _mensal(
                    numerator_column="receita_base_comparavel_reais",
                    denominator_column="consumo_base_comparavel_kwh",
                ),
            ),
        ),
        MetricMapping(
            metric_id="energy.average_consumption_per_uc",
            required_capability_ids=("consumo.mensal_uc",),
            capability_id="faturamento.receita",
            aggregation=Aggregation.RATIO_OF_SUMS,
            unit="kWh por UC com leitura no mês",
            unit_kind=UnitKind.ENERGY,
            numerator_type=ColumnType.DOUBLE,
            denominator_type=ColumnType.BIGINT,
            rounding=Rounding(decimals=2),
            null_rule=_RATIO_NULLS,
            sources=(
                _diagnostico(
                    numerator_column="consumo_total_kwh",
                    denominator_column="qtd_ucs_com_leitura",
                ),
                _bairro(
                    numerator_column="consumo_total_kwh",
                    denominator_column="qtd_ucs_com_leitura",
                ),
            ),
        ),
        MetricMapping(
            metric_id="network.equivalent_interruption_duration",
            required_capability_ids=("interrupcoes.dec_fec",),
            capability_id="interrupcoes.dec_fec",
            aggregation=Aggregation.KEY_GRAIN_READ,
            unit="horas por UC",
            unit_kind=UnitKind.TIME,
            measure_type=ColumnType.DOUBLE,
            rounding=Rounding(decimals=2),
            null_rule=NullRule.READ_NULL_IS_ABSENT,
            required_dimension_ids=("network.feeder",),
            sources=(_dec_fec("DEC"),),
        ),
        MetricMapping(
            metric_id="network.equivalent_interruption_frequency",
            required_capability_ids=("interrupcoes.dec_fec",),
            capability_id="interrupcoes.dec_fec",
            aggregation=Aggregation.KEY_GRAIN_READ,
            unit="interrupções por UC",
            unit_kind=UnitKind.COUNT,
            measure_type=ColumnType.DOUBLE,
            rounding=Rounding(decimals=2),
            null_rule=NullRule.READ_NULL_IS_ABSENT,
            required_dimension_ids=("network.feeder",),
            sources=(_dec_fec("FEC"),),
        ),
    ),
    unavailable=(
        UnavailableCapability(
            capability_id="atendimento.mensal",
            reasons=(ReasonCode.CONTROL_PENDING,),
            note="Fonte e controles C14/C15 disponíveis; mapeamento do domínio em adaptação v2.",
        ),
        UnavailableCapability(
            capability_id="faturamento.preco_volume",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note="Falta tarifa homologada e método aprovado de decomposição preço × volume.",
        ),
        UnavailableCapability(
            capability_id="faturamento.faturas_em_aberto",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note=(
                "Fonte faturas_uc disponível; semântica/controles consumidores "
                "não liberam saldo contábil."
            ),
        ),
        UnavailableCapability(
            capability_id="consumo.variacao_uc",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note="Janela e mínimo de meses da pergunta abertos com Dados; P1/P2 fixos na Gold.",
        ),
        UnavailableCapability(
            capability_id="interrupcoes.uc_acumulado",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note="Só total acumulado por UC, sem mês e sem controle independente.",
        ),
        UnavailableCapability(
            capability_id="atendimento.uc_acumulado",
            reasons=(ReasonCode.CONTROL_PENDING,),
            note=(
                "Fonte e C14 disponíveis; métrica acumulada exige mapeamento próprio "
                "sem período inventado."
            ),
        ),
        UnavailableCapability(
            capability_id="apoio.fila_inspecao",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note="Mapeamento dos rótulos de resultado de inspeção pendente (issue #39).",
        ),
        UnavailableCapability(
            capability_id="apoio.medidor_uc",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note=(
                "Fonte medidor_uc disponível; seleção e interpretação exigem "
                "controles consumidores."
            ),
        ),
        UnavailableCapability(
            capability_id="apoio.energia_recuperavel",
            reasons=(ReasonCode.DEFINITION_PENDING,),
            note="Referência histórica disponível na fila; não é estimativa individual da UC.",
        ),
    ),
    open_points=(),
)
