"""Schema validation for governed business-rule configs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common.business_rules.defaults import (
    ACHIEVEMENT_RULES_KEY,
    AI_COACH_RULES_KEY,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
)

_SCORE_FIELDS = {"logic_score", "accuracy_score", "completeness_score"}
_ACHIEVEMENT_CONDITION_TYPES = {"evaluable_session_count", "max_overall_score"}


class BusinessRuleValidationError(ValueError):
    """Raised when a business-rule config value violates its schema."""


def validate_business_rule_value(key: str, value: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a business-rule config payload."""

    get_business_rule_definition(key)
    if not isinstance(value, dict):
        raise BusinessRuleValidationError("value must be an object")
    if key == ACHIEVEMENT_RULES_KEY:
        return _validate_achievement_ruleset(value)
    if key == AI_COACH_RULES_KEY:
        return _validate_ai_coach_ruleset(value)
    if key == NEXT_PRACTICE_RECOMMENDATION_KEY:
        return _validate_recommendation_ruleset(value)
    if key == SALES_COMBINATION_RULES_KEY:
        return _validate_sales_combination_ruleset(value)
    raise BusinessRuleValidationError(f"unsupported business rule key: {key}")


def _required_string(
    payload: dict[str, Any], field: str, *, max_length: int = 255
) -> str:
    raw = payload.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise BusinessRuleValidationError(f"{field} is required")
    cleaned = raw.strip()
    if len(cleaned) > max_length:
        raise BusinessRuleValidationError(f"{field} must be <= {max_length} characters")
    return cleaned


def _optional_string(
    payload: dict[str, Any],
    field: str,
    *,
    default: str | None = None,
    max_length: int = 500,
) -> str | None:
    raw = payload.get(field, default)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise BusinessRuleValidationError(f"{field} must be a string")
    cleaned = raw.strip()
    if len(cleaned) > max_length:
        raise BusinessRuleValidationError(f"{field} must be <= {max_length} characters")
    return cleaned


def _threshold(value: Any, *, field: str) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError) as exc:
        raise BusinessRuleValidationError(f"{field} must be numeric") from exc
    if threshold <= 0 or threshold > 100:
        raise BusinessRuleValidationError(f"{field} must be within (0, 100]")
    return threshold


def _format_template(template: str, *, field: str) -> str:
    try:
        template.format(
            label="维度",
            score=55.0,
            threshold=60.0,
            source_session_id="session-1",
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise BusinessRuleValidationError(f"{field} has invalid placeholders") from exc
    return template


def _validate_achievement_ruleset(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))

    achievements = normalized.get("achievements")
    if not isinstance(achievements, list):
        raise BusinessRuleValidationError("achievements must be a list")

    seen_codes: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(achievements):
        if not isinstance(item, dict):
            raise BusinessRuleValidationError(
                f"achievements[{index}] must be an object"
            )
        code = _required_string(item, "code", max_length=80)
        if code in seen_codes:
            raise BusinessRuleValidationError(f"duplicate achievement code: {code}")
        seen_codes.add(code)
        condition = item.get("condition")
        if not isinstance(condition, dict):
            raise BusinessRuleValidationError(
                f"achievements[{index}].condition is required"
            )
        condition_type = _required_string(condition, "type", max_length=60)
        if condition_type not in _ACHIEVEMENT_CONDITION_TYPES:
            raise BusinessRuleValidationError(
                f"unsupported achievement condition type: {condition_type}"
            )
        raw_min = condition.get("min", 1)
        minimum: int | float
        if condition_type == "evaluable_session_count":
            try:
                minimum = int(raw_min)
            except (TypeError, ValueError) as exc:
                raise BusinessRuleValidationError(
                    "condition.min must be an integer"
                ) from exc
            if minimum < 1 or minimum > 10000:
                raise BusinessRuleValidationError(
                    "condition.min must be within [1, 10000]"
                )
        else:
            minimum = _threshold(raw_min, field="condition.min")

        normalized_items.append(
            {
                "code": code,
                "name": _required_string(item, "name", max_length=120),
                "description": _required_string(item, "description", max_length=1000),
                "icon_key": _optional_string(
                    item,
                    "icon_key",
                    default="trophy",
                    max_length=60,
                )
                or "trophy",
                "condition": {"type": condition_type, "min": minimum},
                "enabled": bool(item.get("enabled", True)),
            }
        )
    normalized["achievements"] = normalized_items
    return normalized


