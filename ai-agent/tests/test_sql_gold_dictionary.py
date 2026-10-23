"""Dicionário SQL da Gold v1 contra um SQLite sintético com os nomes reais das colunas.

Os dados do banco são sintéticos (ver ``tests/gold_mock.py``). O planejador abaixo existe só
neste teste: resolve um plano declarativo contra os metadados do TOML, monta SQL
parametrizado e o entrega a ``ReadOnlySqlService``, que valida, regenera e executa.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.read_plan import ReadPlanValidator
from app.api.access import demo_access_context
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import (
    CatalogGranularity,
    DimensionValue,
    DomainProfile,
    FilterOperator,
)
from app.schemas.read_plan import LogicalReadPlan, ReadFilter, ReadWindow, WindowKind
from app.sql.audit import InMemoryAuditSink
from app.sql.executors import QueryResult, SqliteReadOnlyExecutor
from app.sql.plan import SqlMetricBinding, SqlPlanCatalog, SqlPlanReader
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected, validate_sql
from tests.gold_mock import (
    GOLD_ROWS,
    JABOATAO,
    PRIORIDADES_ALTAS,
    build_gold_v1_sqlite,
    load_gold_dictionary,
    load_gold_metadata,
    load_gold_snapshot,
)

GOLD_TABLES = {"diagnostico_receita", "indicadores_dec_fec", "fila_inspecao", "visao_360_uc"}
PERSONAL_COLUMNS = (
    "cpf_cnpj", "nome_titular", "logradouro", "numero", "cep", "latitude", "longitude"
)
_V1_TO_DICTIONARY_TYPE = {
    "string": "text",
    "long": "bigint",
    "double": "double",
    "date": "date",
}


@pytest.fixture(scope="module")
def gold_service(tmp_path_factory) -> tuple[ReadOnlySqlService, InMemoryAuditSink]:
    dictionary = load_gold_dictionary()
    database = build_gold_v1_sqlite(tmp_path_factory.mktemp("gold") / "gold_v1.sqlite")
    executor = SqliteReadOnlyExecutor(
        database,
        max_rows=dictionary.limits.max_rows,
        timeout_ms=dictionary.limits.timeout_ms,
        dictionary=dictionary,
    )
    audit = InMemoryAuditSink()
    return ReadOnlySqlService(dictionary, executor, audit), audit


# --- (a) carga e coerência do dicionário -------------------------------------------------


def test_gold_dictionary_loads_with_the_four_v1_tables() -> None:
    dictionary = load_gold_dictionary()

    assert set(dictionary.tables) == GOLD_TABLES
    assert dictionary.version == "gold-v1-31a80e6"
    assert set(PERSONAL_COLUMNS) <= dictionary.sensitive_columns
    for table in dictionary.tables.values():
        assert not set(table.columns) & dictionary.sensitive_columns
        assert not any(column.startswith("_") for column in table.columns)


def test_gold_dictionary_keeps_the_same_limits_as_the_artificial_dictionary() -> None:
    from app.sql.dictionary import load_dictionary

    assert load_gold_dictionary().limits == load_dictionary().limits


def test_semantic_metadata_only_points_to_allowed_columns() -> None:
    raw = load_gold_metadata()
    dictionary = load_gold_dictionary()

    for name, spec in raw["tables"].items():
        allowed = set(dictionary.tables[name].columns)
        assert set(spec["key"]) <= allowed, name
        assert set(spec["dimensions"]) <= allowed, name
        assert set(spec["metrics"]) <= allowed, name
        if "period_column" in spec:
            assert spec["period_column"] in allowed, name
        assert {m["aggregation"] for m in spec["metrics"].values()} <= {"sum", "count", "ratio"}
        assert all(m["unit"] for m in spec["metrics"].values())
    assert raw["relationships"] == []


def test_each_concept_maps_to_the_real_column_of_each_table() -> None:
    concepts = load_gold_metadata()["concepts"]
    dictionary = load_gold_dictionary()

    assert concepts["geracao_distribuida"] == {
        "diagnostico_receita": "possuo_gd",
        "visao_360_uc": "possui_gd",
        "fila_inspecao": "possui_geracao_solar",
    }
    assert concepts["classe_consumo"]["diagnostico_receita"] == "classe_consumo"
    assert concepts["classe_consumo"]["visao_360_uc"] == "classe"
    for mapping in concepts.values():
        for table, column in mapping.items():
            assert column in dictionary.tables[table].columns, (table, column)


# --- (b) snapshot do dicionário v1 ------------------------------------------------------


def test_allowed_plus_excluded_columns_match_the_v1_snapshot() -> None:
    """Falha se o v1 renomear, remover ou acrescentar coluna sem atualizar o TOML."""

    snapshot = load_gold_snapshot()["tables"]
    raw = load_gold_metadata()["tables"]
    dictionary = load_gold_dictionary()

    assert set(snapshot) == set(raw)
    for name, spec in snapshot.items():
        v1_columns = {column.casefold(): v1_type for column, v1_type in spec["columns"].items()}
        allowed = dict(dictionary.tables[name].columns)
        excluded = set(raw[name]["excluded_columns"])

        assert not set(allowed) & excluded, name
        assert set(allowed) | excluded == set(v1_columns), name
        assert excluded <= dictionary.sensitive_columns, name
        assert raw[name]["key"] == [column.casefold() for column in spec["key"]], name
        for column, sql_type in allowed.items():
            v1_type = v1_columns[column]
            expected = _V1_TO_DICTIONARY_TYPE.get(v1_type, v1_type)  # decimal(p,s) igual
            assert sql_type == expected, (name, column)


def test_snapshot_records_its_source_commit() -> None:
    source = load_gold_snapshot()["_source"]

    assert source["commit"].startswith("31a80e6")
    assert source["columns_from"] == "docs/dicionario_gold.md"


# --- (c) validador com o dicionário da Gold ---------------------------------------------


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT municipio, classe_consumo, SUM(receita_total_reais) AS receita "
            "FROM diagnostico_receita WHERE competencia = '2026-08' "
            "GROUP BY municipio, classe_consumo ORDER BY municipio, classe_consumo",
            [(JABOATAO, "COMERCIAL", 960.0), (JABOATAO, "RESIDENCIAL", 480.0),
             ("RECIFE", "COMERCIAL", 400.0)],
        ),
        (
            "SELECT id_alimentador, competencia, DEC, FEC FROM indicadores_dec_fec "
            "ORDER BY id_alimentador, competencia",
            [("ALIM-FIC-01", "2026-08", 1.5, 0.75), ("ALIM-FIC-01", "2026-09", 0.5, 0.25),
             ("ALIM-FIC-02", "2026-08", 2.5, 1.0), ("ALIM-FIC-02", "2026-09", 0.0, 0.0)],
        ),
        (
            "SELECT prioridade_inspecao, COUNT(id_uc) AS ucs FROM fila_inspecao "
            "GROUP BY prioridade_inspecao ORDER BY prioridade_inspecao",
            [("ALTA - CONSUMO ZERO", 1), ("ALTA - HISTORICO IRREGULAR", 1), ("BAIXA", 2),
             ("MEDIA - NUNCA INSPECIONADO", 1), ("REVISAR - SEM HISTORICO DE CONSUMO", 1)],
        ),
    ],
)
def test_correct_gold_queries_are_accepted_and_run_on_the_mock(
    gold_service, sql: str, expected: list[tuple]
) -> None:
    service, _audit = gold_service

    result = service.run(sql)

    assert [tuple(row) for row in result.rows] == expected


@pytest.mark.parametrize(
    "table", ["visao_360_uc", "fila_inspecao"]
)
@pytest.mark.parametrize("column", PERSONAL_COLUMNS)
def test_personal_columns_are_rejected_even_masked(table: str, column: str) -> None:
    with pytest.raises(SqlRejected) as caught:
        validate_sql(f"SELECT id_uc, {column} FROM {table}", load_gold_dictionary(), "sqlite")

    assert caught.value.code == "sensitive_column"


@pytest.mark.parametrize("column", ["_run_id", "_arquivo_origem", "_cpf_cnpj_conflitante"])
def test_pipeline_metadata_columns_are_rejected(column: str) -> None:
    with pytest.raises(SqlRejected) as caught:
        validate_sql(f"SELECT {column} FROM visao_360_uc", load_gold_dictionary(), "sqlite")

    assert caught.value.code == "sensitive_column"


def test_masked_personal_value_cannot_be_aliased_out(gold_service) -> None:
    service, audit = gold_service

    with pytest.raises(SqlRejected, match="sensitive_column"):
        service.run('SELECT id_uc AS "CPF_CNPJ" FROM fila_inspecao')
    assert audit.records[-1].status == "rejected"


@pytest.mark.parametrize(
    "table",
    ["consumo_receita_bairro", "variacao_consumo_uc", "silver_faturas", "gold_indicadores"],
)
def test_tables_outside_the_gold_dictionary_are_rejected(table: str) -> None:
    with pytest.raises(SqlRejected) as caught:
        validate_sql(f"SELECT municipio FROM {table}", load_gold_dictionary(), "sqlite")

    assert caught.value.code == "unknown_table"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM fila_inspecao",
        "UPDATE fila_inspecao SET prioridade_inspecao = 'BAIXA'",
        "INSERT INTO indicadores_dec_fec (id_alimentador) VALUES ('X')",
        "DROP TABLE visao_360_uc",
    ],
)
def test_writes_are_rejected(sql: str) -> None:
    with pytest.raises(SqlRejected) as caught:
        validate_sql(sql, load_gold_dictionary(), "sqlite")

    assert caught.value.code in {"not_select", "forbidden_construct"}


def test_column_from_another_gold_table_is_rejected() -> None:
    """bairro existe na Gold, mas não em diagnostico_receita."""

    with pytest.raises(SqlRejected, match="unknown_column"):
        validate_sql(
            "SELECT bairro, SUM(consumo_total_kwh) FROM diagnostico_receita GROUP BY bairro",
            load_gold_dictionary(),
            "sqlite",
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "O validador não lê 'relationships' do TOML: JOIN entre tabelas permitidas é aceito "
        "mesmo sem chave em comum declarada. Quando a proibição existir, este teste passa e o "
        "xfail estrito obriga a removê-lo."
    ),
)
def test_undeclared_join_between_receita_and_visao_360_is_rejected() -> None:
    sql = (
        "SELECT r.municipio, SUM(r.receita_total_reais), COUNT(v.id_uc) "
        "FROM diagnostico_receita AS r JOIN visao_360_uc AS v ON r.municipio = v.municipio "
        "GROUP BY r.municipio"
    )
    try:
        validate_sql(sql, load_gold_dictionary(), "sqlite")
    except SqlRejected:
        return
    raise AssertionError("JOIN não declarado foi aceito")


# --- (d) ponta a ponta: plano -> SQL regenerado -> execução no mock ----------------------


@dataclass(frozen=True)
class GoldPlan:
    """Plano declarativo de teste. Nomes podem ser coluna ou conceito de [concepts]."""

    measure: str
    filters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    group_by: str | None = None
    by_period: bool = False
    period_range: tuple[str, str] | None = None


@dataclass(frozen=True)
class GoldAnswer:
    status: str  # "ok" ou "no_evidence"
    table: str | None = None
    unit: str | None = None
    rows: tuple[tuple, ...] = ()
    reason: str = ""


def _resolve(name: str, table: str, raw: dict) -> str | None:
    mapped = raw["concepts"].get(name, {}).get(table)
    column = mapped or name
    spec = raw["tables"][table]
    return column if column in spec["dimensions"] or column in spec["key"] else None


def answer_from_gold(plan: GoldPlan, service: ReadOnlySqlService) -> GoldAnswer:
    """Escolhe a tabela pelos metadados do TOML; sem tabela capaz, devolve sem evidência."""

    raw = load_gold_metadata()
    misses: list[str] = []
    for table, spec in sorted(raw["tables"].items()):
        metric = spec["metrics"].get(plan.measure)
        if metric is None:
            continue
        period = spec.get("period_column")
        names = [*plan.filters, *([plan.group_by] if plan.group_by else [])]
        columns = {name: _resolve(name, table, raw) for name in names}
        missing = [name for name, column in columns.items() if column is None]
        if plan.by_period and period is None:
            missing.append("competência")
        if missing:
            misses.append(f"{table} não tem {', '.join(missing)}")
            continue
        if metric["aggregation"] == "ratio":
            fixed = {columns[n] for n, values in plan.filters.items() if len(values) == 1}
            fixed |= {period} if plan.by_period else set()
            fixed |= {columns[plan.group_by]} if plan.group_by else set()
            if not set(spec["key"]) <= fixed:
                misses.append(f"{plan.measure} é razão e exige a chave {spec['key']} fixada")
                continue
        return _run_plan(plan, table, spec, columns, metric, service)
    reason = "; ".join(misses) or f"nenhuma tabela declara a métrica {plan.measure}"
    return GoldAnswer(status="no_evidence", reason=reason)


def _run_plan(plan, table, spec, columns, metric, service) -> GoldAnswer:
    aggregation = metric["aggregation"]
    measure = {
        "sum": f'SUM("{plan.measure}")',
        "count": f'COUNT("{plan.measure}")',
        "ratio": f'"{plan.measure}"',
    }[aggregation]
    conditions: list[str] = []
    parameters: list[str] = []
    for name, values in plan.filters.items():
        if len(values) == 1:
            conditions.append(f'"{columns[name]}" = ?')
        else:
            conditions.append(f'"{columns[name]}" IN ({", ".join("?" for _ in values)})')
        parameters.extend(values)
    period = spec.get("period_column")
    if plan.period_range is not None:
        conditions.append(f'"{period}" BETWEEN ? AND ?')
        parameters.extend(plan.period_range)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    keys = ([f'"{period}" AS period'] if plan.by_period else []) + (
        [f'"{columns[plan.group_by]}" AS category'] if plan.group_by else []
    )
    aliases = ", ".join(key.rsplit(" AS ", 1)[1] for key in keys)
    group = (
        f" GROUP BY {', '.join(key.split(' AS ')[0] for key in keys)}"
        if keys and aggregation != "ratio"
        else ""
    )
    order = f" ORDER BY {aliases}" if keys else ""
    projection = ", ".join([*keys, f"{measure} AS value"])
    sql = f'SELECT {projection} FROM "{table}"{where}{group}{order}'
    result: QueryResult = service.run(sql, tuple(parameters))
    return GoldAnswer(
        status="ok", table=table, unit=metric["unit"], rows=tuple(map(tuple, result.rows))
    )


def test_e2e_commercial_revenue_in_jaboatao(gold_service) -> None:
    service, audit = gold_service
    plan = GoldPlan(
        measure="receita_total_reais",
        filters={"municipio": (JABOATAO,), "classe_consumo": ("COMERCIAL",)},
        by_period=True,
    )

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "diagnostico_receita"
    assert answer.unit == "R$"
    assert answer.rows == (("2026-08", 960.0), ("2026-09", 680.0))
    record = audit.records[-1]
    assert record.status == "accepted"
    assert record.tables == ("diagnostico_receita",)
    assert JABOATAO not in str(record.to_dict())
    assert '"diagnostico_receita"."classe_consumo" = ?' in record.query_template


def test_e2e_dec_of_one_feeder(gold_service) -> None:
    service, _audit = gold_service
    plan = GoldPlan(
        measure="dec",
        filters={"alimentador": ("ALIM-FIC-01",)},
        by_period=True,
        period_range=("2026-08", "2026-09"),
    )

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "indicadores_dec_fec"
    assert answer.unit == "horas"
    assert answer.rows == (("2026-08", 1.5), ("2026-09", 0.5))


def test_dec_without_fixing_the_feeder_is_not_summed(gold_service) -> None:
    """DEC é razão no grão alimentador × competência: somar alimentadores daria número falso."""

    service, _audit = gold_service

    answer = answer_from_gold(GoldPlan(measure="dec", by_period=True), service)

    assert answer.status == "no_evidence"
    assert "razão" in answer.reason


def test_e2e_count_of_high_priority_ucs(gold_service) -> None:
    service, _audit = gold_service
    plan = GoldPlan(measure="id_uc", filters={"prioridade_inspecao": PRIORIDADES_ALTAS})

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "fila_inspecao"
    assert answer.unit == "UCs"
    assert answer.rows == ((2,),)
    assert sum(
        row["prioridade_inspecao"].startswith("ALTA") for row in GOLD_ROWS["fila_inspecao"]
    ) == 2


def test_e2e_neighbourhood_that_lost_most_volume_has_no_evidence(gold_service) -> None:
    """Gold v1 não tem consumo mensal por bairro.

    O volume mensal (consumo_total_kwh) só existe em diagnostico_receita, sem bairro; o bairro
    só existe em visao_360_uc e fila_inspecao, com média histórica e sem competência. Sem a
    tabela consumo_receita_bairro da issue #40, a resposta correta é "não sei".
    """

    service, audit = gold_service
    before = len(audit.records)
    plan = GoldPlan(measure="consumo_total_kwh", group_by="bairro", by_period=True)

    answer = answer_from_gold(plan, service)

    assert answer.status == "no_evidence"
    assert answer.reason == "diagnostico_receita não tem bairro"
    assert len(audit.records) == before


def test_e2e_solar_ucs_with_drop_above_30_percent_has_no_evidence(gold_service) -> None:
    """Gold v1 não tem consumo mensal por UC.

    Queda acima de 30% exige consumo por UC em pelo menos dois meses. diagnostico_receita tem
    competência e GD (possuo_gd), mas não id_uc; visao_360_uc e fila_inspecao têm id_uc e GD,
    mas só média histórica, sem competência. Depende da variacao_consumo_uc da issue #40.
    """

    service, audit = gold_service
    before = len(audit.records)
    plan = GoldPlan(
        measure="consumo_total_kwh",
        filters={"geracao_distribuida": ("Sim",)},
        group_by="id_uc",
        by_period=True,
    )

    answer = answer_from_gold(plan, service)

    assert answer.status == "no_evidence"
    assert answer.reason == "diagnostico_receita não tem id_uc"
    assert len(audit.records) == before

    history = answer_from_gold(
        GoldPlan(
            measure="media_consumo_historico",
            filters={"geracao_distribuida": ("Sim",)},
            group_by="id_uc",
            by_period=True,
        ),
        service,
    )
    assert history.status == "no_evidence"
    assert history.reason == "fila_inspecao não tem competência; visao_360_uc não tem competência"


def test_logical_plan_reader_reads_gold_revenue_with_real_column_names(gold_service) -> None:
    """O leitor existente, sem mudança, aceita o dicionário da Gold v1 no mock sintético.

    O perfil de teste deriva do perfil demonstrativo trocando valores e unidade; o catálogo
    continua "artificial" porque os dados do mock são sintéticos.
    """

    service, audit = gold_service
    dictionary = load_gold_dictionary()
    profile_data = GRID360_DEMO_PROFILE.model_dump(mode="python")
    profile_data["dimensions"][0]["values"] = [
        DimensionValue(value=JABOATAO, aliases=("Jaboatão",))
    ]
    profile_data["dimensions"][1]["values"] = [
        DimensionValue(value="COMERCIAL", aliases=("comercial",))
    ]
    profile_data["metrics"][0]["unit"] = "R$"
    profile = DomainProfile.model_validate(profile_data)
    catalog = SqlPlanCatalog(
        profile_id=profile.profile_id,
        source_id="synthetic.sql",
        version="v1",
        dictionary_version=dictionary.version,
        table="diagnostico_receita",
        period_column="competencia",
        period_granularity=CatalogGranularity.MONTH,
        metrics={
            "billing.revenue": SqlMetricBinding(
                domain_id="revenue",
                unit="R$",
                column="receita_total_reais",
                aggregation="sum",
                dimension_ids=frozenset(
                    {"geography.municipality", "customer.consumption_class"}
                ),
                filter_operators=frozenset({FilterOperator.EQ, FilterOperator.IN}),
            )
        },
        dimensions={
            "geography.municipality": "municipio",
            "customer.consumption_class": "classe_consumo",
        },
    )
    policy = ReadAccessPolicy(profile, "synthetic.sql")
    validator = ReadPlanValidator(profile, "synthetic.sql", policy)
    context = demo_access_context(profile, "1" * 32, "synthetic.sql")
    plan = LogicalReadPlan(
        catalog_version="v1",
        operation="read",
        profile_id=profile.profile_id,
        source_id="synthetic.sql",
        domain_id="revenue",
        metric_id="billing.revenue",
        dimension_ids=("geography.municipality", "customer.consumption_class"),
        unit="R$",
        window=ReadWindow(
            kind=WindowKind.BOUNDED,
            start=date(2026, 8, 1),
            end=date(2026, 9, 30),
            granularity="month",
        ),
        filters=(
            ReadFilter(
                dimension_id="geography.municipality",
                operator=FilterOperator.EQ,
                values=(JABOATAO,),
            ),
            ReadFilter(
                dimension_id="customer.consumption_class",
                operator=FilterOperator.EQ,
                values=("COMERCIAL",),
            ),
        ),
        limit=10,
    )
    reader = SqlPlanReader(catalog, dictionary, service, validator)

    result = reader.read(validator.approve(plan, context), context)

    assert result.rows == (("2026-08", 960.0), ("2026-09", 680.0))
    assert audit.records[-1].status == "accepted"
    assert audit.records[-1].tables == ("diagnostico_receita",)
