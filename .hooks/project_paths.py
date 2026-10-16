"""Shared path helpers for Claude Code and Codex project hooks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def project_root(event: dict[str, Any]) -> Path:
    for value in (os.environ.get("CLAUDE_PROJECT_DIR"), event.get("cwd")):
        if value:
            candidate = Path(str(value)).resolve()
            for path in (candidate, *candidate.parents):
                if (path / ".git").exists() or (path / "docs" / "PRD.md").is_file():
                    return path
    current = Path.cwd().resolve()
    for path in (current, *current.parents):
        if (path / ".git").exists() or (path / "docs" / "PRD.md").is_file():
            return path
    return current
