import asyncio
from contextlib import contextmanager
from decimal import Decimal
from threading import Event
from types import SimpleNamespace

import pytest
from app.services.genai_client import GenAITimeout
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_executor import execute_sql_admission
from app.services.genai_sql_result import SqlResultLimitExceeded

from tests.test_genai_sql_admission import Environment
from tests.test_genai_sql_result import Cursor
from tests.test_genai_sql_semantics import query
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


class Connection:
    def __init__(self):
        self.identity = ("venergy_genai_reader", "on", False, False)
        self.executed = []
        self.cursor = Cursor([(Decimal("150.01"),)])
        self.on_query = lambda: None

    def execute(self, statement, parameters):
        assert "set_config" in str(statement)
        assert 1 <= int(parameters["timeout"].removesuffix("ms")) <= 5000
        return SimpleNamespace(close=lambda: None)

    def exec_driver_sql(self, sql, parameters=None):
        if sql.startswith("SELECT current_user"):
            return SimpleNamespace(one=lambda: self.identity, close=lambda: None)
        self.executed.append((sql, parameters))
        self.on_query()
        return self.cursor

    def execution_options(self, **kwargs):
        assert kwargs == {"stream_results": True, "max_row_buffer": 1}
        return self


def environment(request):
    env = Environment(request)
    env.analytic_engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
        url=SimpleNamespace(username="venergy_genai_reader"), hide_parameters=True, echo=False)
    connection = Connection()
    env.snapshot_closed = False

    @contextmanager
    def snapshot(engine, *, validate_f1_catalog=False, dimension_ids=frozenset(),
                 metric_ids=frozenset(), source_capability_ids=None):
        assert engine is env.analytic_engine
        assert validate_f1_catalog is True
        assert dimension_ids == env.scope.allowed_dimension_ids
        try:
            yield connection
            env.assert_current(engine)
        finally:
            env.snapshot_closed = True

    env.execution_snapshot = snapshot
    return env, connection


def execute(env, candidate, admitted):
    return asyncio.run(execute_sql_admission(admitted, candidate, env.request, **env.kwargs()))


def test_executes_only_fresh_canonical_sql_and_bound_parameters(sql_request):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    result = execute(env, candidate, admitted)
    assert connection.executed == [(admitted.review.canonical_sql,
                                    dict(admitted.review.parameter_items))]
    assert result.result.rows == ((Decimal("150.01"),),)
    assert result.admission_digest == admitted.digest
    assert connection.cursor.closed and env.snapshot_closed


@pytest.mark.parametrize("identity", [
    ("postgres", "on", False, False), ("venergy_genai_reader", "off", False, False),
    ("venergy_genai_reader", "on", True, False), ("venergy_genai_reader", "on", False, True),
])
def test_rejects_wrong_role_or_writable_snapshot_before_candidate(sql_request, identity):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    connection.identity = identity
    with pytest.raises(SqlAdmissionDenied):
        execute(env, candidate, admitted)
    assert connection.executed == [] and env.snapshot_closed


def test_changed_scope_discards_rows(sql_request):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    connection.on_query = lambda: setattr(env, "scope", env.scope.model_copy(
        update={"allowed_metric_ids": frozenset()}))
    with pytest.raises(SqlAdmissionDenied):
        execute(env, candidate, admitted)
    assert connection.cursor.closed and env.snapshot_closed


def test_excess_result_closes_cursor_and_snapshot(sql_request):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    connection.cursor = Cursor([(Decimal(1),)] * 101)
    with pytest.raises(SqlResultLimitExceeded):
        execute(env, candidate, admitted)
    assert connection.cursor.closed and env.snapshot_closed


def test_deadline_during_read_discards_result(sql_request):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    connection.on_query = lambda: env.now.__setitem__(0, 21)
    with pytest.raises(GenAITimeout):
        execute(env, candidate, admitted)
    assert connection.cursor.closed and env.snapshot_closed


def test_cancellation_waits_for_worker_cleanup(sql_request):
    env, connection = environment(sql_request)
    candidate = query(sql_request)
    admitted = env.admit(candidate)
    started, release = Event(), Event()

    def blocked_query():
        started.set()
        assert release.wait(3), "test must release artificial blocking read"

    connection.on_query = blocked_query

    async def scenario():
        task = asyncio.create_task(execute_sql_admission(
            admitted, candidate, env.request, **env.kwargs()))
        assert await asyncio.to_thread(started.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(scenario())
    finally:
        release.set()
    assert connection.cursor.closed and env.snapshot_closed
