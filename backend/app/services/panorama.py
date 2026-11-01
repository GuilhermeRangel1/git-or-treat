from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Any

from app.repositories.panorama import PanoramaRepository
from app.repositories.panorama import GoldPanoramaRepository
from app.schemas.panorama import PanoramaData, PanoramaFilterOptions, PanoramaMetric, PanoramaSeriesPoint
from app.services.analytics import AnalyticsAPIError

DEFAULT_PERIOD = "2024-04"
COMPARISON_TYPES = ("anterior", "ano_anterior", "nenhuma")
ALL_MUNICIPIOS = "todos"
ALL_CLASSES = "todas"
MONTH_LABELS = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def _invalid(field: str, message: str) -> AnalyticsAPIError:
    return AnalyticsAPIError(422, "invalid_query", "Entrada inválida.", [{"field": field, "message": message}])


def validate_period(periodo: str) -> str:
    try:
        parsed = datetime.strptime(periodo, "%Y-%m")
    except ValueError:
        raise _invalid("competencia", "Use uma competência real no formato YYYY-MM.")
    if parsed.strftime("%Y-%m") != periodo:
        raise _invalid("competencia", "Use uma competência real no formato YYYY-MM.")
    return periodo


def validate_comparison(comparacao: str) -> str:
    if comparacao not in COMPARISON_TYPES:
        raise _invalid("comparacao", "Use anterior, ano_anterior ou nenhuma.")
    return comparacao


def validate_filter(value: str, field: str, accepted: set[str], wildcard: str) -> str:
    if not value.strip() or len(value) > 100:
        raise _invalid(field, "Informe de 1 a 100 caracteres.")
    if value != wildcard and value not in accepted:
        raise _invalid(field, "O valor não existe na fonte demonstrativa.")
    return value


def comparison_period(periodo: str, comparacao: str) -> str | None:
    """Competência de referência da comparação: mês anterior, mesmo mês do ano anterior ou nenhuma."""
    if comparacao == "nenhuma":
        return None
    ano, mes = map(int, periodo.split("-"))
    if comparacao == "ano_anterior":
        return f"{ano - 1:04d}-{mes:02d}"
    if mes == 1:
        return f"{ano - 1:04d}-12"
    return f"{ano:04d}-{mes - 1:02d}"


def filter_records(records: list[dict], periodo: str, municipio: str, classe: str) -> list[dict]:
    return [
        record
        for record in records
        if record["competencia"] == periodo
        and (municipio == ALL_MUNICIPIOS or record["municipio"].lower() == municipio.lower())
        and (classe == ALL_CLASSES or record["classe"].lower() == classe.lower())
    ]


def sum_records(records: list[dict]) -> dict[str, Any]:
    if not records:
        return {
            "receita_faturada": 0.0,
            "receita_paga": 0.0,
            "energia_consumida": 0.0,
            "energia_faturada": 0.0,
            "ucs_ativas": 0,
            "dec_horas": 0.0,
            "fec_vezes": 0.0,
        }
    ucs = sum(record["ucs_ativas"] for record in records)
    return {
        "receita_faturada": round(sum(record["receita_faturada"] for record in records), 2),
        "receita_paga": round(sum(record["receita_paga"] for record in records), 2),
        "energia_consumida": round(sum(record["energia_consumida_kwh"] for record in records), 2),
        "energia_faturada": round(sum(record["energia_faturada_kwh"] for record in records), 2),
        "ucs_ativas": ucs,
        "dec_horas": round(sum(record["dec_horas"] * record["ucs_ativas"] for record in records) / ucs, 2) if ucs > 0 else 0.0,
        "fec_vezes": round(sum(record["fec_vezes"] * record["ucs_ativas"] for record in records) / ucs, 2) if ucs > 0 else 0.0,
    }


