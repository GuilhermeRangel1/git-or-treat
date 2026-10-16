"""Antigravity lifecycle hook bridge.

Translates Antigravity hook events (toolCall, camelCase stdin, JSON stdout contracts)
to the shared project hook scripts in .hooks/.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT_HOOKS = Path(__file__).resolve().parent
if str(ROOT_HOOKS) not in sys.path:
    sys.path.insert(0, str(ROOT_HOOKS))

import format_frontend
import quality_gate
import secret_leak_prevention


def handle_pre_tool() -> int:
    try:
        raw_input = sys.stdin.read()
        event = json.loads(raw_input) if raw_input.strip() else {}
    except Exception as exc:
        print(json.dumps({"decision": "deny", "reason": f"Entrada JSON inválida: {exc}"}))
        return 0

    tool_call = event.get("toolCall") or {}
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args") or {}

    workspace_paths = event.get("workspacePaths") or []
    cwd = workspace_paths[0] if workspace_paths else str(Path.cwd())
    translated_event = {"cwd": cwd}

    if tool_name == "run_command":
        cmd = args.get("CommandLine", "")
        translated_event["tool_name"] = "PowerShell"
        translated_event["tool_input"] = {"command": cmd, "cmd": cmd}
    elif tool_name in {
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }:
        translated_event["tool_name"] = "Write" if tool_name == "write_to_file" else "Edit"
        content = args.get("CodeContent", args.get("ReplacementContent", ""))
        if tool_name == "multi_replace_file_content":
            chunks = args.get("ReplacementChunks") or []
            content = "\n".join(
                str(chunk.get("ReplacementContent", ""))
                for chunk in chunks
                if isinstance(chunk, dict)
            )
        target = args.get("TargetFile", "")
        translated_event["tool_input"] = {
            "file_path": target,
            "path": target,
            "content": content,
            "new_string": content,
        }
    elif tool_name == "view_file":
        target = args.get("AbsolutePath", "")
        translated_event["tool_name"] = "Read"
        translated_event["tool_input"] = {"file_path": target, "path": target}
    else:
        print(json.dumps({"decision": "allow"}))
        return 0

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdin = io.StringIO(json.dumps(translated_event))
    capture_out = io.StringIO()
    capture_err = io.StringIO()
    sys.stdout = capture_out
    sys.stderr = capture_err

    try:
        code = secret_leak_prevention.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    if code == 0:
        print(json.dumps({"decision": "allow"}))
    else:
        err_msg = capture_err.getvalue().strip() or "Bloqueado pelo hook de prevencao de segredos."
        print(json.dumps({"decision": "deny", "reason": err_msg}))
    return 0


def handle_post_tool() -> int:
    try:
        raw_input = sys.stdin.read()
        event = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        print("{}")
        return 0

    tool_call = event.get("toolCall") or {}
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args") or {}

    workspace_paths = event.get("workspacePaths") or []
    cwd = workspace_paths[0] if workspace_paths else str(Path.cwd())
    translated_event = {"cwd": cwd}

    if tool_name in {
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }:
        target = args.get("TargetFile", "")
        translated_event["tool_name"] = "Write"
        translated_event["tool_input"] = {"file_path": target, "path": target}

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdin = io.StringIO(json.dumps(translated_event))
    capture_out = io.StringIO()
    capture_err = io.StringIO()
    sys.stdout = capture_out
    sys.stderr = capture_err

    try:
        format_frontend.main()
    except Exception:
        pass
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    print("{}")
    return 0


def handle_stop() -> int:
    try:
        raw_input = sys.stdin.read()
        event = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        event = {}

    workspace_paths = event.get("workspacePaths") or []
    cwd = workspace_paths[0] if workspace_paths else str(Path.cwd())
    translated_event = {
        "hook_event_name": "Stop",
        "cwd": cwd,
    }

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdin = io.StringIO(json.dumps(translated_event))
    capture_out = io.StringIO()
    capture_err = io.StringIO()
    sys.stdout = capture_out
    sys.stderr = capture_err

    try:
        code = quality_gate.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    if code == 0:
        print(json.dumps({"decision": "allow"}))
    else:
        err_msg = capture_err.getvalue().strip() or "Quality gate pendente."
        print(json.dumps({"decision": "continue", "reason": err_msg}))
    return 0


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "pre_tool":
        return handle_pre_tool()
    elif action == "post_tool":
        return handle_post_tool()
    elif action == "stop":
        return handle_stop()
    else:
        print("{}", file=sys.stdout)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
