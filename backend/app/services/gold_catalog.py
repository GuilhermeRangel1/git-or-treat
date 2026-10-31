"""Carrega e confere metadados locais para o futuro executor, sem SQL ou imports GenAI."""

from pathlib import Path

from sqlalchemy import BigInteger, DateTime, Float, Numeric, Text

from app.models.gold_v2 import TABLES
from app.schemas.genai_plan import ReadWindow, WindowKind
from app.schemas.gold_catalog import GoldCatalog

_CAPABILITY_TABLES = {
    "faturamento.receita": {"diagnostico_receita"},
    "faturamento.receita_bairro": {"consumo_receita_bairro"},
    "consumo.mensal_uc": {"consumo_mensal_uc"},
    "interrupcoes.dec_fec": {"indicadores_dec_fec"},
    "atendimento.mensal": {"atendimentos_uc"},
    "atendimento.uc_acumulado": {"visao_360_uc", "atendimentos_uc"},
}
_NULL_RULES = {
    "sum": "sum_ignores_null_all_null_is_absent",
    "ratio_of_sums": "ratio_absent_on_null_or_zero_denominator",
    "key_grain_read": "read_null_is_absent",
    "count_non_null": "count_requires_certified_zero",
    "average_non_null": "average_ignores_null_all_null_is_absent",
}
_TYPES = {"bigint": BigInteger, "double": Float, "decimal": Numeric, "string": Text}


def load_gold_catalog(payload: dict | None = None) -> GoldCatalog:
    """Falha antes de disponibilizar um catálogo incompatível com os modelos instalados."""
    approved = GoldCatalog.model_validate_json(
        (Path(__file__).parents[1] / "catalogs" / "gold_v2.json").read_text(
            encoding="utf-8"
        )
    )
    catalog = approved if payload is None else GoldCatalog.model_validate(payload)
    if len({m.metric_id for m in catalog.metrics}) != len(catalog.metrics):
        raise ValueError("Métrica duplicada no catálogo.")
    for metric in catalog.metrics:
        if not set(metric.required_capability_ids) <= _CAPABILITY_TABLES.keys():
            raise ValueError("Dependência do catálogo desconhecida.")
        if metric.capability_id != metric.sources[0].capability_id:
            raise ValueError("Fonte padrão inconsistente.")
        if (
            metric.aggregation in ("sum", "average_non_null")
            and metric.measure_type == "string"
        ):
            raise ValueError("Soma ou média exige medida numérica.")
        if metric.aggregation == "key_grain_read" and metric.granularities != (
            "month",
        ):
            raise ValueError("DEC/FEC exige granularidade mensal.")
        if metric.null_rule != _NULL_RULES[metric.aggregation]:
            raise ValueError("Regra de ausência inconsistente.")
        if bool(metric.accumulated_period_phrases) != (metric.max_window_days is None):
            raise ValueError("Limite de janela inconsistente com o modo temporal.")
        if metric.aggregation == "key_grain_read" and not metric.required_dimension_ids:
            raise ValueError("Leitura por chave exige filtro obrigatório.")
        if len({s.table for s in metric.sources}) != len(metric.sources):
            raise ValueError("Fonte duplicada.")
        dimensions = {d for s in metric.sources for d in s.dimension_columns}
        if set(metric.dimension_operators) != dimensions or any(
            not operators or len(set(operators)) != len(operators)
            for operators in metric.dimension_operators.values()
        ):
            raise ValueError("Operadores de filtro incompatíveis com as dimensões.")
        for source in metric.sources:
            if source.table not in _CAPABILITY_TABLES.get(source.capability_id, set()):
                raise ValueError("Tabela fora da capacidade autorizada.")
            table = TABLES[source.table]
            if tuple(source.grain) != tuple(c.name for c in table.primary_key):
                raise ValueError("Grão incompatível.")
            if (
                not set(metric.required_dimension_ids)
                <= source.dimension_columns.keys()
            ):
                raise ValueError("Dimensão obrigatória ausente.")
            columns = {
                *source.grain,
                *source.nullable_columns,
                *source.dimension_columns.values(),
            }
            columns.update(
                c
                for c in (
                    source.measure_column,
                    source.numerator_column,
                    source.denominator_column,
                    source.temporal_column,
                )
                if c
            )
            if not columns <= set(table.c.keys()):
                raise ValueError("Coluna fora do schema.")
            if source.temporal_transform == "utc_month":
                if (
                    source.capability_id != "atendimento.mensal"
                    or source.temporal_column != "data_abertura"
                    or not isinstance(table.c[source.temporal_column].type, DateTime)
                    or not table.c[source.temporal_column].type.timezone
                ):
                    raise ValueError("Projeção temporal incompatível.")
            elif source.temporal_column != (
                "competencia" if "competencia" in table.c else None
            ):
                raise ValueError("Coluna temporal incompatível.")
            if (
                source.temporal_transform == "identity"
                and source.temporal_column is not None
                and not isinstance(table.c[source.temporal_column].type, Text)
            ):
                raise ValueError("Competência deve ser texto no schema Gold v2.")
            if any(
                not isinstance(table.c[column].type, Text)
                for column in source.dimension_columns.values()
            ):
                raise ValueError("Dimensão deve ser texto no schema Gold v2.")
            ratio = metric.aggregation == "ratio_of_sums"
            if ratio:
                if (
                    source.measure_column
                    or not source.numerator_column
                    or not source.denominator_column
                    or metric.measure_type
                ):
                    raise ValueError("Razão malformada.")
                pairs = (
                    (source.numerator_column, metric.numerator_type),
                    (source.denominator_column, metric.denominator_type),
                )
            else:
                if (
                    not source.measure_column
                    or source.numerator_column
                    or source.denominator_column
                    or metric.numerator_type
                    or metric.denominator_type
                ):
                    raise ValueError("Medida malformada.")
                pairs = ((source.measure_column, metric.measure_type),)
            for column, kind in pairs:
                if kind is None or not isinstance(table.c[column].type, _TYPES[kind]):
                    raise ValueError("Tipo incompatível.")
            decimal_columns = {
                column for column, kind in pairs if kind == "decimal" and column is not None
            }
            if set(source.decimal_shapes) != decimal_columns:
                raise ValueError("Precisão decimal incompatível com as medidas.")
            for column, shape in source.decimal_shapes.items():
                physical_type = table.c[column].type
                if (
                    not isinstance(physical_type, Numeric)
                    or (physical_type.precision, physical_type.scale) != shape
                ):
                    raise ValueError("Precisão decimal diverge do contrato Gold v2.")
    # Compatibilidade física não aprova outra fórmula/população sob a mesma versão.
    # Mudanças de negócio devem entrar no artefato versionado e em sua revisão.
    if catalog != approved:
        raise ValueError("Catálogo diverge da definição semântica versionada.")
    return catalog


