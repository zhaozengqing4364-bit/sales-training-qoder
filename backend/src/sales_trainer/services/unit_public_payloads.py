from __future__ import annotations

from typing import Any, cast

from sales_trainer.services.learner_public_projection import (
    strip_learner_internal_fields,
)


def learner_safe_unit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe_payload = cast(dict[str, Any], strip_learner_internal_fields(payload))
    config = safe_payload.get("config")
    if not isinstance(config, dict):
        return safe_payload
    path_config = config.get("path")
    if not isinstance(path_config, dict) or "ai_coach" not in path_config:
        return safe_payload

    safe_path_config = dict(path_config)
    safe_path_config.pop("ai_coach", None)
    safe_config = dict(config)
    safe_config["path"] = safe_path_config

    return {
        **safe_payload,
        "config": safe_config,
    }
