"""Unit tests for the recovery drill baseline inventory script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT_DIR / "scripts" / "recovery_drill_baseline.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "recovery_drill_baseline",
        SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None, f"Missing script: {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recovery_drill_inventory_covers_hardened_recovery_surfaces() -> None:
    module = _load_module()

    drill_ids = [drill.id for drill in module.DRILLS]

    assert drill_ids == [
        "db_migration",
        "auth_bootstrap",
        "redis_session_state",
        "websocket_reconnect",
        "oss_signing_playback",
        "health_check",
    ]


def test_recovery_drill_status_report_marks_manual_only_boundaries() -> None:
    module = _load_module()

    report = module.build_status_report(ROOT_DIR)

    assert "Recovery drill baseline" in report
    assert "[drill] websocket_reconnect" in report
    assert "[drill] oss_signing_playback" in report
    assert "[manual-only] redis_service_restore" in report
    assert "[manual-only] oss_bucket_export" in report
    assert "[manual-only] multi_instance_drain" in report


def test_recovery_drill_authority_paths_exist_in_repository() -> None:
    module = _load_module()

    missing = module.validate_repository(ROOT_DIR)

    assert missing == []
