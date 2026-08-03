from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "run_foundation_ai_provider_staging.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "foundation_ai_provider_staging_test_module",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_required_environment_passes_normalized_base_url_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    monkeypatch.setenv("FOUNDATION_AI_REAL_PROVIDER_CONFIRM", "1")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "synthetic-provider-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1/")
    monkeypatch.setenv("LLM_MODEL", "synthetic-model")

    config = module._required_environment()

    assert config["base_url"] == "https://api.deepseek.com/v1"
    assert isinstance(config["base_url"], str)
