from __future__ import annotations

import json
import stat

import pytest

from launch_reset.errors import ResetSafetyError
from launch_reset.manifest import (
    issue_confirmation_token,
    load_manifest,
    refresh_checksums,
    save_manifest,
    verify_confirmation_token,
)


def _manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "format": "sales-training-launch-reset",
        "version": 1,
        "environment": "development",
        "scopes": {
            "postgresql": {"host": "db.internal", "database": "launch_test"},
            "redis": [],
            "chroma": [],
            "local_paths": [],
            "cos": None,
        },
        "inspection": {},
        "stages": {},
    }
    refresh_checksums(manifest)
    return manifest


def test_manifest_is_atomic_private_and_does_not_store_confirmation_token(
    tmp_path,
) -> None:
    path = tmp_path / "reset-manifest.json"
    manifest = _manifest()
    token = issue_confirmation_token(manifest)

    save_manifest(path, manifest)

    persisted = path.read_text(encoding="utf-8")
    assert token not in persisted
    assert "confirmation_token_hash" in persisted
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    verify_confirmation_token(load_manifest(path), token)


def test_manifest_detects_tampering_without_exposing_database_password(
    tmp_path,
) -> None:
    path = tmp_path / "reset-manifest.json"
    manifest = _manifest()
    save_manifest(path, manifest)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["scopes"]["postgresql"]["database"] = "another_database"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ResetSafetyError, match="PLAN_CHECKSUM_MISMATCH"):
        load_manifest(path)


def test_confirmation_token_is_bound_to_the_exact_scope_plan() -> None:
    manifest = _manifest()
    token = issue_confirmation_token(manifest)
    manifest["scopes"]["postgresql"]["database"] = "changed_database"
    refresh_checksums(manifest)

    with pytest.raises(ResetSafetyError, match="CONFIRMATION_TOKEN_INVALID"):
        verify_confirmation_token(manifest, token)
