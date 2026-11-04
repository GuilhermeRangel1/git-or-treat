import hashlib
import json
import logging
from dataclasses import replace

import pytest

from app.sql.audit import (
    InMemoryAuditSink,
    LoggingAuditSink,
    QueryAuditRecord,
    SqlAuditContext,
    template_fingerprint,
)
from app.sql.executors import QueryExecutionError, SqliteReadOnlyExecutor
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected, ValidatedQuery
from tests.sql_support import build_gold_sqlite, load_test_dictionary

DICTIONARY = load_test_dictionary()
PLAN_AUDIT_CONTEXT = SqlAuditContext(plan_fingerprint="a" * 64, catalog_version="v1")


@pytest.mark.parametrize(
    ("fingerprint", "version"),
    [("pergunta privada", "v1"), ("a" * 64, "v1; municipio privado")],
)
def test_sql_audit_context_rejects_free_text(fingerprint: str, version: str) -> None:
    with pytest.raises(ValueError):
        SqlAuditContext(plan_fingerprint=fingerprint, catalog_version=version)


@pytest.fixture
def service_and_audit(tmp_path):
    path = build_gold_sqlite(tmp_path / "gold_teste.sqlite")
    executor = SqliteReadOnlyExecutor(
        path,
        max_rows=DICTIONARY.limits.max_rows,
        timeout_ms=DICTIONARY.limits.timeout_ms,
        dictionary=DICTIONARY,
        sensitive_columns=DICTIONARY.sensitive_columns,
    )
    audit = InMemoryAuditSink()
    return ReadOnlySqlService(DICTIONARY, executor, audit), audit


def test_accepted_query_is_audited_without_rows(service_and_audit) -> None:
    service, audit = service_and_audit
    sql = (
        "SELECT bairro, SUM(receita_total) AS receita FROM gold_indicadores "
        "WHERE municipio = 'Municipio Ficticio A' GROUP BY bairro LIMIT 10"
    )

    result = service.run(sql)

    [record] = audit.records
    assert record.status == "accepted"
    assert record.row_count == result.row_count == 2
    assert record.tables == ("gold_indicadores",)
    assert record.query_template is not None and record.query_template != sql
    assert record.query_template_sha256 == template_fingerprint(record.query_template)
    assert record.plan_fingerprint is None
    assert record.catalog_version is None
    assert record.limit_adjusted is False
    serialized = json.dumps(record.to_dict())
    assert "Municipio Ficticio A" not in serialized
    assert "?" in record.query_template
    for row in result.rows:
        for value in row:
            if isinstance(value, float):
                assert str(value) not in serialized
    assert "rows" not in record.to_dict()


def test_accepted_query_audit_keeps_template_without_filter_literals(service_and_audit) -> None:
    service, audit = service_and_audit
    literal = "AUDIT_PRIVATE_VALUE_73C1"
    sql = (
        "SELECT bairro FROM gold_indicadores "
        f"WHERE municipio = '{literal}' LIMIT 1"
    )

    service.run(sql)

    [record] = audit.records
    serialized = json.dumps(record.to_dict())
    assert record.query_template is not None
    assert "?" in record.query_template
    assert literal not in serialized
    raw_sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    assert raw_sql_hash not in serialized
    assert record.query_template_sha256 == template_fingerprint(record.query_template)


def test_accepted_query_audit_does_not_keep_user_defined_aliases(service_and_audit) -> None:
    service, audit = service_and_audit
    alias = "AUDIT_PRIVATE_ALIAS_91F2"
    sql = f'SELECT bairro AS "{alias}" FROM gold_indicadores LIMIT 1'

    service.run(sql)

    [record] = audit.records
    assert record.query_template is not None
    assert alias.casefold() not in record.query_template.casefold()
    assert alias.casefold() not in json.dumps(record.to_dict()).casefold()


def test_limit_adjustment_is_audited(service_and_audit) -> None:
    service, audit = service_and_audit

    service.run("SELECT bairro FROM gold_indicadores")
    service.run("SELECT bairro FROM gold_indicadores LIMIT 9999")

    missing, too_big = audit.records
    assert (missing.original_limit, missing.applied_limit, missing.limit_adjusted) == (
        None,
        DICTIONARY.limits.max_rows,
        True,
    )
    assert (too_big.original_limit, too_big.applied_limit, too_big.limit_adjusted) == (
        9999,
        DICTIONARY.limits.max_rows,
        True,
    )


