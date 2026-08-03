from __future__ import annotations

import pytest

from launch_reset.cleaners.filesystem import FilesystemCleaner
from launch_reset.errors import ResetSafetyError


@pytest.mark.asyncio
async def test_filesystem_cleaner_preserves_root_and_does_not_follow_child_symlink(
    tmp_path,
) -> None:
    root = tmp_path / "project-data"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "document.txt").write_text("delete", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "audio.webm").write_bytes(b"delete")
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "outside-link").symlink_to(outside, target_is_directory=True)
    cleaner = FilesystemCleaner(
        name="local_paths", scopes=[{"name": "files", "path": str(root)}]
    )

    result = await cleaner.apply()

    assert result == {"cleared_roots": 1, "clean": True}
    assert root.is_dir()
    assert list(root.iterdir()) == []
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.asyncio
async def test_filesystem_cleaner_rejects_symlink_root(tmp_path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    symlink = tmp_path / "configured-root"
    symlink.symlink_to(actual, target_is_directory=True)
    cleaner = FilesystemCleaner(
        name="local_paths", scopes=[{"name": "files", "path": str(symlink)}]
    )

    with pytest.raises(ResetSafetyError, match="FILESYSTEM_ROOT_SYMLINK"):
        await cleaner.inspect()
