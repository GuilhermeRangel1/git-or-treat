"""Empacota definições conceituais do FAQ e catálogo Gold v2; nunca lê datasets."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/src/shared/help/indicatorFaq.generated.json"
TARGET = ROOT / "ai-agent/app/corpora/indicators.json"
BACKEND_TARGET = ROOT / "backend/app/corpora/indicators.json"
INDIVIDUAL_METRICS = (
    "energy.average_consumption_per_uc",
    "network.equivalent_interruption_duration",
    "network.equivalent_interruption_frequency",
    "service.attendance",
    "service.satisfaction",
    "service.accumulated_attendance",
    "service.accumulated_satisfaction",
)


def build() -> str:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    catalog = json.loads(
        (ROOT / "backend/app/catalogs/gold_v2.json").read_text(encoding="utf-8")
    )
    metrics = {item["metric_id"]: item for item in catalog["metrics"]}
    for entry in source["entries"]:
        for definition in entry["definitions"]:
            metric = metrics[definition["metricId"]]
            if (
                definition["text"] != metric["definition"]
                or definition["label"] != metric["label"]
            ):
                raise ValueError(
                    "FAQ divergente do catálogo Gold v2; regenere a fonte primeiro."
                )
    # Preserve os verbetes comparativos; acrescente explicações individuais para
    # conceitos agrupados e métricas já definidas no catálogo autorizado.
    standalone = {
        entry["definitions"][0]["metricId"]
        for entry in source["entries"]
        if len(entry["definitions"]) == 1
    }
    for metric_id in INDIVIDUAL_METRICS:
        if metric_id in standalone:
            continue
        metric = metrics[metric_id]
        source["entries"].append(
            {
                "status": "active",
                "validFrom": "2026-11-03",
                "validUntil": None,
                "audience": "Pessoas usuárias do portal interno",
                "owner": "Dados/negócio (definição); Frontend/GenAI (publicação)",
                "id": "metric-" + metric["metric_id"].replace(".", "-").replace("_", "-"),
                "question": f"O que significa {metric['label']}?",
                "keywords": metric["label"].casefold().split(),
                "screens": ["assistente"],
                "definitions": [{
                    "metricId": metric["metric_id"],
                    "label": metric["label"],
                    "text": metric["definition"],
                }],
            }
        )
    source["version"] = hashlib.sha256(
        json.dumps(source["entries"], ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()[:12]
    return json.dumps(source, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()
    if args.check:
        for target in (TARGET, BACKEND_TARGET):
            if not target.exists() or target.read_text(encoding="utf-8") != expected:
                raise SystemExit(
                    "Corpus documental desatualizado; execute scripts/generate-genai-documentation.py."
                )
    else:
        for target in (TARGET, BACKEND_TARGET):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8")
    print("Corpus conceitual Gold v2 conferido.")
