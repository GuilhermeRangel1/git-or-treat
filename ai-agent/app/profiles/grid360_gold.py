"""Catálogo lógico do Grid 360 sobre a Gold v2 (GENAI-03): vocabulário sem nomes físicos.

Deriva do perfil demonstrativo (mesma técnica de ``grid360_sql_demo``) e mantém só as métricas
das capacidades com definição aprovada em ``app.readiness``: ``faturamento.receita``,
``faturamento.receita_bairro``, ``consumo.mensal_uc``, ``interrupcoes.dec_fec`` e atendimento.
Tabelas,
colunas e fórmulas ficam em ``grid360_gold_mapping``; este perfil só fala a língua do negócio.

Municípios, bairros, subgrupos, bandeiras, alimentadores e UCs não têm lista de valores: os
valores vêm do lote e não entram no repositório. São declarados o domínio fechado de GD (Sim/Não)
e as classes citadas como exemplo no dicionário de dados. Preparação: não prova a Gold real nem
libera consulta (GENAI-06/07/10).
"""

from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DomainProfile

GOLD_PROFILE_ID = "v-energy-grid-360-gold"

# Faturado não é pago; consumo e faturas são fontes independentes no grão UC/mês.
_BILLED_NOT_PAID = (
    "Valor faturado (soma do valor total das faturas), não valor pago nem arrecadado."
)
_INTERSECTION = (
    "Faturamento e consumo são fontes independentes; faturas sem leitura e leituras sem "
    "fatura permanecem nas respectivas medidas. Ausência não equivale a zero."
)
_CURRENT_REGISTRY = (
    "Município, bairro, classe, subgrupo, alimentador e GD vêm do cadastro atual da UC, sem "
    "vigência histórica."
)
_GD_PRESENCE = "GD indica presença de cadastro de geração distribuída, sem vigência nem injeção."
_CAPABILITY_LIMIT = (
    "A consulta depende das capacidades e do escopo autorizados para a publicação Gold v2."
)


def _field(name: str, role: str, value_type: str, dimension_id: str | None = None) -> dict:
    field = {"name": name, "role": role, "value_type": value_type, "sensitivity": "internal"}
    if dimension_id is not None:
        field["dimension_id"] = dimension_id
    return field


# Nome do campo de evidência por dimensão lógica; nunca o nome da coluna física.
_DIMENSION_FIELDS = {
    "geography.municipality": "municipality",
    "geography.neighborhood": "neighborhood",
    "customer.consumption_class": "consumption_class",
    "tariff.subgroup": "tariff_subgroup",
    "tariff.flag": "tariff_flag",
    "generation.distributed": "distributed_generation",
    "network.feeder": "feeder",
    "customer.consumer_unit": "consumer_unit",
}


def _evidence_fields(dimension_ids: tuple[str, ...]) -> list[dict]:
    return [
        _field("value", "measure", "number"),
        _field("unit", "unit", "string"),
        _field("period", "period", "date"),
        *(
            _field(_DIMENSION_FIELDS[dimension_id], "dimension", "string", dimension_id)
            for dimension_id in dimension_ids
        ),
    ]


def _dimension(
    id_: str, label: str, role: str, aliases: tuple[str, ...], values: tuple = ()
) -> dict:
    return {
        "id": id_,
        "label": label,
        "role": role,
        "aliases": aliases,
        "value_type": "string",
        "operators": ("eq", "in"),
        "sensitivity": "internal",
        "values": values,
    }