def select_catalog_source(
    catalog: GoldCatalog,
    metric_id: str,
    filter_ids: set[str],
    available_capabilities: set[str],
    window: dict,
):
    """Seleciona metadados; autorização de valores/lote e execução pertencem ao coordenador."""
    # Os mapas Pydantic são mutáveis apesar de ``frozen=True``; revalida o snapshot recebido
    # antes de qualquer seleção para não confiar em um catálogo alterado após o carregamento.
    catalog = load_gold_catalog(catalog.model_dump(mode="json"))
    metric = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
    if metric is None:
        raise ValueError("Métrica fora do catálogo.")
    window = ReadWindow.model_validate(window)
    if (
        window.granularity is not None
        and window.granularity not in metric.granularities
    ):
        raise ValueError("Granularidade indisponível para a métrica.")
    all_accumulated = {p for m in catalog.metrics for p in m.accumulated_period_phrases}
    if metric.accumulated_period_phrases:
        if (
            window.kind != WindowKind.CATALOG_PHRASE
            or window.granularity is not None
            or window.phrase not in metric.accumulated_period_phrases
        ):
            raise ValueError("Histórico acumulado não admite recorte por datas.")
    elif window.phrase in all_accumulated:
        raise ValueError("Métrica mensal exige período de calendário.")
    if (
        window.kind == WindowKind.BOUNDED
        and (
            metric.max_window_days is None
            or (window.end - window.start).days > metric.max_window_days
        )
    ):
        raise ValueError("Janela solicitada excede o limite da métrica.")
    if (
        not set(metric.required_capability_ids) <= available_capabilities
        or not set(metric.required_dimension_ids) <= filter_ids
    ):
        return None
    return next(
        (
            s
            for s in metric.sources
            if filter_ids <= s.dimension_columns.keys()
            and s.capability_id in available_capabilities
        ),
        None,
    )
