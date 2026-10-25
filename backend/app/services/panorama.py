from datetime import datetime
from typing import Any

from app.repositories.panorama import PanoramaRepository
from app.schemas.panorama import PanoramaData, PanoramaMetric, PanoramaSeriesPoint
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
