from __future__ import annotations

import pytest

from launch_reset.errors import ResetSafetyError
from launch_reset.manifest import sha256_json, utc_now_iso
from launch_reset.snapshot import (
    SNAPSHOT_FORMAT,
    SNAPSHOT_VERSION,
    encryption_key_fingerprint,
    validate_snapshot,
)


def _valid_snapshot() -> dict[str, object]:
    sections: list[object] = []
    snapshot: dict[str, object] = {
        "format": SNAPSHOT_FORMAT,
        "version": SNAPSHOT_VERSION,
        "created_at": utc_now_iso(),
        "encryption_key_fingerprint": encryption_key_fingerprint(),
        "sections": sections,
        "sections_fingerprint": sha256_json(sections),
    }
    snapshot["snapshot_checksum"] = sha256_json(snapshot)
    return snapshot


def test_snapshot_rejects_an_encryption_key_change(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", "source-key")
    snapshot = _valid_snapshot()
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", "different-key")

    with pytest.raises(
        ResetSafetyError, match="RESET_ENCRYPTION_KEY_FINGERPRINT_MISMATCH"
    ):
        validate_snapshot(snapshot)


def test_snapshot_rejects_payload_tampering(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", "source-key")
    snapshot = _valid_snapshot()
    snapshot["created_at"] = "tampered"

    with pytest.raises(ResetSafetyError, match="RESET_SNAPSHOT_CHECKSUM_MISMATCH"):
        validate_snapshot(snapshot)
