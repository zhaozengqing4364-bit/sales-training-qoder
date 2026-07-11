from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = REPO_ROOT / "scripts" / "critical-quality-gate.sh"


def test_critical_gate_routes_every_playwright_call_through_local_library_seam() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert 'PLAYWRIGHT_LIBRARY_DIR="${PLAYWRIGHT_LIBRARY_DIR:-' in source
    assert 'LD_LIBRARY_PATH="${PLAYWRIGHT_LIBRARY_DIR}' in source
    assert source.count("run_playwright test") == 7
    assert "npx playwright test" not in source


def test_critical_gate_shell_syntax_is_valid() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(GATE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