def test_rejected_query_is_audited_without_received_text(service_and_audit) -> None:
    service, audit = service_and_audit
    sql = "SELECT uc_id FROM cadastro_teste WHERE nome_titular = 'Pessoa Ficticia Um' LIMIT 1"

    with pytest.raises(SqlRejected):
        service.run(sql, audit_context=PLAN_AUDIT_CONTEXT)

    [record] = audit.records
    assert record.status == "rejected"
    assert record.reason_code == "sensitive_column"
    assert record.plan_fingerprint == PLAN_AUDIT_CONTEXT.plan_fingerprint
    assert record.catalog_version == "v1"
    assert record.query_template is None
    assert record.query_template_sha256 is None
    assert record.row_count is None
    serialized = json.dumps(record.to_dict())
    assert "Pessoa Ficticia" not in serialized
    assert hashlib.sha256(sql.encode("utf-8")).hexdigest() not in serialized
    assert record.received_sql_chars == len(sql)


def test_failed_execution_is_audited(tmp_path) -> None:
    path = build_gold_sqlite(tmp_path / "gold_teste.sqlite")
    executor = SqliteReadOnlyExecutor(path, max_rows=10, timeout_ms=1000, dictionary=DICTIONARY)
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)
    # O dicionário promete uma tabela que o banco não tem: falha de execução, não recusa.
    path.unlink()
    path.write_bytes(b"")

    with pytest.raises(QueryExecutionError):
        service.run(
            "SELECT bairro FROM gold_indicadores LIMIT 1",
            audit_context=PLAN_AUDIT_CONTEXT,
        )

    [record] = audit.records
    assert record.status == "failed"
    assert record.reason_code == "database_error"
    assert record.error_type == "OperationalError"
    assert record.plan_fingerprint == PLAN_AUDIT_CONTEXT.plan_fingerprint
    assert record.catalog_version == "v1"
    assert record.query_template is not None
    assert record.row_count is None


def test_attack_never_reaches_executor(service_and_audit) -> None:
    service, audit = service_and_audit

    for sql in [
        "DROP TABLE gold_indicadores",
        "SELECT bairro FROM gold_indicadores LIMIT 1; DELETE FROM gold_indicadores",
        "WITH x AS (DELETE FROM gold_indicadores RETURNING bairro) SELECT bairro FROM x",
    ]:
        with pytest.raises(SqlRejected):
            service.run(sql)

    assert [r.status for r in audit.records] == ["rejected"] * 3
    assert service.run("SELECT COUNT(*) AS n FROM gold_indicadores").rows == ((8,),)


def test_table_reference_limit_is_audited_before_executor(service_and_audit, monkeypatch) -> None:
    service, audit = service_and_audit
    executor_calls = 0

    def fail_if_executed(query):
        nonlocal executor_calls
        executor_calls += 1
        pytest.fail("consulta acima do limite chegou ao executor")

    monkeypatch.setattr(service._executor, "execute", fail_if_executed)
    sql = " UNION ALL ".join(
        "SELECT municipio FROM gold_indicadores" for _ in range(6)
    )

    with pytest.raises(SqlRejected) as info:
        service.run(sql)

    assert info.value.code == "too_many_tables"
    assert executor_calls == 0
    [record] = audit.records
    assert record.status == "rejected"
    assert record.reason_code == "too_many_tables"


def test_bound_filter_value_stays_data_and_never_enters_audit(service_and_audit) -> None:
    service, audit = service_and_audit
    template = (
        "SELECT SUM(receita_total) AS receita FROM gold_indicadores "
        "WHERE municipio = ? AND competencia = ? LIMIT 1"
    )

    valid = service.run(template, parameters=("Municipio Ficticio A", "2025-01"))
    malicious = service.run(template, parameters=("Municipio Ficticio A' OR 1=1 --", "2025-01"))

    assert valid.rows == ((3500.5,),)
    assert malicious.rows == ((None,),)
    assert all("Municipio Ficticio A" not in json.dumps(item.to_dict()) for item in audit.records)


def test_bound_values_keep_sql_order_through_cte_and_subquery(service_and_audit) -> None:
    service, audit = service_and_audit
    sql = (
        "WITH mensal AS ("
        "SELECT receita_total, municipio FROM gold_indicadores WHERE competencia = ?"
        ") SELECT SUM(receita_total) AS receita FROM mensal "
        "WHERE municipio = ? AND receita_total > "
        "(SELECT MIN(receita_total) FROM gold_indicadores WHERE classe = ?) LIMIT 1"
    )

    result = service.run(
        sql, parameters=("2025-01", "Municipio Ficticio A", "comercial")
    )

    assert result.rows == ((2500.0,),)
    [record] = audit.records
    assert record.status == "accepted"
    assert record.query_template is not None
    assert "2025-01" not in json.dumps(record.to_dict())
    assert "Municipio Ficticio A" not in json.dumps(record.to_dict())


