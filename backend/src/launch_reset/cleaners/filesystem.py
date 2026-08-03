"""Filesystem cleaner that deletes contents but preserves explicit roots."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from launch_reset.errors import ResetSafetyError


class FilesystemCleaner:
    def __init__(self, *, name: str, scopes: list[dict[str, str]]) -> None:
        self.name = name
        self.scopes = scopes

    @staticmethod
    def _validate_runtime_root(path: Path) -> None:
        if path.is_symlink():
            raise ResetSafetyError(f"[RESET_FILESYSTEM_ROOT_SYMLINK:{path}]")
        if path.exists() and not path.is_dir():
            raise ResetSafetyError(f"[RESET_FILESYSTEM_ROOT_NOT_DIRECTORY:{path}]")

    @staticmethod
    def _inventory(path: Path) -> dict[str, int | bool]:
        if not path.exists():
            return {"exists": False, "files": 0, "directories": 0, "bytes": 0}
        files = 0
        directories = 0
        size_bytes = 0
        for item in path.rglob("*"):
            if item.is_symlink():
                files += 1
                continue
            if item.is_dir():
                directories += 1
            elif item.is_file():
                files += 1
                size_bytes += item.stat().st_size
        return {
            "exists": True,
            "files": files,
            "directories": directories,
            "bytes": size_bytes,
        }

    async def inspect(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for scope in self.scopes:
            path = Path(scope["path"])
            self._validate_runtime_root(path)
            items.append({**scope, **self._inventory(path)})
        return {"items": items}

    async def apply(self) -> dict[str, Any]:
        deleted_roots = 0
        for scope in self.scopes:
            path = Path(scope["path"])
            self._validate_runtime_root(path)
            if not path.exists():
                continue
            for child in path.iterdir():
                if child.is_symlink() or child.is_file():
                    child.unlink()
                elif child.is_dir():
                    shutil.rmtree(child)
            deleted_roots += 1
        verification = await self.verify()
        if not verification["clean"]:
            raise ResetSafetyError(f"[RESET_{self.name.upper()}_VERIFY_FAILED]")
        return {"cleared_roots": deleted_roots, "clean": True}

    async def verify(self) -> dict[str, Any]:
        inspection = await self.inspect()
        clean = all(
            item["files"] == 0 and item["directories"] == 0
            for item in inspection["items"]
        )
        return {**inspection, "clean": clean}


__all__ = ["FilesystemCleaner"]
