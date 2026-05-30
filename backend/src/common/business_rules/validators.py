"""Schema validation for governed business-rule configs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common.business_rules.defaults import (
    ACHIEVEMENT_RULES_KEY,
    ADMIN_SETTINGS_GENERAL_KEY,
    ADMIN_SETTINGS_NOTIFICATIONS_KEY,
    ADMIN_SETTINGS_SECURITY_KEY,
    AI_COACH_RULES_KEY,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
    OBJECTION_LEDGER_RULES_KEY,
    ROLEPLAY_EVAL_RELEASE_GATE_KEY,
    ROLEPLAY_SITUATION_PACKS_KEY,
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
)

_SCORE_FIELDS = {"logic_score", "accuracy_score", "completeness_score"}
_ACHIEVEMENT_CONDITION_TYPES = {"evaluable_session_count", "max_overall_score"}
_ROLEPLAY_REQUIRED_PUBLISHED_CODES = {
    "first_visit",
    "follow_up",
    "proposal_review",
    "price_negotiation",
    "renewal",
    "complaint_recovery",
}
_ROLEPLAY_ALLOWED_VISIBLE_KEYS = {
    "industry",
    "company_profile",
    "customer_role",
    "pain_points",
    "objections",
    "success_criteria",
    "hidden_information",
    "budget",
    "decision_chain",
    "competitor_quote",
    "internal_floor_price",
    "renewal_risk",
    "compensation_boundary",
}
_ROLEPLAY_RELATIONSHIP_VALUES = {
    "none",
    "one_meeting",
    "multiple_meetings",
    "existing_customer",
    "unspecified",
}
_ROLEPLAY_PACK_STATUSES = {"draft", "published", "archived"}
_ROLEPLAY_CONFLICT_STRATEGIES = {
    "customer_confused_correction",
    "neutral_clarification",
    "strict_refusal",
}
_ROLEPLAY_VIOLATION_ACTIONS = {
    "cancel_or_regenerate_once",
    "regenerate_once",
    "cancel_stream",
    "hard_fail",
    "mark_and_continue",
    "mark_for_report",
}
_ROLEPLAY_POLICY_KEYS = {
    "relationship_history_contradiction",
    "hidden_information_leak",
    "forbidden_topic",
    "persona_style_drift",
}
_ROLEPLAY_EVAL_GATE_MODES = {"blocking", "warn_only", "disabled"}
_ROLEPLAY_GRADER_MODES = {"blocking", "warn_only", "disabled"}


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
    if key == OBJECTION_LEDGER_RULES_KEY:
        return _validate_objection_ledger_ruleset(value)
    if key == ROLEPLAY_SITUATION_PACKS_KEY:
        return _validate_roleplay_situation_packs(value)
    if key == ROLEPLAY_EVAL_RELEASE_GATE_KEY:
        return _validate_roleplay_eval_release_gate(value)
    if key == ADMIN_SETTINGS_GENERAL_KEY:
        return _validate_admin_general_settings(value)
    if key == ADMIN_SETTINGS_SECURITY_KEY:
        return _validate_admin_security_settings(value)
    if key == ADMIN_SETTINGS_NOTIFICATIONS_KEY:
        return _validate_admin_notification_settings(value)
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


def _validate_roleplay_eval_release_gate(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    deterministic_mode = _required_string(
        normalized,
        "deterministic_gate_mode",
        max_length=40,
    )
    if deterministic_mode not in _ROLEPLAY_EVAL_GATE_MODES:
        raise BusinessRuleValidationError(
            f"unsupported deterministic_gate_mode: {deterministic_mode}"
        )
    llm_mode = _required_string(normalized, "llm_grader_mode", max_length=40)
    if llm_mode not in _ROLEPLAY_GRADER_MODES:
        raise BusinessRuleValidationError(f"unsupported llm_grader_mode: {llm_mode}")
    blocking_codes = normalized.get("blocking_violation_codes", [])
    if not isinstance(blocking_codes, list):
        raise BusinessRuleValidationError("blocking_violation_codes must be a list")
    normalized["blocking_violation_codes"] = [
        _required_string({"code": code}, "code", max_length=120)
        for code in blocking_codes
    ]
    try:
        retention_days = int(normalized.get("artifact_retention_days", 30))
    except (TypeError, ValueError) as exc:
        raise BusinessRuleValidationError(
            "artifact_retention_days must be an integer"
        ) from exc
    if retention_days < 1 or retention_days > 365:
        raise BusinessRuleValidationError(
            "artifact_retention_days must be within [1, 365]"
        )
    normalized["deterministic_gate_mode"] = deterministic_mode
    normalized["llm_grader_mode"] = llm_mode
    normalized["artifact_retention_days"] = retention_days
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

        raw_priority = item.get("priority")
        if raw_priority is None:
            raise BusinessRuleValidationError(
                f"combinations[{index}].priority must be a positive number"
            )
        try:
            priority = int(raw_priority)
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


def _validate_objection_ledger_ruleset(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["rule_set_id"] = _required_string(
        normalized,
        "rule_set_id",
        max_length=120,
    )
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    normalized["ack_patterns"] = _string_list(
        normalized.get("ack_patterns"),
        field="ack_patterns",
    )
    if not normalized["ack_patterns"]:
        raise BusinessRuleValidationError("ack_patterns must be non-empty")
    normalized["open_stage_names"] = _string_list(
        normalized.get("open_stage_names"),
        field="open_stage_names",
    )
    if not normalized["open_stage_names"]:
        raise BusinessRuleValidationError("open_stage_names must be non-empty")
    normalized["numeric_evidence_tokens"] = _string_list(
        normalized.get("numeric_evidence_tokens"),
        field="numeric_evidence_tokens",
    )

    families = normalized.get("families")
    if not isinstance(families, dict) or not families:
        raise BusinessRuleValidationError("families must be a non-empty object")
    normalized_families: dict[str, dict[str, Any]] = {}
    focus_dimensions: set[str] = set()
    for raw_family, raw_config in families.items():
        family = str(raw_family).strip()
        if not family:
            raise BusinessRuleValidationError("family key cannot be empty")
        if not isinstance(raw_config, dict):
            raise BusinessRuleValidationError(f"families.{family} must be an object")
        focus_dimension = _required_string(
            raw_config,
            "focus_dimension",
            max_length=120,
        )
        focus_dimensions.add(focus_dimension)
        normalized_families[family] = {
            "focus_dimension": focus_dimension,
            "promised_proof": _required_string(
                raw_config,
                "promised_proof",
                max_length=500,
            ),
            "next_expected_evidence": _required_string(
                raw_config,
                "next_expected_evidence",
                max_length=500,
            ),
            "detect_any": _non_empty_string_list(
                raw_config.get("detect_any"),
                field=f"families.{family}.detect_any",
            ),
            "evidence_any": _non_empty_string_list(
                raw_config.get("evidence_any"),
                field=f"families.{family}.evidence_any",
            ),
            "open_pressure_any": _non_empty_string_list(
                raw_config.get("open_pressure_any"),
                field=f"families.{family}.open_pressure_any",
            ),
            "open_pressure_requires_any": _string_list(
                raw_config.get("open_pressure_requires_any"),
                field=f"families.{family}.open_pressure_requires_any",
            ),
        }
    normalized["families"] = normalized_families

    synthetic = normalized.get("synthetic_dimensions_by_focus")
    if not isinstance(synthetic, dict) or not synthetic:
        raise BusinessRuleValidationError(
            "synthetic_dimensions_by_focus must be a non-empty object"
        )
    normalized_synthetic: dict[str, dict[str, float]] = {}
    for focus_dimension in focus_dimensions:
        raw_scores = synthetic.get(focus_dimension)
        if not isinstance(raw_scores, dict) or not raw_scores:
            raise BusinessRuleValidationError(
                f"synthetic_dimensions_by_focus.{focus_dimension} is required"
            )
        normalized_scores: dict[str, float] = {}
        for raw_name, raw_score in raw_scores.items():
            dimension_name = str(raw_name).strip()
            if not dimension_name:
                raise BusinessRuleValidationError(
                    f"synthetic_dimensions_by_focus.{focus_dimension} key cannot be empty"
                )
            normalized_scores[dimension_name] = _score(
                raw_score,
                field=f"synthetic_dimensions_by_focus.{focus_dimension}.{dimension_name}",
            )
        normalized_synthetic[focus_dimension] = normalized_scores
    normalized["synthetic_dimensions_by_focus"] = normalized_synthetic
    normalized["management_backlog"] = _optional_string(
        normalized,
        "management_backlog",
        default=None,
        max_length=1000,
    )
    return normalized


def _validate_roleplay_situation_packs(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    packs = normalized.get("packs")
    if not isinstance(packs, list) or not packs:
        raise BusinessRuleValidationError("packs must be a non-empty list")

    seen_codes: set[str] = set()
    published_codes: set[str] = set()
    normalized_packs: list[dict[str, Any]] = []
    for index, item in enumerate(packs):
        if not isinstance(item, dict):
            raise BusinessRuleValidationError(f"packs[{index}] must be an object")
        pack = _validate_roleplay_situation_pack(item, index=index)
        code = str(pack["code"])
        if code in seen_codes:
            raise BusinessRuleValidationError(f"duplicate roleplay situation code: {code}")
        seen_codes.add(code)
        if pack["status"] == "published":
            published_codes.add(code)
        normalized_packs.append(pack)

    missing = sorted(_ROLEPLAY_REQUIRED_PUBLISHED_CODES - published_codes)
    if missing:
        raise BusinessRuleValidationError(
            f"missing required published roleplay situation packs: {', '.join(missing)}"
        )
    normalized["packs"] = sorted(
        normalized_packs,
        key=lambda pack: (pack["code"], pack["version"]),
    )
    return normalized


def _validate_roleplay_situation_pack(
    item: dict[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    code = _required_string(item, "code", max_length=80)
    status = _one_of(
        item.get("status", "draft"),
        field=f"packs[{index}].status",
        allowed=_ROLEPLAY_PACK_STATUSES,
    )
    relationship = _roleplay_relationship_context(
        item.get("default_relationship_context"),
        field=f"packs[{index}].default_relationship_context",
    )
    visible_scope = _roleplay_visible_scope(
        item.get("default_visible_information_scope"),
        field=f"packs[{index}].default_visible_information_scope",
    )
    forbidden_patterns = _string_list(
        item.get("default_forbidden_claim_patterns"),
        field=f"packs[{index}].default_forbidden_claim_patterns",
    )
    if code == "first_visit" and status == "published" and not forbidden_patterns:
        raise BusinessRuleValidationError(
            "first_visit published pack requires default_forbidden_claim_patterns"
        )
    if code == "first_visit":
        if relationship.get("has_prior_meeting") is True:
            raise BusinessRuleValidationError(
                "first_visit cannot set has_prior_meeting=true"
            )
        summary = relationship.get("meeting_history_summary")
        if isinstance(summary, str) and summary.strip():
            raise BusinessRuleValidationError(
                "first_visit cannot include meeting_history_summary"
            )
    if code == "follow_up" and status == "published":
        prior = relationship.get("prior_interactions")
        if prior == "none":
            raise BusinessRuleValidationError(
                "follow_up cannot set prior_interactions=none"
            )
    return {
        "code": code,
        "label": _required_string(item, "label", max_length=120),
        "version": _required_string(item, "version", max_length=120),
        "status": status,
        "initial_stage_hint": _optional_string(
            item,
            "initial_stage_hint",
            default="opening",
            max_length=80,
        )
        or "opening",
        "default_relationship_context": relationship,
        "default_visible_information_scope": visible_scope,
        "default_forbidden_claim_patterns": forbidden_patterns,
        "default_forbidden_topic_codes": _string_list(
            item.get("default_forbidden_topic_codes"),
            field=f"packs[{index}].default_forbidden_topic_codes",
        ),
        "default_forbidden_stage_codes": _string_list(
            item.get("default_forbidden_stage_codes"),
            field=f"packs[{index}].default_forbidden_stage_codes",
        ),
        "stage_transition_notes": _string_list(
            item.get("stage_transition_notes"),
            field=f"packs[{index}].stage_transition_notes",
        ),
        "default_conflict_response_strategy": _one_of(
            item.get("default_conflict_response_strategy", "neutral_clarification"),
            field=f"packs[{index}].default_conflict_response_strategy",
            allowed=_ROLEPLAY_CONFLICT_STRATEGIES,
        ),
        "default_behavior_rules_for_prompt_only": _string_list(
            item.get("default_behavior_rules_for_prompt_only"),
            field=f"packs[{index}].default_behavior_rules_for_prompt_only",
        ),
        "default_disclosure_policy": _roleplay_disclosure_policy(
            item.get("default_disclosure_policy"),
            field=f"packs[{index}].default_disclosure_policy",
        ),
        "default_runtime_violation_policy": _roleplay_violation_policy(
            item.get("default_runtime_violation_policy"),
            field=f"packs[{index}].default_runtime_violation_policy",
        ),
        "compatible_practice_modes": _non_empty_string_list(
            item.get("compatible_practice_modes"),
            field=f"packs[{index}].compatible_practice_modes",
        ),
        "compatible_scenario_types": _non_empty_string_list(
            item.get("compatible_scenario_types"),
            field=f"packs[{index}].compatible_scenario_types",
        ),
    }


def _roleplay_relationship_context(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BusinessRuleValidationError(f"{field} must be an object")
    prior = _one_of(
        value.get("prior_interactions", "unspecified"),
        field=f"{field}.prior_interactions",
        allowed=_ROLEPLAY_RELATIONSHIP_VALUES,
    )
    summary = value.get("meeting_history_summary")
    if summary is not None and not isinstance(summary, str):
        raise BusinessRuleValidationError(f"{field}.meeting_history_summary must be a string or null")
    if prior == "none" and isinstance(summary, str) and summary.strip():
        raise BusinessRuleValidationError(
            f"{field}.meeting_history_summary requires prior_interactions != none"
        )
    return {
        "prior_interactions": prior,
        "has_prior_meeting": _optional_bool(value.get("has_prior_meeting")),
        "has_seen_proposal": _optional_bool(value.get("has_seen_proposal")),
        "has_discussed_budget": _optional_bool(value.get("has_discussed_budget")),
        "has_existing_partnership": _optional_bool(value.get("has_existing_partnership")),
        "meeting_history_summary": summary.strip() if isinstance(summary, str) and summary.strip() else None,
    }


def _roleplay_visible_scope(value: Any, *, field: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise BusinessRuleValidationError(f"{field} must be an object")
    initial = _string_list(value.get("initial_visible_keys"), field=f"{field}.initial_visible_keys")
    conditional = _string_list(
        value.get("conditionally_visible_keys"),
        field=f"{field}.conditionally_visible_keys",
    )
    hidden = _string_list(value.get("hidden_by_default_keys"), field=f"{field}.hidden_by_default_keys")
    unknown = sorted((set(initial) | set(conditional) | set(hidden)) - _ROLEPLAY_ALLOWED_VISIBLE_KEYS)
    if unknown:
        raise BusinessRuleValidationError(
            f"{field} contains unsupported keys: {', '.join(unknown)}"
        )
    overlap = sorted(set(initial) & set(hidden))
    if overlap:
        raise BusinessRuleValidationError(
            f"{field} hidden keys cannot be initially visible: {', '.join(overlap)}"
        )
    conditional = list(dict.fromkeys([*conditional, *[key for key in hidden if key not in initial]]))
    return {
        "initial_visible_keys": list(dict.fromkeys(initial)),
        "conditionally_visible_keys": conditional,
        "hidden_by_default_keys": list(dict.fromkeys(hidden)),
    }


def _roleplay_disclosure_policy(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {"default_hidden": True, "phases": [], "never_disclose_keys": []}
    if not isinstance(value, dict):
        raise BusinessRuleValidationError(f"{field} must be an object")
    phases = value.get("phases", [])
    if not isinstance(phases, list):
        raise BusinessRuleValidationError(f"{field}.phases must be a list")
    return {
        "default_hidden": True,
        "phases": [item for item in phases if isinstance(item, dict)],
        "never_disclose_keys": _string_list(
            value.get("never_disclose_keys"),
            field=f"{field}.never_disclose_keys",
        ),
    }


def _roleplay_violation_policy(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise BusinessRuleValidationError(f"{field} must be an object")
    normalized: dict[str, str] = {}
    for key in sorted(_ROLEPLAY_POLICY_KEYS):
        action = _one_of(
            value.get(key, "mark_for_report"),
            field=f"{field}.{key}",
            allowed=_ROLEPLAY_VIOLATION_ACTIONS,
        )
        normalized[key] = action
    unknown = set(value) - _ROLEPLAY_POLICY_KEYS
    if unknown:
        raise BusinessRuleValidationError(
            f"{field} contains unsupported policy keys: {', '.join(sorted(unknown))}"
        )
    return normalized


def _validate_admin_general_settings(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    normalized["platform_name"] = _required_string(
        normalized,
        "platform_name",
        max_length=120,
    )
    normalized["support_email"] = _required_string(
        normalized,
        "support_email",
        max_length=255,
    )
    if "@" not in normalized["support_email"]:
        raise BusinessRuleValidationError("support_email must be a valid email")
    normalized["welcome_message"] = _required_string(
        normalized,
        "welcome_message",
        max_length=500,
    )
    normalized["default_language"] = _one_of(
        normalized.get("default_language", "zh-CN"),
        field="default_language",
        allowed={"zh-CN", "en-US"},
    )
    normalized["timezone"] = _one_of(
        normalized.get("timezone", "Asia/Shanghai"),
        field="timezone",
        allowed={"Asia/Shanghai", "UTC"},
    )
    normalized["date_format"] = _one_of(
        normalized.get("date_format", "YYYY-MM-DD"),
        field="date_format",
        allowed={"YYYY-MM-DD", "MM/DD/YYYY"},
    )
    return normalized


def _validate_admin_security_settings(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    normalized["enforce_admin_2fa"] = bool(normalized.get("enforce_admin_2fa", True))
    normalized["new_device_login_alert"] = bool(
        normalized.get("new_device_login_alert", True)
    )
    normalized["password_min_length"] = _integer_range(
        normalized.get("password_min_length", 8),
        field="password_min_length",
        minimum=8,
        maximum=128,
    )
    normalized["password_expiry_days"] = _integer_range(
        normalized.get("password_expiry_days", 90),
        field="password_expiry_days",
        minimum=0,
        maximum=365,
    )
    return normalized


def _validate_admin_notification_settings(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    normalized["version"] = _required_string(normalized, "version", max_length=120)
    normalized["enabled"] = bool(normalized.get("enabled", True))
    email_notifications = normalized.get("email_notifications")
    if not isinstance(email_notifications, dict):
        raise BusinessRuleValidationError("email_notifications must be an object")
    allowed = {
        "user_registration_admin",
        "system_exception_alert",
        "weekly_report",
        "knowledge_base_update",
    }
    normalized["email_notifications"] = {
        key: bool(email_notifications.get(key, False)) for key in sorted(allowed)
    }
    unknown = set(email_notifications) - allowed
    if unknown:
        raise BusinessRuleValidationError(
            f"unsupported email notification keys: {', '.join(sorted(unknown))}"
        )
    return normalized


def _score(value: Any, *, field: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise BusinessRuleValidationError(f"{field} must be numeric") from exc
    if score < 0 or score > 100:
        raise BusinessRuleValidationError(f"{field} must be within [0, 100]")
    return round(score, 2)


def _integer_range(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise BusinessRuleValidationError(f"{field} must be an integer") from exc
    if normalized < minimum or normalized > maximum:
        raise BusinessRuleValidationError(
            f"{field} must be within [{minimum}, {maximum}]"
        )
    return normalized


def _one_of(value: Any, *, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise BusinessRuleValidationError(f"{field} must be a string")
    normalized = value.strip()
    if normalized not in allowed:
        raise BusinessRuleValidationError(
            f"{field} must be one of {', '.join(sorted(allowed))}"
        )
    return normalized


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise BusinessRuleValidationError("boolean field must be true, false, or null")


def _non_empty_string_list(value: Any, *, field: str) -> list[str]:
    normalized = _string_list(value, field=field)
    if not normalized:
        raise BusinessRuleValidationError(f"{field} must be non-empty")
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
