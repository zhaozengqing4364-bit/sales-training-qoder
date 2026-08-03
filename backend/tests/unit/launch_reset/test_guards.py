from __future__ import annotations

import pytest

from launch_reset.errors import ResetSafetyError
from launch_reset.guards import require_apply_authorization, sync_database_url


def _manifest(*, environment: str = "development") -> dict[str, object]:
    return {
        "environment": environment,
        "scopes": {"postgresql": {"database": "launch_db"}},
        "inspection": {"postgresql": {"fingerprint": "fingerprint-a"}},
    }


def _authorize(monkeypatch, manifest: dict[str, object]) -> None:
    monkeypatch.setenv("LAUNCH_RESET_APPLY_ENABLED", "true")
    monkeypatch.setenv("LAUNCH_RESET_ALLOWED_DATABASES", "launch_db")
    require_apply_authorization(
        manifest=manifest,
        current_fingerprint="fingerprint-a",
        supplied_fingerprint="fingerprint-a",
    )


def test_apply_requires_enable_flag_database_allowlist_and_exact_fingerprint(
    monkeypatch,
) -> None:
    _authorize(monkeypatch, _manifest())

    monkeypatch.setenv("LAUNCH_RESET_ALLOWED_DATABASES", "another_db")
    with pytest.raises(ResetSafetyError, match="DATABASE_NOT_ALLOWLISTED"):
        require_apply_authorization(
            manifest=_manifest(),
            current_fingerprint="fingerprint-a",
            supplied_fingerprint="fingerprint-a",
        )


def test_apply_is_never_allowed_for_production(monkeypatch) -> None:
    monkeypatch.setenv("LAUNCH_RESET_APPLY_ENABLED", "true")
    monkeypatch.setenv("LAUNCH_RESET_ALLOWED_DATABASES", "launch_db")

    with pytest.raises(ResetSafetyError, match="ENVIRONMENT_NOT_ALLOWED"):
        require_apply_authorization(
            manifest=_manifest(environment="production"),
            current_fingerprint="fingerprint-a",
            supplied_fingerprint="fingerprint-a",
        )


def test_sync_database_url_preserves_credentials_only_for_runtime_connection() -> None:
    assert (
        sync_database_url(
            "postgresql+asyncpg://launch_user:secret@db.internal:5432/launch_db"
        )
        == "postgresql://launch_user:secret@db.internal:5432/launch_db"
    )
