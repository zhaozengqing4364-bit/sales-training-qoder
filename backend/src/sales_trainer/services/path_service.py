from __future__ import annotations

from importlib import import_module
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.services.path_config_service import (
    PathProjection,
    SalesTrainerPathConfigService,
)
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
            )
        ]

    async def _apply_journey_visibility(
        self,
        payload: dict[str, Any],
        *,
        learner: User,
    ) -> dict[str, Any]:
        journey_service_module = import_module(
            "sales_trainer.services.training_journey_service"
        )
        training_journey_service = journey_service_module.TrainingJourneyService
        journey = await training_journey_service(self._db).get_learner_journey(
            str(learner.user_id),
            viewer=learner,
        )
        modules_by_unit_id: dict[str, dict[str, Any]] = {}
        for module in journey.get("modules") or []:
            if not isinstance(module, dict):
                continue
            for target_unit_id in module.get("target_unit_ids") or []:
                modules_by_unit_id[str(target_unit_id)] = module
            target_unit_id = module.get("target_unit_id")
            if target_unit_id:
                modules_by_unit_id[str(target_unit_id)] = module
        for level in payload.get("levels") or []:
            if not isinstance(level, dict):
                continue
            module = modules_by_unit_id.get(str(level.get("unit_id") or ""))
            if not module:
                continue
            level["learner_level_required"] = list(
                module.get("learner_level_required") or []
            )
            if module.get("locked"):
                level["locked"] = True
                level["lock_reason"] = module.get("block_reason") or level.get(
                    "lock_reason"
                )
                level["status"] = "locked"
        available = [
            level
            for level in payload.get("levels") or []
            if isinstance(level, dict)
            and not level.get("locked")
            and level.get("status") != "completed"
        ]
        current_level_id = available[0]["unit_id"] if available else None
        payload["current_level_id"] = current_level_id
        payload["next_level_id"] = current_level_id
        return payload


def _ordered_projection_items(
    active_projection: PathProjection,
) -> list[PathBuildItem]:
    return sorted(
        [
            (item.unit, item.path_config)
            for item in active_projection.items
        ],
        key=lambda item: item[1].order_index,
    )
