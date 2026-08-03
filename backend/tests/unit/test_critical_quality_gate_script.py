from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SCRIPT = REPO_ROOT / "scripts" / "critical-quality-gate.sh"


def test_critical_gate_routes_every_playwright_call_through_local_library_seam() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert 'PLAYWRIGHT_LIBRARY_DIR="${PLAYWRIGHT_LIBRARY_DIR:-' in source
    assert 'LD_LIBRARY_PATH="${PLAYWRIGHT_LIBRARY_DIR}' in source
    assert source.count("run_playwright test") == 5
    assert "npx playwright test" not in source


def test_critical_gate_shell_syntax_is_valid() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(GATE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_critical_gate_removes_all_generated_next_type_roots_before_tsc() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert (
        "rm -rf .next/types .next/dev/types .next-smoke/types "
        ".next-smoke/dev/types"
    ) in source


def test_critical_gate_runs_foundation_ai_gold_set_and_controlled_staging() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "scripts/evaluate_foundation_ai_gold_set.py" in source
    assert "CRITICAL_GATE_MODE=foundation-ai-real-provider" in source
    assert "scripts/run_foundation_ai_provider_staging.py" in source
    assert "FOUNDATION_AI_REAL_PROVIDER_CONFIRM=1" in source
    assert "newcomer-ai-coach-real-provider" not in source


def test_critical_gate_runs_release_build_and_foundation_capacity_baseline() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert 'log "Web production build"' in source
    assert "npm run build" in source
    assert "tests/performance/test_foundation_capacity.py" in source
    assert "foundation-capacity-baseline.json" in source
    assert "FOUNDATION_CAPACITY_TIMEOUT_SECONDS" in source


def test_critical_gate_backend_watchdog_leaves_coverage_finalization_headroom() -> None:
    source = GATE_SCRIPT.read_text(encoding="utf-8")

    assert 'BACKEND_SUITE_TIMEOUT_SECONDS="${BACKEND_SUITE_TIMEOUT_SECONDS:-1500}"' in source
