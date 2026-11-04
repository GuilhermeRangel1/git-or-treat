"""Consome a decomposição publicada; não recalcula o método de Dados no prompt."""

from decimal import ROUND_HALF_EVEN, Decimal, DecimalException

from sqlalchemy import case, func, literal, or_, select

from app.models.gold_v2 import TABLES
from app.schemas.genai_evidence import PublishedWindows

COMPONENTS = {
    "efeito_volume_reais": "Efeito volume",
    "efeito_preco_observado_reais": "Efeito preço observado",
    "efeito_interacao_reais": "Interação preço-volume",
    "variacao_entradas_reais": "Entradas na base",
    "variacao_saidas_reais": "Saídas da base",
    "variacao_sem_leitura_fora_base_reais": "Sem leitura fora da base",
    "variacao_outros_fora_base_reais": "Outras parcelas fora da base",
}
COUNTS = {
    "qtd_ucs_base_comum": "Participações de UCs na base comum",
    "qtd_ucs_observadas": "Participações de UCs observadas",
}
WINDOW_COLUMNS = ("inicio_p0", "fim_p0", "inicio_p1", "fim_p1", "metodo")
METADATA_COLUMNS = (*WINDOW_COLUMNS, "estado_decomposicao", "run_id_silver", "lote_bronze_silver")
FINANCIAL_COLUMNS = (*COMPONENTS, "variacao_faturamento_total_reais",
                     "faturamento_p0_reais", "faturamento_p1_reais", "residuo_reconciliacao_reais")


def published_windows(row) -> PublishedWindows:
    return PublishedWindows(
        p0_start=row["inicio_p0"], p0_end=row["fim_p0"],
        p1_start=row["inicio_p1"], p1_end=row["fim_p1"], method=row["metodo"],
    )


def _filters(plan):
    c = TABLES["decomposicao_receita"].c
    columns = {"geography.municipality": c.municipio, "geography.neighborhood": c.bairro,
               "customer.consumption_class": c.classe_consumo}
    return [columns[item.dimension_id].in_(item.values) for item in plan.filters]


def configured_windows(connection, plan) -> PublishedWindows | None:
    c = TABLES["decomposicao_receita"].c
    rows = connection.execute(select(*(c[name] for name in WINDOW_COLUMNS)).where(
        *_filters(plan), c.estado_decomposicao == "CALCULADA_BASE_COMUM",
    ).distinct().limit(2)).mappings().all()
    return published_windows(rows[0]) if len(rows) == 1 else None


def decomposition_query(plan):
    c = TABLES["decomposicao_receita"].c
    delta = c.variacao_faturamento_total_reais
    tolerance = func.greatest(literal(0.000001), func.abs(delta) * 0.000000001)
    components = sum((c[name] for name in COMPONENTS), literal(0))
    bad = or_(
        *(c[name].is_(None) for name in (*FINANCIAL_COLUMNS, *COUNTS,
                                        "qtd_ucs_entrantes", "qtd_ucs_saintes")),
        c.qtd_ucs_base_comum <= 0, c.qtd_ucs_observadas <= 0,
        c.qtd_ucs_base_comum > c.qtd_ucs_observadas,
        c.qtd_ucs_entrantes < 0, c.qtd_ucs_saintes < 0,
        c.qtd_ucs_base_comum + c.qtd_ucs_entrantes + c.qtd_ucs_saintes > c.qtd_ucs_observadas,
        func.abs(components - delta) > tolerance,
        func.abs(c.faturamento_p1_reais - c.faturamento_p0_reais - delta) > tolerance,
        func.abs(c.residuo_reconciliacao_reais) > tolerance,
    )
    metadata = [c[name] for name in METADATA_COLUMNS]
    return select(
        *metadata,
        *(func.sum(c[name]).label(name) for name in (*FINANCIAL_COLUMNS, *COUNTS)),
        func.sum(case((bad, 1), else_=0)).label("invalid_rows"),
    ).where(*_filters(plan)).group_by(*metadata).limit(2)


def decomposition_records(rows, plan, origin) -> tuple[list[dict], PublishedWindows]:
    if len(rows) != 1:
        raise ValueError("decomposição ausente ou com janelas/estados misturados")
    row = rows[0]
    if (row["estado_decomposicao"] != "CALCULADA_BASE_COMUM" or row["invalid_rows"] != 0
            or row["run_id_silver"] != origin["run_id_silver"]
            or row["lote_bronze_silver"] != origin["lote_bronze_silver"]):
        raise ValueError("decomposição sem reconciliação ou de outra origem")
    windows = published_windows(row)

    def number(name):
        value = Decimal(str(row[name]))
        if not value.is_finite():
            raise ValueError("componente não finito")
        return value

    try:
        delta = number("variacao_faturamento_total_reais")
        total = sum((number(name) for name in COMPONENTS), Decimal(0))
        if abs(total - delta) > max(Decimal("0.000001"), abs(delta) * Decimal("1e-9")):
            raise ValueError("componentes não reconciliados")
        financial = {**COMPONENTS, "variacao_faturamento_total_reais": "Variação total"}
        records = [{"label": label, "unit": "R$", "period": plan.window.phrase,
                    "value": float(number(name).quantize(Decimal("0.01"), ROUND_HALF_EVEN))}
                   for name, label in financial.items()]
        for name, label in COUNTS.items():
            count = number(name)
            if count < 0 or count != count.to_integral_value():
                raise ValueError("contagem de participações inválida")
            records.append({"label": label, "unit": "participações",
                            "period": plan.window.phrase, "value": int(count)})
    except DecimalException:
        raise ValueError("decomposição fora do limite numérico") from None
    if number("qtd_ucs_base_comum") <= 0 or (
        number("qtd_ucs_base_comum") > number("qtd_ucs_observadas")
    ):
        raise ValueError("base comum vazia ou maior que a população observada")
    return records, windows


def window_months(windows: PublishedWindows) -> tuple[str, ...]:
    months = []
    for start, end in ((windows.p0_start, windows.p0_end), (windows.p1_start, windows.p1_end)):
        year, month = map(int, start.split("-"))
        while f"{year:04d}-{month:02d}" <= end:
            months.append(f"{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(months)
