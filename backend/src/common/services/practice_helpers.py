"""Shared practice-route/service helper utilities."""

from __future__ import annotations

from typing import Any


class PracticeRetryEntryAssembler:
    """Shape retry-focus intent and retry-entry projections consistently."""

    @staticmethod
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

    @classmethod
    def _sanitize_text(cls, value: Any, *, max_length: int) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized[:max_length]

    @classmethod
    def _sanitize_text_list(
        cls,
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
            if (sanitized := cls._sanitize_text(item, max_length=max_length))
        ]
        return items or None

    @classmethod
    def _sanitize_presentation_page_focus(cls, value: Any) -> dict[str, Any] | None:
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
        reason = cls._sanitize_text(value.get("reason"), max_length=120)
        summary = cls._sanitize_text(value.get("summary"), max_length=500)
        missing_required_points = cls._sanitize_text_list(
            value.get("missing_required_points")
        )
        if reason is not None:
            sanitized["reason"] = reason
        if summary is not None:
            sanitized["summary"] = summary
        if missing_required_points is not None:
            sanitized["missing_required_points"] = missing_required_points
        return sanitized

    @classmethod
    def sanitize_focus_intent(cls, focus_intent: Any) -> dict[str, Any] | None:
        if focus_intent is None or not isinstance(focus_intent, dict):
            return None

        main_issue = cls._filter_retry_focus_fields(
            focus_intent.get("main_issue"),
            allowed_keys=("issue_type", "issue_text", "recovery_rule"),
        )
        next_goal = cls._filter_retry_focus_fields(
            focus_intent.get("next_goal"),
            allowed_keys=("goal_type", "goal_text", "rule"),
        )
        presentation_page = cls._sanitize_presentation_page_focus(
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
        return sanitized

    @classmethod
    def build_focus_intent(
        cls,
        *,
        session_id: str,
        scenario_type: str,
        main_issue: Any,
        next_goal: Any,
    ) -> dict[str, Any] | None:
        if str(scenario_type or "").lower() != "sales":
            return None

        return cls.sanitize_focus_intent(
            {
                "version": "retry_focus_v1",
                "source_session_id": session_id,
                "main_issue": main_issue,
                "next_goal": next_goal,
            }
        )

    @classmethod
    def build_retry_entry(
        cls,
        *,
        session: Any,
        scenario_type: str,
        main_issue: Any = None,
        next_goal: Any = None,
    ) -> dict[str, Any]:
        retry_entry: dict[str, Any] = {
            "scenario_type": scenario_type,
            "agent_id": str(session.agent_id)
            if getattr(session, "agent_id", None)
            else None,
            "persona_id": str(session.persona_id)
            if getattr(session, "persona_id", None)
            else None,
            "presentation_id": (
                str(session.presentation_id)
                if getattr(session, "presentation_id", None)
                else None
            ),
        }
        focus_intent = cls.build_focus_intent(
            session_id=str(session.session_id),
            scenario_type=scenario_type,
            main_issue=main_issue,
            next_goal=next_goal,
        )
        if focus_intent is not None:
            retry_entry["focus_intent"] = focus_intent
        return retry_entry