def test_parameter_mismatch_is_rejected_before_executor() -> None:
    class RecordingExecutor:
        dialect = "sqlite"

        def __init__(self) -> None:
            self.calls = 0

        def execute(self, query) -> None:
            self.calls += 1
            raise AssertionError("executor não deve ser chamado")

    executor = RecordingExecutor()
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)

    for sql, parameters in (
        ("SELECT bairro FROM gold_indicadores WHERE municipio = ? LIMIT 1", ()),
        ("SELECT bairro FROM gold_indicadores WHERE municipio = ? LIMIT 1", ("A", "B")),
        ("SELECT ? FROM gold_indicadores LIMIT 1", ("bairro",)),
    ):
        with pytest.raises(SqlRejected):
            service.run(sql, parameters=parameters)

    assert executor.calls == 0
    assert [record.status for record in audit.records] == ["rejected"] * 3


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT ? FROM gold_indicadores LIMIT 1",
        "SELECT SUM(?) FROM gold_indicadores LIMIT 1",
        "SELECT ?(bairro) FROM gold_indicadores LIMIT 1",
        "SELECT bairro FROM ? LIMIT 1",
        "SELECT bairro FROM gold_indicadores ORDER BY ? LIMIT 1",
        "WITH mensal AS (SELECT bairro FROM gold_indicadores WHERE municipio = ?) "
        "SELECT bairro FROM mensal ORDER BY ? LIMIT 1",
        "WITH mensal AS (SELECT segredo FROM gold_indicadores WHERE municipio = ?) "
        "SELECT segredo FROM mensal LIMIT 1",
        "SELECT bairro FROM gold_indicadores WHERE EXISTS "
        "(SELECT 1 FROM cadastro_teste WHERE cpf_cnpj = ?) LIMIT 1",
    ],
)
def test_structural_placeholders_are_rejected_before_executor(sql: str) -> None:
    class RecordingExecutor:
        dialect = "sqlite"

        def __init__(self) -> None:
            self.calls = 0

        def execute(self, query) -> None:
            self.calls += 1
            raise AssertionError("executor não deve ser chamado")

    executor = RecordingExecutor()
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)
    parameters = ("Municipio Ficticio A", "bairro") if sql.count("?") == 2 else ("bairro",)

    with pytest.raises(SqlRejected):
        service.run(sql, parameters=parameters)

    assert executor.calls == 0
    [record] = audit.records
    assert record.status == "rejected"


def test_prebuilt_validated_query_cannot_bypass_service_validation() -> None:
    class RecordingExecutor:
        dialect = "sqlite"

        def __init__(self) -> None:
            self.calls = 0

        def execute(self, query) -> None:
            self.calls += 1
            raise AssertionError("executor não deve ser chamado")

    executor = RecordingExecutor()
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)
    forged = ValidatedQuery(
        sql="SELECT segredo FROM interna_nao_listada LIMIT 1",
        sql_template="SELECT segredo FROM interna_nao_listada LIMIT 1",
        dialect="sqlite",
        tables=("gold_indicadores",),
        dictionary_version=DICTIONARY.version,
        applied_limit=1,
        original_limit=1,
        limit_adjusted=False,
    )

    with pytest.raises(SqlRejected) as info:
        service.run(forged)  # type: ignore[arg-type]

    assert info.value.code == "invalid_sql_input"
    assert executor.calls == 0
    [record] = audit.records
    assert record.status == "rejected"
    assert record.reason_code == "invalid_sql_input"
    assert record.received_sql_chars == 0
    assert "interna_nao_listada" not in json.dumps(record.to_dict())


def test_executor_dictionary_mismatch_is_audited_before_database_access(tmp_path) -> None:
    path = build_gold_sqlite(tmp_path / "gold_teste.sqlite")
    executor = SqliteReadOnlyExecutor(
        path,
        max_rows=10,
        timeout_ms=1000,
        dictionary=replace(DICTIONARY, version="outra-versao"),
    )
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)

    with pytest.raises(SqlRejected) as info:
        service.run("SELECT bairro FROM gold_indicadores LIMIT 1")

    assert info.value.code == "invalid_validated_query"
    [record] = audit.records
    assert record.status == "rejected"
    assert record.reason_code == "invalid_validated_query"
    assert record.row_count is None


def test_logging_sink_writes_one_json_line(caplog) -> None:
    record = QueryAuditRecord(
        status="rejected",
        dialect="sqlite",
        dictionary_version="teste",
        received_sql_chars=3,
        reason_code="not_select",
    )

    with caplog.at_level(logging.INFO, logger="app.sql.audit"):
        LoggingAuditSink().record(record)

    [message] = caplog.messages
    payload = json.loads(message)
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "not_select"
    assert "question" not in payload
