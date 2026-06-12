from __future__ import annotations

from typing import Any


def learner_safe_unit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("config")
    if not isinstance(config, dict):
        return payload
    path_config = config.get("path")
    if not isinstance(path_config, dict) or "ai_coach" not in path_config:
        return payload

    safe_path_config = dict(path_config)
    safe_path_config.pop("ai_coach", None)
    safe_config = dict(config)
    safe_config["path"] = safe_path_config

    return {
        **payload,
        "config": safe_config,
    }
