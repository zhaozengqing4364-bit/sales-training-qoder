from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import SalesTrainerPathConfig

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


@dataclass(frozen=True)
class UnitProgress:
    status: str
    passed: bool | None
    score: float | None
    max_score: float | None
    submitted_at: Any
    result_id: str | None
    target_path: str | None
    improvements: tuple[str, ...] = ()


class SalesTrainerPathService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_paths_for_user(self, user_id: str) -> list[dict[str, Any]]:
        units = await self._load_published_path_units()
        if not units:
            return []
        quiz_progress = await self._load_latest_quiz_progress(user_id)
        audio_progress = await self._load_latest_audio_progress(user_id)

        grouped: dict[str, list[tuple[SalesTrainerUnit, SalesTrainerPathConfig]]] = (
            defaultdict(list)
        )
        for unit in units:
            path_config = _path_config(unit.config or {})
            if path_config and path_config.enabled:
                grouped[path_config.path_key].append((unit, path_config))

        paths: list[dict[str, Any]] = []
        for path_key, items in grouped.items():
            ordered_items = sorted(
                items,
                key=lambda item: (
                    item[1].order_index,
                    str(item[0].updated_at),
                    str(item[0].unit_id),
                ),
            )
            levels = [
                self._serialize_level(
                    unit,
                    path_config,
                    quiz_progress=quiz_progress,
                    audio_progress=audio_progress,
                )
                for unit, path_config in ordered_items
            ]
            completed_unit_ids = {
                level["unit_id"] for level in levels if level["status"] == "completed"
            }
            for level in levels:
                missing = [
                    unit_id
                    for unit_id in level["unlock_after_unit_ids"]
                    if unit_id not in completed_unit_ids
                ]
                if missing:
                    level["locked"] = True
                    level["lock_reason"] = _guidance_text(level, "locked")
                    level["status"] = "locked"
                level.pop("unlock_after_unit_ids", None)

            available = [
                level
                for level in levels
                if not level["locked"] and level["status"] != "completed"
            ]
            current_level_id = available[0]["unit_id"] if available else None
            completed_levels = sum(1 for level in levels if level["status"] == "completed")
            first_config = ordered_items[0][1]
            paths.append(
                {
                    "path_key": path_key,
                    "title": first_config.path_title or "销售训练闯关",
                    "goal_title": first_config.goal_title,
                    "total_levels": len(levels),
                    "completed_levels": completed_levels,
                    "current_level_id": current_level_id,
                    "next_level_id": current_level_id,
                    "goal_context": _build_goal_context(
                        goal_title=first_config.goal_title,
                        levels=levels,
                    ),
                    "levels": [_public_level(level) for level in levels],
                }
            )
        return sorted(paths, key=lambda item: str(item["path_key"]))

    async def _load_published_path_units(self) -> list[SalesTrainerUnit]:
        result = await self._db.execute(
            select(SalesTrainerUnit)
            .where(SalesTrainerUnit.status == "published")
            .order_by(SalesTrainerUnit.updated_at.desc())
        )
        return [
            unit
            for unit in result.scalars().all()
            if (_path_config(unit.config or {}) or SalesTrainerPathConfig()).enabled
        ]

    async def _load_latest_quiz_progress(
        self, user_id: str
    ) -> dict[str, UnitProgress]:
        result = await self._db.execute(
            select(SalesTrainerQuizAttempt)
            .where(SalesTrainerQuizAttempt.user_id == user_id)
            .order_by(SalesTrainerQuizAttempt.submitted_at.desc())
        )
        progress: dict[str, UnitProgress] = {}
        for attempt in result.scalars().all():
            unit_id = str(attempt.unit_id)
            if unit_id in progress:
                continue
            progress[unit_id] = UnitProgress(
                status=str(attempt.status),
                passed=attempt.passed,
                score=_decimal_to_float(attempt.total_score),
                max_score=_decimal_to_float(attempt.max_score),
                submitted_at=attempt.submitted_at,
                result_id=str(attempt.attempt_id),
                target_path=f"/sales-trainer/quiz/result/{attempt.attempt_id}",
            )
        return progress

    async def _load_latest_audio_progress(
        self, user_id: str
    ) -> dict[str, UnitProgress]:
        result = await self._db.execute(
            select(SalesTrainerAudioSubmission, SalesTrainerAudioScoreResult)
            .outerjoin(
                SalesTrainerAudioScoreResult,
                SalesTrainerAudioSubmission.submission_id
                == SalesTrainerAudioScoreResult.submission_id,
            )
            .where(SalesTrainerAudioSubmission.user_id == user_id)
            .order_by(
                SalesTrainerAudioSubmission.created_at.desc(),
                SalesTrainerAudioScoreResult.created_at.desc(),
            )
        )
        progress: dict[str, UnitProgress] = {}
        for submission, score in result.all():
            unit_id = str(submission.unit_id or "")
            if not unit_id or unit_id in progress:
                continue
            progress[unit_id] = UnitProgress(
                status=str(submission.status),
                passed=score.passed if score is not None else None,
                score=_decimal_to_float(score.total_score) if score is not None else None,
                max_score=None,
                submitted_at=submission.created_at,
                result_id=str(submission.submission_id),
                target_path=f"/sales-trainer/audio/result/{submission.submission_id}",
                improvements=_string_tuple(score.improvements if score is not None else []),
            )
        return progress

    def _serialize_level(
        self,
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
        completed = _is_completed(progress, path_config.completion_rule)
        status = "completed" if completed else "in_progress" if progress else "available"
        return {
            "unit_id": unit_id,
            "name": unit.name,
            "description": unit.description,
            "unit_type": unit.unit_type,
            "order_index": path_config.order_index,
            "level_title": path_config.level_title or unit.name,
            "level_description": path_config.level_description or unit.description,
            "locked": False,
            "lock_reason": None,
            "status": status,
            "completion_rule": path_config.completion_rule,
            "primary_action_label": path_config.primary_action_label
            or ("开始做题" if unit.unit_type == "quiz" else "上传录音"),
            "retry_action_label": path_config.retry_action_label or "重练本关",
            "review_action_label": path_config.review_action_label or "查看结果",
            "target_path": _unit_target_path(unit),
            "latest_result": _progress_payload(progress),
            "unlock_after_unit_ids": path_config.unlock_after_unit_ids,
            "guidance_templates": {
                **DEFAULT_GUIDANCE_TEMPLATES,
                **path_config.guidance_templates,
            },
        }


def _path_config(config: dict[str, Any]) -> SalesTrainerPathConfig | None:
    raw_path = config.get("path")
    if not isinstance(raw_path, dict):
        return None
    return SalesTrainerPathConfig.model_validate(raw_path)


def _public_level(level: dict[str, Any]) -> dict[str, Any]:
    payload = dict(level)
    payload.pop("guidance_templates", None)
    return payload


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
        return progress.status == "scored"
    return progress.passed is True


def _unit_target_path(unit: SalesTrainerUnit) -> str:
    if unit.unit_type == "quiz":
        return f"/sales-trainer/quiz/{unit.unit_id}"
    return f"/sales-trainer/audio/{unit.unit_id}"


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


def _build_goal_context(
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
        return {
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "issue_type": "locked",
            "issue_text": level.get("lock_reason") or _guidance_text(level, "locked"),
            "evidence_id": None,
            "score": None,
            "max_score": None,
        }
    result = level["latest_result"]
    if result is None:
        return {
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "issue_type": "not_started",
            "issue_text": _guidance_text(level, "not_started"),
            "evidence_id": None,
            "score": None,
            "max_score": None,
        }
    if result["passed"] is False:
        return {
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "issue_type": "not_passed",
            "issue_text": _guidance_text(level, "not_passed"),
            "evidence_id": result["result_id"],
            "score": result["score"],
            "max_score": result["max_score"],
        }
    if level["completion_rule"] in {"passed", "scored"} and result["status"] != "scored":
        return {
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "issue_type": "not_scored",
            "issue_text": _guidance_text(level, "not_scored"),
            "evidence_id": result["result_id"],
            "score": result["score"],
            "max_score": result["max_score"],
        }
    improvements = result.get("improvements") or []
    if level["unit_type"] == "audio_scoring" and improvements and level["status"] != "completed":
        return {
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "issue_type": "audio_improvement",
            "issue_text": _guidance_text(
                level,
                "audio_improvement",
                improvement=str(improvements[0]),
            ),
            "evidence_id": result["result_id"],
            "score": result["score"],
            "max_score": result["max_score"],
        }
    return None


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
        level = actionable[0]
        weak_point = next(
            (
                item
                for item in weak_points
                if item["unit_id"] == level["unit_id"]
            ),
            None,
        )
        if level["latest_result"]:
            return {
                "title": _guidance_text(
                    level,
                    "retry_level_title",
                    level_title=level["level_title"],
                ),
                "reason": weak_point["issue_text"]
                if weak_point
                else _guidance_text(level, "retry_level_reason"),
                "action_label": level["retry_action_label"],
                "target_path": level["target_path"],
                "unit_id": level["unit_id"],
                "level_title": level["level_title"],
                "recommendation_kind": "retry_level",
            }
        return {
            "title": _guidance_text(
                level,
                "start_level_title",
                level_title=level["level_title"],
            ),
            "reason": weak_point["issue_text"]
            if weak_point
            else _guidance_text(level, "start_level_reason"),
            "action_label": level["primary_action_label"],
            "target_path": level["target_path"],
            "unit_id": level["unit_id"],
            "level_title": level["level_title"],
            "recommendation_kind": "start_level",
        }
    completed = [level for level in levels if level["latest_result"]]
    if completed:
        level = completed[-1]
        result_path = level["latest_result"]["target_path"]
        if result_path:
            return {
                "title": _guidance_text(level, "path_completed_title"),
                "reason": _guidance_text(level, "path_completed_reason"),
                "action_label": level["review_action_label"],
                "target_path": result_path,
                "unit_id": level["unit_id"],
                "level_title": level["level_title"],
                "recommendation_kind": "path_completed",
            }
    return None


def _string_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(item) for item in values if str(item).strip())


def _guidance_text(level: dict[str, Any], key: str, **variables: str) -> str:
    templates = level.get("guidance_templates")
    if not isinstance(templates, dict):
        templates = DEFAULT_GUIDANCE_TEMPLATES
    template = str(templates.get(key) or DEFAULT_GUIDANCE_TEMPLATES[key])
    try:
        return template.format(**variables)
    except (KeyError, ValueError):
        return DEFAULT_GUIDANCE_TEMPLATES[key].format(**variables)


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
