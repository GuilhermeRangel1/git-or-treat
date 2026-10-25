"""Vocabulário e catálogo demonstrativos do Grid 360; não representam a Gold oficial."""

from app.schemas.domain_profile import (
    AmbiguityRule,
    CatalogGranularity,
    CatalogOperation,
    CatalogSensitivity,
    ClarificationMessages,
    DetailRule,
    DimensionDefinition,
    DimensionRole,
    DimensionValue,
    DomainDefinition,
    DomainProfile,
    EvidenceFieldDefinition,
    EvidenceFieldRole,
    FilterOperator,
    FilterValueType,
    MetricDefinition,
    UnitDefinition,
    UnitKind,
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
_EVIDENCE_FIELDS = (
    EvidenceFieldDefinition(
        name="value",
        role=EvidenceFieldRole.MEASURE,
        value_type=FilterValueType.NUMBER,
        sensitivity=CatalogSensitivity.INTERNAL,
    ),
    EvidenceFieldDefinition(
        name="unit",
        role=EvidenceFieldRole.UNIT,
        value_type=FilterValueType.STRING,
        sensitivity=CatalogSensitivity.INTERNAL,
    ),
)
_REVENUE_EVIDENCE_FIELDS = (
    *_EVIDENCE_FIELDS,
    EvidenceFieldDefinition(
        name="period",
        role=EvidenceFieldRole.PERIOD,
        value_type=FilterValueType.DATE,
        sensitivity=CatalogSensitivity.INTERNAL,
    ),
)

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
            accepted_unit_kinds=(UnitKind.CURRENCY,),
            aliases=("faturamento", "receita", "faturamos", "faturou", "faturaram", "faturei"),
            unit="unidades fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
            evidence_fields=_REVENUE_EVIDENCE_FIELDS,
            limitation_texts=(
                "Períodos e valores inventados; não representam faturamento, receita ou fórmula "
                "oficial da V-Energy.",
            ),
        ),
        MetricDefinition(
            id="energy.consumption",
            domain_id="consumption",
            accepted_unit_kinds=(UnitKind.ENERGY,),
            aliases=("queda de consumo", "consumo", "leitura", "leituras"),
            unit="unidades fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
            evidence_fields=_EVIDENCE_FIELDS,
            limitation_texts=(
                "Valor inventado; não representa leitura, consumo ou unidade consumidora "
                "da V-Energy.",
            ),
        ),
        MetricDefinition(
            id="network.interruptions",
            domain_id="network",
            accepted_unit_kinds=(UnitKind.COUNT,),
            aliases=(
                "falta de luz",
                "faltas de luz",
                "falta de energia",
                "faltas de energia",
                "interrup\u00e7\u00e3o de fornecimento",
                "interrup\u00e7\u00f5es de fornecimento",
                "interrupção",
                "interrupções",
                "apagão",
                "apagões",
                "queda de energia",
                "quedas de energia",
                "queda de luz",
                "quedas de luz",
            ),
            unit="ocorrências fictícias",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
            evidence_fields=_EVIDENCE_FIELDS,
            limitation_texts=(
                "Contagem inventada; não descreve ocorrências de rede nem indicador DEC/FEC real.",
            ),
        ),
        MetricDefinition(
            id="service.attendance",
            domain_id="service",
            accepted_unit_kinds=(UnitKind.COUNT,),
            aliases=(
                "atendimentos",
                "atendimento",
                "chamados",
                "chamado",
                "reclamação",
                "reclamações",
            ),
            unit="atendimento fictício",
            granularities=_MONTH_YEAR,
            dimension_ids=_ALL_DIMENSIONS,
            sensitivity=CatalogSensitivity.INTERNAL,
            evidence_fields=_EVIDENCE_FIELDS,
            limitation_texts=(
                "Contagem inventada; não representa atendimento, satisfação ou chamado "
                "da V-Energy.",
            ),
        ),
    ),
    dimensions=(_GEOGRAPHY, _CUSTOMER_CLASS),
    period_phrases=(
        "período de demonstração",
        "dois períodos de demonstração",
        "comparação demonstrativa",
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
    default_period_phrase="período de demonstração",
    default_period_context_phrases=(
        "cenário de demonstração",
        "cenário sintético",
        "demonstração",
    ),
    comparison_period_phrases=(
        "dois períodos de demonstração",
        "comparação demonstrativa",
    ),
    non_location_phrases=(
        "cen\u00e1rio de demonstra\u00e7\u00e3o",
        "cen\u00e1rio sint\u00e9tico",
        "demonstra\u00e7\u00e3o",
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
    # "receita" sozinha é faturamento e "código" sozinho aparece em "código da UC";
    # "programação" também é usada para desligamentos programados; "algoritmo" e
    # "placar" aparecem em perguntas sobre a fila de inspeção.
    out_of_scope_terms=(
        "capital",
        "clima",
        "previsão do tempo",
        "futebol",
        "cotação",
        "receita de bolo",
        "receita culinária",
        "receita de comida",
        "bolo",
        "jogo do",
        "jogo de futebol",
        "partida de futebol",
        "campeonato",
        "poema",
        "poesia",
        "piada",
        "letra de música",
        "python",
        "javascript",
        "linguagem de programação",
    ),
    ambiguities=(
        AmbiguityRule(
            phrases=("conta de luz",),
            clarification=(
                "Quando você diz ‘conta de luz’, quer saber de consumo, valor faturado, "
                "valor pago ou outro dado da fatura?"
            ),
        ),
    ),
    # Unidades citadas em "em <unidade>". Antes ficavam no interpretador; o tipo indica se a
    # métrica pode ser respondida nela. Potência (kW) não é consumo (kWh).
    units=(
        UnitDefinition(
            id="energy.wh",
            kind=UnitKind.ENERGY,
            aliases=(
                "Wh",
                "kWh",
                "MWh",
                "GWh",
                "watt-hora",
                "watts-hora",
                "quilowatt-hora",
                "quilowatts-hora",
                "megawatt-hora",
                "megawatts-hora",
            ),
        ),
        UnitDefinition(
            id="power.w",
            kind=UnitKind.POWER,
            aliases=(
                "kW",
                "MW",
                "GW",
                "kVA",
                "MVA",
                "quilowatt",
                "quilowatts",
                "megawatt",
                "megawatts",
            ),
        ),
        UnitDefinition(id="currency.brl", kind=UnitKind.CURRENCY, aliases=("R$", "real", "reais")),
        UnitDefinition(
            id="count.occurrences",
            kind=UnitKind.COUNT,
            aliases=("ocorrências", "quantidade", "vezes"),
        ),
        UnitDefinition(
            id="time.hours",
            kind=UnitKind.TIME,
            aliases=("hora", "horas", "minuto", "minutos"),
        ),
        UnitDefinition(
            id="ratio.percentage",
            kind=UnitKind.PERCENTAGE,
            aliases=("porcentagem", "percentual", "percentagem"),
        ),
    ),
    # Mês isolado e série por período não são janelas deste perfil; média não é calculada.
    # Frases contidas em um período do catálogo (ex.: "março de 2025") não disparam a regra.
    detail_rules=(
        DetailRule(
            phrases=(
                "janeiro",
                "fevereiro",
                "março",
                "abril",
                "maio",
                "junho",
                "julho",
                "agosto",
                "setembro",
                "outubro",
                "novembro",
                "dezembro",
                "mês",
                "meses",
                "por dia",
                "por semana",
                "por mês",
                "por trimestre",
                "por semestre",
                "por ano",
                "mês a mês",
                "ano a ano",
            ),
            clarification=(
                "Ainda não consulto um mês isolado nem séries por dia, mês ou ano. Qual período "
                "disponível você quer, como ‘último trimestre’ ou ‘período de demonstração’?"
            ),
        ),
        DetailRule(
            phrases=("em média", "média", "médias", "médio", "médios"),
            clarification=(
                "Por enquanto mostro só o total do período, sem média. Quer o total?"
            ),
        ),
        DetailRule(phrases=("no total", "total", "ao todo")),
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
        unsupported_breakdown=(
            "Ainda não separo o resultado por {dimension}. Posso mostrar o total do período "
            "ou filtrar um valor, por exemplo ‘em Olinda’ ou ‘residencial’."
        ),
        unit_mismatch=(
            "Não tenho esse indicador em {unit}: consumo é energia (kWh), faturamento é em "
            "reais, e interrupções e atendimentos são contagens. Quer na unidade do indicador?"
        ),
    ),
    operations=(CatalogOperation.READ,),
)
