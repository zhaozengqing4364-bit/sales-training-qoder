"""Regression proof for the auth bootstrap recovery entrypoint."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import configure_mappers

ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT_DIR / "backend" / "scripts" / "bootstrap_auth_admin.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_auth_admin", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"Missing script: {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_auth_admin_registers_agent_related_mappers() -> None:
    module = _load_module()

    assert hasattr(module, "bootstrap_user")
    configure_mappers()