_DIMENSIONS = (
    _dimension(
        "geography.municipality",
        "Município",
        "geography",
        ("município", "municípios", "cidade", "cidades"),
    ),
    _dimension("geography.neighborhood", "Bairro", "geography", ("bairro", "bairros")),
    # Grafias citadas em docs/dicionario_gold.md como exemplos da origem, não domínio fechado.
    # Sem valores, o interpretador ignoraria "residencial" e responderia o total.
    _dimension(
        "customer.consumption_class",
        "Classe de consumo",
        "classification",
        ("classe", "classe de consumo"),
        (
            {"value": "RESIDENCIAL", "aliases": ("residencial",)},
            {"value": "COMERCIAL", "aliases": ("comercial",)},
            {"value": "INDUSTRIAL", "aliases": ("industrial",)},
            {"value": "PODER PUBLICO", "aliases": ("poder público",)},
            {"value": "RURAL", "aliases": ("rural",)},
        ),
    ),
    _dimension(
        "tariff.subgroup",
        "Subgrupo tarifário",
        "classification",
        ("subgrupo", "subgrupo tarifário"),
    ),
    _dimension(
        "tariff.flag", "Bandeira tarifária", "classification", ("bandeira", "bandeira tarifária")
    ),
    _dimension(
        "generation.distributed",
        "Geração distribuída (GD)",
        "classification",
        ("GD", "geração distribuída"),
        (
            {"value": "Sim", "aliases": ("com GD", "com geração distribuída")},
            {"value": "Não", "aliases": ("sem GD", "sem geração distribuída")},
        ),
    ),
    _dimension("network.feeder", "Alimentador", "other", ("alimentador", "alimentadores")),
    # Identificador da unidade: interno, não anônimo; acesso real depende de GENAI-06/07.
    _dimension(
        "customer.consumer_unit",
        "Unidade consumidora (UC)",
        "other",
        ("UC", "UCs", "unidade consumidora", "unidades consumidoras"),
    ),
)

# Dimensões sustentadas por ao menos uma tabela fonte de cada métrica (ver o mapeamento).
_COMMERCIAL = (
    "geography.municipality",
    "customer.consumption_class",
    "tariff.subgroup",
    "tariff.flag",
    "generation.distributed",
    "geography.neighborhood",
)
_COMMERCIAL_WITH_UC = (*_COMMERCIAL, "customer.consumer_unit")
_CONTINUITY = ("network.feeder", "geography.municipality")
_MONTH_YEAR = ("month", "year")
GOLD_MAX_WINDOW_DAYS = 366 * 5

# Metadados de negócio versionados com o perfil; o Backend recebe uma cópia verificada.
_BUSINESS_METRICS = {
    "billing.revenue": (
        "Receita faturada",
        "Total das faturas do recorte, incluindo faturas sem leitura; não representa valor pago.",
    ),
    "energy.consumption": (
        "Consumo medido",
        (
            "Total medido nas leituras do recorte, incluindo leituras sem fatura; "
            "não é energia faturada."
        ),
    ),
    "billing.average_ticket": (
        "Ticket médio por UC faturada no mês",
        "Razão entre a soma da receita faturada e a soma das UCs faturadas de cada mês do recorte.",
    ),
    "billing.effective_tariff": (
        "Preço médio observado por kWh",
        (
            "Receita dividida pelo consumo da mesma base com fatura e leituras "
            "integralmente válidas; não é tarifa homologada."
        ),
    ),
    "energy.average_consumption_per_uc": (
        "Consumo médio por UC com leitura no mês",
        "Razão entre o consumo medido e a soma das UCs com leitura de cada mês do recorte.",
    ),
    "network.equivalent_interruption_duration": (
        "Duração equivalente de interrupção (DEC)",
        (
            "Horas de interrupção por UC do alimentador no mês; indicador "
            "simplificado com cadastro atual, sem agregação entre meses ou "
            "alimentadores."
        ),
    ),
    "network.equivalent_interruption_frequency": (
        "Frequência equivalente de interrupção (FEC)",
        (
            "Pares UC–ocorrência por UC do alimentador no mês; indicador "
            "simplificado com cadastro atual, sem agregação entre meses ou "
            "alimentadores."
        ),
    ),
    "service.attendance": (
        "Chamados por abertura",
        (
            "Contagem de protocolos abertos no recorte em UTC, sem contar "
            "tratativas; zero exige cobertura certificada."
        ),
    ),
    "service.satisfaction": (
        "Satisfação dos chamados por abertura",
        (
            "Média das notas individuais válidas dos protocolos abertos no recorte "
            "em UTC; zero é válido e ausência não é nota."
        ),
    ),
    "service.accumulated_attendance": (
        "Chamados no histórico acumulado",
        (
            "Total de protocolos do histórico publicado, sem intervalo de datas "
            "conhecido ou certificação de completude histórica."
        ),
    ),
    "service.accumulated_satisfaction": (
        "Satisfação no histórico acumulado",
        (
            "Média das notas individuais válidas do histórico publicado, sem "
            "período conhecido; não é média das médias por UC."
        ),
    ),
}


