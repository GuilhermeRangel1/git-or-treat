"""Dicionário SQL da Gold v1 contra um SQLite sintético com os nomes reais das colunas.

Os dados do banco são sintéticos (ver ``tests/gold_mock.py``). O planejador abaixo existe só
neste teste: resolve um plano declarativo contra os metadados do TOML, monta SQL
parametrizado e o entrega a ``ReadOnlySqlService``, que valida, regenera e executa.
"""

import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

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
    MUNICIPIO_A,
    MUNICIPIO_B,
    MUNICIPIO_C,
    PRIORIDADES_ALTAS,
    build_gold_v1_sqlite,
    load_gold_dictionary,
    load_gold_metadata,
    load_gold_snapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_DATA_DICTIONARY = REPO_ROOT / "docs" / "dicionario_gold.md"
BACKEND_GOLD_MODEL = REPO_ROOT / "backend" / "app" / "models" / "gold_v1.py"

GOLD_TABLES = {
    "diagnostico_receita",
    "indicadores_dec_fec",
    "fila_inspecao",
    "visao_360_uc",
    "consumo_receita_bairro",
    "variacao_consumo_uc",
    "consumo_mensal_uc",
}
PERSONAL_COLUMNS = (
    "cpf_cnpj", "nome_titular", "logradouro", "numero", "cep", "latitude", "longitude"
)
_V1_TO_DICTIONARY_TYPE = {
    "string": "text",
    "long": "bigint",
    "double": "double",
    "date": "date",
    "boolean": "boolean",
}
# Fábricas de coluna de backend/app/models/gold_v1.py -> tipo do snapshot.
_BACKEND_TO_V1_TYPE = {
    "strings": "string",
    "integers": "long",
    "numbers": "double",
    "money": "decimal(38,2)",
    "dates": "date",
    "booleans": "boolean",
}
# Primeira palavra do "Tipo conceitual" de docs/dicionario_gold.md -> tipo do dicionário.
_DOC_TO_DICTIONARY_TYPE = {
    "texto": "text",
    "inteiro": "bigint",
    "número": "double",
    "decimal": "decimal(38,2)",
    "data": "date",
    "booleano": "boolean",
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


def test_gold_dictionary_loads_with_the_seven_v1_tables() -> None:
    dictionary = load_gold_dictionary()

    assert set(dictionary.tables) == GOLD_TABLES
    assert dictionary.version == "gold-v1-develop-c9580cd"
    assert dictionary.status == "gold-v1-nao-homologado"
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

    assert set(raw["tables"]) == GOLD_TABLES
    for name, spec in raw["tables"].items():
        allowed = set(dictionary.tables[name].columns)
        assert spec["description"], name
        assert spec["grain"], name
        assert set(spec["key"]) <= allowed, name
        assert set(spec["dimensions"]) <= allowed, name
        assert set(spec["metrics"]) <= allowed, name
        assert set(spec.get("known_values", {})) <= allowed, name
        if "period_column" in spec:
            assert spec["period_column"] in allowed, name
        assert {m["aggregation"] for m in spec["metrics"].values()} <= {"sum", "count", "ratio"}
        assert all(m["unit"] for m in spec["metrics"].values())
    assert raw["relationships"] == []


def test_nullable_columns_point_only_to_existing_columns_outside_the_key() -> None:
    """O Backend marca como anulável toda coluna fora da chave; a chave nunca é anulável."""

    raw = load_gold_metadata()["tables"]
    dictionary = load_gold_dictionary()

    for name, spec in raw.items():
        allowed = set(dictionary.tables[name].columns)
        nullable = spec["nullable_columns"]
        assert len(nullable) == len(set(nullable)), name
        assert set(nullable) <= allowed, name
        assert set(nullable) == allowed - set(spec["key"]), name


def test_each_concept_maps_to_the_real_column_of_each_table() -> None:
    concepts = load_gold_metadata()["concepts"]
    dictionary = load_gold_dictionary()

    assert concepts["geracao_distribuida"] == {
        "diagnostico_receita": "possui_gd",
        "visao_360_uc": "possui_gd",
        "variacao_consumo_uc": "possui_gd",
        "fila_inspecao": "possui_geracao_solar",
    }
    assert concepts["subgrupo_tarifario"] == {
        "diagnostico_receita": "subgrupo_tarifario",
        "visao_360_uc": "subgrupo",
        "fila_inspecao": "subgrupo",
    }
    assert concepts["classe_consumo"]["consumo_receita_bairro"] == "classe_consumo"
    assert concepts["classe_consumo"]["visao_360_uc"] == "classe"
    for mapping in concepts.values():
        for table, column in mapping.items():
            assert column in dictionary.tables[table].columns, (table, column)


def test_attendance_columns_exist_only_in_visao_360() -> None:
    """A fila agrega atendimentos no processamento, mas não os projeta na tabela final."""

    dictionary = load_gold_dictionary()
    attendance = {"total_chamados_callcenter", "media_satisfacao_atendimento"}

    assert attendance <= set(dictionary.tables["visao_360_uc"].columns)
    assert not attendance & set(dictionary.tables["fila_inspecao"].columns)


# --- (b) snapshot e coerência com as fontes ---------------------------------------------


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

    assert source["commit"].startswith("c9580cd")
    assert source["columns_from"] == "docs/dicionario_gold.md"
    assert source["types_keys_and_nullability_from"] == "backend/app/models/gold_v1.py"


def _documented_tables() -> dict[str, dict[str, str]]:
    """Colunas e primeira palavra do tipo conceitual de cada seção ``## N. `tabela` ``."""

    tables: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in GOLD_DATA_DICTIONARY.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^## \d+\. `(\w+)`", line)
        if heading:
            current = tables.setdefault(heading.group(1), {})
            continue
        if line.startswith("## "):
            current = None
            continue
        row = re.match(r"^\| `(\w+)` \| ([^|]+) \|", line)
        if current is not None and row:
            current[row.group(1)] = row.group(2).strip().split()[0].rstrip(":")
    return tables


def test_documented_columns_are_exactly_the_dictionary_columns() -> None:
    """docs/dicionario_gold.md é a fonte: o dicionário não pode derivar da documentação."""

    documented = _documented_tables()
    dictionary = load_gold_dictionary()
    snapshot = load_gold_snapshot()["tables"]

    assert set(documented) - {"controle_gold"} == GOLD_TABLES
    for name in GOLD_TABLES:
        assert list(documented[name]) == list(snapshot[name]["columns"]), name
        columns = dict(dictionary.tables[name].columns)
        assert {column.casefold() for column in documented[name]} == set(columns), name
        for column, doc_type in documented[name].items():
            assert _DOC_TO_DICTIONARY_TYPE[doc_type] == columns[column.casefold()], (
                name,
                column,
            )


def _backend_tables() -> dict[str, tuple[list[str], dict[str, str]]]:
    """Chave e colunas tipadas declaradas em ``TABLES`` de backend/app/models/gold_v1.py."""

    module = ast.parse(BACKEND_GOLD_MODEL.read_text(encoding="utf-8"))
    tables_node = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "TABLES" for t in node.targets)
    )
    tables: dict[str, tuple[list[str], dict[str, str]]] = {}
    for call in tables_node.values:
        name, key, strings = (ast.literal_eval(arg) for arg in call.args)
        groups = {"strings": strings} | {
            keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
        }
        columns = {
            column: _BACKEND_TO_V1_TYPE[group]
            for group, names in groups.items()
            for column in names.split()
        }
        tables[name] = (sorted(key), columns)
    return tables


