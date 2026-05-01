"""
Persona policy normalization and legacy compatibility helpers.

Persona policy is the single source of truth for:
- Role core system prompt
- Bound knowledge base ids
- KB/network tool strategy
- Sales-focus behavior extensions used by runtime instruction compilation
"""

from __future__ import annotations

from typing import Any

PERSONA_POLICY_VERSION = 1

PERSONA_OWNED_TOOL_POLICY_KEYS: set[str] = {
    "enable_web_search",
    "enable_internal_retrieval",
    "retrieval_priority",
    "strict_instruction_following",
    "require_grounding",
    "network_access_mode",
    "enforcement_level",
    "allow_web_search_without_kb",
    "require_kb_grounding",
}

_BOOL_TOOL_POLICY_KEYS = {
    "enable_web_search",
    "enable_internal_retrieval",
    "strict_instruction_following",
    "require_grounding",
    "allow_web_search_without_kb",
    "require_kb_grounding",
}

_STRING_TOOL_POLICY_KEYS = {
    "retrieval_priority",
    "network_access_mode",
    "enforcement_level",
}

_PERSONA_STRING_EXTENSION_KEYS = {
    "sales_focus",
}

_PERSONA_LIST_EXTENSION_KEYS = {
    "value_axes",
    "objection_axes",
    "expected_customer_questions",
}

_CUSTOMER_PRESSURE_SOURCE_EXPLICIT = "explicit"
_CUSTOMER_PRESSURE_SOURCE_LEGACY = "legacy_sales_focus_extensions"
_CUSTOMER_PRESSURE_SOURCE_NONE = "none"

_CUSTOMER_PRESSURE_TOP_LEVEL_KEYS = {
    "source",
    "pressure_direction",
    "follow_up_behavior",
    "sales_focus",
    "value_axes",
    "objection_axes",
    "expected_customer_questions",
    "question_strategy",
    "revisit_on_evasion",
    "require_evidence",
}

_CUSTOMER_PRESSURE_DIRECTION_KEYS = {
    "sales_focus",
    "value_axes",
    "objection_axes",
}