def _metric(
    id_: str,
    domain_id: str,
    aliases: tuple[str, ...],
    unit: str,
    unit_kinds: tuple[str, ...],
    dimension_ids: tuple[str, ...],
    limitations: tuple[str, ...],
    granularities: tuple[str, ...] = _MONTH_YEAR,
    accumulated: bool = False,
) -> dict:
    return {
        "id": id_,
        "domain_id": domain_id,
        "label": _BUSINESS_METRICS[id_][0],
        "definition": _BUSINESS_METRICS[id_][1],
        "aliases": aliases,
        "unit": unit,
        "granularities": granularities,
        "max_window_days": None if accumulated else GOLD_MAX_WINDOW_DAYS,
        "dimension_ids": dimension_ids,
        "accumulated_metric_id": {
            "service.attendance": "service.accumulated_attendance",
            "service.satisfaction": "service.accumulated_satisfaction",
        }.get(id_),
        "grouping_dimension_ids": (
            ("customer.consumption_class",) if id_ == "billing.revenue" else ()
        ),
        "required_filter_dimension_ids": (
            ("network.feeder",) if id_.startswith("network.equivalent_interruption_") else ()
        ),
        "sensitivity": "internal",
        "evidence_fields": _evidence_fields(dimension_ids),
        "limitation_texts": (*limitations, _CAPABILITY_LIMIT),
        "accepted_unit_kinds": unit_kinds,
        "accumulated_period_phrases": ("histórico acumulado",) if accumulated else (),
    }


_METRICS = (
    _metric(
        "billing.revenue",
        "revenue",
        (
            "faturamento",
            "receita",
            "receita faturada",
            "valor faturado",
            "faturamos",
            "faturou",
            "faturaram",
            "faturei",
        ),
        "R$",
        ("currency",),
        _COMMERCIAL_WITH_UC,
        (_BILLED_NOT_PAID, _INTERSECTION, _CURRENT_REGISTRY),
    ),
    _metric(
        "energy.consumption",
        "consumption",
        ("consumo", "consumo de energia", "energia consumida"),
        "kWh",
        ("energy",),
        _COMMERCIAL_WITH_UC,
        (
            "Consumo medido nas leituras, não energia faturada nem injetada.",
            _INTERSECTION,
            _CURRENT_REGISTRY,
        ),
    ),
    _metric(
        "billing.average_ticket",
        "revenue",
        ("ticket médio", "receita média por UC", "faturamento médio por UC"),
        "R$ por UC faturada no mês",
        ("currency",),
        _COMMERCIAL,
        (
            "Receita faturada dividida pelo número de UCs faturadas em cada mês do recorte "
            "(média por UC e mês), calculada como razão de somas.",
            _BILLED_NOT_PAID,
            _INTERSECTION,
        ),
    ),
    _metric(
        "billing.effective_tariff",
        "revenue",
        ("tarifa média efetiva", "tarifa efetiva", "preço médio por kWh",
         "preço médio observado da energia"),
        "R$/kWh",
        ("currency",),
        _COMMERCIAL_WITH_UC,
        (
            "Preço observado: receita da base comparável dividida pelo consumo da mesma "
            "base, como razão de "
            "somas; não é tarifa homologada nem decomposição de preço e volume.",
            "Sem consumo comparável no recorte (zero ou ausente), o valor fica indisponível.",
            "Somente pares com fatura e leituras integralmente válidas compõem a base comparável.",
        ),
    ),
    _metric(
        "energy.average_consumption_per_uc",
        "consumption",
        ("consumo médio por UC", "consumo médio por unidade consumidora",
         "consumo médio por unidade com leitura"),
        "kWh por UC com leitura no mês",
        ("energy",),
        _COMMERCIAL,
        (
            "Consumo medido dividido pelo número de UCs com leitura em cada mês do recorte, "
            "calculado como razão de somas.",
            _INTERSECTION,
        ),
    ),
    _metric(
        "network.equivalent_interruption_duration",
        "network",
        ("DEC", "duração equivalente de interrupção", "duração equivalente"),
        "horas por UC",
        ("time",),
        _CONTINUITY,
        (
            "Indicador interno simplificado por alimentador e mês, não apuração regulatória.",
            "Lido só por alimentador e mês: não é somado nem tirado em média entre "
            "alimentadores ou meses.",
            "Mês sem linha não prova ausência de interrupção; o denominador é o cadastro atual.",
        ),
        ("month",),
    ),
    _metric(
        "network.equivalent_interruption_frequency",
        "network",
        ("FEC", "frequência equivalente de interrupção", "frequência equivalente"),
        "interrupções por UC",
        ("count",),
        _CONTINUITY,
        (
            "Indicador interno simplificado por alimentador e mês, não apuração regulatória.",
            "Lido só por alimentador e mês: não é somado nem tirado em média entre "
            "alimentadores ou meses.",
            "Conta pares UC–ocorrência; mês sem linha não prova ausência de interrupção.",
        ),
        ("month",),
    ),
    _metric(
        "service.attendance",
        "service",
        ("chamados", "atendimentos", "protocolos"),
        "protocolos",
        ("count",),
        ("customer.consumer_unit",),
        ("Conta protocolos por abertura UTC; exige C14/C15. Não conta tratativas.",),
    ),
    _metric(
        "service.satisfaction",
        "service",
        ("satisfação", "nota de satisfação", "satisfação média"),
        "pontos",
        ("score",),
        ("customer.consumer_unit",),
        (
            "Média das notas válidas por abertura UTC; zero é válido, ausência é nula. "
            "Sem escala presumida.",
        ),
    ),
    _metric(
        "service.accumulated_attendance",
        "service",
        ("chamados acumulados", "atendimentos acumulados"),
        "protocolos",
        ("count",),
        ("customer.consumer_unit",),
        ("Resumo acumulado da publicação, sem período conhecido. Não aceita filtros de datas.",),
        accumulated=True,
    ),
    _metric(
        "service.accumulated_satisfaction",
        "service",
        ("satisfação acumulada",),
        "pontos",
        ("score",),
        ("customer.consumer_unit",),
        (
            "Média das notas válidas do histórico; não é média de médias "
            "nem aceita filtro de datas.",
        ),
        accumulated=True,
    ),
)


