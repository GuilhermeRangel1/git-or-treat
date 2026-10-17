import json
import logging

import pytest

from app.sql.audit import InMemoryAuditSink, LoggingAuditSink, QueryAuditRecord, fingerprint
from app.sql.executors import QueryExecutionError, SqliteReadOnlyExecutor
from app.sql.service import ReadOnlySqlService
from app.sql.validator import SqlRejected
from tests.sql_support import build_gold_sqlite, load_test_dictionary

DICTIONARY = load_test_dictionary()


@pytest.fixture
def service_and_audit(tmp_path):
    path = build_gold_sqlite(tmp_path / "gold_teste.sqlite")
    executor = SqliteReadOnlyExecutor(
        path,
        max_rows=DICTIONARY.limits.max_rows,
        timeout_ms=DICTIONARY.limits.timeout_ms,
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
    assert record.executed_sql is not None and record.executed_sql != sql
    assert record.received_sql_sha256 == fingerprint(sql)
    assert record.limit_adjusted is False
    serialized = json.dumps(record.to_dict())
    for row in result.rows:
        for value in row:
            if isinstance(value, float):
                assert str(value) not in serialized
    assert "rows" not in record.to_dict()


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
        service.run(sql)

    [record] = audit.records
    assert record.status == "rejected"
    assert record.reason_code == "sensitive_column"
    assert record.executed_sql is None
    assert record.row_count is None
    assert "Pessoa Ficticia" not in json.dumps(record.to_dict())
    assert record.received_sql_chars == len(sql)


def test_failed_execution_is_audited(tmp_path) -> None:
    path = build_gold_sqlite(tmp_path / "gold_teste.sqlite")
    executor = SqliteReadOnlyExecutor(path, max_rows=10, timeout_ms=1000)
    audit = InMemoryAuditSink()
    service = ReadOnlySqlService(DICTIONARY, executor, audit)
    # O dicionário promete uma tabela que o banco não tem: falha de execução, não recusa.
    path.unlink()
    path.write_bytes(b"")

    with pytest.raises(QueryExecutionError):
        service.run("SELECT bairro FROM gold_indicadores LIMIT 1")

    [record] = audit.records
    assert record.status == "failed"
    assert record.reason_code == "database_error"
    assert record.error_type == "OperationalError"
    assert record.executed_sql is not None
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


def test_logging_sink_writes_one_json_line(caplog) -> None:
    record = QueryAuditRecord(
        status="rejected",
        dialect="sqlite",
        dictionary_version="teste",
        received_sql_sha256="abc",
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
