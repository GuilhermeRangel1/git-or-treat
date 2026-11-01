"""Publication schema gate for DEV13.1 analytic consumers."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.models.gold_v2_load import BATCH
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.repositories.gold_context import load_gold_context
from app.schemas.gold import GoldMetadata
from app.services.analytics import AnalyticsAPIError


@pytest.fixture
def published_context_connection():
    engine = create_engine("sqlite://")
    BATCH.create(engine)
    with engine.begin() as connection:
        connection.execute(BATCH.insert().values(
            id=1,
            lote="context-v2-test",
            schema_version="gold-csv-v2",
            fingerprint="a" * 64,
            importado_em=datetime(2026, 10, 31, tzinfo=timezone.utc),
            manifesto={},
        ))
    with engine.connect() as connection:
        yield connection
    engine.dispose()


def test_context_accepts_v2_publication_and_preserves_identity(published_context_connection):
    context = load_gold_context(
        published_context_connection,
        expected_lote="context-v2-test",
        expected_fingerprint="a" * 64,
    )

    assert context.connection is published_context_connection
    assert context.schema_version == "gold-csv-v2"
    assert context.lote == "context-v2-test"
    assert context.fingerprint == "a" * 64


def test_gold_metadata_defaults_to_v2_physical_schema_without_changing_http_contract():
    schema = GoldMetadata.model_json_schema()

    assert schema["properties"]["schema_version"]["default"] == "gold-csv-v2"
    assert schema["properties"]["contract_version"]["default"] == "2.0.0"


@pytest.mark.parametrize("schema_version", ["gold-csv-v1", "unknown-v9"])
def test_context_fails_closed_for_non_v2_publications(published_context_connection, schema_version):
    published_context_connection.execute(
        BATCH.update().values(schema_version=schema_version)
    )

    with pytest.raises(AnalyticsSourceUnavailable):
        load_gold_context(published_context_connection)


@pytest.mark.parametrize(
    ("expected_lote", "expected_fingerprint"),
    [("older-batch", "a" * 64), ("context-v2-test", "b" * 64)],
)
def test_context_rejects_stale_publication_guards(
    published_context_connection, expected_lote, expected_fingerprint,
):
    with pytest.raises(AnalyticsAPIError) as error:
        load_gold_context(
            published_context_connection,
            expected_lote=expected_lote,
            expected_fingerprint=expected_fingerprint,
        )

    assert error.value.status_code == 409
    assert error.value.code == "stale_batch"


def test_context_rejects_malformed_expected_fingerprint(published_context_connection):
    with pytest.raises(AnalyticsAPIError) as error:
        load_gold_context(
            published_context_connection,
            expected_fingerprint="not-a-fingerprint",
        )

    assert error.value.status_code == 422
    assert error.value.code == "invalid_query"
