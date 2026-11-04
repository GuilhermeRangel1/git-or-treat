"""Agregação e comparação sanitizadas para o runner de regressão existente."""

import re
from collections import defaultdict

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("identificador de avaliação inválido")
    return value


def summarize_cases(cases: list[dict]) -> dict:
    """Só publica IDs, categorias e checks booleanos; nunca perguntas/respostas."""
    results = []
    seen = set()
    categories = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    dimensions = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for case in sorted(cases, key=lambda row: row["id"]):
        key = _identifier(case["id"])
        if key in seen:
            raise ValueError("caso duplicado na avaliação")
        seen.add(key)
        category = _identifier(case["category"])
        checks = {_identifier(k): v for k, v in sorted(case["checks"].items())}
        if not checks or any(type(value) is not bool for value in checks.values()):
            raise ValueError("checks devem conter resultados booleanos não vazios")
        passed = all(checks.values())
        outcome = _identifier(case.get("outcome", "passed" if passed else "unexpected_failure"))
        results.append({"id": key, "category": category, "checks": checks,
                        "passed": passed, "outcome": outcome})
        categories[category]["total"] += 1
        categories[category]["passed"] += int(passed)
        categories[category]["failed"] += int(not passed)
        for check, ok in checks.items():
            dimensions[check]["total"] += 1
            dimensions[check]["passed"] += int(ok)
            dimensions[check]["failed"] += int(not ok)
    passed = sum(row["passed"] for row in results)
    return {"summary": {"total": len(results), "passed": passed,
                        "failed": len(results) - passed,
                        "known_failures": sum(row["outcome"].startswith("known_failure")
                                              and not row["passed"] for row in results)},
            "categories": dict(sorted(categories.items())),
            "dimensions": dict(sorted(dimensions.items())), "cases": results}


def compare_reports(before: dict, after: dict) -> dict:
    """Casos/checks removidos nunca desaparecem no percentual agregado."""
    previous_summary = summarize_cases(before["cases"])
    current_summary = summarize_cases(after["cases"])
    old = {row["id"]: row for row in previous_summary["cases"]}
    new = {row["id"]: row for row in current_summary["cases"]}
    regressions, improvements, changed_known = [], [], []
    for key in sorted(old.keys() & new.keys()):
        previous, current = old[key], new[key]
        bad = sorted(k for k, ok in previous["checks"].items()
                     if ok and current["checks"].get(k) is not True)
        good = sorted(k for k, ok in previous["checks"].items()
                      if not ok and current["checks"].get(k) is True)
        removed_checks = sorted(previous["checks"].keys() - current["checks"].keys())
        bad += [k for k, ok in current["checks"].items()
                if not ok and k not in previous["checks"]]
        if bad or removed_checks or previous["category"] != current["category"]:
            regressions.append({"id": key, "checks": sorted(set(bad + removed_checks))})
        if good:
            improvements.append({"id": key, "checks": good})
        if previous.get("outcome", "").startswith("known_failure") and (
            previous["checks"] != current["checks"]
            or previous.get("outcome") != current.get("outcome")
        ):
            changed_known.append(key)
    removed, added = sorted(old.keys() - new.keys()), sorted(new.keys() - old.keys())
    incompatible = any(before.get(key) != after.get(key) for key in (
        "report_type", "dataset_digest", "execution_scope",
    ))
    new_failures = [key for key in added if not all(new[key]["checks"].values())]
    previous_categories = previous_summary["categories"]
    current_categories = current_summary["categories"]
    categories = {
        key: {"before": previous_categories.get(key), "after": current_categories.get(key)}
        for key in sorted(previous_categories.keys() | current_categories.keys())
    }
    return {"regressions": regressions, "improvements": improvements,
            "removed": removed, "added": added, "known_failure_changes": changed_known,
            "incompatible": incompatible, "categories": categories,
            "gate_passed": not (
                regressions or removed or changed_known or incompatible or new_failures
            )}


def summarize_backend_junit(path):
    """Extrai somente resultados das fronteiras autorizadas; descarta logs e nomes livres."""
    import hashlib
    from xml.etree import ElementTree

    modules = {
        "test_genai_continuity_observed": "backend.coverage",
        "test_genai_profile_access": "backend.authorization",
        "test_platform_authorization": "backend.permissions",
    }
    content = path.read_bytes()
    if len(content) > 10_000_000 or b"<!" in content:
        raise ValueError("JUnit não permitido")
    root = ElementTree.fromstring(content)
    cases, present = [], set()
    for node in root.iter("testcase"):
        module = node.get("classname", "").split(".")[-1]
        if module not in modules:
            continue
        present.add(module)
        digest = hashlib.sha256((module + node.get("name", "")).encode()).hexdigest()[:20]
        passed = all(node.find(tag) is None for tag in ("failure", "error", "skipped"))
        cases.append({"id": "BACKEND-" + digest, "category": modules[module],
                      "checks": {"contract": passed}})
    cases.append({"id": "BACKEND-COVERAGE", "category": "backend.coverage",
                  "checks": {"required_suites": present == set(modules)}})
    report = summarize_cases(cases)
    report.update({"report_type": "backend_boundary_evaluation_v1",
                   "execution_scope": "backend_contract_fixtures",
                   "dataset_digest": "backend-boundaries-v1",
                   "versions": {"physical_catalog": "gold-catalog-v2", "schema": "gold-csv-v2",
                                "prompt": "not_applicable", "model": "not_applicable",
                                "batch": "test_fixtures"},
                   "limitations": ["Fixtures e contratos; não é reconciliação Gold privada."]})
    return report
