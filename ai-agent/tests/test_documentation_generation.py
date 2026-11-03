"""Atualizar um FAQ não altera a vigência de conceitos independentes."""

import importlib.util
import json
from pathlib import Path


def test_individual_selection_and_validity_do_not_follow_first_faq(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/generate-genai-documentation.py"
    spec = importlib.util.spec_from_file_location("documentation_generator", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.SOURCE = tmp_path / "faq.json"
    metrics = [
        {"metric_id": key, "label": key, "definition": "Definição de " + key}
        for key in ("billing.revenue", *module.INDIVIDUAL_METRICS, "future.metric")
    ]
    catalog = tmp_path / "backend/app/catalogs/gold_v2.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"metrics": metrics}), encoding="utf-8")
    source = {
        "catalogVersion": "gold-catalog-v2",
        "source": "Fonte de teste",
        "entries": [{
            "id": "revenue", "status": "withdrawn", "validUntil": "2026-11-02",
            "definitions": [{
                "metricId": "billing.revenue", "label": metrics[0]["label"],
                "text": metrics[0]["definition"],
            }],
        }],
    }
    module.SOURCE.write_text(json.dumps(source), encoding="utf-8")
    entries = json.loads(module.build())["entries"]
    assert entries[0]["status"] == "withdrawn"
    assert len(entries) == 8
    assert all(entry["status"] == "active" for entry in entries[1:])
    assert all(entry["validUntil"] is None for entry in entries[1:])
    assert all(entry["validFrom"] == "2026-11-03" for entry in entries[1:])
    assert all(entry["definitions"][0]["metricId"] != "future.metric" for entry in entries)
