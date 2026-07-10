from __future__ import annotations

from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.services.path_config_service import (
    PathProjection,
    SalesTrainerPathConfigService,
)
from sales_trainer.services.path_guidance import build_goal_context
from sales_trainer.services.path_progress_service import (
    load_latest_audio_progress,
    load_latest_quiz_progress,
)
from sales_trainer.services.path_projection_payloads import (
    PathBuildItem,
    build_path_payload,
)


class SalesTrainerPathService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_paths_for_user(self, user_id: str) -> list[dict[str, Any]]:
        active_projection = await SalesTrainerPathConfigService(
            self._db
        ).active_projection()
        if active_projection is None:
            return []
        return await self._list_revision_paths_for_user(user_id, active_projection)

    async def _list_revision_paths_for_user(
        self,
        user_id: str,
        active_projection: PathProjection,
    ) -> list[dict[str, Any]]:
        if not active_projection.items:
            return []
        learner = await self._db.get(User, user_id)
        if learner is None:
            return []
        quiz_progress = await load_latest_quiz_progress(self._db, user_id)
        audio_progress = await load_latest_audio_progress(self._db, user_id)
        ordered_items = _ordered_projection_items(active_projection)
        guidance_templates_by_unit_id = {
            str(unit.unit_id): dict(path_config.guidance_templates)
            for unit, path_config in ordered_items
        }
        first_config = ordered_items[0][1]
        payload = build_path_payload(
            path_key=active_projection.path_key,
            path_revision_id=active_projection.revision_id,
            path_revision_no=active_projection.revision_no,
            title=first_config.path_title or "新人训练路径",
            goal_title=first_config.goal_title,
            ordered_items=ordered_items,
            quiz_progress=quiz_progress,
            audio_progress=audio_progress,
        )
        return [
            await self._apply_journey_visibility(
                payload,
                learner=learner,
                guidance_templates_by_unit_id=guidance_templates_by_unit_id,
            )
        ]

    async def _apply_journey_visibility(
        self,
        payload: dict[str, Any],
        *,
        learner: User,
        guidance_templates_by_unit_id: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        journey_service_module = import_module(
            "sales_trainer.services.training_journey_service"
        )
        training_journey_service = journey_service_module.TrainingJourneyService
        journey = await training_journey_service(self._db).get_learner_journey(
            str(learner.user_id),
            viewer=learner,
        )
        learning_topic_source_module_keys = {
            str(topic.get("source_module_key") or "")
            for topic in journey.get("learning_topics") or []
            if isinstance(topic, dict) and topic.get("source_module_key")
        }
        modules_by_unit_id: dict[str, dict[str, Any]] = {}
        for module in journey.get("modules") or []:
            if not isinstance(module, dict):
                continue
            for target_unit_id in module.get("target_unit_ids") or []:
                modules_by_unit_id[str(target_unit_id)] = module
            target_unit_id = module.get("target_unit_id")
            if target_unit_id:
                modules_by_unit_id[str(target_unit_id)] = module
        levels = [
            level
            for level in payload.get("levels") or []
            if isinstance(level, dict)
            and str(level.get("module_key") or "")
            not in learning_topic_source_module_keys
        ]
        payload["levels"] = levels
        for level in levels:
            module = modules_by_unit_id.get(str(level.get("unit_id") or ""))
            if not module:
                continue
            level["learner_level_required"] = list(
                module.get("learner_level_required") or []
            )
            locked = bool(module.get("locked"))
            level["locked"] = locked
            level["lock_reason"] = module.get("block_reason") if locked else None
            if locked:
                level["status"] = "locked"
            elif module.get("completion_satisfied"):
                level["status"] = "completed"
            elif module.get("status") == "not_started":
                level["status"] = "available"
            else:
                level["status"] = "in_progress"
            level["latest_result"] = _latest_result_from_journey(module, level)
        available = [
            level
            for level in levels
            if not level.get("locked") and level.get("status") != "completed"
        ]
        current_level_id = available[0]["unit_id"] if available else None
        payload["total_levels"] = len(levels)
        payload["completed_levels"] = sum(
            1 for level in levels if level.get("status") == "completed"
        )
        payload["current_level_id"] = current_level_id
        payload["next_level_id"] = current_level_id
        for level in levels:
            guidance_templates = guidance_templates_by_unit_id.get(
                str(level.get("unit_id") or "")
            )
            if guidance_templates:
                level["guidance_templates"] = guidance_templates
        payload["goal_context"] = build_goal_context(
            goal_title=payload.get("goal_title"),
            levels=levels,
        )
        for level in levels:
            level.pop("guidance_templates", None)
        return payload


def _ordered_projection_items(
    active_projection: PathProjection,
) -> list[PathBuildItem]:
    return sorted(
        [(item.unit, item.path_config) for item in active_projection.items],
        key=lambda item: item[1].order_index,
    )


def _latest_result_from_journey(
    module: dict[str, Any],
    level: dict[str, Any],
) -> dict[str, Any] | None:
    outcome = _latest_outcome_for_level(module, level)
    if outcome is None:
        return None
    result_id = str(outcome.get("source_record_id") or "")
    if not result_id:
        return None
    unit_type = str(level.get("unit_type") or "")
    result_type = "quiz" if unit_type == "quiz" else "audio"
    return {
        "status": _legacy_result_status(outcome.get("status"), result_type),
        "passed": outcome.get("passed"),
        "score": outcome.get("score"),
        "max_score": outcome.get("max_score"),
        "submitted_at": outcome.get("submitted_at"),
        "result_id": result_id,
        "target_path": f"/sales-trainer/{result_type}/result/{result_id}",
        "improvements": [],
    }


def _latest_outcome_for_level(
    module: dict[str, Any],
    level: dict[str, Any],
) -> dict[str, Any] | None:
    unit_id = str(level.get("unit_id") or "")
    history = [
        outcome
        for outcome in module.get("outcome_history") or []
        if isinstance(outcome, dict)
    ]
    for outcome in history:
        if str(outcome.get("target_unit_id") or "") == unit_id:
            return outcome

    target_unit_ids = {
        str(target_unit_id)
        for target_unit_id in module.get("target_unit_ids") or []
        if str(target_unit_id)
    }
    if len(target_unit_ids) > 1:
        return None
    latest = module.get("latest_outcome")
    if not isinstance(latest, dict):
        return None
    latest_target_unit_id = str(latest.get("target_unit_id") or "")
    if latest_target_unit_id and latest_target_unit_id != unit_id:
        return None
    return latest


def _legacy_result_status(status: Any, result_type: str) -> str:
    stage = str(status or "")
    if stage in {"passed", "failed", "scored"}:
        return "scored"
    if stage == "processing":
        return "scoring" if result_type == "audio" else "in_progress"
    if stage == "error_terminal":
        return "scoring_failed" if result_type == "audio" else "failed"
    return stage or "in_progress"
