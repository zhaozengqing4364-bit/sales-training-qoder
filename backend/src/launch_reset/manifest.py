"""Versioned, secret-free reset manifest and confirmation-token handling."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from launch_reset.errors import ResetSafetyError

MANIFEST_FORMAT = "sales-training-launch-reset"
MANIFEST_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def plan_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": manifest.get("format"),
        "version": manifest.get("version"),
        "environment": manifest.get("environment"),
        "scopes": manifest.get("scopes"),
    }


def refresh_checksums(manifest: dict[str, Any]) -> None:
    manifest["plan_checksum"] = sha256_json(plan_payload(manifest))
    without_checksum = {
        key: value for key, value in manifest.items() if key != "manifest_checksum"
    }
    manifest["manifest_checksum"] = sha256_json(without_checksum)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ResetSafetyError("[RESET_MANIFEST_FORMAT_INVALID]")
    if manifest.get("version") != MANIFEST_VERSION:
        raise ResetSafetyError("[RESET_MANIFEST_VERSION_UNSUPPORTED]")

    expected_plan_checksum = sha256_json(plan_payload(manifest))
    if not secrets.compare_digest(
        str(manifest.get("plan_checksum") or ""), expected_plan_checksum
    ):
        raise ResetSafetyError("[RESET_MANIFEST_PLAN_CHECKSUM_MISMATCH]")

    without_checksum = {
        key: value for key, value in manifest.items() if key != "manifest_checksum"
    }
    expected_manifest_checksum = sha256_json(without_checksum)
    if not secrets.compare_digest(
        str(manifest.get("manifest_checksum") or ""), expected_manifest_checksum
    ):
        raise ResetSafetyError("[RESET_MANIFEST_CHECKSUM_MISMATCH]")


def issue_confirmation_token(manifest: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    plan_checksum = str(manifest["plan_checksum"])
    manifest["confirmation_token_hash"] = hashlib.sha256(
        f"{plan_checksum}:{token}".encode()
    ).hexdigest()
    manifest["confirmation_issued_at"] = utc_now_iso()
    return token


def verify_confirmation_token(manifest: dict[str, Any], token: str) -> None:
    plan_checksum = str(manifest.get("plan_checksum") or "")
    expected = str(manifest.get("confirmation_token_hash") or "")
    actual = hashlib.sha256(f"{plan_checksum}:{token}".encode()).hexdigest()
    if not expected or not secrets.compare_digest(expected, actual):
        raise ResetSafetyError("[RESET_CONFIRMATION_TOKEN_INVALID]")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResetSafetyError("[RESET_MANIFEST_READ_FAILED]") from exc
    if not isinstance(payload, dict):
        raise ResetSafetyError("[RESET_MANIFEST_ROOT_INVALID]")
    validate_manifest(payload)
    return payload


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    refresh_checksums(manifest)
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


__all__ = [
    "MANIFEST_FORMAT",
    "MANIFEST_VERSION",
    "canonical_json",
    "issue_confirmation_token",
    "load_manifest",
    "refresh_checksums",
    "save_manifest",
    "sha256_json",
    "utc_now_iso",
    "validate_manifest",
    "verify_confirmation_token",
]
