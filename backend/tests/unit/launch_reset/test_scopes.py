from __future__ import annotations

import json
from pathlib import Path

import pytest

from launch_reset.errors import ResetSafetyError
from launch_reset.scopes import _validate_local_path, build_manifest_from_environment


def _configure_safe_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TENCENT_COS_BUCKET", raising=False)
    monkeypatch.delenv("TENCENT_COS_REGION", raising=False)
    monkeypatch.delenv("LAUNCH_RESET_COS_PREFIXES", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://launch_user:top-secret@db.internal:5432/launch_db",
    )
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@cache.internal:6379/14")
    monkeypatch.setenv("SESSION_STATE_REDIS_URL", "redis://cache.internal:6379/14")
    monkeypatch.setenv("LAUNCH_RESET_REDIS_PREFIXES", "sales-training:")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path / "documents"))
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path / "audio"))
    monkeypatch.setenv("AUDIO_ARCHIVE_STORAGE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("PPT_UPLOAD_DIR", str(tmp_path / "ppt-uploads"))
    monkeypatch.setenv("PPT_VERSION_STORAGE_PATH", str(tmp_path / "ppt-versions"))
    monkeypatch.setenv(
        "SALES_TRAINER_AUDIO_STORAGE_PATH", str(tmp_path / "sales-audio")
    )
    monkeypatch.setenv(
        "SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path / "materials")
    )
    monkeypatch.setenv("NEWCOMER_ASSIGNMENT_LOCAL_ROOT", str(tmp_path / "assignments"))
    monkeypatch.setenv("PPT_STORAGE_PATH", str(tmp_path / "presentations"))
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", str(tmp_path / "chroma"))
    monkeypatch.setenv("CHROMADB_PERSIST_DIR", str(tmp_path / "chromadb"))


def test_manifest_contains_target_descriptors_but_no_connection_secrets(
    monkeypatch, tmp_path
) -> None:
    _configure_safe_environment(monkeypatch, tmp_path)

    manifest = build_manifest_from_environment()
    serialized = json.dumps(manifest)

    assert manifest["scopes"]["postgresql"] == {
        "name": "postgresql",
        "driver": "postgresql+asyncpg",
        "host": "db.internal",
        "port": 5432,
        "database": "launch_db",
        "schema": "public",
    }
    assert "top-secret" not in serialized
    assert "redis-secret" not in serialized


@pytest.mark.parametrize("path", [Path("/"), Path("/home"), Path("/home/dev/work")])
def test_cleanup_scope_rejects_broad_or_repository_ancestor_paths(path: Path) -> None:
    with pytest.raises(ResetSafetyError, match="RESET_LOCAL_PATH_PROTECTED"):
        _validate_local_path(path.resolve(strict=False))


def test_shared_redis_prefix_rejects_scan_wildcards(monkeypatch, tmp_path) -> None:
    _configure_safe_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LAUNCH_RESET_REDIS_PREFIXES", "sales-training:*,safe:")

    with pytest.raises(ResetSafetyError, match="RESET_REDIS_PREFIX_INVALID"):
        build_manifest_from_environment()


def test_custom_postgres_schema_is_rejected_in_v1(monkeypatch, tmp_path) -> None:
    _configure_safe_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LAUNCH_RESET_POSTGRES_SCHEMA", "tenant_a")

    with pytest.raises(
        ResetSafetyError, match="RESET_POSTGRES_CUSTOM_SCHEMA_UNSUPPORTED"
    ):
        build_manifest_from_environment()


def test_configured_cos_requires_explicit_project_prefixes(
    monkeypatch, tmp_path
) -> None:
    _configure_safe_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("TENCENT_COS_BUCKET", "shared-bucket")
    monkeypatch.setenv("TENCENT_COS_REGION", "ap-shanghai")
    monkeypatch.delenv("LAUNCH_RESET_COS_PREFIXES", raising=False)

    with pytest.raises(
        ResetSafetyError, match="RESET_COS_EXPLICIT_PREFIXES_REQUIRED"
    ):
        build_manifest_from_environment()
