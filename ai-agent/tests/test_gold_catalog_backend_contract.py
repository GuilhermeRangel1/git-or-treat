"""O Backend recebe o mesmo catálogo físico, sem importar a GenAI."""
import json
import subprocess
import sys
from pathlib import Path

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING


def test_backend_artifact_matches_mapping_and_is_loadable_without_genai_imports():
    artifact = Path(__file__).resolve().parents[2] / "backend/app/catalogs/gold_v2.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == GRID360_GOLD_MAPPING.model_dump(
        mode="json"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.services.gold_catalog import load_gold_catalog; "
            "print(len(load_gold_catalog().metrics))",
        ],
        cwd=artifact.parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "14"


def test_business_metadata_matches_logical_profile_without_physical_names():
    artifact = Path(__file__).resolve().parents[2] / "backend/app/catalogs/gold_v2.json"
    data = json.loads(artifact.read_text(encoding="utf-8"))
    profile = {m.id: m for m in GRID360_GOLD_PROFILE.metrics}
    for metric in data["metrics"]:
        logical = profile[metric["metric_id"]]
        assert (metric["label"], metric["definition"], metric["unit"]) == (
            logical.label, logical.definition, logical.unit,
        )
        assert metric["label"] and metric["definition"]
        assert all(s["table"] not in metric["definition"] for s in metric["sources"])
