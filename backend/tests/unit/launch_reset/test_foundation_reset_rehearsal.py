from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.engine import make_url

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "rehearse_foundation_reset.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "foundation_reset_rehearsal_test_module",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rehearsal_requires_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    monkeypatch.delenv("FOUNDATION_RESET_REHEARSAL_CONFIRM", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:secret@127.0.0.1:5432/foundation",
    )

    with pytest.raises(
        RuntimeError,
        match=r"\[FOUNDATION_RESET_REHEARSAL_CONFIRM_REQUIRED\]",
    ):
        module._base_database_url()


def test_rehearsal_rejects_remote_or_mismatched_admin_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    monkeypatch.setenv("FOUNDATION_RESET_REHEARSAL_CONFIRM", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:secret@127.0.0.1:5432/foundation",
    )
    base_url = module._base_database_url()

    monkeypatch.setenv(
        "FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_URL",
        "postgresql://admin:secret@localhost:5433/postgres",
    )
    with pytest.raises(
        RuntimeError,
        match=r"\[FOUNDATION_RESET_REHEARSAL_ADMIN_TARGET_MISMATCH\]",
    ):
        module._admin_database_url(base_url)


def test_rehearsal_environment_isolated_to_disposable_scopes(tmp_path: Path) -> None:
    module = _load_script()
    database_name = "foundation_reset_rehearsal_deadbeef"
    redis_prefix = "foundation-reset-rehearsal:deadbeef:"
    database_url = (
        f"postgresql+asyncpg://app:secret@127.0.0.1:5432/{database_name}"
    )

    environment = module._rehearsal_environment(
        database_url=database_url,
        database_name=database_name,
        root=tmp_path,
        redis_prefix=redis_prefix,
    )

    assert make_url(str(environment["DATABASE_URL"])).database == database_name
    assert environment["LAUNCH_RESET_ALLOWED_DATABASES"] == database_name
    assert environment["LAUNCH_RESET_POSTGRES_SCHEMA"] == "public"
    assert environment["LAUNCH_RESET_LOCAL_PATHS"] == ""
    assert environment["LAUNCH_RESET_REDIS_EXCLUSIVE_DB"] == "false"
    assert environment["LAUNCH_RESET_REDIS_PREFIXES"] == redis_prefix
    assert environment["SESSION_STATE_KEY_PREFIX"] == redis_prefix
    assert environment["TENCENT_COS_BUCKET"] is None
    assert environment["TENCENT_COS_REGION"] is None
    assert environment["LAUNCH_RESET_COS_PREFIXES"] is None
    for name in (
        "DOCUMENT_STORAGE_PATH",
        "AUDIO_STORAGE_PATH",
        "AUDIO_ARCHIVE_STORAGE_PATH",
        "UPLOAD_DIR",
        "PPT_UPLOAD_DIR",
        "PPT_VERSION_STORAGE_PATH",
        "SALES_TRAINER_AUDIO_STORAGE_PATH",
        "SALES_TRAINER_MATERIAL_STORAGE_PATH",
        "NEWCOMER_ASSIGNMENT_LOCAL_ROOT",
        "PPT_STORAGE_PATH",
        "PPT_THUMBNAIL_STORAGE_PATH",
        "CHROMA_PERSIST_DIRECTORY",
        "CHROMADB_PERSIST_DIR",
    ):
        assert Path(str(environment[name])).is_relative_to(tmp_path)


def test_rehearsal_failure_uses_safe_code_from_exception_chain() -> None:
    module = _load_script()
    cause = RuntimeError("[RESET_ALEMBIC_UPGRADE_FAILED] private diagnostics")
    outer = RuntimeError()
    outer.__cause__ = cause

    assert module._safe_failure(outer) == "[RESET_ALEMBIC_UPGRADE_FAILED]"


def test_rehearsal_reports_failed_stage_without_private_details(tmp_path: Path) -> None:
    module = _load_script()
    manifest_path = tmp_path / "cycle-1" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "stages": {
                    "snapshot": {"status": "completed"},
                    "schema": {
                        "status": "failed",
                        "error_code": "[RESET_ALEMBIC_UPGRADE_FAILED]",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert module._failed_stage_context(tmp_path) == {
        "failure_cycle": "cycle-1",
        "failure_stage": "schema",
        "failure_stage_code": "[RESET_ALEMBIC_UPGRADE_FAILED]",
        "completed_stages": ["snapshot"],
    }
