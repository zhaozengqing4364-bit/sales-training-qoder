"""Resolve reset scopes from existing configuration without exposing secrets."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from launch_reset.errors import ResetSafetyError
from launch_reset.manifest import (
    MANIFEST_FORMAT,
    MANIFEST_VERSION,
    refresh_checksums,
    utc_now_iso,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent

def _csv_env(name: str) -> list[str]:
    return [part.strip() for part in os.getenv(name, "").split(",") if part.strip()]


def _secret_free_url_scope(raw_url: str, *, name: str) -> dict[str, Any]:
    try:
        parsed = make_url(raw_url)
    except Exception as exc:
        raise ResetSafetyError(f"[RESET_{name.upper()}_URL_INVALID]") from exc
    return {
        "name": name,
        "driver": parsed.drivername,
        "host": parsed.host or "local-socket",
        "port": parsed.port,
        "database": parsed.database or "",
    }


def _resolve_configured_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path.resolve(strict=False)


def _validate_local_path(path: Path) -> None:
    protected = {
        Path("/").resolve(),
        Path.home().resolve(),
        REPOSITORY_ROOT.resolve(),
        REPOSITORY_ROOT.parent.resolve(),
        BACKEND_ROOT.resolve(),
    }
    # A configured cleanup root must never be a broad ancestor of the
    # repository or the operator's home.  Exact-value checks alone would still
    # allow dangerous inputs such as ``/home`` or ``/home/dev/work``.
    if len(path.parts) < 3 or any(
        protected_path == path or protected_path.is_relative_to(path)
        for protected_path in protected
    ):
        raise ResetSafetyError(f"[RESET_LOCAL_PATH_PROTECTED:{path}]")
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent.exists()):
        raise ResetSafetyError(f"[RESET_LOCAL_PATH_SYMLINK:{path}]")


def _local_path_scopes() -> list[dict[str, str]]:
    configured: list[tuple[str, str]] = [
        ("documents", os.getenv("DOCUMENT_STORAGE_PATH", "./data/documents")),
        ("audio", os.getenv("AUDIO_STORAGE_PATH", "./data/audio")),
        (
            "audio_archive",
            os.getenv("AUDIO_ARCHIVE_STORAGE_PATH", "/data/audio_archived"),
        ),
        ("uploads", os.getenv("UPLOAD_DIR", "./uploads")),
        ("ppt_uploads", os.getenv("PPT_UPLOAD_DIR", "/data/uploads")),
        (
            "ppt_versions",
            os.getenv("PPT_VERSION_STORAGE_PATH", "/data/ppt_versions"),
        ),
        (
            "sales_trainer_audio",
            os.getenv("SALES_TRAINER_AUDIO_STORAGE_PATH", "./data/sales_trainer_audio"),
        ),
        (
            "sales_trainer_materials",
            os.getenv(
                "SALES_TRAINER_MATERIAL_STORAGE_PATH",
                "./data/sales_trainer_materials",
            ),
        ),
        (
            "newcomer_assignments",
            os.getenv("NEWCOMER_ASSIGNMENT_LOCAL_ROOT", "uploads/assignments"),
        ),
    ]
    ppt_path = os.getenv("PPT_STORAGE_PATH")
    if ppt_path:
        configured.append(("presentations", ppt_path))
    else:
        configured.extend(
            [
                ("presentations_legacy", "./data/presentations"),
                ("presentations_runtime", "./data/ppts"),
            ]
        )
    thumbnail_path = os.getenv("PPT_THUMBNAIL_STORAGE_PATH", "").strip()
    if thumbnail_path:
        configured.append(("presentation_thumbnails", thumbnail_path))
    for index, value in enumerate(_csv_env("LAUNCH_RESET_LOCAL_PATHS"), start=1):
        configured.append((f"explicit_{index}", value))

    deduplicated: dict[str, str] = {}
    for label, raw_path in configured:
        path = _resolve_configured_path(raw_path)
        _validate_local_path(path)
        deduplicated.setdefault(str(path), label)
    return [
        {"name": label, "path": path}
        for path, label in sorted(deduplicated.items(), key=lambda item: item[0])
    ]


def _chroma_scopes() -> list[dict[str, str]]:
    values = {
        os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma"),
        os.getenv("CHROMADB_PERSIST_DIR", "./data/chromadb"),
    }
    scopes: list[dict[str, str]] = []
    for index, value in enumerate(sorted(values), start=1):
        path = _resolve_configured_path(value)
        _validate_local_path(path)
        scopes.append({"name": f"chroma_{index}", "path": str(path)})
    return scopes


def _redis_scopes() -> list[dict[str, Any]]:
    raw_urls = {
        "cache": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "session": os.getenv(
            "SESSION_STATE_REDIS_URL",
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        ),
    }
    explicit_prefixes = _csv_env("LAUNCH_RESET_REDIS_PREFIXES")
    session_prefix = os.getenv("SESSION_STATE_KEY_PREFIX", "ws:session_state:").strip()
    exclusive = os.getenv("LAUNCH_RESET_REDIS_EXCLUSIVE_DB", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    scopes_by_target: dict[tuple[object, ...], dict[str, Any]] = {}
    for name, raw_url in raw_urls.items():
        descriptor = _secret_free_url_scope(raw_url, name=name)
        parsed = make_url(raw_url)
        db_number = int(parsed.database or 0)
        key = (descriptor["host"], descriptor["port"], db_number)
        scope = scopes_by_target.setdefault(
            key,
            {
                **descriptor,
                "database": db_number,
                "mode": "exclusive_db" if exclusive else "shared_prefixes",
                "prefixes": set(explicit_prefixes),
                "sources": [],
            },
        )
        scope["sources"].append(name)
        if name == "session" and session_prefix:
            scope["prefixes"].add(session_prefix)

    scopes: list[dict[str, Any]] = []
    for scope in scopes_by_target.values():
        prefixes = sorted(str(prefix) for prefix in scope.pop("prefixes"))
        if any(
            not prefix or any(character in prefix for character in "*?[]")
            for prefix in prefixes
        ):
            raise ResetSafetyError("[RESET_REDIS_PREFIX_INVALID]")
        scope["prefixes"] = prefixes
        scope["sources"] = sorted(scope["sources"])
        scopes.append(scope)
    return sorted(scopes, key=lambda item: (str(item["host"]), int(item["database"])))


def _cos_scope() -> dict[str, Any] | None:
    bucket = os.getenv("TENCENT_COS_BUCKET", "").strip()
    region = os.getenv("TENCENT_COS_REGION", "").strip()
    if not bucket and not region:
        return None
    if not bucket or not region:
        raise ResetSafetyError("[RESET_COS_TARGET_INCOMPLETE]")
    prefixes = _csv_env("LAUNCH_RESET_COS_PREFIXES")
    if not prefixes:
        raise ResetSafetyError("[RESET_COS_EXPLICIT_PREFIXES_REQUIRED]")
    for prefix in prefixes:
        if (
            not prefix
            or prefix.startswith("/")
            or not prefix.endswith("/")
            or ".." in prefix.split("/")
        ):
            raise ResetSafetyError(f"[RESET_COS_PREFIX_INVALID:{prefix}]")
    return {
        "bucket": bucket,
        "region": region,
        "scheme": os.getenv("TENCENT_COS_SCHEME", "https"),
        "prefixes": sorted(set(prefixes)),
    }


def build_manifest_from_environment() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ResetSafetyError("[RESET_DATABASE_URL_MISSING]")
    database_scope = _secret_free_url_scope(database_url, name="postgresql")
    database_scope["schema"] = os.getenv(
        "LAUNCH_RESET_POSTGRES_SCHEMA", "public"
    ).strip()
    if not database_scope["database"] or not database_scope["schema"]:
        raise ResetSafetyError("[RESET_DATABASE_SCOPE_INCOMPLETE]")
    if database_scope["schema"] != "public":
        raise ResetSafetyError("[RESET_POSTGRES_CUSTOM_SCHEMA_UNSUPPORTED]")

    scopes: dict[str, Any] = {
        "postgresql": database_scope,
        "redis": _redis_scopes(),
        "chroma": _chroma_scopes(),
        "local_paths": _local_path_scopes(),
        "cos": _cos_scope(),
    }
    manifest: dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "created_at": utc_now_iso(),
        "environment": os.getenv("ENVIRONMENT", "development").strip().lower(),
        "scopes": scopes,
        "inspection": {},
        "stages": {},
        "warnings": [],
    }
    refresh_checksums(manifest)
    return manifest


def database_target_fingerprint(scope: dict[str, Any], server: dict[str, Any]) -> str:
    payload = {"scope": scope, "server": server}
    return hashlib.sha256(json_stable(payload).encode("utf-8")).hexdigest()


def json_stable(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "BACKEND_ROOT",
    "REPOSITORY_ROOT",
    "build_manifest_from_environment",
    "database_target_fingerprint",
]
