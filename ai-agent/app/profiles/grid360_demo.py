"""Vocabulário e catálogo demonstrativos do Grid 360; não representam a Gold oficial."""

from app.schemas.domain_profile import (
    AmbiguityRule,
    CatalogGranularity,
    CatalogOperation,
    CatalogSensitivity,
    ClarificationMessages,
    DimensionDefinition,
    DimensionRole,
    DimensionValue,
    DomainDefinition,
    DomainProfile,
    FilterOperator,
    FilterValueType,
    MetricDefinition,
)

_GEOGRAPHY = DimensionDefinition(
    id="geography.municipality",
    label="Município",
    role=DimensionRole.GEOGRAPHY,
    aliases=("município", "municípios", "cidade", "cidades"),
    value_type=FilterValueType.STRING,
    operators=(FilterOperator.EQ, FilterOperator.IN),
    sensitivity=CatalogSensitivity.INTERNAL,
    values=(
        DimensionValue(
            value="Jaboatão dos Guararapes", aliases=("Jaboatão dos Guararapes", "Jaboatão")
        ),
        DimensionValue(value="Olinda", aliases=("Olinda",)),
    ),
)

_CUSTOMER_CLASS = DimensionDefinition(
    id="customer.consumption_class",
    label="Classe de consumo",
    role=DimensionRole.CLASSIFICATION,
    aliases=("classe", "classe de consumo"),
    value_type=FilterValueType.STRING,
    operators=(FilterOperator.EQ, FilterOperator.IN),
    sensitivity=CatalogSensitivity.INTERNAL,
    values=(
        DimensionValue(value="residencial", aliases=("residencial",)),
        DimensionValue(value="comercial", aliases=("comercial",)),
        DimensionValue(value="industrial", aliases=("industrial",)),
        DimensionValue(value="poder público", aliases=("poder público",)),
    ),
)

_ALL_DIMENSIONS = (_GEOGRAPHY.id, _CUSTOMER_CLASS.id)
_MONTH_YEAR = (CatalogGranularity.MONTH, CatalogGranularity.YEAR)

GRID360_DEMO_PROFILE = DomainProfile(
    profile_id="v-energy-grid-360-demo",
    domains=(
        DomainDefinition(
            id="revenue",
            label="Faturamento e receita",
            example_questions=("Quanto cresceu a receita comercial?",),
        ),
        DomainDefinition(
            id="consumption",
            label="Consumo e medição",
            example_questions=("Quais UCs tiveram queda de consumo?",),
        ),
        DomainDefinition(
            id="network",
            label="Interrupções de rede",
            example_questions=("Houve falta de luz no período?",),
        ),
        DomainDefinition(
            id="service",
            label="Atendimento",
            example_questions=("Quantos chamados foram registrados?",),
        ),
    ),
    metrics=(
        MetricDefinition(
            id="billing.revenue",
            domain_id="revenue",
            aliases=("faturamento", "receita"),
            unit="unidades fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
        ),
        MetricDefinition(
            id="energy.consumption",
            domain_id="consumption",
            aliases=("queda de consumo", "consumo", "leitura", "leituras"),
            unit="unidades fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
        ),
        MetricDefinition(
            id="network.interruptions",
            domain_id="network",
            aliases=(
                "falta de luz",
                "falta de energia",
                "interrupção de fornecimento",
                "interrupção",
                "interrupções",
            ),
            unit="ocorrências fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
        ),
        MetricDefinition(
            id="service.attendance",
            domain_id="service",
            aliases=("atendimentos", "atendimento", "chamados", "chamado"),
            unit="registros fictícios",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
        ),
    ),
    dimensions=(_GEOGRAPHY, _CUSTOMER_CLASS),
    period_phrases=(
        "período de demonstração",
        "últimos 12 meses",
        "último ano",
        "ano passado",
        "último trimestre",
        "últimos três meses",
        "últimos 3 meses",
        "mês passado",
        "este ano",
        "neste mês",
    ),
    comparison_terms=(
        "compare",
        "comparar",
        "comparação",
        "cresceu",
        "caiu",
        "variação",
        "aumentou",
        "reduziu",
    ),
    correction_terms=("não", "na verdade", "corrigindo"),
    follow_up_starters=("e", "também", "nesse", "neste", "então", "agora"),
    direction_terms=("queda", "redução", "aumento", "subida", "crescimento"),
    ambiguities=(
        AmbiguityRule(
            phrases=("conta de luz",),
            clarification=(
                "Quando você diz ‘conta de luz’, quer saber de consumo, valor faturado, "
                "valor pago ou outro dado da fatura?"
            ),
        ),
    ),
    clarifications=ClarificationMessages(
        missing_metric="Qual indicador ou assunto você quer consultar?",
        multiple_domains=(
            "Você quer consultar qual assunto primeiro: consumo, faturamento, "
            "interrupções ou atendimento?"
        ),
        multiple_metrics="Você quer consultar qual indicador primeiro?",
        unknown_geography=(
            "Não reconheci esse local nas referências disponíveis; confirme a geografia desejada."
        ),
        multiple_geographies="Qual local você quer consultar?",
        multiple_classes="Qual classe de consumo você quer consultar?",
        missing_period="Qual período você quer consultar ou comparar?",
        comparison_baseline="Qual período deve servir de base para essa comparação?",
        multiple_periods="Você mencionou mais de um período; quer compará-los?",
    ),
    operations=(CatalogOperation.READ,),
)
