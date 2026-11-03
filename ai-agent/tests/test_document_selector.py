"""A saída do provedor é uma seleção fechada, nunca texto pronto para o usuário."""

import asyncio
import builtins
from datetime import date
from types import SimpleNamespace

import pytest

from app.providers.document_selector import DocumentSelectionUnavailable, GeminiDocumentSelector
from app.tools.documentation import IndicatorDocumentation
from tests.test_documentation_source import access


def test_optional_sdk_is_required_only_for_remote_selection(monkeypatch):
    original = builtins.__import__

    def without_google(name, *args, **kwargs):
        if name == "google":
            raise ImportError("SDK opcional ausente")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_google)
    service = GeminiDocumentSelector(api_key="fake", model="fake")
    chunks = IndicatorDocumentation().authorized_chunks(
        access({"billing.revenue"}), date(2026, 11, 3)
    )
    with pytest.raises(DocumentSelectionUnavailable):
        asyncio.run(service.select("O que é receita?", chunks))


@pytest.mark.parametrize(
    "text,reason,expected",
    [
        ('{"id":"revenue","sufficient":true}', "STOP", "revenue"),
        ('{"id":null,"sufficient":false}', "STOP", None),
        ('{"id":"secret.document"}', "STOP", "invalid"),
        ('{"id":"revenue", "sql":"SELECT 1"}', "STOP", "invalid"),
        ('{"id":"revenue","sufficient":true}', "MAX_TOKENS", "invalid"),
        ("not json", "STOP", "invalid"),
    ],
)
def test_provider_cannot_invent_source_or_expand_response(text, reason, expected):
    calls = []

    async def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=reason)])

    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    service = GeminiDocumentSelector(api_key="fake", model="fake", client=client)
    chunks = IndicatorDocumentation().authorized_chunks(
        access({"billing.revenue"}), date(2026, 11, 3)
    )
    if expected == "invalid":
        with pytest.raises(DocumentSelectionUnavailable):
            asyncio.run(service.select("O que é receita?", chunks))
    else:
        assert asyncio.run(service.select("O que é receita?", chunks)).id == expected
    assert len(calls) == 1
    assert "tools" not in calls[0]["config"]
    assert calls[0]["config"]["response_json_schema"]["properties"]["id"]["anyOf"][0]["enum"] == [
        "revenue"
    ]