def test_snapshot_types_and_keys_match_the_backend_physical_contract() -> None:
    backend = _backend_tables()
    snapshot = load_gold_snapshot()["tables"]

    assert set(backend) == GOLD_TABLES
    for name, (key, columns) in backend.items():
        assert sorted(snapshot[name]["key"]) == key, name
        assert snapshot[name]["columns"] == columns, name


def test_mock_rows_have_exactly_the_snapshot_columns() -> None:
    snapshot = load_gold_snapshot()["tables"]

    assert set(GOLD_ROWS) == GOLD_TABLES
    for name, rows in GOLD_ROWS.items():
        assert rows, name
        for row in rows:
            assert set(row) == set(snapshot[name]["columns"]), name


# --- (c) validador com o dicionário da Gold ---------------------------------------------


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT municipio, classe_consumo, SUM(receita_total_reais) AS receita "
            "FROM diagnostico_receita WHERE competencia = '2026-08' "
            "GROUP BY municipio, classe_consumo ORDER BY municipio, classe_consumo",
            [(MUNICIPIO_A, "COMERCIAL", 320.0), (MUNICIPIO_A, "RESIDENCIAL", 190.0),
             (MUNICIPIO_B, "COMERCIAL", 400.0), (MUNICIPIO_C, "RESIDENCIAL", 80.0)],
        ),
        (
            "SELECT id_alimentador, competencia, DEC, FEC FROM indicadores_dec_fec "
            "ORDER BY id_alimentador, competencia",
            [("ALIM-FIC-01", "2026-08", 2.0, 1.0), ("ALIM-FIC-01", "2026-09", 0.5, 1.0),
             ("ALIM-FIC-02", "2026-08", 2.5, 1.0)],
        ),
        (
            "SELECT prioridade_inspecao, COUNT(id_uc) AS ucs FROM fila_inspecao "
            "GROUP BY prioridade_inspecao ORDER BY prioridade_inspecao",
            [("ALTA - CONSUMO ZERO", 1), ("ALTA - HISTORICO IRREGULAR", 1), ("BAIXA", 2),
             ("MEDIA - NUNCA INSPECIONADO", 1), ("REVISAR - SEM HISTORICO DE CONSUMO", 1)],
        ),
        (
            "SELECT competencia, SUM(consumo_kwh) AS kwh, SUM(receita_reais) AS reais "
            "FROM consumo_mensal_uc GROUP BY competencia ORDER BY competencia",
            [("2026-08", 1200.0, 990.0), ("2026-09", 1060.0, 931.0)],
        ),
        (
            "SELECT id_uc FROM variacao_consumo_uc "
            "WHERE queda_consumo_superior_30_pct AND possui_gd = 'Sim' ORDER BY id_uc",
            [("UC100003",), ("UC100005",)],
        ),
        (
            "SELECT bairro, SUM(consumo_total_kwh) AS kwh FROM consumo_receita_bairro "
            "WHERE competencia = '2026-09' GROUP BY bairro ORDER BY bairro",
            [("BAIRRO FICTICIO 1", 300.0), ("BAIRRO FICTICIO 2", 150.0),
             ("BAIRRO FICTICIO 3", 520.0), ("BAIRRO FICTICIO 4", 90.0)],
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
    ("table", "energy", "revenue"),
    [
        ("consumo_mensal_uc", "consumo_kwh", "receita_reais"),
        ("consumo_receita_bairro", "consumo_total_kwh", "receita_total_reais"),
        ("diagnostico_receita", "consumo_total_kwh", "receita_total_reais"),
    ],
)
def test_financial_tables_of_the_mock_reconcile_by_period(
    gold_service, table: str, energy: str, revenue: str
) -> None:
    """Mesma interseção fatura × leitura nas três tabelas: totais iguais por competência."""

    service, _audit = gold_service

    result = service.run(
        f"SELECT competencia, SUM({energy}), SUM({revenue}) FROM {table} "
        "GROUP BY competencia ORDER BY competencia"
    )

    assert [tuple(row) for row in result.rows] == [
        ("2026-08", 1200.0, 990.0),
        ("2026-09", 1060.0, 931.0),
    ]


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
    ["controle_gold", "gold_diagnostico_receita", "silver_faturas", "gold_indicadores"],
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
        "DELETE FROM consumo_mensal_uc",
    ],
)
def test_writes_are_rejected(sql: str) -> None:
    with pytest.raises(SqlRejected) as caught:
        validate_sql(sql, load_gold_dictionary(), "sqlite")

    assert caught.value.code in {"not_select", "forbidden_construct"}


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        (
            "SELECT bairro, SUM(consumo_total_kwh) FROM diagnostico_receita GROUP BY bairro",
            "bairro existe na Gold, mas não em diagnostico_receita",
        ),
        (
            "SELECT id_uc, total_chamados_callcenter FROM fila_inspecao",
            "atendimento existe em visao_360_uc, não na fila",
        ),
        (
            "SELECT id_uc, subgrupo_tarifario FROM visao_360_uc",
            "nas tabelas por UC o nome real é subgrupo",
        ),
        (
            "SELECT possuo_gd FROM diagnostico_receita",
            "possuo_gd era grafia antiga; o real é possui_gd",
        ),
    ],
)
def test_column_from_another_table_or_old_name_is_rejected(sql: str, reason: str) -> None:
    with pytest.raises(SqlRejected, match="unknown_column"):
        validate_sql(sql, load_gold_dictionary(), "sqlite")


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
    filters: Mapping[str, tuple[str | bool, ...]] = field(default_factory=dict)
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
    parameters: list[str | bool] = []
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


