"""Distinguish absent observations, unusable bases and observed zero in Gold."""
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import operations as routes
from app.services.operations import (
    build_gold_operation_summary,
    gold_operation_points,
    gold_operation_series,
)


@pytest.mark.parametrize(
    "observed,denominator,expected",
    [(False, None, "empty"), (True, None, "unavailable"), (True, 10, "partial")],
)
def test_gold_window_state_depends_on_observations_not_feeder_inventory(
    monkeypatch, observed, denominator, expected,
):
    class Repository:
        context = SimpleNamespace(
            lote="artificial", schema_version="gold-csv-v2", fingerprint="a" * 64,
            imported_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        def options(self):
            return ["2026-01"], {"F1": "Artificial"}

        def aggregate(self, *_args):
            if not observed:
                return []
            return [{
                "feeder_id": "F1", "municipality": "Artificial", "competencia": "2026-01",
                "observed_rows": 1, "min_denominator": denominator, "max_denominator": denominator,
                "denominator_values": int(denominator is not None),
                "duration_sum": 0, "interruption_count": 0, "duration_values": 1, "count_values": 1,
            }]

    repository = Repository()
    points, metadata = gold_operation_points(repository, "2026-01", "2026-01")
    series = gold_operation_series(repository, "2026-01", "2026-01")
    summary = build_gold_operation_summary(repository, "2026-01", "2026-01")
    monkeypatch.setattr(routes, "GoldOperationsRepository", lambda _context: repository)
    ranking = routes.get_operation_ranking(
        period=("2026-01", "2026-01"), alimentador=None, metric="dec", municipio=None,
        gold_context=repository.context, repository_provider=None,
    )

    assert metadata.status == series.metadata.status == summary.metadata.status == ranking.metadata.status == expected
    assert points[0].status == series.data.items[0].status == summary.data.status == expected
    assert summary.data.dec_status == summary.data.fec_status == expected
    if expected == "partial":
        assert summary.data.dec_hours_per_uc == summary.data.fec_interruptions_per_uc == 0
        assert len(ranking.data.items) == 1
    else:
        assert summary.data.dec_hours_per_uc is summary.data.fec_interruptions_per_uc is None
        assert ranking.data.items == []