def _validate_ai_coach_ruleset(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    normalized["weak_score_threshold"] = _threshold(
        normalized.get("weak_score_threshold", 60.0),
        field="weak_score_threshold",
    )

    dimensions = normalized.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise BusinessRuleValidationError("dimensions must be a non-empty list")
    seen_keys: set[str] = set()
    normalized_dimensions: list[dict[str, str]] = []
    for index, item in enumerate(dimensions):
        if not isinstance(item, dict):
            raise BusinessRuleValidationError(f"dimensions[{index}] must be an object")
        key = _required_string(item, "key", max_length=80)
        if key in seen_keys:
            raise BusinessRuleValidationError(f"duplicate dimension key: {key}")
        seen_keys.add(key)
        score_field = _required_string(item, "score_field", max_length=80)
        if score_field not in _SCORE_FIELDS:
            raise BusinessRuleValidationError(f"unsupported score_field: {score_field}")
        normalized_dimensions.append(
            {
                "key": key,
                "label": _required_string(item, "label", max_length=120),
                "score_field": score_field,
            }
        )
    normalized["dimensions"] = normalized_dimensions

    template = normalized.get("notification_template")
    if template is None:
        normalized["notification_template"] = None
        return normalized
    if not isinstance(template, dict):
        raise BusinessRuleValidationError(
            "notification_template must be an object or null"
        )
    title_template = _format_template(
        _required_string(template, "title_template", max_length=180),
        field="notification_template.title_template",
    )
    content_template = _format_template(
        _required_string(template, "content_template", max_length=1200),
        field="notification_template.content_template",
    )
    action_path_template = _format_template(
        _required_string(template, "action_path_template", max_length=500),
        field="notification_template.action_path_template",
    )
    normalized["notification_template"] = {
        "title_template": title_template,
        "content_template": content_template,
        "action_label": _required_string(template, "action_label", max_length=80),
        "action_path_template": action_path_template,
    }
    return normalized


def _validate_recommendation_ruleset(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    normalized["weak_score_threshold"] = _threshold(
        normalized.get("weak_score_threshold", 60.0),
        field="weak_score_threshold",
    )

    dimensions = normalized.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise BusinessRuleValidationError("dimensions must be a non-empty object")
    normalized_dimensions: dict[str, dict[str, str]] = {}
    for raw_key, item in dimensions.items():
        key = str(raw_key).strip()
        if not key:
            raise BusinessRuleValidationError("dimension key cannot be empty")
        if not isinstance(item, dict):
            raise BusinessRuleValidationError(f"dimensions.{key} must be an object")
        score_field = _required_string(item, "score_field", max_length=80)
        if score_field not in _SCORE_FIELDS:
            raise BusinessRuleValidationError(f"unsupported score_field: {score_field}")
        reason_template = _format_template(
            _required_string(item, "reason_template", max_length=1200),
            field=f"dimensions.{key}.reason_template",
        )
        normalized_dimensions[key] = {
            "score_field": score_field,
            "label": _required_string(item, "label", max_length=120),
            "title": _required_string(item, "title", max_length=180),
            "reason_template": reason_template,
            "action_label": _required_string(item, "action_label", max_length=80),
            "target_path": _required_string(item, "target_path", max_length=500),
        }
    normalized["dimensions"] = normalized_dimensions

    fallback = normalized.get("fallback")
    if not isinstance(fallback, dict):
        raise BusinessRuleValidationError("fallback must be an object")
    normalized["fallback"] = {
        "title": _required_string(fallback, "title", max_length=180),
        "reason": _required_string(fallback, "reason", max_length=1200),
        "action_label": _required_string(fallback, "action_label", max_length=80),
        "target_path": _required_string(fallback, "target_path", max_length=500),
    }
    return normalized


def _validate_sales_combination_ruleset(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["rule_set_id"] = _required_string(
        normalized,
        "rule_set_id",
        max_length=120,
    )
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))

    fallback_policy = _optional_string(
        normalized,
        "fallback_policy",
        default="client_default_v1",
        max_length=40,
    )
    if fallback_policy not in {"client_default_v1", "hide_all"}:
        raise BusinessRuleValidationError(
            "fallback_policy must be client_default_v1 or hide_all"
        )
    normalized["fallback_policy"] = fallback_policy

    combinations = normalized.get("combinations")
    if not isinstance(combinations, list):
        raise BusinessRuleValidationError("combinations must be a list")
    if not combinations and fallback_policy != "hide_all":
        raise BusinessRuleValidationError(
            "combinations must be non-empty unless fallback_policy is hide_all"
        )

    seen_ids: set[str] = set()
    seen_pairs: set[str] = set()
    normalized_combinations: list[dict[str, Any]] = []
    enabled_count = 0
    for index, item in enumerate(combinations):
        if not isinstance(item, dict):
            raise BusinessRuleValidationError(
                f"combinations[{index}] must be an object"
            )

        combination_id = _required_string(item, "id", max_length=80)
        if combination_id in seen_ids:
            raise BusinessRuleValidationError(
                f"duplicate combination id: {combination_id}"
            )
        seen_ids.add(combination_id)

        capability = _required_string(item, "capability", max_length=120)
        role = _required_string(item, "role", max_length=120)
        pair_key = f"{capability}::{role}".lower()
        if pair_key in seen_pairs:
            raise BusinessRuleValidationError(
                f"duplicate capability/role pair: {capability} × {role}"
            )
        seen_pairs.add(pair_key)

        try:
            priority = int(item.get("priority"))
        except (TypeError, ValueError) as exc:
            raise BusinessRuleValidationError(
                f"combinations[{index}].priority must be a positive number"
            ) from exc
        if priority <= 0:
            raise BusinessRuleValidationError(
                f"combinations[{index}].priority must be a positive number"
            )

        enabled = item.get("enabled", True) is not False
        if enabled:
            enabled_count += 1

        normalized_combinations.append(
            {
                "id": combination_id,
                "capability": capability,
                "role": role,
                "priority": priority,
                "enabled": enabled,
                "required_agent_match": _string_list(
                    item.get("required_agent_match"),
                    field=f"combinations[{index}].required_agent_match",
                ),
                "required_persona_match": _string_list(
                    item.get("required_persona_match"),
                    field=f"combinations[{index}].required_persona_match",
                ),
            }
        )

    if normalized_combinations and enabled_count == 0 and fallback_policy != "hide_all":
        raise BusinessRuleValidationError(
            "all combinations are disabled; fallback_policy must be hide_all"
        )

    normalized["combinations"] = sorted(
        normalized_combinations,
        key=lambda item: (item["priority"], item["id"]),
    )
    return normalized


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise BusinessRuleValidationError(f"{field} must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise BusinessRuleValidationError(f"{field}[{index}] must be a string")
        cleaned = item.strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized
