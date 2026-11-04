"""Composição do relatório ampliado sobre os avaliadores existentes."""

import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from app.generation.prompts import PROMPT_VERSION

from .evaluation_report import summarize_cases
from .gold_evaluation import DATASET_PATH, evaluate_gold_case, load_cases

ROOT = Path(__file__).parent


def dataset_digest():
    paths = [DATASET_PATH, *(ROOT / "fixtures" / name for name in (
        "genai_regression.json", "gold_language_eval.json", "gold_language_holdout.json",
    ))]
    canonical = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def _score(case, evaluate, **kwargs):
    try:
        return evaluate(case, **kwargs)
    except Exception:
        # O relatório público registra a falha, nunca a mensagem privada da exceção.
        return {"id": case["id"], "category": case.get("category", "question_flow"),
                "checks": {"evaluator_execution": False}, "outcome": "evaluator_error"}


def build_expanded_report(*, adapter=None, live_limit=None):
    from .test_genai_regression import (
        DATASET,
        build_gold_language_report,
        evaluate_case,
    )

    results = []
    if live_limit is None:
        for case in DATASET["cases"]:
            row = _score(case, evaluate_case)
            results.append({**row, "id": "LEGACY-" + row["id"],
                            "category": "legacy." + row["category"]})
        for name in ("gold_language_eval.json", "gold_language_holdout.json"):
            prefix = "LANG-" if name == "gold_language_eval.json" else "HOLDOUT-"
            for row in build_gold_language_report(name, include_checks=True)["cases"]:
                results.append({**row, "id": prefix + row["id"],
                                "category": "language." + row["category"]})
    numeric = load_cases()
    if live_limit is not None:
        if adapter is None or not 1 <= live_limit <= 6:
            raise ValueError("Amostra real exige adaptador e orçamento de 1 a 6 casos.")
        numeric = [case for case in numeric if case["id"].startswith("NUM-")][:live_limit]
    results.extend(_score(case, evaluate_gold_case, adapter=adapter) for case in numeric)
    report = summarize_cases(results)
    report.update({
        "report_type": "expanded_genai_evaluation_v1",
        "execution_scope": "gemini_artificial_aggregates" if live_limit else "offline_artificial",
        "dataset_digest": dataset_digest(),
        "versions": {"numeric_dataset": "1.1.0", "profile": "v-energy-grid-360-gold",
                     "legacy_dataset": DATASET["dataset_version"],
                     "physical_catalog": "gold-catalog-v2", "schema": "gold-csv-v2",
                     "prompt": PROMPT_VERSION, "model": "configured_gemini" if live_limit
                     else "fixed_test_adapter", "batch": json.loads(
                         DATASET_PATH.read_text(encoding="utf-8"))["batch_ref"]},
        "measurements": {"latency_ms": None, "cost": None,
                         "reason": "Determinismo offline; métricas reais em relatório separado."},
        "limitations": ["Não executa SQL Gold privado nem comprova cobertura dos dados.",
                         "Aviso público e perfis reais são verificados no Backend separadamente.",
                         "Holdout de linguagem é separado; precisão geral não é inferida."],
    })
    return report


def build_real_report(limit):
    from app.config import Settings
    from app.providers.gemini import GeminiModelAdapter

    if os.environ.get("GENAI_RUN_LIVE_SMOKE") != "1" or not 1 <= limit <= 6:
        raise ValueError("Provedor real exige opt-in e orçamento entre 1 e 6 casos.")
    settings = Settings()
    if settings.gemini_api_key is None:
        raise ValueError("Chave local Gemini ausente.")
    adapter = GeminiModelAdapter(model_name=settings.gemini_model,
                                 api_key=settings.gemini_api_key.get_secret_value())
    started = perf_counter()
    report = build_expanded_report(adapter=adapter, live_limit=limit)
    report["versions"]["model"] = settings.gemini_model
    report["measurements"] = {
        "latency_ms": round((perf_counter() - started) * 1000),
        "cost": None, "reason": "Tempo total observado; custo financeiro não disponível.",
        "maximum_cases": limit,
    }
    return report
