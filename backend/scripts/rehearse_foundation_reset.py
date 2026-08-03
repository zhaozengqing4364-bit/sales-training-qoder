#!/usr/bin/env python3
"""Rehearse the guarded launch reset twice in a disposable local PostgreSQL DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common.db.model_registry.registration import register_all_models
from foundation_standard_pack import install_or_verify_standard_pack
from launch_reset.application import ResetApplicationService
from launch_reset.bootstrap import AlembicSchemaBootstrap
from launch_reset.guards import sync_database_url
from learning.models import LearningQuestion, LearningQuiz
from newcomer_training.models import NewcomerPath

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = REPO_ROOT / ".sisyphus/evidence/foundation-reset-rehearsal.json"
_SAFE_ERROR_CODE = re.compile(r"\[[A-Z0-9_:-]+\]")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--cycles", type=int, default=2, choices=(2,))
    return parser.parse_args()


def _base_database_url() -> URL:
    if os.getenv("FOUNDATION_RESET_REHEARSAL_CONFIRM", "0") != "1":
        raise RuntimeError(
            "[FOUNDATION_RESET_REHEARSAL_CONFIRM_REQUIRED] "
            "Set FOUNDATION_RESET_REHEARSAL_CONFIRM=1 explicitly."
        )
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_DATABASE_URL_REQUIRED]")
    parsed = make_url(raw)
    if not parsed.drivername.startswith("postgresql"):
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_POSTGRES_REQUIRED]")
    if parsed.host not in {None, "localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_LOCAL_DATABASE_REQUIRED]")
    if not parsed.database:
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_DATABASE_NAME_REQUIRED]")
    return parsed


def _admin_database_url(base_url: URL) -> URL:
    raw = os.getenv("FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_URL", "").strip()
    parsed = make_url(raw) if raw else base_url
    if not parsed.drivername.startswith("postgresql"):
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_ADMIN_POSTGRES_REQUIRED]")
    if parsed.host not in {None, "localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_ADMIN_LOCAL_DATABASE_REQUIRED]")
    if (parsed.host, parsed.port) != (base_url.host, base_url.port):
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_ADMIN_TARGET_MISMATCH]")
    if not parsed.database:
        raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_ADMIN_DATABASE_REQUIRED]")
    return parsed


@contextmanager
def _temporary_environment(values: dict[str, str | None]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _quoted_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _create_database(admin_url: URL, database_name: str, owner: str | None) -> None:
    engine = create_engine(
        sync_database_url(admin_url.render_as_string(hide_password=False)),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            owner_clause = f" OWNER {_quoted_identifier(owner)}" if owner else ""
            connection.execute(
                text(f"CREATE DATABASE {_quoted_identifier(database_name)}{owner_clause}")
            )
    except ProgrammingError as exc:
        if getattr(exc.orig, "pgcode", None) == "42501":
            raise RuntimeError(
                "[FOUNDATION_RESET_REHEARSAL_CREATE_DATABASE_FORBIDDEN]"
            ) from exc
        raise
    finally:
        engine.dispose()


def _drop_database(admin_url: URL, database_name: str) -> None:
    engine = create_engine(
        sync_database_url(admin_url.render_as_string(hide_password=False)),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(
                text(f"DROP DATABASE IF EXISTS {_quoted_identifier(database_name)}")
            )
    finally:
        engine.dispose()


def _rehearsal_environment(
    *,
    database_url: str,
    database_name: str,
    root: Path,
    redis_prefix: str,
) -> dict[str, str | None]:
    paths = {
        "DOCUMENT_STORAGE_PATH": root / "documents",
        "AUDIO_STORAGE_PATH": root / "audio",
        "AUDIO_ARCHIVE_STORAGE_PATH": root / "audio-archive",
        "UPLOAD_DIR": root / "uploads",
        "PPT_UPLOAD_DIR": root / "ppt-uploads",
        "PPT_VERSION_STORAGE_PATH": root / "ppt-versions",
        "SALES_TRAINER_AUDIO_STORAGE_PATH": root / "sales-audio",
        "SALES_TRAINER_MATERIAL_STORAGE_PATH": root / "sales-materials",
        "NEWCOMER_ASSIGNMENT_LOCAL_ROOT": root / "assignments",
        "PPT_STORAGE_PATH": root / "presentations",
        "PPT_THUMBNAIL_STORAGE_PATH": root / "thumbnails",
        "CHROMA_PERSIST_DIRECTORY": root / "chroma",
        "CHROMADB_PERSIST_DIR": root / "chromadb",
    }
    environment: dict[str, str | None] = {
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "test",
        "LAUNCH_RESET_APPLY_ENABLED": "true",
        "LAUNCH_RESET_ALLOWED_ENVIRONMENTS": "test",
        "LAUNCH_RESET_ALLOWED_DATABASES": database_name,
        "LAUNCH_RESET_POSTGRES_SCHEMA": "public",
        "LAUNCH_RESET_LOCAL_PATHS": "",
        "LAUNCH_RESET_REDIS_EXCLUSIVE_DB": "false",
        "LAUNCH_RESET_REDIS_PREFIXES": redis_prefix,
        "SESSION_STATE_KEY_PREFIX": redis_prefix,
        "TENCENT_COS_BUCKET": None,
        "TENCENT_COS_REGION": None,
        "LAUNCH_RESET_COS_PREFIXES": None,
    }
    environment.update({key: str(value) for key, value in paths.items()})
    return environment


async def _seed_and_verify(database_url: str) -> dict[str, Any]:
    register_all_models()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            first = await install_or_verify_standard_pack(
                session,
                organization_id="foundation-reset-rehearsal",
            )
            await session.commit()
        async with factory() as session:
            second = await install_or_verify_standard_pack(
                session,
                organization_id="foundation-reset-rehearsal",
            )
            await session.commit()
        async with factory() as session:
            verified = await install_or_verify_standard_pack(
                session,
                organization_id="foundation-reset-rehearsal",
                verify_only=True,
            )
            await session.rollback()
        async with factory() as session:
            counts = {
                "paths": int(
                    await session.scalar(select(func.count(NewcomerPath.path_id))) or 0
                ),
                "questions": int(
                    await session.scalar(
                        select(func.count(LearningQuestion.question_id))
                    )
                    or 0
                ),
                "quizzes": int(
                    await session.scalar(select(func.count(LearningQuiz.quiz_id))) or 0
                ),
            }
        if first.path_revision_id != second.path_revision_id:
            raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_SEED_NOT_IDEMPOTENT]")
        if verified.path_revision_id != first.path_revision_id or not verified.verified_only:
            raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_VERIFY_FAILED]")
        if counts != {"paths": 1, "questions": 7, "quizzes": 7}:
            raise RuntimeError("[FOUNDATION_RESET_REHEARSAL_SEED_COUNTS_INVALID]")
        return {
            "path_revision_id": first.path_revision_id,
            "counts": counts,
            "verified_only": verified.verified_only,
        }
    finally:
        await engine.dispose()


async def _run_cycles(
    *,
    database_url: str,
    control_root: Path,
    cycles: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for cycle in range(1, cycles + 1):
        cycle_root = control_root / f"cycle-{cycle}"
        cycle_root.mkdir(parents=True, exist_ok=True)
        manifest_path = cycle_root / "manifest.json"
        snapshot_path = cycle_root / "snapshot.json"
        service = ResetApplicationService()
        manifest, confirmation_token = await service.dry_run(manifest_path)
        fingerprint = str(manifest["inspection"]["postgresql"]["fingerprint"])
        apply_result = await service.apply(
            manifest_path=manifest_path,
            snapshot_path=snapshot_path,
            supplied_fingerprint=fingerprint,
            confirmation_token=confirmation_token,
            admin_email="foundation-reset-admin@example.com",
            admin_name="Foundation Reset Rehearsal Admin",
            initial_password="synthetic-reset-password-only",
        )
        verify_result = await service.verify(
            manifest_path=manifest_path,
            snapshot_path=snapshot_path,
            admin_email="foundation-reset-admin@example.com",
        )
        seed_result = await _seed_and_verify(database_url)
        completed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        results.append(
            {
                "cycle": cycle,
                "reset_result": apply_result,
                "verify_result": verify_result,
                "seed_result": seed_result,
                "completed_stages": sorted(
                    name
                    for name, value in completed_manifest.get("stages", {}).items()
                    if isinstance(value, dict) and value.get("status") == "completed"
                ),
            }
        )
    return results


def _safe_failure(exc: BaseException) -> str:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        match = _SAFE_ERROR_CODE.search(str(current))
        if match:
            return match.group(0)
        current = current.__cause__ or current.__context__
    return f"[{type(exc).__name__.upper()}]"


def _failed_stage_context(control_root: Path) -> dict[str, Any]:
    for manifest_path in sorted(control_root.glob("cycle-*/manifest.json"), reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            continue
        completed = sorted(
            name
            for name, value in stages.items()
            if isinstance(value, dict) and value.get("status") == "completed"
        )
        for name, value in stages.items():
            if not isinstance(value, dict) or value.get("status") != "failed":
                continue
            error_code = str(value.get("error_code") or "")
            return {
                "failure_cycle": manifest_path.parent.name,
                "failure_stage": name,
                "failure_stage_code": error_code
                if _SAFE_ERROR_CODE.fullmatch(error_code)
                else "[RESET_STAGE_FAILURE_UNCLASSIFIED]",
                "completed_stages": completed,
            }
    return {}


async def _main() -> int:
    args = _arguments()
    started_at = datetime.now(UTC)
    database_name = f"foundation_reset_rehearsal_{uuid.uuid4().hex[:12]}"
    report: dict[str, Any]
    failure_context: dict[str, Any] = {}
    database_created = False
    base_url: URL | None = None
    admin_url: URL | None = None
    try:
        base_url = _base_database_url()
        admin_url = _admin_database_url(base_url)
        _create_database(admin_url, database_name, base_url.username)
        database_created = True
        rehearsal_url = base_url.set(database=database_name).render_as_string(
            hide_password=False
        )
        with tempfile.TemporaryDirectory(
            prefix="foundation-reset-rehearsal-"
        ) as directory:
            root = Path(directory)
            runtime_root = root / "runtime"
            control_root = root / "control"
            runtime_root.mkdir(parents=True)
            control_root.mkdir(parents=True)
            redis_prefix = f"foundation-reset-rehearsal:{uuid.uuid4().hex}:"
            with _temporary_environment(
                _rehearsal_environment(
                    database_url=rehearsal_url,
                    database_name=database_name,
                    root=runtime_root,
                    redis_prefix=redis_prefix,
                )
            ):
                source_schema = AlembicSchemaBootstrap(rehearsal_url).upgrade_head()
                try:
                    cycles = await _run_cycles(
                        database_url=rehearsal_url,
                        control_root=control_root,
                        cycles=args.cycles,
                    )
                except Exception:
                    failure_context = _failed_stage_context(control_root)
                    raise
        report = {
            "contract_version": "foundation_reset_rehearsal_v1",
            "status": "passed",
            "cycles": cycles,
            "database_scope": "disposable_local_database",
            "redis_scope": "unique_prefix_only",
            "filesystem_scope": "temporary_directory_only",
            "source_schema": source_schema,
        }
    except Exception as exc:
        report = {
            "contract_version": "foundation_reset_rehearsal_v1",
            "status": "failed",
            "failure_code": _safe_failure(exc),
            **failure_context,
        }
    finally:
        if database_created and admin_url is not None:
            try:
                _drop_database(admin_url, database_name)
            except Exception as cleanup_exc:
                report = {
                    **report,
                    "status": "failed",
                    "cleanup_failure_code": _safe_failure(cleanup_exc),
                }
    report["started_at"] = started_at.isoformat()
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["database_removed"] = database_created and "cleanup_failure_code" not in report
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
