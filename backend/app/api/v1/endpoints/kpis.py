from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import AnalyticalResponse, AnalyticalMetadata

router = APIRouter()

# Base sintética canônica correspondente aos controles do PRD e do protótipo Figma
SYNTHETIC_DATA: List[Dict[str, Any]] = [
    # 2024-04 (Total: Faturado R$ 76.500 | Pago R$ 74.200 | Consumo 90.000 kWh | Faturado 90.000 kWh | UCs 1.248)
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 21000.0, "receita_paga": 20300.0, "energia_consumida_kwh": 25000.0, "energia_faturada_kwh": 25000.0, "ucs_ativas": 520, "dec_horas": 1.20, "fec_vezes": 0.80},
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 12000.0, "receita_paga": 11800.0, "energia_consumida_kwh": 14000.0, "energia_faturada_kwh": 14000.0, "ucs_ativas": 80, "dec_horas": 1.15, "fec_vezes": 0.75},
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Industrial", "receita_faturada": 5000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 20, "dec_horas": 1.00, "fec_vezes": 0.60},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 12500.0, "receita_paga": 12100.0, "energia_consumida_kwh": 14500.0, "energia_faturada_kwh": 14500.0, "ucs_ativas": 310, "dec_horas": 1.45, "fec_vezes": 0.95},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Comercial", "receita_faturada": 7000.0, "receita_paga": 6900.0, "energia_consumida_kwh": 8500.0, "energia_faturada_kwh": 8500.0, "ucs_ativas": 50, "dec_horas": 1.40, "fec_vezes": 0.90},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Industrial", "receita_faturada": 3000.0, "receita_paga": 3000.0, "energia_consumida_kwh": 3500.0, "energia_faturada_kwh": 3500.0, "ucs_ativas": 10, "dec_horas": 1.30, "fec_vezes": 0.85},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Residencial", "receita_faturada": 8500.0, "receita_paga": 8200.0, "energia_consumida_kwh": 10000.0, "energia_faturada_kwh": 10000.0, "ucs_ativas": 220, "dec_horas": 1.50, "fec_vezes": 0.95},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Comercial", "receita_faturada": 5500.0, "receita_paga": 5400.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 30, "dec_horas": 1.42, "fec_vezes": 0.92},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Industrial", "receita_faturada": 2000.0, "receita_paga": 1500.0, "energia_consumida_kwh": 2500.0, "energia_faturada_kwh": 2500.0, "ucs_ativas": 8, "dec_horas": 1.38, "fec_vezes": 0.90},

    # 2024-03 (Total: Faturado R$ 80.000 | Pago R$ 78.500 | Consumo 100.000 kWh | Faturado 100.000 kWh | UCs 1.250)
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 22800.0, "receita_paga": 22300.0, "energia_consumida_kwh": 29000.0, "energia_faturada_kwh": 29000.0, "ucs_ativas": 522, "dec_horas": 1.30, "fec_vezes": 0.88},
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 12000.0, "receita_paga": 11900.0, "energia_consumida_kwh": 15000.0, "energia_faturada_kwh": 15000.0, "ucs_ativas": 80, "dec_horas": 1.25, "fec_vezes": 0.80},
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Industrial", "receita_faturada": 5000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 20, "dec_horas": 1.10, "fec_vezes": 0.65},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 13400.0, "receita_paga": 13100.0, "energia_consumida_kwh": 17000.0, "energia_faturada_kwh": 17000.0, "ucs_ativas": 310, "dec_horas": 1.55, "fec_vezes": 1.05},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Comercial", "receita_faturada": 7000.0, "receita_paga": 6900.0, "energia_consumida_kwh": 9000.0, "energia_faturada_kwh": 9000.0, "ucs_ativas": 50, "dec_horas": 1.48, "fec_vezes": 0.98},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Industrial", "receita_faturada": 3000.0, "receita_paga": 3000.0, "energia_consumida_kwh": 3500.0, "energia_faturada_kwh": 3500.0, "ucs_ativas": 10, "dec_horas": 1.40, "fec_vezes": 0.90},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Residencial", "receita_faturada": 9300.0, "receita_paga": 8900.0, "energia_consumida_kwh": 11000.0, "energia_faturada_kwh": 11000.0, "ucs_ativas": 220, "dec_horas": 1.60, "fec_vezes": 1.05},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Comercial", "receita_faturada": 5500.0, "receita_paga": 5400.0, "energia_consumida_kwh": 6500.0, "energia_faturada_kwh": 6500.0, "ucs_ativas": 30, "dec_horas": 1.50, "fec_vezes": 1.00},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Industrial", "receita_faturada": 2000.0, "receita_paga": 2000.0, "energia_consumida_kwh": 3000.0, "energia_faturada_kwh": 3000.0, "ucs_ativas": 8, "dec_horas": 1.45, "fec_vezes": 0.95},

    # 2024-05 (Período em aberto/incompleto)
    {"competencia": "2024-05", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 14000.0, "receita_paga": 8000.0, "energia_consumida_kwh": 16000.0, "energia_faturada_kwh": 16000.0, "ucs_ativas": 520, "dec_horas": 0.80, "fec_vezes": 0.40},
    {"competencia": "2024-05", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 8000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 9000.0, "energia_faturada_kwh": 9000.0, "ucs_ativas": 80, "dec_horas": 0.70, "fec_vezes": 0.35},
    {"competencia": "2024-05", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 9000.0, "receita_paga": 4500.0, "energia_consumida_kwh": 10000.0, "energia_faturada_kwh": 10000.0, "ucs_ativas": 310, "dec_horas": 0.90, "fec_vezes": 0.45},
]