def test_e2e_commercial_revenue_in_one_municipality(gold_service) -> None:
    """Duas tabelas declaram a receita por município e classe; ambas reconciliam no mock."""

    service, audit = gold_service
    plan = GoldPlan(
        measure="receita_total_reais",
        filters={"municipio": (MUNICIPIO_A,), "classe_consumo": ("COMERCIAL",)},
        by_period=True,
    )

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "consumo_receita_bairro"
    assert answer.unit == "R$"
    assert answer.rows == (("2026-08", 320.0), ("2026-09", 255.0))
    record = audit.records[-1]
    assert record.status == "accepted"
    assert record.tables == ("consumo_receita_bairro",)
    assert MUNICIPIO_A not in str(record.to_dict())
    assert '"consumo_receita_bairro"."classe_consumo" = ?' in record.query_template


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
    assert answer.unit == "horas por UC"
    assert answer.rows == (("2026-08", 2.0), ("2026-09", 0.5))


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


def test_e2e_neighbourhood_that_lost_most_volume(gold_service) -> None:
    """consumo_receita_bairro responde consumo mensal por bairro, antes sem evidência."""

    service, _audit = gold_service
    plan = GoldPlan(measure="consumo_total_kwh", group_by="bairro", by_period=True)

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "consumo_receita_bairro"
    assert answer.unit == "kWh"
    assert answer.rows == (
        ("2026-08", "BAIRRO FICTICIO 1", 400.0),
        ("2026-08", "BAIRRO FICTICIO 2", 200.0),
        ("2026-08", "BAIRRO FICTICIO 3", 500.0),
        ("2026-08", "BAIRRO FICTICIO 4", 100.0),
        ("2026-09", "BAIRRO FICTICIO 1", 300.0),
        ("2026-09", "BAIRRO FICTICIO 2", 150.0),
        ("2026-09", "BAIRRO FICTICIO 3", 520.0),
        ("2026-09", "BAIRRO FICTICIO 4", 90.0),
    )
    by_month = {(period, bairro): value for period, bairro, value in answer.rows}
    loss = {
        bairro: by_month[("2026-08", bairro)] - by_month[("2026-09", bairro)]
        for _period, bairro in by_month
    }
    assert max(loss, key=loss.get) == "BAIRRO FICTICIO 1"


