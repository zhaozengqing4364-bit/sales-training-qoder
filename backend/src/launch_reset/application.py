"""Application service that owns reset ordering, resume state, and reporting."""

from __future__ import annotations

import inspect as python_inspect
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from launch_reset.bootstrap import (
    AlembicSchemaBootstrap,
    ManagedAdminBootstrap,
    SystemSeedService,
)
from launch_reset.cleaners import (
    CosPrefixCleaner,
    FilesystemCleaner,
    PostgreSQLCleaner,
    RedisCleaner,
)
from launch_reset.cleaners.base import ScopedCleaner
from launch_reset.errors import ResetExecutionError, ResetSafetyError
from launch_reset.guards import (
    PostgreSQLRunLock,
    inspect_postgresql_target,
    require_apply_authorization,
)
from launch_reset.manifest import (
    issue_confirmation_token,
    load_manifest,
    save_manifest,
    sha256_json,
    utc_now_iso,
    verify_confirmation_token,
)
from launch_reset.scopes import build_manifest_from_environment
from launch_reset.snapshot import (
    export_config_snapshot,
    load_snapshot,
    restore_config_snapshot,
    write_snapshot,
)
from launch_reset.verifier import IndependentVerifier

_SAFE_ERROR_CODE = re.compile(r"\[[A-Z0-9_:-]+\]")


def _safe_error_code(error: BaseException) -> str:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        match = _SAFE_ERROR_CODE.search(str(current))
        if match:
            return match.group(0)
        current = current.__cause__ or current.__context__
    return f"[{type(error).__name__.upper()}]"


