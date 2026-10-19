import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[1] / "app"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_core_contract_modules_do_not_import_concrete_adapters_or_composition() -> None:
    core_roots = [
        APP_ROOT / "agent",
        APP_ROOT / "generation",
        APP_ROOT / "ports",
        APP_ROOT / "schemas",
    ]
    forbidden_prefixes = (
        "app.main",
        "app.tools",
        "app.providers.gemini",
        "app.providers.fallback",
        "app.providers.caching",
        "app.providers.factory",
        "app.providers.unavailable",
        "app.profiles.grid360_demo",
        "fastapi",
        "google.genai",
        "sqlalchemy",
        "psycopg",
        "sqlite3",
    )
    violations = []

    for root in core_roots:
        for path in root.rglob("*.py"):
            for module in _imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path.relative_to(APP_ROOT)} imports {module}")

    assert violations == []


def test_concrete_adapters_do_not_import_the_agent_or_composition_root() -> None:
    adapter_roots = [APP_ROOT / "tools", APP_ROOT / "providers"]
    forbidden_prefixes = ("app.agent", "app.main")
    violations = []

    for root in adapter_roots:
        for path in root.rglob("*.py"):
            for module in _imported_modules(path):
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{path.relative_to(APP_ROOT)} imports {module}")

    assert violations == []
