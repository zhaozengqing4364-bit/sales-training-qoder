"""
Persona policy normalization and legacy compatibility helpers.

Persona policy is the single source of truth for:
- Role core system prompt
- Bound knowledge base ids
- KB/network tool strategy
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


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


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
        policy.get("system_prompt")
        or fallback_system_prompt
        or ""
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

    normalized = {
        "version": PERSONA_POLICY_VERSION,
        "system_prompt": system_prompt,
        "knowledge_base_ids": knowledge_base_ids,
        "tool_policy": tool_policy,
    }

    # Keep non-core extension keys for forward compatibility.
    for key, value in policy.items():
        if key in normalized:
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
    persona.knowledge_base_ids = _dedupe_kb_ids(persona_policy.get("knowledge_base_ids"))
