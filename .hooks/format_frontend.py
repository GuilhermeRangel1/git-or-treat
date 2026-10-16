"""Shared Claude Code/Codex PostToolUse hook for frontend formatting."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from project_paths import project_root


FORMATTABLE = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".html", ".json"}


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        print("Hook de formatação: entrada JSON inválida.", file=sys.stderr)
        return 2

    root = project_root(event)
    arguments = event.get("tool_input") or {}
    candidates = [arguments.get("file_path"), arguments.get("path")]
    command = arguments.get("command")
    if isinstance(command, str):
        import re

        candidates.extend(re.findall(r"(?m)^\*\*\* (?:Update|Add) File: ([^\r\n]+)", command))

    targets = set()
    for raw_path in candidates:
        if not isinstance(raw_path, str) or not raw_path:
            continue
        target = Path(raw_path)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        try:
            relative = target.relative_to(root)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] == "frontend" and target.suffix.lower() in FORMATTABLE and target.is_file():
            targets.add(target)
    if not targets:
        return 0

    prettier = root / "frontend" / "node_modules" / "prettier" / "bin" / "prettier.cjs"
    node = shutil.which("node")
    if not prettier.is_file() or not node:
        print("Hook de formatação: instale Prettier localmente em frontend/ para formatar este arquivo.", file=sys.stderr)
        return 2
    try:
        result = subprocess.run([node, str(prettier), "--write", *map(str, sorted(targets))], cwd=root / "frontend", capture_output=True, text=True, timeout=50, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Hook de formatação falhou: {type(exc).__name__}.", file=sys.stderr)
        return 2
    if result.returncode:
        print("Hook de formatação: Prettier falhou. " + (result.stderr or result.stdout)[-500:], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
