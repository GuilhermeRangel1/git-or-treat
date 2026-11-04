from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / ".agents" / "run_hook.py"
PRETTIER = ROOT / "frontend" / "node_modules" / "prettier" / "bin" / "prettier.cjs"


class AntigravityCliTests(unittest.TestCase):
    def run_hook(
        self, action: str, event: dict[str, object]
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(CLI), action],
            cwd=ROOT,
            input=json.dumps(event),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result, json.loads(result.stdout)

    def test_safe_command_is_allowed(self) -> None:
        _, output = self.run_hook(
            "pre_tool",
            {
                "workspacePaths": [str(ROOT)],
                "toolCall": {"name": "run_command", "args": {"CommandLine": "git status --short"}},
            },
        )

        self.assertEqual(output, {"decision": "allow"})

    def test_sensitive_file_read_is_denied(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            _, output = self.run_hook(
                "pre_tool",
                {
                    "workspacePaths": [str(ROOT)],
                    "toolCall": {"name": "view_file", "args": {"AbsolutePath": str(env_path)}},
                },
            )

        self.assertEqual(output["decision"], "deny")
        self.assertNotIn(str(env_path), json.dumps(output))

    def test_fake_github_token_in_write_is_denied_without_echoing_token(self) -> None:
        fake_token = "ghp_" + "A" * 36
        _, output = self.run_hook(
            "pre_tool",
            {
                "workspacePaths": [str(ROOT)],
                "toolCall": {
                    "name": "write_to_file",
                    "args": {"TargetFile": str(ROOT / "README.md"), "CodeContent": fake_token},
                },
            },
        )

        self.assertEqual(output["decision"], "deny")
        self.assertNotIn(fake_token, json.dumps(output))

    def test_stop_gate_continues_when_completed_requirement_has_no_dated_evidence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "docs" / "PRD.md").write_text(
                "| IA-06 | Segurança | Concluído |\n",
                encoding="utf-8",
            )
            _, output = self.run_hook("stop", {"workspacePaths": [str(project)]})

        self.assertEqual(output["decision"], "continue")
        self.assertIn("IA-06", str(output.get("reason", "")))

    def test_stop_gate_allows_completed_requirement_with_dated_evidence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "docs" / "PRD.md").write_text(
                "| IA-06 | Segurança | Concluído |\n"
                "\n### 2026-10-22 — IA-06 verificação\n",
                encoding="utf-8",
            )
            _, output = self.run_hook("stop", {"workspacePaths": [str(project)]})

        self.assertEqual(output, {"decision": "allow"})

    @unittest.skipUnless(
        shutil.which("node") and PRETTIER.is_file(),
        "Node.js e Prettier local são necessários",
    )
    def test_post_tool_formats_frontend_file_through_cli(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".js",
            prefix="antigravity-hook-",
            dir=ROOT / "frontend",
            delete=False,
        ) as source:
            source.write("const answer={value:42}\n")
            target = Path(source.name)

        try:
            _, output = self.run_hook(
                "post_tool",
                {
                    "workspacePaths": [str(ROOT)],
                    "toolCall": {"name": "write_to_file", "args": {"TargetFile": str(target)}},
                },
            )

            self.assertEqual(output, {})
            self.assertEqual(target.read_text(encoding="utf-8"), "const answer = { value: 42 };\n")
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
