"""Generate or verify the Backend Gold v2 catalog from the GenAI v2 mapping.

The GenAI mapping is the authoring source; backend/app/catalogs/gold_v2.json is derived.
Run from repository root: python scripts/generate-gold-v2-catalog.py [--check]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend/app/catalogs/gold_v2.json"
EXPORT = (
    "from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING; "
    "import json; print(json.dumps(GRID360_GOLD_MAPPING.model_dump(mode='json'), "
    "ensure_ascii=False, indent=2))"
)


def canonical_catalog() -> str:
    result = subprocess.run(
        [sys.executable, "-c", EXPORT],
        cwd=ROOT / "ai-agent",
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return result.stdout.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the derived JSON is stale"
    )
    args = parser.parse_args()
    expected = canonical_catalog()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
            print(
                "gold_v2.json diverge do mapeamento canônico da GenAI.", file=sys.stderr
            )
            return 1
        print("gold_v2_catalog_matches_canonical_mapping")
        return 0
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Catálogo Gold v2 gerado: {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
