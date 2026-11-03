"""A saída do provedor é uma seleção fechada, nunca texto pronto para o usuário."""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.providers.document_selector import DocumentSelectionUnavailable, GeminiDocumentSelector
from app.tools.documentation import IndicatorDocumentation
from tests.test_documentation_source import access


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
