"""Fontes conceituais respeitam permissão e vigência antes de expor conteúdo."""

import hashlib
import json
from datetime import date

import pytest

from app.schemas.access import AccessContext
from app.tools.documentation import CORPUS, IndicatorDocumentation


def access(metrics):
    return AccessContext(
        caller_ref="user.test",
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        correlation_id="a" * 32,
        allowed_operations=frozenset({"read"}),
        allowed_metric_ids=frozenset(metrics),
        allowed_dimension_ids=frozenset(),
    )


def test_scope_is_applied_before_any_chunk_is_returned():
    source = IndicatorDocumentation()
    chunks = source.authorized_chunks(access({"billing.revenue"}), date(2026, 11, 3))
    assert [chunk.id for chunk in chunks] == ["revenue"]
    assert chunks[0].metric_ids == {"billing.revenue"}
    assert "não representa valor pago" in chunks[0].text
    assert source.authorized_chunks(access(set()), date(2026, 11, 3)) == ()


def test_individual_definitions_do_not_require_permission_for_related_metrics():
    source = IndicatorDocumentation()
    metric = "network.equivalent_interruption_duration"
    chunks = source.authorized_chunks(access({metric}), date(2026, 11, 3))
    assert len(chunks) == 1
    assert chunks[0].metric_ids == {metric}
    assert chunks[0].id == "metric-" + metric.replace(".", "-").replace("_", "-")
    assert "Frequência equivalente" not in chunks[0].text


def test_two_identities_do_not_share_authorized_documents():
    source = IndicatorDocumentation()
    first = access({"billing.revenue"}).model_copy(update={"caller_ref": "user.first"})
    second = access({"energy.consumption"}).model_copy(update={"caller_ref": "user.second"})
    assert [item.id for item in source.authorized_chunks(first, date(2026, 11, 3))] == ["revenue"]
    assert [item.id for item in source.authorized_chunks(second, date(2026, 11, 3))] == [
        "consumption"
    ]
    revoked = first.model_copy(update={"allowed_operations": frozenset()})
    assert source.authorized_chunks(revoked, date(2026, 11, 3)) == ()


def test_conflict_expiration_removal_and_version_change_take_effect_without_cache(tmp_path):
    path = tmp_path / "corpus.json"
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    revenue = next(entry for entry in corpus["entries"] if entry["id"] == "revenue")
    corpus["entries"] = [revenue]
    source = IndicatorDocumentation(path)

    def write():
        corpus["version"] = hashlib.sha256(
            json.dumps(
                corpus["entries"],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:12]
        path.write_text(json.dumps(corpus), encoding="utf-8")

    write()
    assert len(source.authorized_chunks(access({"billing.revenue"}), date(2026, 11, 3))) == 1
    corpus["entries"].append(dict(revenue))
    write()
    with pytest.raises(ValueError, match="conflito"):
        source.authorized_chunks(access({"billing.revenue"}), date(2026, 11, 3))
    corpus["entries"] = [revenue]
    revenue["validUntil"] = "2026-11-02"
    write()
    assert source.authorized_chunks(access({"billing.revenue"}), date(2026, 11, 3)) == ()
    corpus["entries"] = []
    write()
    assert source.authorized_chunks(access({"billing.revenue"}), date(2026, 11, 3)) == ()