def _calcular_comp_anterior(periodo: str, comparacao: str) -> Optional[str]:
    if comparacao == "nenhuma":
        return None
    try:
        ano, mes = map(int, periodo.split("-"))
        if comparacao == "ano_anterior":
            return f"{ano - 1:04d}-{mes:02d}"
        if mes == 1:
            return f"{ano - 1:04d}-12"
        return f"{ano:04d}-{mes - 1:02d}"
    except Exception:
        return None


def _somar_registros(registros: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not registros:
        return {
            "receita_faturada": 0.0,
            "receita_paga": 0.0,
            "energia_consumida": 0.0,
            "energia_faturada": 0.0,
            "ucs_ativas": 0,
            "dec_horas": 0.0,
            "fec_vezes": 0.0,
        }
    fat = sum(r["receita_faturada"] for r in registros)
    pag = sum(r["receita_paga"] for r in registros)
    con = sum(r["energia_consumida_kwh"] for r in registros)
    efat = sum(r["energia_faturada_kwh"] for r in registros)
    ucs = sum(r["ucs_ativas"] for r in registros)
    dec_pond = sum(r["dec_horas"] * r["ucs_ativas"] for r in registros)
    fec_pond = sum(r["fec_vezes"] * r["ucs_ativas"] for r in registros)
    return {
        "receita_faturada": round(fat, 2),
        "receita_paga": round(pag, 2),
        "energia_consumida": round(con, 2),
        "energia_faturada": round(efat, 2),
        "ucs_ativas": ucs,
        "dec_horas": round(dec_pond / ucs, 2) if ucs > 0 else 0.0,
        "fec_vezes": round(fec_pond / ucs, 2) if ucs > 0 else 0.0,
    }


def _montar_metrica(
    id_: str,
    nome: str,
    subtitulo: str,
    categoria: str,
    tipo_grandeza: str,
    val_atual: float,
    val_anterior: Optional[float],
    unidade: str,
    definicao: str,
    formula: str,
    bom_sentido: str = "positivo",
) -> Dict[str, Any]:
    tem_ant = val_anterior is not None
    base_zero = tem_ant and val_anterior == 0.0
    var_abs = None
    var_pct = None

    if tem_ant and not base_zero:
        var_abs = round(val_atual - val_anterior, 2)
        var_pct = round(((val_atual - val_anterior) / val_anterior) * 100, 2)
    elif tem_ant and base_zero:
        var_abs = round(val_atual, 2)
        var_pct = None

    return {
        "id": id_,
        "nome": nome,
        "subtitulo": subtitulo,
        "categoria": categoria,
        "tipoGrandeza": tipo_grandeza,
        "valorAtual": val_atual,
        "valorAnterior": val_anterior if tem_ant else None,
        "variacaoAbsoluta": var_abs,
        "variacaoPercentual": var_pct,
        "unidade": unidade,
        "definicao": definicao,
        "formula": formula,
        "baseZero": base_zero,
        "bomSentido": bom_sentido,
    }


@router.get("", summary="Listar indicadores agregados do Panorama")
def get_kpis(
    competencia: Optional[str] = Query("2024-04", description="Competência no formato YYYY-MM"),
    comparacao: Optional[str] = Query("anterior", description="Tipo de comparação (anterior, ano_anterior, nenhuma)"),
    municipio: Optional[str] = Query("todos", description="Filtro de município"),
    classe: Optional[str] = Query("todas", description="Classe de consumo"),
    db: Session = Depends(get_db),
):
    """
    Retorna métricas consolidadas e séries históricas do Panorama (WEB-01).
    Distinção explícita entre faturado/pago e consumido/faturado, com tratamento de base zero e período incompleto.
    """
    periodo = competencia or "2024-04"
    comp_tipo = comparacao or "anterior"
    mun = municipio or "todos"
    cla = classe or "todas"

    comp_anterior = _calcular_comp_anterior(periodo, comp_tipo)

    # Filtragem dos registros
    def filtrar(comp: str):
        return [
            r
            for r in SYNTHETIC_DATA
            if r["competencia"] == comp
            and (mun == "todos" or r["municipio"].lower() == mun.lower())
            and (cla == "todas" or r["classe"].lower() == cla.lower())
        ]

    registros_atuais = filtrar(periodo)
    registros_anteriores = filtrar(comp_anterior) if comp_anterior else []

    atual = _somar_registros(registros_atuais)
    anterior = _somar_registros(registros_anteriores) if comp_anterior else None

    preco_medio_atual = round(atual["receita_faturada"] / atual["energia_faturada"], 2) if atual["energia_faturada"] > 0 else 0.0
    preco_medio_ant = round(anterior["receita_faturada"] / anterior["energia_faturada"], 2) if anterior and anterior["energia_faturada"] > 0 else None

    is_incompleto = periodo == "2024-05"

    metricas = {
        "receitaFaturada": _montar_metrica(
            "rec_fat", "Receita Faturada", "Valor faturado em contas emitidas",
            "financeiro", "faturado", atual["receita_faturada"],
            anterior["receita_faturada"] if anterior else None, "R$",
            "Total monetário faturado no ciclo da competência.", "Σ(faturas_emitidas.valor_total)", "positivo"
        ),
        "receitaPaga": _montar_metrica(
            "rec_pag", "Receita Arrecadada / Paga", "Valor liquidado e recebido",
            "financeiro", "pago", atual["receita_paga"],
            anterior["receita_paga"] if anterior else None, "R$",
            "Total financeiro liquidado e recebido no período (distingue-se do faturado).", "Σ(pagamentos.valor_pago)", "positivo"
        ),
        "energiaConsumida": _montar_metrica(
            "ene_con", "Energia Consumida", "Volume medido nos medidores",
            "fisico", "consumido", atual["energia_consumida"],
            anterior["energia_consumida"] if anterior else None, "kWh",
            "Volume físico medido nos pontos de entrega das unidades consumidoras.", "Σ(medicoes.leitura_atual - leitura_anterior)", "positivo"
        ),
        "energiaFaturada": _montar_metrica(
            "ene_fat", "Energia Faturada", "Volume faturado nas contas",
            "fisico", "faturado", atual["energia_faturada"],
            anterior["energia_faturada"] if anterior else None, "kWh",
            "Volume de energia considerado para fins tarifários nas faturas.", "Σ(faturas.consumo_faturado_kwh)", "positivo"
        ),
        "precoMedioEfetivo": _montar_metrica(
            "prc_med", "Preço Médio Efetivo", "Receita faturada ÷ volume faturado",
            "financeiro", "faturado", preco_medio_atual, preco_medio_ant, "R$/kWh",
            "Tarifa média efetiva praticada no período. Não confundir com a tarifa homologada ANEEL.", "Receita Faturada / Energia Faturada", "positivo"
        ),
        "ucsAtivas": _montar_metrica(
            "ucs_atv", "UCs Ativas", "Unidades com contrato regular",
            "operacional", "operacao", atual["ucs_ativas"],
            anterior["ucs_ativas"] if anterior else None, "UCs",
            "Contagem de unidades consumidoras ativas no período.", "COUNT(DISTINCT uc_id WHERE status = 'ATIVO')", "positivo"
        ),
        "continuidadeDec": _montar_metrica(
            "cont_dec", "Duração Equivalente (DEC)", "DEC médio simplificado",
            "operacional", "operacao", atual["dec_horas"],
            anterior["dec_horas"] if anterior else None, "horas/UC",
            "Duração média simplificada das interrupções por unidade atendida.", "Σ(duracao × ucs_afetadas) / Total UCs", "negativo"
        ),
        "continuidadeFec": _montar_metrica(
            "cont_fec", "Frequência Equivalente (FEC)", "FEC médio simplificado",
            "operacional", "operacao", atual["fec_vezes"],
            anterior["fec_vezes"] if anterior else None, "interrupções/UC",
            "Frequência média simplificada de interrupções por unidade atendida.", "Σ(ucs_afetadas_interrupcao) / Total UCs", "negativo"
        ),
    }

    # Série mensal (últimas competências disponíveis)
    meses_hist = ["2024-03", "2024-04"]
    serie_mensal = []
    for c in meses_hist:
        regs_c = filtrar(c)
        s_c = _somar_registros(regs_c)
        serie_mensal.append({
            "competencia": c,
            "label": "Mar/24" if c == "2024-03" else "Abr/24",
            "receitaFaturada": s_c["receita_faturada"],
            "receitaPaga": s_c["receita_paga"],
            "energiaConsumidaKwh": s_c["energia_consumida"],
            "energiaFaturadaKwh": s_c["energia_faturada"],
            "ucsAtivas": s_c["ucs_ativas"],
            "decHoras": s_c["dec_horas"],
            "fecVezes": s_c["fec_vezes"],
        })

    filtros = {
        "periodo": periodo,
        "comparacao": comp_tipo,
        "municipio": mun,
        "classe": cla,
    }

    return AnalyticalResponse(
        data={
            "filtros": filtros,
            "periodoIncompleto": is_incompleto,
            "totalRegistros": len(registros_atuais),
            "dataAtualizacao": "2024-04-30T18:00:00Z",
            "loteVersao": "Lote Gold 2024.04-sintetico-v1",
            "metricas": metricas,
            "serieMensal": serie_mensal,
        },
        metadata=AnalyticalMetadata(
            periodo=periodo,
            filtros_aplicados=filtros,
            unidade="BRL / kWh / UCs / Horas",
            lote_gold_versao="Lote Gold 2024.04-sintetico-v1",
            qualidade_cobertura="Sintético Validado (PRD WEB-01)",
        ),
    )
