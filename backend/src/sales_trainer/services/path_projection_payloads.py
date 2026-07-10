from __future__ import annotations

from typing import Any, TypeAlias, cast

from pydantic import ValidationError

from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import AiCoachConfig, SalesTrainerPathConfig
from sales_trainer.services.learner_public_projection import (
    strip_learner_internal_fields,
)
from sales_trainer.services.path_guidance import (
    DEFAULT_GUIDANCE_TEMPLATES,
    build_goal_context,
)
from sales_trainer.services.path_progress_service import UnitProgress

PathBuildItem: TypeAlias = tuple[SalesTrainerUnit, SalesTrainerPathConfig]


def build_path_payload(
    *,
    path_key: str,
    title: str,
    goal_title: str | None,
    path_revision_id: str | None = None,
    path_revision_no: int | None = None,
    ordered_items: list[PathBuildItem],
    quiz_progress: dict[str, UnitProgress],
    audio_progress: dict[str, UnitProgress],
) -> dict[str, Any]:
    levels = [
        _serialize_level(
            unit,
            path_config,
            quiz_progress=quiz_progress,
            audio_progress=audio_progress,
        )
        for unit, path_config in ordered_items
    ]

    available = [
        level
        for level in levels
        if not level["locked"] and level["status"] != "completed"
    ]
    current_level_id = available[0]["unit_id"] if available else None
    completed_levels = sum(1 for level in levels if level["status"] == "completed")
    return {
        "path_key": path_key,
        "path_revision_id": path_revision_id,
        "path_revision_no": path_revision_no,
        "title": title,
        "goal_title": goal_title,
        "total_levels": len(levels),
        "completed_levels": completed_levels,
        "current_level_id": current_level_id,
        "next_level_id": current_level_id,
        "goal_context": build_goal_context(
            goal_title=goal_title,
            levels=levels,
        ),
        "levels": [_public_level(level) for level in levels],
    }


def _serialize_level(
    unit: SalesTrainerUnit,
    path_config: SalesTrainerPathConfig,
    *,
    quiz_progress: dict[str, UnitProgress],
    audio_progress: dict[str, UnitProgress],
) -> dict[str, Any]:
    unit_id = str(unit.unit_id)
    progress = (
        quiz_progress.get(unit_id)
        if unit.unit_type == "quiz"
        else audio_progress.get(unit_id)
    )
    disabled = path_config.enabled is False
    completed = _is_completed(progress, path_config.completion_rule)
    status = (
        "locked"
        if disabled
        else "completed"
        if completed
        else "in_progress"
        if progress
        else "available"
    )
    return {
        "unit_id": unit_id,
        "name": unit.name,
        "description": unit.description,
        "unit_type": unit.unit_type,
        "module_key": path_config.module_key,
        "module_type": path_config.module_type,
        "learning_content_id": path_config.learning_content_id,
        "exam_paper_id": path_config.exam_paper_id,
        "order_index": path_config.order_index,
        "level_title": path_config.level_title or unit.name,
        "level_description": path_config.level_description or unit.description,
        "locked": disabled,
        "lock_reason": path_config.disabled_reason if disabled else None,
        "status": status,
        "learner_level_required": path_config.learner_level_required,
        "completion_rule": path_config.completion_rule,
        "primary_action_label": path_config.primary_action_label
        or ("开始做题" if unit.unit_type == "quiz" else "上传录音"),
        "retry_action_label": path_config.retry_action_label or "重练本关",
        "review_action_label": path_config.review_action_label or "查看结果",
        "target_path": _unit_target_path(unit, path_config),
        "ai_coach_availability": _ai_coach_availability(path_config),
        "latest_result": _progress_payload(progress),
        "guidance_templates": {
            **DEFAULT_GUIDANCE_TEMPLATES,
            **path_config.guidance_templates,
        },
    }


def _public_level(level: dict[str, Any]) -> dict[str, Any]:
    payload = dict(level)
    payload.pop("guidance_templates", None)
    return cast(dict[str, Any], strip_learner_internal_fields(payload))


def _is_completed(progress: UnitProgress | None, rule: str) -> bool:
    if progress is None:
        return False
    if rule == "submitted":
        return progress.status in {
            "submitted",
            "scored",
            "uploaded",
            "transcribing",
            "transcribed",
            "scoring",
            "scoring_failed",
            "scored",
        }
    if rule == "scored":
        return bool(progress.status == "scored")
    return progress.passed is True


def _unit_target_path(
    unit: SalesTrainerUnit,
    path_config: SalesTrainerPathConfig,
) -> str:
    if path_config.module_type == "article_exam":
        return "/sales-trainer/business-skills"
    if unit.unit_type == "quiz":
        return f"/sales-trainer/quiz/{unit.unit_id}"
    return f"/sales-trainer/audio/{unit.unit_id}"


def _ai_coach_availability(
    path_config: SalesTrainerPathConfig,
) -> dict[str, Any] | None:
    if path_config.module_key != "business_skills":
        return None
    raw_config = path_config.ai_coach
    if not isinstance(raw_config, dict):
        return {
            "enabled": False,
            "configured": False,
            "available": False,
            "coach_path": None,
            "disabled_reason": "AI 教练未启用。",
            "allowed_interaction_types": [],
        }
    try:
        ai_coach = AiCoachConfig.model_validate(raw_config)
    except ValidationError:
        return {
            "enabled": False,
            "configured": False,
            "available": False,
            "coach_path": None,
            "disabled_reason": "AI 教练配置非法，请联系管理员处理。",
            "allowed_interaction_types": [],
        }

    configured = bool(ai_coach.prompt_template_id)
    available = ai_coach.enabled and configured
    disabled_reason = None
    if not ai_coach.enabled:
        disabled_reason = "AI 教练未启用。"
    elif not configured:
        disabled_reason = "AI 教练未绑定生成 Prompt。"
    return {
        "enabled": ai_coach.enabled,
        "configured": configured,
        "available": available,
        "coach_path": "/sales-trainer/business-skills/coach" if available else None,
        "disabled_reason": disabled_reason,
        "allowed_interaction_types": list(ai_coach.allowed_interaction_types),
    }


def _progress_payload(progress: UnitProgress | None) -> dict[str, Any] | None:
    if progress is None:
        return None
    return {
        "status": progress.status,
        "passed": progress.passed,
        "score": progress.score,
        "max_score": progress.max_score,
        "submitted_at": progress.submitted_at,
        "result_id": progress.result_id,
        "target_path": progress.target_path,
        "improvements": list(progress.improvements),
    }
