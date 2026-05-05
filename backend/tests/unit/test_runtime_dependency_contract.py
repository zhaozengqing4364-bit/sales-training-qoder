"""Focused regression tests for backend runtime dependency contracts."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_REQUIREMENTS = ROOT_DIR / "backend" / "requirements.txt"


def test_stepfun_realtime_requirements_include_python_socks() -> None:
    """StepFun realtime websocket clients must support SOCKS proxy environments."""
    requirement_lines = {
        line.strip()
        for line in BACKEND_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert any(
        line.startswith("python-socks") for line in requirement_lines
    ), "backend/requirements.txt must declare python-socks for websocket SOCKS proxy support"