_CUSTOMER_PRESSURE_FOLLOW_UP_KEYS = {
    "question_strategy",
    "revisit_on_evasion",
    "require_evidence",
    "expected_customer_questions",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _pick_policy_value(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    key: str,
    fallback: Any,
) -> Any:
    if key in primary:
        return primary.get(key)
    if key in secondary:
        return secondary.get(key)
    return fallback


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _dedupe_kb_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _normalize_extension_string(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return normalized.lower()


def _normalize_extension_string_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    else:
        return []

    normalized_items: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        dedupe_key = normalized.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_items.append(normalized)
    return normalized_items


def _normalize_question_strategy(value: Any, *, default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized:
        return normalized
    return default


def _normalize_customer_pressure(
    raw_policy: dict[str, Any],
    *,
    legacy_sales_focus: str,
    legacy_value_axes: list[str],
    legacy_objection_axes: list[str],
    legacy_expected_questions: list[str],
) -> dict[str, Any]:
    raw_customer_pressure = _as_dict(raw_policy.get("customer_pressure"))
    raw_pressure_direction = _as_dict(raw_customer_pressure.get("pressure_direction"))
    raw_follow_up_behavior = _as_dict(raw_customer_pressure.get("follow_up_behavior"))

    explicit_has_pressure = (
        bool(raw_pressure_direction)
        or bool(raw_follow_up_behavior)
        or any(
            key in raw_customer_pressure
            for key in (
                "sales_focus",
                "value_axes",
                "objection_axes",
                "expected_customer_questions",
                "question_strategy",
                "revisit_on_evasion",
                "require_evidence",
            )
        )
    )
    legacy_has_pressure = any(
        [
            legacy_sales_focus,
            legacy_value_axes,
            legacy_objection_axes,
            legacy_expected_questions,
        ]
    )

    sales_focus = _normalize_extension_string(
        _pick_policy_value(
            raw_pressure_direction,
            raw_customer_pressure,
            "sales_focus",
            legacy_sales_focus,
        )
    )
    value_axes = _normalize_extension_string_list(
        _pick_policy_value(
            raw_pressure_direction,
            raw_customer_pressure,
            "value_axes",
            legacy_value_axes,
        )
    )
    objection_axes = _normalize_extension_string_list(
        _pick_policy_value(
            raw_pressure_direction,
            raw_customer_pressure,
            "objection_axes",
            legacy_objection_axes,
        )
    )
    expected_questions = _normalize_extension_string_list(
        _pick_policy_value(
            raw_follow_up_behavior,
            raw_customer_pressure,
            "expected_customer_questions",
            legacy_expected_questions,
        )
    )

    has_pressure_context = any(
        [sales_focus, value_axes, objection_axes, expected_questions]
    )

    normalized_direction: dict[str, Any] = {
        "sales_focus": sales_focus,
        "value_axes": value_axes,
        "objection_axes": objection_axes,
    }
    for key, value in raw_pressure_direction.items():
        if key in _CUSTOMER_PRESSURE_DIRECTION_KEYS:
            continue
        normalized_direction[key] = value

    normalized_follow_up_behavior: dict[str, Any] = {
        "question_strategy": _normalize_question_strategy(
            _pick_policy_value(
                raw_follow_up_behavior,
                raw_customer_pressure,
                "question_strategy",
                "single_issue" if has_pressure_context else "",
            ),
            default="single_issue" if has_pressure_context else "",
        ),
        "revisit_on_evasion": _to_bool(
            _pick_policy_value(
                raw_follow_up_behavior,
                raw_customer_pressure,
                "revisit_on_evasion",
                has_pressure_context,
            ),
            has_pressure_context,
        ),
        "require_evidence": _to_bool(
            _pick_policy_value(
                raw_follow_up_behavior,
                raw_customer_pressure,
                "require_evidence",
                has_pressure_context,
            ),
            has_pressure_context,
        ),
        "expected_customer_questions": expected_questions,
    }
    for key, value in raw_follow_up_behavior.items():
        if key in _CUSTOMER_PRESSURE_FOLLOW_UP_KEYS:
            continue
        normalized_follow_up_behavior[key] = value

    if explicit_has_pressure:
        source = _CUSTOMER_PRESSURE_SOURCE_EXPLICIT
    elif legacy_has_pressure:
        source = _CUSTOMER_PRESSURE_SOURCE_LEGACY
    else:
        source = _CUSTOMER_PRESSURE_SOURCE_NONE

    normalized_customer_pressure: dict[str, Any] = {
        "source": source,
        "pressure_direction": normalized_direction,
        "follow_up_behavior": normalized_follow_up_behavior,
    }
    for key, value in raw_customer_pressure.items():
        if key in _CUSTOMER_PRESSURE_TOP_LEVEL_KEYS:
            continue
        normalized_customer_pressure[key] = value

    return normalized_customer_pressure


def normalize_persona_policy(
    raw_policy: dict[str, Any] | None,
    *,
    fallback_system_prompt: str | None,
    fallback_kb_ids: list[str] | None,
) -> dict[str, Any]:
    """
    Normalize persona policy and preserve unrelated extension fields.
    """
    policy = _as_dict(raw_policy)

    system_prompt = str(
        policy.get("system_prompt") or fallback_system_prompt or ""
    ).strip()

    knowledge_base_ids = _dedupe_kb_ids(
        policy.get("knowledge_base_ids")
        if "knowledge_base_ids" in policy
        else (fallback_kb_ids or [])
    )

    raw_tool_policy = _as_dict(policy.get("tool_policy"))
    tool_policy: dict[str, Any] = {}
    for key in PERSONA_OWNED_TOOL_POLICY_KEYS:
        if key not in raw_tool_policy:
            continue
        if key in _BOOL_TOOL_POLICY_KEYS:
            tool_policy[key] = _to_bool(raw_tool_policy.get(key), False)
            continue
        if key in _STRING_TOOL_POLICY_KEYS:
            tool_policy[key] = str(raw_tool_policy.get(key) or "").strip().lower()
            continue
        tool_policy[key] = raw_tool_policy.get(key)

    legacy_sales_focus = _normalize_extension_string(policy.get("sales_focus"))
    legacy_value_axes = _normalize_extension_string_list(policy.get("value_axes"))
    legacy_objection_axes = _normalize_extension_string_list(
        policy.get("objection_axes")
    )
    legacy_expected_questions = _normalize_extension_string_list(
        policy.get("expected_customer_questions")
    )

    customer_pressure = _normalize_customer_pressure(
        policy,
        legacy_sales_focus=legacy_sales_focus,
        legacy_value_axes=legacy_value_axes,
        legacy_objection_axes=legacy_objection_axes,
        legacy_expected_questions=legacy_expected_questions,
    )
    pressure_direction = _as_dict(customer_pressure.get("pressure_direction"))
    follow_up_behavior = _as_dict(customer_pressure.get("follow_up_behavior"))

    normalized = {
        "version": PERSONA_POLICY_VERSION,
        "system_prompt": system_prompt,
        "knowledge_base_ids": knowledge_base_ids,
        "tool_policy": tool_policy,
        "sales_focus": _normalize_extension_string(
            pressure_direction.get("sales_focus")
        ),
        "value_axes": _normalize_extension_string_list(
            pressure_direction.get("value_axes")
        ),
        "objection_axes": _normalize_extension_string_list(
            pressure_direction.get("objection_axes")
        ),
        "expected_customer_questions": _normalize_extension_string_list(
            follow_up_behavior.get("expected_customer_questions")
        ),
        "customer_pressure": customer_pressure,
    }

    # Keep non-core extension keys for forward compatibility.
    reserved_keys = {
        *normalized.keys(),
        *_PERSONA_STRING_EXTENSION_KEYS,
        *_PERSONA_LIST_EXTENSION_KEYS,
    }
    for key, value in policy.items():
        if key in reserved_keys:
            continue
        normalized[key] = value

    return normalized


def resolve_persona_policy(persona: Any | None) -> dict[str, Any]:
    if persona is None:
        return normalize_persona_policy(
            {},
            fallback_system_prompt="",
            fallback_kb_ids=[],
        )

    return normalize_persona_policy(
        _as_dict(getattr(persona, "persona_policy", {})),
        fallback_system_prompt=str(getattr(persona, "system_prompt", "") or ""),
        fallback_kb_ids=(
            getattr(persona, "knowledge_base_ids", [])
            if isinstance(getattr(persona, "knowledge_base_ids", []), list)
            else []
        ),
    )


def sync_legacy_persona_fields(persona: Any, persona_policy: dict[str, Any]) -> None:
    """Backfill legacy fields for old handlers and compatibility views."""
    if persona is None:
        return
    persona.system_prompt = str(persona_policy.get("system_prompt", "") or "").strip()
    persona.knowledge_base_ids = _dedupe_kb_ids(
        persona_policy.get("knowledge_base_ids")
    )