class ResetApplicationService:
    """Orchestrate registered adapters without embedding deletion logic."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        if not self.database_url:
            raise ResetSafetyError("[RESET_DATABASE_URL_MISSING]")

    @staticmethod
    def _redis_url_for_scope(scope: dict[str, Any]) -> str:
        sources = set(scope.get("sources", []))
        if "cache" in sources:
            return os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return os.getenv(
            "SESSION_STATE_REDIS_URL",
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        )

    def _cleaners(self, manifest: dict[str, Any]) -> dict[str, ScopedCleaner]:
        scopes = manifest["scopes"]
        cleaners: dict[str, ScopedCleaner] = {}
        for index, scope in enumerate(scopes["redis"]):
            cleaners[f"redis_{index}"] = RedisCleaner(
                self._redis_url_for_scope(scope), scope
            )
        cleaners["chroma"] = FilesystemCleaner(
            name="chroma", scopes=list(scopes["chroma"])
        )
        cleaners["local_paths"] = FilesystemCleaner(
            name="local_paths", scopes=list(scopes["local_paths"])
        )
        if scopes.get("cos") is not None:
            cleaners["cos"] = CosPrefixCleaner(dict(scopes["cos"]))
        cleaners["postgresql"] = PostgreSQLCleaner(
            self.database_url, dict(scopes["postgresql"])
        )
        return cleaners

    @staticmethod
    def _assert_control_paths_are_safe(
        manifest: dict[str, Any], *, control_paths: tuple[Path, ...]
    ) -> None:
        resolved_paths = tuple(path.resolve(strict=False) for path in control_paths)
        if len(set(resolved_paths)) != len(resolved_paths):
            raise ResetSafetyError("[RESET_CONTROL_PATHS_COLLIDE]")

        cleanup_roots = [
            Path(scope["path"]).resolve(strict=False)
            for scope_group in ("chroma", "local_paths")
            for scope in manifest["scopes"][scope_group]
        ]
        for control_path in resolved_paths:
            if any(
                control_path == cleanup_root
                or control_path.is_relative_to(cleanup_root)
                for cleanup_root in cleanup_roots
            ):
                raise ResetSafetyError(
                    f"[RESET_CONTROL_PATH_INSIDE_CLEANUP_SCOPE:{control_path}]"
                )

    @staticmethod
    def _assert_snapshot_binding(
        *,
        manifest: dict[str, Any],
        snapshot: dict[str, Any],
        snapshot_path: Path,
        supplied_fingerprint: str,
    ) -> None:
        if snapshot.get("source_fingerprint") != supplied_fingerprint:
            raise ResetSafetyError("[RESET_SNAPSHOT_SOURCE_MISMATCH]")
        details = manifest.get("stages", {}).get("snapshot", {}).get("details", {})
        if not isinstance(details, dict):
            raise ResetSafetyError("[RESET_SNAPSHOT_STAGE_DETAILS_INVALID]")
        if details.get("checksum") != snapshot.get("snapshot_checksum"):
            raise ResetSafetyError("[RESET_SNAPSHOT_STAGE_CHECKSUM_MISMATCH]")
        recorded_path = Path(str(details.get("path") or "")).resolve(strict=False)
        if recorded_path != snapshot_path.resolve(strict=False):
            raise ResetSafetyError("[RESET_SNAPSHOT_STAGE_PATH_MISMATCH]")

    async def inspect(self, manifest_path: Path) -> dict[str, Any]:
        manifest = build_manifest_from_environment()
        self._assert_control_paths_are_safe(manifest, control_paths=(manifest_path,))
        inspections: dict[str, Any] = {}
        for name, cleaner in self._cleaners(manifest).items():
            inspections[name] = await cleaner.inspect()
        manifest["inspection"] = inspections
        if any(
            scope["mode"] == "shared_prefixes" for scope in manifest["scopes"]["redis"]
        ):
            manifest["warnings"].append(
                "shared Redis DB: only the explicit key prefixes in this manifest are in scope"
            )
        save_manifest(manifest_path, manifest)
        return manifest

    async def dry_run(self, manifest_path: Path) -> tuple[dict[str, Any], str]:
        manifest = await self.inspect(manifest_path)
        token = issue_confirmation_token(manifest)
        manifest["dry_run_at"] = utc_now_iso()
        save_manifest(manifest_path, manifest)
        return manifest, token

    async def _run_stage(
        self,
        *,
        manifest_path: Path,
        manifest: dict[str, Any],
        stage_name: str,
        action: Callable[[], Any | Awaitable[Any]],
    ) -> dict[str, Any]:
        stage = manifest.setdefault("stages", {}).setdefault(stage_name, {})
        if stage.get("status") == "completed":
            details = stage.get("details")
            return details if isinstance(details, dict) else {}
        stage.update({"status": "running", "started_at": utc_now_iso()})
        for stale_field in ("error_code", "failed_at", "completed_at", "details"):
            stage.pop(stale_field, None)
        save_manifest(manifest_path, manifest)
        try:
            result = action()
            if python_inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            stage.update(
                {
                    "status": "failed",
                    "failed_at": utc_now_iso(),
                    "error_code": _safe_error_code(exc),
                }
            )
            save_manifest(manifest_path, manifest)
            raise
        details = result if isinstance(result, dict) else {"result": result}
        stage.update(
            {
                "status": "completed",
                "completed_at": utc_now_iso(),
                "details": details,
            }
        )
        save_manifest(manifest_path, manifest)
        return details

    @staticmethod
    def _assert_current_plan_matches(manifest: dict[str, Any]) -> None:
        current = build_manifest_from_environment()
        if current["plan_checksum"] != manifest.get("plan_checksum"):
            raise ResetSafetyError("[RESET_CURRENT_SCOPE_MISMATCH]")

    async def apply(
        self,
        *,
        manifest_path: Path,
        snapshot_path: Path,
        supplied_fingerprint: str,
        confirmation_token: str,
        admin_email: str,
        admin_name: str,
        initial_password: str,
    ) -> dict[str, Any]:
        manifest = load_manifest(manifest_path)
        if manifest.get("applied_at"):
            raise ResetSafetyError("[RESET_MANIFEST_ALREADY_APPLIED]")
        self._assert_current_plan_matches(manifest)
        self._assert_control_paths_are_safe(
            manifest, control_paths=(manifest_path, snapshot_path)
        )
        verify_confirmation_token(manifest, confirmation_token)

        current_target = inspect_postgresql_target(
            self.database_url, manifest["scopes"]["postgresql"]
        )
        require_apply_authorization(
            manifest=manifest,
            current_fingerprint=str(current_target["fingerprint"]),
            supplied_fingerprint=supplied_fingerprint,
        )

        cleaners = self._cleaners(manifest)
        with PostgreSQLRunLock(self.database_url, supplied_fingerprint):
            snapshot_stage = manifest.get("stages", {}).get("snapshot", {})
            if snapshot_stage.get("status") != "completed":

                def create_snapshot() -> dict[str, Any]:
                    snapshot = export_config_snapshot(self.database_url)
                    snapshot["source_fingerprint"] = supplied_fingerprint
                    without_checksum = {
                        key: value
                        for key, value in snapshot.items()
                        if key != "snapshot_checksum"
                    }
                    snapshot["snapshot_checksum"] = sha256_json(without_checksum)
                    write_snapshot(snapshot_path, snapshot)
                    return {
                        "path": str(snapshot_path.resolve(strict=False)),
                        "checksum": snapshot["snapshot_checksum"],
                        "sections": len(snapshot["sections"]),
                    }

                await self._run_stage(
                    manifest_path=manifest_path,
                    manifest=manifest,
                    stage_name="snapshot",
                    action=create_snapshot,
                )
            snapshot = load_snapshot(snapshot_path)
            self._assert_snapshot_binding(
                manifest=manifest,
                snapshot=snapshot,
                snapshot_path=snapshot_path,
                supplied_fingerprint=supplied_fingerprint,
            )

            for name, cleaner in cleaners.items():
                if name == "postgresql":
                    continue
                await self._run_stage(
                    manifest_path=manifest_path,
                    manifest=manifest,
                    stage_name=f"clean_{name}",
                    action=cleaner.apply,
                )

            await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="clean_postgresql",
                action=cleaners["postgresql"].apply,
            )
            await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="schema",
                action=AlembicSchemaBootstrap(self.database_url).upgrade_head,
            )
            await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="system_seed",
                action=SystemSeedService(self.database_url).seed,
            )
            admin_result = await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="admin_bootstrap",
                action=lambda: ManagedAdminBootstrap(self.database_url).bootstrap(
                    email=admin_email,
                    name=admin_name,
                    initial_password=initial_password,
                ),
            )
            admin_user_id = str(admin_result["user_id"])
            await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="config_restore",
                action=lambda: restore_config_snapshot(
                    self.database_url,
                    snapshot,
                    admin_user_id=admin_user_id,
                ),
            )
            verification = await self._run_stage(
                manifest_path=manifest_path,
                manifest=manifest,
                stage_name="verify",
                action=lambda: IndependentVerifier(self.database_url).verify(
                    admin_email=admin_email,
                    expected_config_fingerprint=str(snapshot["sections_fingerprint"]),
                ),
            )

        manifest["applied_at"] = utc_now_iso()
        manifest["confirmation_token_hash"] = None
        manifest["result"] = "completed"
        save_manifest(manifest_path, manifest)
        return dict(verification)

    async def verify(
        self,
        *,
        manifest_path: Path,
        snapshot_path: Path | None,
        admin_email: str | None,
    ) -> dict[str, Any]:
        manifest = load_manifest(manifest_path)
        self._assert_current_plan_matches(manifest)
        self._assert_control_paths_are_safe(
            manifest,
            control_paths=(manifest_path,)
            if snapshot_path is None
            else (manifest_path, snapshot_path),
        )
        snapshot = load_snapshot(snapshot_path) if snapshot_path else None
        expected_config_fingerprint = (
            str(snapshot["sections_fingerprint"]) if snapshot else None
        )
        result: dict[str, Any] = {
            "database": IndependentVerifier(self.database_url).verify(
                admin_email=admin_email,
                expected_config_fingerprint=expected_config_fingerprint,
            ),
            "external": {},
        }
        for name, cleaner in self._cleaners(manifest).items():
            if name == "postgresql":
                continue
            verification = await cleaner.verify()
            result["external"][name] = verification
            if not verification.get("clean"):
                raise ResetExecutionError(f"[RESET_VERIFY_{name.upper()}_NOT_CLEAN]")
        return result


__all__ = ["ResetApplicationService"]
