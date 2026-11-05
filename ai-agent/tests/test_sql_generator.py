import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.protocols import (
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.providers.sql_generator import GeminiSqlGenerator


def payload():
    path = Path(__file__).resolve().parents[2] / "docs/contracts/examples/text-to-sql-f1-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))["valid"][0]


def generator(*, response=None, error=None):
    method = AsyncMock(return_value=response, side_effect=error)
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=method)))
    return GeminiSqlGenerator(client=client, model_name="test-model"), method


def test_generator_proposes_untrusted_candidate_using_closed_response_schema():
    row = payload()
    gen, method = generator(response=SimpleNamespace(text=json.dumps(row)))
    result = asyncio.run(gen.generate("{}", context_version=row["context_version"]))
    assert result.sql == row["sql"]
    assert result.status == "sql_candidate"
    assert method.await_count == 1
    config = method.call_args.kwargs["config"]
    assert config["response_json_schema"]["additionalProperties"] is False


@pytest.mark.parametrize("kind", ["malformed", "wrong_context", "truncated"])
def test_generator_rejects_invalid_stale_or_incomplete_output(kind):
    row = payload()
    version = row["context_version"]
    if kind == "wrong_context":
        row["context_version"] = "b" * 64
    response = SimpleNamespace(
        text="private-invalid-output" if kind == "malformed" else json.dumps(row)
    )
    if kind == "truncated":
        response.candidates = [SimpleNamespace(finish_reason="MAX_TOKENS")]
    gen, _ = generator(response=response)
    with pytest.raises(ModelProviderInvalidResponse) as exc:
        asyncio.run(gen.generate("{}", context_version=version))
    assert "private-invalid-output" not in str(exc.value)


@pytest.mark.parametrize(
    "status,expected",
    [
        (503, ModelProviderUnavailable),
        (429, ModelProviderUnavailable),
        (401, ModelProviderRejected),
    ],
)
def test_provider_errors_do_not_become_clarification_or_leak_details(status, expected):
    class ProviderError(Exception):
        code = status

    gen, method = generator(error=ProviderError("private-provider-detail"))
    with pytest.raises(expected) as exc:
        asyncio.run(gen.generate("{}", context_version="a" * 64))
    assert "private-provider-detail" not in str(exc.value)
    assert method.await_count == 1


def test_timeout_is_not_an_unsupported_analysis():
    async def wait(**kwargs):
        await asyncio.Event().wait()

    gen, method = generator()
    method.side_effect = wait
    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(gen.generate("{}", context_version="a" * 64, timeout_seconds=0.01))


def test_network_error_is_unavailable_not_rejected_analysis():
    gen, _ = generator(error=httpx.ConnectError("private-network-detail"))
    with pytest.raises(ModelProviderUnavailable) as exc:
        asyncio.run(gen.generate("{}", context_version="a" * 64))
    assert "private-network-detail" not in str(exc.value)


def test_invalid_budget_or_context_never_calls_provider():
    gen, method = generator()
    with pytest.raises(ValueError):
        asyncio.run(gen.generate("{}", context_version="a" * 64, timeout_seconds=0))
    with pytest.raises(ValueError):
        asyncio.run(gen.generate("x" * 65537, context_version="a" * 64))
    method.assert_not_called()


@pytest.mark.parametrize("configuration", [
    {"max_output_tokens": 0}, {"max_output_tokens": 4097}, {"max_output_tokens": True},
    {"temperature": float("nan")}, {"temperature": 2}, {"temperature": True},
])
def test_generator_configuration_is_bounded(configuration):
    with pytest.raises(ValueError):
        GeminiSqlGenerator(client=object(), model_name="test-model", **configuration)
