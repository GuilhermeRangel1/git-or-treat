import subprocess
import sys
from pathlib import Path


def test_readiness_cli_exposes_approved_gd_controls():
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_gold_readiness.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "C08" in result.stdout
    assert "C09" in result.stdout
