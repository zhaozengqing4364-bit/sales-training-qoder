"""Alembic migration graph invariants."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_upgrade_head_has_single_unique_head() -> None:
    """Regression: startup guidance uses ``alembic upgrade head``."""
    backend_root = Path(__file__).resolve().parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    script = ScriptDirectory.from_config(config)
    revisions = [revision.revision for revision in script.walk_revisions()]
    heads = script.get_heads()

    assert len(revisions) == len(set(revisions))
    assert len(heads) == 1, f"Expected exactly one Alembic head, got {heads!r}"