def build_metric(
    id_: str,
    nome: str,
    subtitulo: str,
    categoria: str,
    tipo_grandeza: str,
    valor_atual: float,
    valor_anterior: float | None,
    unidade: str,
    definicao: str,
    formula: str,
    bom_sentido: str = "positivo",
) -> PanoramaMetric:
    tem_anterior = valor_anterior is not None
    base_zero = tem_anterior and valor_anterior == 0.0
    variacao_absoluta: float | None = None
    variacao_percentual: float | None = None

    if tem_anterior and not base_zero:
        variacao_absoluta = round(valor_atual - valor_anterior, 2)
        variacao_percentual = round(((valor_atual - valor_anterior) / valor_anterior) * 100, 2)
    elif tem_anterior and base_zero:
        variacao_absoluta = round(valor_atual, 2)

    return PanoramaMetric(
        id=id_,
        nome=nome,
        subtitulo=subtitulo,
        categoria=categoria,
        tipoGrandeza=tipo_grandeza,
        valorAtual=valor_atual,
        valorAnterior=valor_anterior,
        variacaoAbsoluta=variacao_absoluta,
        variacaoPercentual=variacao_percentual,
        unidade=unidade,
        definicao=definicao,
        formula=formula,
        baseZero=base_zero,
        bomSentido=bom_sentido,
    )


def period_label(competencia: str) -> str:
    ano, mes = competencia.split("-")
    return f"{MONTH_LABELS[int(mes) - 1]}/{ano[2:]}"


