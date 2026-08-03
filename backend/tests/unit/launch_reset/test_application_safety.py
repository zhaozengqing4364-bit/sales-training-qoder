from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from launch_reset.application import ResetApplicationService
from launch_reset.errors import ResetSafetyError


def _manifest(cleanup_root: Path, snapshot_path: Path) -> dict[str, object]:
    return {
        "scopes": {
            "chroma": [{"name": "chroma", "path": str(cleanup_root / "chroma")}],
            "local_paths": [{"name": "files", "path": str(cleanup_root)}],
        },
        "stages": {
            "snapshot": {
                "details": {
                    "path": str(snapshot_path.resolve(strict=False)),
                    "checksum": "snapshot-checksum",
                }
            }
        },
    }


def test_manifest_or_snapshot_cannot_live_inside_a_cleanup_scope(tmp_path) -> None:
    cleanup_root = tmp_path / "project-data"
    outside_snapshot = tmp_path / "control" / "snapshot.json"
    manifest = _manifest(cleanup_root, outside_snapshot)

    with pytest.raises(ResetSafetyError, match="CONTROL_PATH_INSIDE_CLEANUP_SCOPE"):
        ResetApplicationService._assert_control_paths_are_safe(
            manifest,
            control_paths=(cleanup_root / "reset-manifest.json", outside_snapshot),
        )


def test_manifest_and_snapshot_paths_must_not_collide(tmp_path) -> None:
    path = tmp_path / "control" / "reset.json"
    manifest = _manifest(tmp_path / "project-data", path)

    with pytest.raises(ResetSafetyError, match="CONTROL_PATHS_COLLIDE"):
        ResetApplicationService._assert_control_paths_are_safe(
            manifest, control_paths=(path, path)
        )


def test_snapshot_must_match_confirmed_target_stage_and_path(tmp_path) -> None:
    snapshot_path = tmp_path / "control" / "snapshot.json"
    manifest = _manifest(tmp_path / "project-data", snapshot_path)
    snapshot = {
        "source_fingerprint": "target-a",
        "snapshot_checksum": "snapshot-checksum",
    }

    ResetApplicationService._assert_snapshot_binding(
        manifest=manifest,
        snapshot=snapshot,
        snapshot_path=snapshot_path,
        supplied_fingerprint="target-a",
    )

    snapshot["source_fingerprint"] = "target-b"
    with pytest.raises(ResetSafetyError, match="SNAPSHOT_SOURCE_MISMATCH"):
        ResetApplicationService._assert_snapshot_binding(
            manifest=manifest,
            snapshot=snapshot,
            snapshot_path=snapshot_path,
            supplied_fingerprint="target-a",
        )


@pytest.mark.asyncio
async def test_completed_stage_is_resumed_without_repeating_action(
    tmp_path, monkeypatch
) -> None:
    service = object.__new__(ResetApplicationService)
    manifest: dict[str, Any] = {
        "stages": {
            "schema": {
                "status": "completed",
                "details": {"head": "20260715_0000_001"},
            }
        }
    }
    action_calls = 0

    def action() -> dict[str, str]:
        nonlocal action_calls
        action_calls += 1
        return {"head": "unexpected"}

    monkeypatch.setattr("launch_reset.application.save_manifest", lambda *_: None)

    result = await service._run_stage(
        manifest_path=tmp_path / "manifest.json",
        manifest=manifest,
        stage_name="schema",
        action=action,
    )

    assert result == {"head": "20260715_0000_001"}
    assert action_calls == 0


@pytest.mark.asyncio
async def test_failed_stage_can_be_retried_and_records_the_completed_boundary(
    tmp_path, monkeypatch
) -> None:
    service = object.__new__(ResetApplicationService)
    manifest: dict[str, Any] = {
        "stages": {
            "system_seed": {
                "status": "failed",
                "error_code": "[OLD]",
                "failed_at": "2026-07-15T00:00:00+00:00",
            }
        }
    }
    monkeypatch.setattr("launch_reset.application.save_manifest", lambda *_: None)

    result = await service._run_stage(
        manifest_path=tmp_path / "manifest.json",
        manifest=manifest,
        stage_name="system_seed",
        action=lambda: {"inserted": 3},
    )

    stage = manifest["stages"]["system_seed"]
    assert result == {"inserted": 3}
    assert stage["status"] == "completed"
    assert stage["details"] == {"inserted": 3}
    assert "error_code" not in stage
    assert "failed_at" not in stage


@pytest.mark.asyncio
async def test_failed_stage_records_safe_code_from_exception_chain(
    tmp_path, monkeypatch
) -> None:
    service = object.__new__(ResetApplicationService)
    manifest: dict[str, Any] = {"stages": {}}
    monkeypatch.setattr("launch_reset.application.save_manifest", lambda *_: None)

    def fail() -> None:
        try:
            raise RuntimeError("[RESET_SNAPSHOT_TABLE_READ_FAILED]")
        except RuntimeError as cause:
            raise RuntimeError() from cause

    with pytest.raises(RuntimeError):
        await service._run_stage(
            manifest_path=tmp_path / "manifest.json",
            manifest=manifest,
            stage_name="snapshot",
            action=fail,
        )

    assert manifest["stages"]["snapshot"]["error_code"] == (
        "[RESET_SNAPSHOT_TABLE_READ_FAILED]"
    )
