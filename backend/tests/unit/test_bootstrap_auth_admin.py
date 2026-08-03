"""Regression proof for the auth bootstrap recovery entrypoint."""

from __future__ import annotations

import importlib.util
import inspect
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


def test_bootstrap_auth_admin_uses_managed_credentials_without_department() -> None:
    module = _load_module()
    parameters = inspect.signature(module.bootstrap_user).parameters
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "password" in parameters
    assert "department" not in parameters
    assert "hashed_password=pwd_context.hash" in source
    assert "AUTH_SHARED_PASSWORD" not in source
    assert "AUTH_USER_PASSWORDS_JSON" not in source