def build_panorama(
    repository: PanoramaRepository,
    competencia: str = DEFAULT_PERIOD,
    comparacao: str = "anterior",
    municipio: str = ALL_MUNICIPIOS,
    classe: str = ALL_CLASSES,
) -> PanoramaData:
    periodo = validate_period(competencia)
    tipo_comparacao = validate_comparison(comparacao)
    municipios = {record["municipio"] for record in repository.records}
    classes = {record["classe"] for record in repository.records} | {"Rural"}
    municipio_filtrado = validate_filter(municipio, "municipio", municipios, ALL_MUNICIPIOS)
    classe_filtrada = validate_filter(classe, "classe", classes, ALL_CLASSES)

    competencia_anterior = comparison_period(periodo, tipo_comparacao)
    registros_atuais = filter_records(repository.records, periodo, municipio_filtrado, classe_filtrada)
    registros_anteriores = (
        filter_records(repository.records, competencia_anterior, municipio_filtrado, classe_filtrada)
        if competencia_anterior
        else []
    )

    atual = sum_records(registros_atuais)
    # Totais parciais não são comparáveis com uma competência fechada.
    periodos_completos = not repository.incomplete_periods.intersection(
        {periodo, competencia_anterior}
    )
    anterior = sum_records(registros_anteriores) if registros_anteriores and periodos_completos else None

    preco_medio_atual = (
        round(atual["receita_faturada"] / atual["energia_faturada"], 2) if atual["energia_faturada"] > 0 else 0.0
    )
    preco_medio_anterior = (
        round(anterior["receita_faturada"] / anterior["energia_faturada"], 2)
        if anterior and anterior["energia_faturada"] > 0
        else None
    )

    metricas = {
        "receitaFaturada": build_metric(
            "rec_fat",
            "Receita Faturada",
            "Valor faturado em contas emitidas",
            "financeiro",
            "faturado",
            atual["receita_faturada"],
            anterior["receita_faturada"] if anterior else None,
            "R$",
            "Total monetário faturado no ciclo da competência.",
            "Σ(faturas_emitidas.valor_total)",
        ),
        "receitaPaga": build_metric(
            "rec_pag",
            "Receita Arrecadada / Paga",
            "Valor liquidado e recebido",
            "financeiro",
            "pago",
            atual["receita_paga"],
            anterior["receita_paga"] if anterior else None,
            "R$",
            "Total financeiro liquidado e recebido no período (distingue-se do faturado).",
            "Σ(pagamentos.valor_pago)",
        ),
        "energiaConsumida": build_metric(
            "ene_con",
            "Energia Consumida",
            "Volume medido nos medidores",
            "fisico",
            "consumido",
            atual["energia_consumida"],
            anterior["energia_consumida"] if anterior else None,
            "kWh",
            "Volume físico medido nos pontos de entrega das unidades consumidoras.",
            "Σ(medicoes.leitura_atual - leitura_anterior)",
        ),
        "energiaFaturada": build_metric(
            "ene_fat",
            "Energia Faturada",
            "Volume faturado nas contas",
            "fisico",
            "faturado",
            atual["energia_faturada"],
            anterior["energia_faturada"] if anterior else None,
            "kWh",
            "Volume de energia considerado para fins tarifários nas faturas.",
            "Σ(faturas.consumo_faturado_kwh)",
        ),
        "precoMedioEfetivo": build_metric(
            "prc_med",
            "Preço Médio Efetivo",
            "Receita faturada ÷ volume faturado",
            "financeiro",
            "faturado",
            preco_medio_atual,
            preco_medio_anterior,
            "R$/kWh",
            "Tarifa média efetiva praticada no período. Não confundir com a tarifa homologada ANEEL.",
            "Receita Faturada / Energia Faturada",
        ),
        "ucsAtivas": build_metric(
            "ucs_atv",
            "UCs Ativas",
            "Unidades com contrato regular",
            "operacional",
            "operacao",
            atual["ucs_ativas"],
            anterior["ucs_ativas"] if anterior else None,
            "UCs",
            "Contagem de unidades consumidoras ativas no período.",
            "COUNT(DISTINCT uc_id WHERE status = 'ATIVO')",
        ),
        "continuidadeDec": build_metric(
            "cont_dec",
            "Duração Equivalente (DEC)",
            "DEC médio simplificado",
            "operacional",
            "operacao",
            atual["dec_horas"],
            anterior["dec_horas"] if anterior else None,
            "horas/UC",
            "Duração média simplificada das interrupções por unidade atendida.",
            "Σ(duracao × ucs_afetadas) / Total UCs",
            "negativo",
        ),
        "continuidadeFec": build_metric(
            "cont_fec",
            "Frequência Equivalente (FEC)",
            "FEC médio simplificado",
            "operacional",
            "operacao",
            atual["fec_vezes"],
            anterior["fec_vezes"] if anterior else None,
            "interrupções/UC",
            "Frequência média simplificada de interrupções por unidade atendida.",
            "Σ(ucs_afetadas_interrupcao) / Total UCs",
            "negativo",
        ),
    }

    serie_mensal = []
    for competencia_historia in sorted({record["competencia"] for record in repository.records if record["competencia"] <= periodo}):
        soma = sum_records(filter_records(repository.records, competencia_historia, municipio_filtrado, classe_filtrada))
        serie_mensal.append(
            PanoramaSeriesPoint(
                competencia=competencia_historia,
                label=period_label(competencia_historia),
                receitaFaturada=soma["receita_faturada"],
                receitaPaga=soma["receita_paga"],
                energiaConsumidaKwh=soma["energia_consumida"],
                energiaFaturadaKwh=soma["energia_faturada"],
                ucsAtivas=soma["ucs_ativas"],
                decHoras=soma["dec_horas"],
                fecVezes=soma["fec_vezes"],
            )
        )

    filtros = {
        "periodo": periodo,
        "comparacao": tipo_comparacao,
        "municipio": municipio_filtrado,
        "classe": classe_filtrada,
    }

    return PanoramaData(
        filtros=filtros,
        periodoIncompleto=periodo in repository.incomplete_periods,
        totalRegistros=len(registros_atuais),
        dataAtualizacao=repository.source_updated_at,
        loteVersao=repository.source_version,
        metricas=metricas,
        serieMensal=serie_mensal,
    )


