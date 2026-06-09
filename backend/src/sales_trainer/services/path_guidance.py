from __future__ import annotations

from typing import Any

DEFAULT_GUIDANCE_TEMPLATES = {
    "locked": "完成前置关卡后解锁。",
    "not_started": "本关还没有训练证据。",
    "not_passed": "最近一次训练未达通关线，建议重练本关。",
    "not_scored": "本关已有提交，但还没有形成可用评分。",
    "audio_improvement": "{improvement}",
    "start_level_title": "下一关：{level_title}",
    "retry_level_title": "重练：{level_title}",
    "path_completed_title": "路径已完成",
    "start_level_reason": "继续推进当前训练路径。",
    "retry_level_reason": "最近一次训练还没有通关，建议先重练本关。",
    "path_completed_reason": "当前路径已形成完整训练证据，可以回看最近一次结果。",
}


def build_goal_context(
    *,
    goal_title: str | None,
    levels: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_items = [_evidence_item(level) for level in levels if level["latest_result"]]
    weak_points = [weak_point for level in levels if (weak_point := _weak_point(level))]
    next_recommendation = _next_recommendation(levels, weak_points)
    return {
        "goal_title": goal_title,
        "score_basis": "sales_trainer_path_projection_v1",
        "evidence_items": evidence_items,
        "weak_points": weak_points,
        "next_recommendation": next_recommendation,
    }


def guidance_text(level: dict[str, Any], key: str, **variables: str) -> str:
    templates = level.get("guidance_templates")
    if not isinstance(templates, dict):
        templates = DEFAULT_GUIDANCE_TEMPLATES
    template = str(templates.get(key) or DEFAULT_GUIDANCE_TEMPLATES[key])
    try:
        return template.format(**variables)
    except (KeyError, ValueError):
        return DEFAULT_GUIDANCE_TEMPLATES[key].format(**variables)


def _evidence_item(level: dict[str, Any]) -> dict[str, Any]:
    result = level["latest_result"]
    return {
        "evidence_id": result["result_id"],
        "evidence_type": "quiz_attempt"
        if level["unit_type"] == "quiz"
        else "audio_submission",
        "unit_id": level["unit_id"],
        "unit_type": level["unit_type"],
        "level_title": level["level_title"],
        "status": result["status"],
        "passed": result["passed"],
        "score": result["score"],
        "max_score": result["max_score"],
        "submitted_at": result["submitted_at"],
        "result_path": result["target_path"],
    }


def _weak_point(level: dict[str, Any]) -> dict[str, Any] | None:
    if level["locked"]:
        return _weak_point_payload(level, issue_type="locked")
    result = level["latest_result"]
    if result is None:
        return _weak_point_payload(level, issue_type="not_started")
    if result["passed"] is False:
        return _weak_point_payload(level, issue_type="not_passed", result=result)
    if level["completion_rule"] in {"passed", "scored"} and result["status"] != "scored":
        return _weak_point_payload(level, issue_type="not_scored", result=result)
    improvements = result.get("improvements") or []
    if level["unit_type"] == "audio_scoring" and improvements and level["status"] != "completed":
        return _weak_point_payload(
            level,
            issue_type="audio_improvement",
            result=result,
            improvement=str(improvements[0]),
        )
    return None


def _weak_point_payload(
    level: dict[str, Any],
    *,
    issue_type: str,
    result: dict[str, Any] | None = None,
    improvement: str | None = None,
) -> dict[str, Any]:
    return {
        "unit_id": level["unit_id"],
        "level_title": level["level_title"],
        "issue_type": issue_type,
        "issue_text": guidance_text(
            level,
            issue_type,
            **({"improvement": improvement} if improvement else {}),
        ),
        "evidence_id": result["result_id"] if result else None,
        "score": result["score"] if result else None,
        "max_score": result["max_score"] if result else None,
    }


def _next_recommendation(
    levels: list[dict[str, Any]],
    weak_points: list[dict[str, Any]],
) -> dict[str, Any] | None:
    actionable = [
        level
        for level in levels
        if not level["locked"] and level["status"] != "completed"
    ]
    if actionable:
        return _actionable_recommendation(actionable[0], weak_points)
    completed = [level for level in levels if level["latest_result"]]
    if not completed:
        return None
    level = completed[-1]
    result_path = level["latest_result"]["target_path"]
    if not result_path:
        return None
    return {
        "title": guidance_text(level, "path_completed_title"),
        "reason": guidance_text(level, "path_completed_reason"),
        "action_label": level["review_action_label"],
        "target_path": result_path,
        "unit_id": level["unit_id"],
        "level_title": level["level_title"],
        "recommendation_kind": "path_completed",
    }


def _actionable_recommendation(
    level: dict[str, Any],
    weak_points: list[dict[str, Any]],
) -> dict[str, Any]:
    weak_point = next(
        (item for item in weak_points if item["unit_id"] == level["unit_id"]),
        None,
    )
    if level["latest_result"]:
        return {
            "title": guidance_text(
                level,
                "retry_level_title",
                level_title=level["level_title"],
            ),
            "reason": weak_point["issue_text"]
            if weak_point
            else guidance_text(level, "retry_level_reason"),
            "action_label": level["retry_action_label"],
            "target_path": level["target_path"],
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "recommendation_kind": "retry_level",
        }
    return {
        "title": guidance_text(
            level,
            "start_level_title",
            level_title=level["level_title"],
        ),
        "reason": weak_point["issue_text"]
        if weak_point
        else guidance_text(level, "start_level_reason"),
        "action_label": level["primary_action_label"],
        "target_path": level["target_path"],
        "unit_id": level["unit_id"],
        "level_title": level["level_title"],
        "recommendation_kind": "start_level",
    }
