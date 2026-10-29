"""Catálogo lógico do Grid 360 sobre a Gold v1 (GENAI-03): vocabulário sem nomes físicos.

Deriva do perfil demonstrativo (mesma técnica de ``grid360_sql_demo``) e mantém só as métricas
das capacidades com definição aprovada em ``app.readiness``: ``faturamento.receita``,
``faturamento.receita_bairro``, ``consumo.mensal_uc`` e ``interrupcoes.dec_fec``. Tabelas,
colunas e fórmulas ficam em ``grid360_gold_mapping``; este perfil só fala a língua do negócio.

Bairros, subgrupos, bandeiras, alimentadores e UCs não têm lista de valores: os valores vêm do
lote e não entram no repositório. São declarados o domínio fechado de GD (Sim/Não), as classes
citadas como exemplo no dicionário de dados e os três municípios que o case cita (GENAI-04).
Perguntas sobre capacidades indisponíveis ou recortes sem valores no catálogo recebem
esclarecimento específico (``ambiguities``), nunca o total sem o filtro. Preparação: não prova a
Gold real nem libera consulta (GENAI-06/07/10).
"""

from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DomainProfile

GOLD_PROFILE_ID = "v-energy-grid-360-gold"

# Faturado não é pago; o consumo vem das leituras e só entra para UC/mês que também tem fatura.
_BILLED_NOT_PAID = (
    "Valor faturado (soma do valor total das faturas), não valor pago nem arrecadado."
)
_INTERSECTION = (
    "Considera só os pares UC/mês com fatura e leitura; faturas sem leitura e leituras sem "
    "fatura ficam de fora."
)
_CURRENT_REGISTRY = (
    "Município, bairro, classe, subgrupo, alimentador e GD vêm do cadastro atual da UC, sem "
    "vigência histórica."
)
_GD_PRESENCE = "GD indica presença de cadastro de geração distribuída, sem vigência nem injeção."
_NOT_HOMOLOGATED = "Dados da Gold v1 ainda não homologados; uso em preparação."


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
    # Só os municípios citados no case. O dicionário não fixa a grafia de `municipio`; a
    # conferência local do lote de 28/10 achou maiúsculas com acento preservado. Os aliases são
    # comparados sem caixa e sem acento, então "jaboatao" também é reconhecido.
    _dimension(
        "geography.municipality", "Município", "geography",
        ("município", "municípios", "cidade", "cidades"),
        (
            {"value": "RECIFE", "aliases": ("Recife",)},
            {"value": "OLINDA", "aliases": ("Olinda",)},
            {
                "value": "JABOATÃO DOS GUARARAPES",
                "aliases": ("Jaboatão dos Guararapes", "Jaboatão"),
            },
        ),
    ),
    _dimension("geography.neighborhood", "Bairro", "geography", ("bairro", "bairros")),
    # Grafias citadas em docs/dicionario_gold.md como exemplos da origem, não domínio fechado.
    # Sem valores, o interpretador ignoraria "residencial" e responderia o total.
    _dimension(
        "customer.consumption_class", "Classe de consumo", "classification",
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
        "tariff.subgroup", "Subgrupo tarifário", "classification",
        ("subgrupo", "subgrupo tarifário"),
    ),
    _dimension(
        "tariff.flag", "Bandeira tarifária", "classification", ("bandeira", "bandeira tarifária")
    ),
    _dimension(
        "generation.distributed", "Geração distribuída (GD)", "classification",
        ("GD", "geração distribuída"),
        (
            {"value": "Sim", "aliases": ("com GD", "com geração distribuída")},
            {"value": "Não", "aliases": ("sem GD", "sem geração distribuída")},
        ),
    ),
    _dimension("network.feeder", "Alimentador", "other", ("alimentador", "alimentadores")),
    # Identificador da unidade: interno, não anônimo; acesso real depende de GENAI-06/07.
    _dimension(
        "customer.consumer_unit", "Unidade consumidora (UC)", "other",
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


def _metric(
    id_: str,
    domain_id: str,
    aliases: tuple[str, ...],
    unit: str,
    unit_kinds: tuple[str, ...],
    dimension_ids: tuple[str, ...],
    limitations: tuple[str, ...],
    granularities: tuple[str, ...] = _MONTH_YEAR,
) -> dict:
    return {
        "id": id_,
        "domain_id": domain_id,
        "aliases": aliases,
        "unit": unit,
        "granularities": granularities,
        "dimension_ids": dimension_ids,
        "sensitivity": "internal",
        "evidence_fields": _evidence_fields(dimension_ids),
        "limitation_texts": (*limitations, _NOT_HOMOLOGATED),
        "accepted_unit_kinds": unit_kinds,
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
        ("tarifa média efetiva", "tarifa efetiva", "preço médio por kWh"),
        "R$/kWh",
        ("currency",),
        _COMMERCIAL_WITH_UC,
        (
            "Preço observado: receita faturada dividida pelo consumo medido, como razão de "
            "somas; não é tarifa homologada nem decomposição de preço e volume.",
            "Sem consumo no recorte (zero ou ausente), o valor fica indisponível.",
            _INTERSECTION,
        ),
    ),
    _metric(
        "energy.average_consumption_per_uc",
        "consumption",
        ("consumo médio por UC", "consumo médio por unidade consumidora"),
        "kWh por UC faturada no mês",
        ("energy",),
        _COMMERCIAL,
        (
            "Consumo medido dividido pelo número de UCs faturadas em cada mês do recorte, "
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
)


def _rule(phrases: tuple[str, ...], clarification: str) -> dict:
    return {"phrases": phrases, "clarification": clarification}


# Uma regra por grupo de capacidades indisponíveis do mapeamento (`unavailable`). Ficam antes
# das demais: "reclamações de falta de luz" é atendimento, não DEC/FEC. Nenhuma frase isolada
# coincide com alias de métrica ("consumo" sozinho não dispara a regra de variação).
_UNAVAILABLE_RULES = (
    # faturamento.faturas_em_aberto
    _rule(
        (
            "em aberto",
            "fatura vencida",
            "faturas vencidas",
            "conta vencida",
            "contas vencidas",
            "vencimento",
            "inadimplência",
            "inadimplente",
            "inadimplentes",
            "atraso no pagamento",
            "atrasos no pagamento",
            "pagamento",
            "pagamentos",
            "valor pago",
            "arrecadação",
            "arrecadado",
            "débito",
            "débitos",
        ),
        "Faturas em aberto, pagamentos e inadimplência ainda não estão disponíveis na Gold "
        "carregada; tenho o valor faturado. Quer a receita faturada de um período?",
    ),
    # atendimento.uc_acumulado
    _rule(
        (
            "atendimento",
            "atendimentos",
            "chamado",
            "chamados",
            "reclamação",
            "reclamações",
            "reclamou",
            "reclamaram",
            "satisfação",
            "protocolo",
            "protocolos",
            "ouvidoria",
            "call center",
            "central de atendimento",
            "SAC",
        ),
        "Atendimentos, chamados, reclamações e satisfação ainda não estão disponíveis na Gold "
        "carregada. Posso mostrar receita, consumo ou DEC/FEC de um período.",
    ),
    # apoio.medidor_uc
    _rule(
        ("medidor", "medidores"),
        "Dados de medidor ainda não estão disponíveis na Gold carregada. Posso mostrar o "
        "consumo medido nas leituras de um período, como ‘últimos 12 meses’.",
    ),
    # apoio.energia_recuperavel
    _rule(
        (
            "energia a recuperar",
            "energia recuperável",
            "energia recuperada",
            "recuperação de energia",
            "recuperar energia",
            "perda de energia",
            "perdas de energia",
            "perda não técnica",
            "perdas não técnicas",
            "perdas comerciais",
        ),
        "Energia a recuperar e perdas de energia ainda não estão disponíveis na Gold "
        "carregada. Posso mostrar o consumo medido ou a receita faturada de um período.",
    ),
    # faturamento.preco_volume
    _rule(
        (
            "preço e volume",
            "preço ou volume",
            "preço x volume",
            "preço × volume",
            "preço versus volume",
            "efeito preço",
            "efeito volume",
            "efeito de preço",
            "efeito de volume",
            "decomposição",
            "decompor",
        ),
        "A separação em efeito preço e efeito volume ainda não está disponível na Gold "
        "carregada. Posso mostrar receita, consumo ou tarifa média efetiva de um período.",
    ),
    # consumo.variacao_uc
    _rule(
        (
            "queda de consumo",
            "quedas de consumo",
            "queda do consumo",
            "queda no consumo",
            "redução de consumo",
            "redução do consumo",
            "redução no consumo",
            "aumento de consumo",
            "aumento do consumo",
            "variação de consumo",
            "variação do consumo",
            "consumo caiu",
            "consumo aumentou",
            "consumo variou",
            "perda de consumo",
        ),
        "Variação e queda de consumo, por UC ou entre períodos, ainda não estão disponíveis "
        "na Gold carregada. Posso mostrar o consumo total de um período, como ‘último ano’.",
    ),
    # apoio.fila_inspecao
    _rule(
        (
            "inspeção",
            "inspeções",
            "fila de inspeção",
            "vistoria",
            "vistorias",
            "irregularidade",
            "irregularidades",
            "irregular",
            "irregulares",
            "fraude",
            "fraudes",
            "furto de energia",
            "ligação clandestina",
            "ligações clandestinas",
        ),
        "Fila de inspeção, inspeções e irregularidades ainda não estão disponíveis na Gold "
        "carregada. Posso mostrar consumo ou receita de um período.",
    ),
)

# Recortes que o catálogo não sabe aplicar: sem estas regras, o termo seria ignorado e a
# resposta traria o total sem o filtro. "por bairro" continua sendo pedido de quebra.
_UNSUPPORTED_SLICE_RULES = (
    _rule(
        (
            "solar",
            "energia solar",
            "geração solar",
            "painel solar",
            "painéis solares",
            "placa solar",
            "placas solares",
            "fotovoltaica",
            "fotovoltaico",
        ),
        "Não tenho filtro de geração solar, só a presença de cadastro de geração distribuída "
        "(GD), sem o tipo de fonte. Quer filtrar ‘com GD’?",
    ),
    _rule(
        ("iluminação pública", "serviço público", "consumo próprio"),
        "Não reconheço essa classe de consumo. As classes do catálogo são residencial, "
        "comercial, industrial, poder público e rural; qual delas?",
    ),
    _rule(
        (
            "ranking",
            "top",
            "maior",
            "maiores",
            "menor",
            "menores",
            "pior",
            "piores",
            "melhor",
            "melhores",
            "qual município",
            "quais municípios",
            "qual cidade",
            "quais cidades",
            "qual bairro",
            "quais bairros",
            "qual classe",
            "quais classes",
            "qual alimentador",
            "quais alimentadores",
        ),
        "Ainda não monto ranking nem comparo municípios, bairros, classes ou alimentadores "
        "entre si. Posso mostrar o total de um recorte, como ‘receita residencial em Olinda’.",
    ),
    _rule(
        (
            "no bairro",
            "do bairro",
            "neste bairro",
            "nesse bairro",
            "deste bairro",
            "desse bairro",
            "nos bairros",
            "dos bairros",
        ),
        "Ainda não filtro por bairro: o catálogo não tem a lista de bairros. Posso mostrar o "
        "total de um município, como ‘em Olinda’.",
    ),
    _rule(
        (
            "na bandeira",
            "da bandeira",
            "com bandeira",
            "bandeira verde",
            "bandeira amarela",
            "bandeira vermelha",
            "no subgrupo",
            "do subgrupo",
        ),
        "Ainda não filtro por bandeira tarifária nem por subgrupo: o catálogo não tem a lista "
        "desses valores. Posso filtrar por município, classe ou GD.",
    ),
    _rule(
        (
            "do alimentador",
            "no alimentador",
            "deste alimentador",
            "desse alimentador",
            "dos alimentadores",
            "nos alimentadores",
        ),
        "DEC e FEC são lidos por alimentador e mês, mas ainda não identifico o alimentador "
        "pelo nome ou código. Posso mostrar receita ou consumo do período.",
    ),
    _rule(
        (
            "da UC",
            "na UC",
            "desta UC",
            "dessa UC",
            "qual UC",
            "quais UCs",
            "quantas UCs",
            "da unidade consumidora",
            "na unidade consumidora",
            "quais unidades consumidoras",
            "quantas unidades consumidoras",
        ),
        "Ainda não consulto, conto nem listo UCs específicas. Posso mostrar o total de um "
        "recorte por município, classe ou GD.",
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
    values["metrics"] = _METRICS
    values["dimensions"] = _DIMENSIONS
    # Frases relativas; a janela concreta depende das competências do lote (executor futuro).
    values["period_phrases"] = (
        "últimos 12 meses",
        "último ano",
        "ano passado",
        "último trimestre",
        "últimos três meses",
        "últimos 3 meses",
        "mês passado",
        "este ano",
    )
    values["period_windows"] = ()
    values["default_period_phrase"] = None
    values["default_period_context_phrases"] = ()
    values["comparison_period_phrases"] = ()
    values["non_location_phrases"] = ()
    values["ambiguities"] = (
        *_UNAVAILABLE_RULES,
        *_UNSUPPORTED_SLICE_RULES,
        *values["ambiguities"],
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
            "Ainda não consulto um mês isolado nem séries por dia, mês ou ano. Qual período "
            "você quer, como ‘último trimestre’ ou ‘últimos 12 meses’?"
        ),
    }
    # "média" genérica continua pedindo o total; as médias do catálogo são por UC e mês e só
    # valem pelo nome ("ticket médio", "consumo médio por UC"), que o interpretador reconhece.
    detail_rules[1] = {
        **detail_rules[1],
        "clarification": (
            "Mostro o total do período; as médias que tenho são por UC e mês: ‘ticket médio’ e "
            "‘consumo médio por UC’. Quer o total ou uma delas?"
        ),
    }
    values["detail_rules"] = detail_rules
    values["clarifications"] = {
        **values["clarifications"],
        "multiple_domains": (
            "Você quer consultar qual assunto primeiro: consumo, faturamento ou DEC/FEC?"
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
