"""Load COO short-answer AI scoring prompts for seed scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS_PATH = Path(__file__).resolve().parent / "coo_short_answer_prompts.json"


def load_short_answer_prompts(path: Path | None = None) -> dict[str, Any]:
    target = path or PROMPTS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def resolve_short_answer_ai_scoring(
    spec: dict[str, Any],
    *,
    prompts_data: dict[str, Any] | None = None,
    enabled: bool = True,
    pass_threshold: float = 70,
) -> dict[str, Any]:
    """Build ai_scoring config for a short_answer question spec."""
    data = prompts_data if prompts_data is not None else load_short_answer_prompts()
    series_key = str(spec.get("series_index", ""))
    series_prompts = (data.get("series") or {}).get(series_key) or {}
    default_prompts = data.get("default") or {}

    spec_override = spec.get("ai_scoring")
    override = dict(spec_override) if isinstance(spec_override, dict) else {}

    system_prompt = (
        override.get("system_prompt")
        or series_prompts.get("system_prompt")
        or default_prompts.get("system_prompt")
    )
    prompt_template = (
        override.get("prompt_template")
        or series_prompts.get("prompt_template")
        or default_prompts.get("prompt_template")
    )

    config: dict[str, Any] = {
        "enabled": override.get("enabled", enabled),
        "pass_threshold": override.get("pass_threshold", pass_threshold),
        "temperature": override.get("temperature", 0.2),
        "timeout": override.get("timeout", 30),
        "max_retries": override.get("max_retries", 1),
        "max_tokens": override.get("max_tokens", 800),
    }
    if system_prompt:
        config["system_prompt"] = system_prompt
    if prompt_template:
        config["prompt_template"] = prompt_template
    return config