def _gold_metric(
    id_: str,
    nome: str,
    subtitulo: str,
    categoria: str,
    tipo_grandeza: str,
    current: float | Decimal | int | None,
    previous: float | Decimal | int | None,
    unit: str,
    definition: str,
    formula: str,
    status: str,
    limitations: list[str],
    bom_sentido: str = "positivo",
    comparison_status: str = "available",
    comparison_limitations: list[str] | None = None,
    value_precision: int | None = None,
) -> PanoramaMetric:
    current_decimal = Decimal(str(current)) if current is not None else None
    previous_decimal = Decimal(str(previous)) if previous is not None else None
    base_zero = previous == 0 if previous is not None else False
    can_compare = comparison_status in {"available", "partial"}
    change = percent = None
    if can_compare and current_decimal is not None and previous_decimal is not None:
        with localcontext() as context:
            # Numeric(38, 2) has at most 38 significant digits; 100 leaves room for the quotient and percentage.
            context.prec = 100
            raw_change = current_decimal - previous_decimal
            change = float(raw_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            if previous_decimal != 0:
                raw_percent = raw_change / previous_decimal * Decimal("100")
                percent = float(raw_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def output_value(value: Decimal | None) -> float | None:
        if value is None:
            return None
        if value_precision is not None:
            quantum = Decimal(1).scaleb(-value_precision)
            with localcontext() as context:
                context.prec = 100
                value = value.quantize(quantum, rounding=ROUND_HALF_UP)
        return float(value)

    return PanoramaMetric(
        id=id_, nome=nome, subtitulo=subtitulo, categoria=categoria,
        tipoGrandeza=tipo_grandeza, valorAtual=output_value(current_decimal), valorAnterior=output_value(previous_decimal),
        variacaoAbsoluta=change, variacaoPercentual=percent, unidade=unit,
        definicao=definition, formula=formula, baseZero=base_zero,
        bomSentido=bom_sentido, status=status, limitacoes=limitations,
        statusComparacao=comparison_status,
        limitacoesComparacao=comparison_limitations or [],
    )


@dataclass(frozen=True)
class GoldFinancialSnapshot:
    periods: list[str]
    municipalities: list[str]
    classes: list[str]
    period: str
    comparison: str
    municipality: str
    consumption_class: str
    selected_municipality: str | None
    selected_class: str | None
    reference: str | None
    actual: dict[str, Any]
    prior: dict[str, Any] | None


def read_gold_panorama_financials(
    repository: GoldPanoramaRepository, competencia: str | None,
    comparacao: str, municipio: str, classe: str,
) -> GoldFinancialSnapshot:
    """Lê somente o diagnóstico financeiro autorizado, sem cadastro individual."""
    periods, municipalities, classes = repository.options()
    if not periods:
        raise AnalyticsAPIError(503, "source_unavailable", "A fonte Gold não contém competências publicadas.")
    period = validate_period(competencia or periods[-1])
    compare = validate_comparison(comparacao)
    municipality = validate_filter(municipio, "municipio", set(municipalities), ALL_MUNICIPIOS)
    consumption_class = validate_filter(classe, "classe", set(classes), ALL_CLASSES)
    selected_municipality = None if municipality == ALL_MUNICIPIOS else municipality
    selected_class = None if consumption_class == ALL_CLASSES else consumption_class

    reference = comparison_period(period, compare)
    actual = repository.aggregate(period, selected_municipality, selected_class)
    prior = (
        repository.aggregate(reference, selected_municipality, selected_class)
        if reference and reference in periods else None
    )

    return GoldFinancialSnapshot(periods, municipalities, classes, period, compare, municipality,
            consumption_class, selected_municipality, selected_class, reference, actual, prior)


def gold_panorama_revenue_metric(actual: dict[str, Any], prior: dict[str, Any] | None, reference: str | None) -> PanoramaMetric:
    """Uma regra de receita comparável compartilhada pelo KPI e pelo insight."""
    def status(row):
        if row is None or row["row_count"] == 0:
            return "empty"
        if row["revenue_values"] == 0:
            return "unavailable"
        return "partial" if row["revenue_values"] < row["row_count"] else "available"
    state = status(actual)
    comparison = ("empty" if not reference or prior is None else
                  "partial" if state == status(prior) == "available" else "unavailable")
    if comparison == "partial":
        comparison_limits = ["Ambas as competências têm valores observados, mas a Gold não declara fechamento mensal; variações descrevem somente os valores publicados."]
    elif reference and prior is None:
        comparison_limits = ["A competência de comparação não foi observada na fonte Gold."]
    elif reference:
        comparison_limits = ["Uma das competências tem valores ausentes ou indisponíveis; variação não calculada."]
    else:
        comparison_limits = ["Nenhuma competência de comparação foi solicitada."]
    limits = ([] if state == "available" else
        ["Não há linha Gold para a competência e os filtros selecionados."] if state == "empty" else
        ["Valores ausentes em alguma dimensão; o total soma somente o que foi observado."] if state == "partial" else
        ["A tabela Gold não contém esta grandeza."])
    return _gold_metric(
        "rec_fat", "Receita comparável", "Faturamento com todas as leituras observadas válidas",
        "financeiro", "faturado", actual["revenue"],
        prior["revenue"] if comparison == "partial" else None, "R$",
        "Faturamento de UC/mês com fatura e todas as leituras observadas válidas.",
        "Σ(receita_base_comparavel_reais)", state, limits,
        comparison_status=comparison, comparison_limitations=comparison_limits,
    )


def build_gold_panorama(
    repository: GoldPanoramaRepository,
    competencia: str | None,
    comparacao: str,
    municipio: str,
    classe: str,
) -> PanoramaData:
    financials = read_gold_panorama_financials(repository, competencia, comparacao, municipio, classe)
    periods, municipalities, classes = financials.periods, financials.municipalities, financials.classes
    period, compare = financials.period, financials.comparison
    municipality, consumption_class = financials.municipality, financials.consumption_class
    selected_municipality, selected_class = financials.selected_municipality, financials.selected_class
    reference, actual, prior = financials.reference, financials.actual, financials.prior

    billed_count = repository.billed_uc_count(period, selected_municipality, selected_class)
    prior_billed_count = repository.billed_uc_count(reference, selected_municipality, selected_class) if prior is not None else None
    registered_count = repository.registered_uc_count(selected_municipality, selected_class)

    def number(row, field):
        value = row[field] if row is not None else None
        return value

    def measure_status(row, values_field):
        if row is None or row["row_count"] == 0:
            return "empty"
        if row[values_field] == 0:
            return "unavailable"
        if row[values_field] < row["row_count"]:
            return "partial"
        return "available"

    revenue = number(actual, "revenue")
    energy = number(actual, "energy")
    prior_revenue = number(prior, "revenue")
    prior_energy = number(prior, "energy")
    with localcontext() as context:
        # Preserve precision above Numeric(38, 2) input capacity without changing the process-wide context.
        context.prec = 100
        price = revenue / Decimal(str(energy)) if revenue is not None and energy not in (None, 0) else None
        prior_price = prior_revenue / Decimal(str(prior_energy)) if prior_revenue is not None and prior_energy not in (None, 0) else None
    observed = actual["row_count"] > 0
    metric_limit = ["Não há linha Gold para a competência e os filtros selecionados."] if not observed else []
    unavailable = ["A tabela Gold não contém esta grandeza."]
    revenue_status = measure_status(actual, "revenue_values")
    energy_status = measure_status(actual, "energy_values")
    base_limit = ["Valores ausentes em alguma dimensão; o total soma somente o que foi observado."]
    current_continuity = prior_continuity = None
    continuity_limitations = ["A continuidade não é segregada por classe na fonte Gold."]
    if consumption_class == ALL_CLASSES:
        from app.repositories.gold_operations import GoldOperationsRepository
        from app.services.operations import build_gold_operation_summary

        operations = GoldOperationsRepository(repository.context)
        _, feeder_municipalities = operations.options()
        continuity_municipalities = set(feeder_municipalities.values())
        if selected_municipality is None or selected_municipality in continuity_municipalities:
            current_continuity = build_gold_operation_summary(operations, period, period, selected_municipality).data
            if reference and reference in periods:
                prior_continuity = build_gold_operation_summary(operations, reference, reference, selected_municipality).data
            continuity_limitations = list(current_continuity.limitations)
        else:
            continuity_limitations = [
                "O município tem dados financeiros, mas não há município/alimentador correspondente em indicadores_dec_fec."
            ]
    prior_revenue_status = measure_status(prior, "revenue_values") if prior is not None else "empty"
    prior_energy_status = measure_status(prior, "energy_values") if prior is not None else "empty"

    def comparison_state(current_complete: bool, previous_complete: bool) -> str:
        if not reference or prior is None:
            return "empty"
        return "partial" if current_complete and previous_complete else "unavailable"

    def comparison_limitations(state: str) -> list[str]:
        if state == "partial":
            return ["Ambas as competências têm valores observados, mas a Gold não declara fechamento mensal; variações descrevem somente os valores publicados."]
        if reference and prior is None:
            return ["A competência de comparação não foi observada na fonte Gold."]
        if reference:
            return ["Uma das competências tem valores ausentes ou indisponíveis; variação não calculada."]
        return ["Nenhuma competência de comparação foi solicitada."]

    energy_comparison = comparison_state(energy_status == "available", prior_energy_status == "available")
    price_comparison = comparison_state(
        price is not None and revenue_status == energy_status == "available",
        prior_price is not None and prior_revenue_status == prior_energy_status == "available",
    )
    dec_comparison = comparison_state(
        current_continuity is not None and current_continuity.dec_hours_per_uc is not None,
        prior_continuity is not None and prior_continuity.dec_hours_per_uc is not None,
    )
    fec_comparison = comparison_state(
        current_continuity is not None and current_continuity.fec_interruptions_per_uc is not None,
        prior_continuity is not None and prior_continuity.fec_interruptions_per_uc is not None,
    )
    metrics = {
        "receitaFaturada": gold_panorama_revenue_metric(actual, prior, reference),
        "receitaPaga": _gold_metric(
            "rec_pag", "Receita Paga", "Indisponível na exportação Gold", "financeiro", "pago",
            None, None, "R$", "A Gold não contém pagamentos.", "indisponível",
            "unavailable", unavailable, comparison_status="unavailable",
        ),
        "energiaConsumida": _gold_metric(
            "ene_con", "Consumo Medido", "Consumo dos mesmos pares UC/mês da receita comparável", "fisico", "consumido",
            energy, prior_energy if energy_comparison == "partial" else None, "kWh", "Consumo medido dos mesmos pares UC/mês usados na receita comparável.",
            "Σ(consumo_base_comparavel_kwh)", energy_status,
            metric_limit if energy_status == "empty" else (base_limit if energy_status == "partial" else ([] if energy_status == "available" else unavailable)),
            comparison_status=energy_comparison, comparison_limitations=comparison_limitations(energy_comparison),
        ),
        "energiaFaturada": _gold_metric(
            "ene_fat", "Energia Faturada", "Indisponível na exportação Gold", "fisico", "faturado",
            None, None, "kWh", "A Gold não contém energia faturada separada do consumo medido.",
            "indisponível", "unavailable", unavailable, comparison_status="unavailable",
        ),
        "precoMedioEfetivo": _gold_metric(
            "prc_med", "Preço Observado", "Razão entre receita e consumo da base comparável",
            "financeiro", "faturado", price, prior_price if price_comparison == "partial" else None, "R$/kWh",
            "Razão entre receita e consumo medidos na mesma base comparável; não é tarifa homologada.",
            "Σ(receita_base_comparavel_reais) / Σ(consumo_base_comparavel_kwh)",
            "available" if price is not None and revenue_status == energy_status == "available" else ("partial" if price is not None else ("empty" if not observed else "unavailable")),
            metric_limit if not observed else (base_limit if price is not None and (revenue_status != "available" or energy_status != "available") else ([] if price is not None else ["Consumo ausente ou zero; preço não calculado."])),
            comparison_status=price_comparison, comparison_limitations=comparison_limitations(price_comparison),
            value_precision=2,
        ),
        "ucsAtivas": _gold_metric(
            "ucs_atv", "UCs cadastradas no lote", "Cadastro atual; todos os status", "operacional", "operacao",
            registered_count, None, "UCs", "UCs distintas no cadastro atual da publicação; não representa população ativa histórica.",
            "COUNT(DISTINCT visao_360_uc.id_uc)", "available",
            ["Fotografia cadastral do lote, independente da competência selecionada; inclui todos os status."],
            comparison_status="unavailable", comparison_limitations=["O cadastro não comprova vigência histórica mensal."],
        ),
        "ucsFaturadasNoMes": _gold_metric(
            "ucs_fat", "UCs Faturadas no Mês", "UCs distintas com fatura observada na competência",
            "operacional", "operacao", billed_count, prior_billed_count, "UCs",
            "Contagem distinta de UCs com tem_fatura=true, inclusive quando não há leitura; filtros pelo cadastro atual.",
            "COUNT(DISTINCT consumo_mensal_uc.id_uc) WHERE tem_fatura=true",
            "available" if observed else "empty", ["Cadastro atual; presença de fatura não certifica fechamento mensal."],
            comparison_status="partial" if prior is not None else "empty",
            comparison_limitations=["Comparação observada; sem declaração de fechamento mensal."],
        ),
        "continuidadeDec": _gold_metric(
            "cont_dec", "DEC", "Consulta disponível em Operação", "operacional", "operacao",
            current_continuity.dec_hours_per_uc if current_continuity else None,
            prior_continuity.dec_hours_per_uc if dec_comparison == "partial" else None,
            "horas/UC", "Soma das durações observadas dividida uma vez pelo denominador cadastral constante por alimentador.",
            "Σ(duracao_total_interrupcoes_horas) / denominador cadastral",
            "partial" if current_continuity and current_continuity.dec_hours_per_uc is not None else "unavailable",
            continuity_limitations, "negativo", dec_comparison, comparison_limitations(dec_comparison),
        ),
        "continuidadeFec": _gold_metric(
            "cont_fec", "FEC", "Consulta disponível em Operação", "operacional", "operacao",
            current_continuity.fec_interruptions_per_uc if current_continuity else None,
            prior_continuity.fec_interruptions_per_uc if fec_comparison == "partial" else None,
            "interrupções/UC", "Soma das frequências observadas dividida uma vez pelo denominador cadastral constante por alimentador.",
            "Σ(frequencia_total_interrupcoes) / denominador cadastral",
            "partial" if current_continuity and current_continuity.fec_interruptions_per_uc is not None else "unavailable",
            continuity_limitations, "negativo", fec_comparison, comparison_limitations(fec_comparison),
        ),
    }

    series_rows = {row["competencia"]: row for row in repository.series(period, selected_municipality, selected_class)}
    series = []
    for month in (value for value in periods if value <= period):
        row = series_rows.get(month)
        has_data = row is not None and row["row_count"] > 0
        rev = number(row, "revenue") if has_data else None
        ene = number(row, "energy") if has_data else None
        series.append(PanoramaSeriesPoint(
            competencia=month, label=period_label(month), receitaFaturada=float(rev) if rev is not None else None,
            receitaPaga=None, energiaConsumidaKwh=float(ene) if ene is not None else None, energiaFaturadaKwh=None,
            ucsAtivas=None, decHoras=None, fecVezes=None,
            status="partial" if has_data else "empty",
        ))
    return PanoramaData(
        filtros={"periodo": period, "comparacao": compare, "municipio": municipality, "classe": consumption_class},
        periodoIncompleto=False,
        totalRegistros=actual["row_count"],
        dataAtualizacao=repository.source_updated_at,
        loteVersao=repository.context.lote,
        metricas=metrics,
        serieMensal=series,
        opcoesFiltros=PanoramaFilterOptions(competencias=periods, municipios=municipalities, classes=classes),
    )
