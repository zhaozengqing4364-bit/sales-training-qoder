"""Versioned Phase 4 E2E fixture loading."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def e2e_fixture_dir() -> Path:
    configured = os.getenv("PHASE4_E2E_FIXTURE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return _repo_root() / "tests" / "e2e" / "fixtures"


def load_versioned_fixture(name: str) -> dict[str, Any]:
    safe_name = Path(name).name
    fixture_path = e2e_fixture_dir() / safe_name
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"E2E fixture must be a JSON object: {safe_name}")
    fixture_version = str(payload.get("fixture_version") or "").strip()
    if not fixture_version:
        raise ValueError(f"E2E fixture missing fixture_version: {safe_name}")
    return payload