def _build_profile() -> DomainProfile:
    values = GRID360_DEMO_PROFILE.model_dump(mode="python")
    values["profile_id"] = GOLD_PROFILE_ID
    values["domains"] = (
        {
            "id": "revenue",
            "label": "Faturamento",
            "example_questions": ("Qual foi a receita faturada no último trimestre?",),
        },
        {
            "id": "consumption",
            "label": "Consumo medido",
            "example_questions": ("Qual foi o consumo nos últimos 12 meses?",),
        },
        {
            "id": "network",
            "label": "Continuidade do fornecimento",
            "example_questions": ("Qual foi o DEC do alimentador no mês passado?",),
        },
    )
    values["domains"] = (
        *values["domains"],
        {
            "id": "service",
            "label": "Atendimento",
            "example_questions": ("Quantos chamados no último trimestre?",),
        },
    )
    values["units"] = (
        *values["units"],
        {"id": "service.score", "kind": "score", "aliases": ("ponto", "pontos")},
    )
    values["metrics"] = _METRICS
    values["dimensions"] = _DIMENSIONS
    # Frases relativas; o planejador resolve limites com as competências do lote recebido.
    values["period_phrases"] = (
        "últimos 12 meses",
        "último ano",
        "ano passado",
        "último trimestre",
        "últimos três meses",
        "últimos 3 meses",
        "mês passado",
        "este ano",
        "neste ano",
        "histórico acumulado",
    )
    values["period_windows"] = ()
    values["default_period_phrase"] = None
    values["structured_dimension_filters"] = True
    values["supports_grouping"] = True
    values["supports_ordering"] = True
    values["default_period_context_phrases"] = ()
    values["comparison_period_phrases"] = ()
    values["non_location_phrases"] = ()
    values["ambiguities"] = (
        *values["ambiguities"],
        {
            "phrases": (
                "valor pago", "valores pagos", "quanto foi pago", "receita recebida",
                "receita paga", "valor recebido", "arrecadação", "arrecadado",
                "pagamento", "pagamentos", "faturas pagas",
            ),
            "clarification": (
                "Receita faturada não comprova pagamento ou arrecadação. "
                "Você quer consultar a receita faturada?"
            ),
        },
        {
            "phrases": ("energia faturada", "kwh faturados", "kwh faturado"),
            "clarification": (
                "A Gold v2 publica consumo medido em kWh, não energia faturada. "
                "Quer consultar o consumo medido?"
            ),
        },
        {
            "phrases": (
                "energia injetada", "energia compensada", "energia entregue",
                "consumo injetado", "consumo compensado",
            ),
            "clarification": (
                "Consumo medido não representa energia injetada, compensada ou entregue. "
                "Você quer consultar o consumo medido?"
            ),
        },
        {
            "phrases": ("solar", "energia solar", "painel solar", "painéis solares"),
            "clarification": (
                "A Gold v2 registra geração distribuída (GD), mas não confirma que a origem "
                "seja solar. Posso filtrar UCs com ou sem GD registrada?"
            ),
        },
        {
            "phrases": (
                "interrupção",
                "interrupções",
                "falta de luz",
                "faltas de luz",
                "falta de energia",
                "faltas de energia",
                "queda de energia",
                "quedas de energia",
                "apagão",
                "apagões",
            ),
            "clarification": (
                "Sobre interrupções, consulto DEC (horas por UC) ou FEC (interrupções por UC) "
                "por alimentador e mês. Qual dos dois você quer?"
            ),
        },
    )
    detail_rules = list(values["detail_rules"])
    detail_rules[0] = {
        **detail_rules[0],
        "clarification": (
            "Informe uma competência com mês e ano, um intervalo de meses completos "
            "ou uma janela como ‘último trimestre’. Séries e recortes por dia ainda "
            "não estão disponíveis neste planejamento."
        ),
    }
    values["detail_rules"] = [
        *detail_rules,
        {
            "phrases": (
                "sem leitura", "com leitura", "sem leituras", "com leituras",
                "sem fatura", "com fatura", "sem faturas", "com faturas",
                "estorno", "estornos", "estimada", "estimadas", "estimado", "estimados",
                "vencida", "vencidas", "vencido", "vencidos", "em aberto",
            ),
            "clarification": (
                "Esse recorte de leitura ou situação da fatura ainda não é representado "
                "neste catálogo de perguntas. Reformule o recorte antes de consultar."
            ),
        },
        {
            "phrases": (
                "top", "ranking", "ordene", "ordenar", "ordenado", "ordenada",
                "crescente", "decrescente", "maiores", "menores", "primeiros",
            ),
            "clarification": (
                "O planejamento atual não representa esse ranking ou essa ordenação. "
                "Escolha um indicador e um recorte específico para consultar."
            ),
        },
        {
            "phrases": (
                "acima de", "abaixo de", "maior que", "menor que", "entre valores",
                "mais de", "menos de", "pelo menos",
            ),
            "clarification": (
                "Esse filtro por valor ainda não está disponível no planejamento. "
                "Informe um recorte sem esse limite numérico."
            ),
        },
    ]
    values["clarifications"] = {
        **values["clarifications"],
        "temporal_coverage_unavailable": (
            "Não consigo confirmar uma janela mensal completa nessa publicação. Informe outro "
            "período mensal, como ‘últimos três meses’."
        ),
        "multiple_domains": (
            "Qual assunto consultar primeiro: consumo, faturamento, atendimento ou DEC/FEC?"
        ),
        "unsupported_breakdown": (
            "Ainda não separo o resultado por {dimension}. Posso mostrar o total do período."
        ),
        "unit_mismatch": (
            "Não tenho esse indicador em {unit}: consumo é energia (kWh), faturamento é em "
            "reais e DEC/FEC são indicadores por UC. Quer na unidade do indicador?"
        ),
    }
    return DomainProfile.model_validate(values)


GRID360_GOLD_PROFILE = _build_profile()