def test_e2e_solar_ucs_with_drop_above_30_percent(gold_service) -> None:
    """variacao_consumo_uc responde a queda acima de 30% por UC com GD."""

    service, _audit = gold_service
    plan = GoldPlan(
        measure="id_uc",
        filters={"geracao_distribuida": ("Sim",), "queda_consumo_superior_30_pct": (True,)},
    )

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "variacao_consumo_uc"
    assert answer.unit == "UCs"
    assert answer.rows == ((2,),)


def test_e2e_monthly_consumption_of_one_uc(gold_service) -> None:
    service, _audit = gold_service
    plan = GoldPlan(measure="consumo_kwh", filters={"id_uc": ("UC100003",)}, by_period=True)

    answer = answer_from_gold(plan, service)

    assert answer.status == "ok"
    assert answer.table == "consumo_mensal_uc"
    assert answer.unit == "kWh"
    assert answer.rows == (("2026-08", 500.0), ("2026-09", 520.0))


def test_e2e_historical_average_by_period_has_no_evidence(gold_service) -> None:
    """media_consumo_historico só existe nas tabelas por UC, sem competência."""

    service, audit = gold_service
    before = len(audit.records)

    answer = answer_from_gold(
        GoldPlan(
            measure="media_consumo_historico",
            filters={"geracao_distribuida": ("Sim",)},
            group_by="id_uc",
            by_period=True,
        ),
        service,
    )

    assert answer.status == "no_evidence"
    assert answer.reason == "fila_inspecao não tem competência; visao_360_uc não tem competência"
    assert len(audit.records) == before


def test_logical_plan_reader_reads_gold_revenue_with_real_column_names(gold_service) -> None:
    """O leitor existente, sem mudança, aceita o dicionário da Gold v1 no mock sintético.

    O perfil de teste deriva do perfil demonstrativo trocando valores e unidade; o catálogo
    continua "artificial" porque os dados do mock são sintéticos.
    """

    service, audit = gold_service
    dictionary = load_gold_dictionary()
    profile_data = GRID360_DEMO_PROFILE.model_dump(mode="python")
    profile_data["dimensions"][0]["values"] = [
        DimensionValue(value=MUNICIPIO_A, aliases=("municipio ficticio a",))
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
                values=(MUNICIPIO_A,),
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

    assert result.rows == (("2026-08", 320.0), ("2026-09", 255.0))
    assert audit.records[-1].status == "accepted"
    assert audit.records[-1].tables == ("diagnostico_receita",)
