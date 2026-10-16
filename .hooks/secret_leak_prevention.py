"""Shared Claude Code/Codex PreToolUse hook for high-confidence secret exposure."""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePath


PATTERNS = {
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "Anthropic/OpenAI key": re.compile(r"\b(?:sk-ant-[A-Za-z0-9_-]{20,}|sk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,})\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def sensitive_path(path: str) -> bool:
    name = PurePath(path.replace("\\", "/")).name.lower()
    if name == ".env.example":
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.endswith((".pem", ".key", ".p12", ".pfx"))
        or name in {"id_rsa", "id_ed25519"}
    )


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        print("Hook de segredos: entrada JSON inválida.", file=sys.stderr)
        return 2

    tool = str(event.get("tool_name", ""))
    arguments = event.get("tool_input") or {}
    if not isinstance(arguments, dict):
        return 0

    file_path = str(arguments.get("file_path", arguments.get("path", "")))
    if file_path and sensitive_path(file_path):
        print("Hook de segredos: acesso direto a arquivo sensível bloqueado.", file=sys.stderr)
        return 2
    if tool == "apply_patch":
        patch = str(arguments.get("command", ""))
        for patched_path in re.findall(r"(?m)^\*\*\* (?:Update|Add|Delete) File: ([^\r\n]+)", patch):
            if sensitive_path(patched_path):
                print("Hook de segredos: alteração de arquivo sensível bloqueada.", file=sys.stderr)
                return 2

    if tool in {"Write", "Edit", "apply_patch"}:
        text = "\n".join(str(arguments.get(key, "")) for key in ("content", "new_string", "command"))
    elif tool in {"Bash", "PowerShell", "exec_command"}:
        text = str(arguments.get("command", arguments.get("cmd", "")))
        # High-confidence shell access to credential files; this is not a full shell parser.
        if re.search(
            r"(?i)\b(?:cat|type|Get-Content|head|tail|git\s+add)\b[^\r\n;|]*?"
            r"(?:^|[\\/\s'\"])\.env(?:\.[\w-]+)?\b",
            text,
        ):
            print("Hook de segredos: comando envolvendo arquivo .env bloqueado.", file=sys.stderr)
            return 2
    else:
        return 0

    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            print(f"Hook de segredos: possível {label} bloqueado; valor omitido.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
