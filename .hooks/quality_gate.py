"""Shared Claude Code/Codex Stop hook for PRD evidence and module checks."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from project_paths import project_root


MODULES = {"frontend", "backend", "data-engineering", "ai-agent"}


def changed_paths(root: Path) -> set[str]:
    git = shutil.which("git")
    if not git:
        return set()
    result = subprocess.run(
        [git, "status", "--porcelain", "--untracked-files=all"],
        cwd=root, capture_output=True, text=True, timeout=20, check=False,
    )
    if result.returncode:
        return set()
    paths = set()
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.replace("\\", "/"))
    return paths


def missing_prd_evidence(root: Path) -> list[str]:
    prd = root / "docs" / "PRD.md"
    if not prd.is_file():
        return ["docs/PRD.md ausente"]
    content = prd.read_text(encoding="utf-8")
    completed = set(re.findall(r"^\|\s*((?:DE|WEB|IA|ENT)-\d+)\s*\|[^\n]*\|\s*Concluído\s*\|", content, re.M))
    missing = []
    for req_id in sorted(completed):
        if not re.search(r"^###\s+\d{4}-\d{2}-\d{2}\s+—[^\n]*\b" + re.escape(req_id) + r"\b", content, re.M):
            missing.append(f"{req_id} está Concluído sem entrada datada no Registro de progresso")
    return missing


def run_check(command: list[str], cwd: Path, name: str, errors: list[str]) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False, env={**os.environ, "CI": "true"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"{name}: {type(exc).__name__}")
        return
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-5:]
        errors.append(f"{name} falhou (código {result.returncode}): {' | '.join(detail)[:700]}")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        print("Quality gate: entrada JSON inválida.", file=sys.stderr)
        return 2
    if event.get("stop_hook_active"):
        return 0  # Avoid an endless Stop loop; the original failure remains in the transcript.

    root = project_root(event)
    errors = missing_prd_evidence(root)
    paths = changed_paths(root)
    touched = {path.split("/", 1)[0] for path in paths if "/" in path} & MODULES

    for module in sorted(touched):
        folder = root / module
        code_paths = [p for p in paths if p.startswith(module + "/") and Path(p).suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}]
        if not code_paths:
            continue
        package = folder / "package.json"
        if package.is_file():
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            except (ValueError, UnicodeError):
                errors.append(f"{module}/package.json inválido")
                continue
            npm = shutil.which("npm")
            if not npm:
                errors.append(f"{module}: npm indisponível")
                continue
            for script in ("format:check", "lint", "typecheck", "test", "build"):
                if script in scripts:
                    run_check([npm, "run", script], folder, f"{module}: {script}", errors)
        python_paths = [root / p for p in code_paths if p.endswith(".py") and (root / p).is_file()]
        if python_paths:
            run_check([sys.executable, "-m", "py_compile", *map(str, python_paths)], folder, f"{module}: sintaxe Python", errors)
            if (folder / "tests").is_dir():
                run_check([sys.executable, "-m", "pytest", "-q"], folder, f"{module}: pytest", errors)

    if errors:
        print("Quality gate pendente:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2
    if event.get("hook_event_name") == "Stop":
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
