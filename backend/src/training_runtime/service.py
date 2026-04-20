"""Helpers for constructing unified training runtime descriptors."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from common.db.models import PracticeSession

from .models import TrainingRuntimeDescriptor


def _filter_retry_focus_fields(
    value: Any,
    *,
    allowed_keys: tuple[str, ...],
) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None

    filtered = {
        key: str(value[key]).strip()
        for key in allowed_keys
        if value.get(key) is not None and str(value.get(key)).strip()
    }
    return filtered or None


def _sanitize_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized[:max_length]


def _sanitize_text_list(
    value: Any,
    *,
    max_items: int = 10,
    max_length: int = 120,
) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [
        sanitized
        for item in value[:max_items]
        if (sanitized := _sanitize_text(item, max_length=max_length))
    ]
    return items or None


def _sanitize_presentation_page_focus(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw_page_number = value.get("page_number")
    if isinstance(raw_page_number, bool):
        return None
    try:
        page_number = int(raw_page_number)
    except (TypeError, ValueError):
        return None
    if page_number <= 0:
        return None

    sanitized: dict[str, Any] = {"page_number": page_number}
    reason = _sanitize_text(value.get("reason"), max_length=120)
    summary = _sanitize_text(value.get("summary"), max_length=500)
    missing_required_points = _sanitize_text_list(value.get("missing_required_points"))
    if reason is not None:
        sanitized["reason"] = reason
    if summary is not None:
        sanitized["summary"] = summary
    if missing_required_points is not None:
        sanitized["missing_required_points"] = missing_required_points
    return sanitized


def _extract_runtime_focus_intent(
    session: PracticeSession,
    *,
    scenario_type: str,
) -> dict[str, Any] | None:
    snapshot = getattr(session, "voice_policy_snapshot", None)
    if not isinstance(snapshot, dict):
        return None

    focus_intent = snapshot.get("focus_intent")
    if not isinstance(focus_intent, dict):
        return None

    main_issue = _filter_retry_focus_fields(
        focus_intent.get("main_issue"),
        allowed_keys=("issue_type", "issue_text", "recovery_rule"),
    )
    next_goal = _filter_retry_focus_fields(
        focus_intent.get("next_goal"),
        allowed_keys=("goal_type", "goal_text", "rule"),
    )
    presentation_page = _sanitize_presentation_page_focus(
        focus_intent.get("presentation_page")
    )
    if main_issue is None and next_goal is None and presentation_page is None:
        return None

    sanitized: dict[str, Any] = {
        "version": str(focus_intent.get("version") or "retry_focus_v1"),
    }
    source_session_id = focus_intent.get("source_session_id")
    if source_session_id is not None and str(source_session_id).strip():
        sanitized["source_session_id"] = str(source_session_id)
    if main_issue is not None:
        sanitized["main_issue"] = main_issue
    if next_goal is not None:
        sanitized["next_goal"] = next_goal
    if presentation_page is not None:
        sanitized["presentation_page"] = presentation_page
    return deepcopy(sanitized)


def build_training_runtime_descriptor(
    session: PracticeSession,
    *,
    scenario_type: str | None = None,
) -> TrainingRuntimeDescriptor:
    """Build the canonical runtime descriptor for one persisted session."""

    resolved_scenario_type = str(
        scenario_type
        or getattr(getattr(session, "scenario", None), "scenario_type", None)
        or "sales"
    ).lower()

    return TrainingRuntimeDescriptor(
        session_id=str(session.session_id),
        scenario_type=resolved_scenario_type,
        agent_id=str(session.agent_id) if getattr(session, "agent_id", None) else None,
        persona_id=(
            str(session.persona_id) if getattr(session, "persona_id", None) else None
        ),
        presentation_id=(
            str(session.presentation_id)
            if getattr(session, "presentation_id", None)
            else None
        ),
        voice_mode=str(getattr(session, "voice_mode", "") or "") or None,
        runtime_profile_id=(
            str(session.voice_runtime_profile_id)
            if getattr(session, "voice_runtime_profile_id", None)
            else None
        ),
        focus_intent=_extract_runtime_focus_intent(
            session,
            scenario_type=resolved_scenario_type,
        ),
    )
