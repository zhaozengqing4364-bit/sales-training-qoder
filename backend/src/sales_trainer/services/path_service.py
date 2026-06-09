from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import SalesTrainerPathConfig
from sales_trainer.services.path_config_models import path_config
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
        if active_projection is not None:
            return await self._list_revision_paths_for_user(user_id, active_projection)

        units = await self._load_published_path_units()
        if not units:
            return []
        quiz_progress = await load_latest_quiz_progress(self._db, user_id)
        audio_progress = await load_latest_audio_progress(self._db, user_id)

        grouped: dict[str, list[PathBuildItem]] = defaultdict(list)
        for unit in units:
            unit_path_config = path_config(unit.config or {})
            if unit_path_config and unit_path_config.enabled:
                grouped[unit_path_config.path_key].append((unit, unit_path_config))

        paths: list[dict[str, Any]] = []
        for path_key, items in grouped.items():
            ordered_items = _ordered_items(items)
            first_config = ordered_items[0][1]
            paths.append(
                build_path_payload(
                    path_key=path_key,
                    title=first_config.path_title or "销售训练闯关",
                    goal_title=first_config.goal_title,
                    ordered_items=ordered_items,
                    quiz_progress=quiz_progress,
                    audio_progress=audio_progress,
                )
            )
        return sorted(paths, key=lambda item: str(item["path_key"]))

    async def _list_revision_paths_for_user(
        self,
        user_id: str,
        active_projection: PathProjection,
    ) -> list[dict[str, Any]]:
        if not active_projection.items:
            return []
        quiz_progress = await load_latest_quiz_progress(self._db, user_id)
        audio_progress = await load_latest_audio_progress(self._db, user_id)
        ordered_items = _ordered_projection_items(active_projection)
        first_config = ordered_items[0][1]
        return [
            build_path_payload(
                path_key=active_projection.path_key,
                path_revision_id=active_projection.revision_id,
                path_revision_no=active_projection.revision_no,
                title=first_config.path_title or "新人训练路径",
                goal_title=first_config.goal_title,
                ordered_items=ordered_items,
                quiz_progress=quiz_progress,
                audio_progress=audio_progress,
            )
        ]

    async def _load_published_path_units(self) -> list[SalesTrainerUnit]:
        result = await self._db.execute(
            select(SalesTrainerUnit)
            .where(SalesTrainerUnit.status == "published")
            .order_by(SalesTrainerUnit.updated_at.desc())
        )
        return [
            unit
            for unit in result.scalars().all()
            if (path_config(unit.config or {}) or SalesTrainerPathConfig()).enabled
        ]


def _ordered_items(items: list[PathBuildItem]) -> list[PathBuildItem]:
    return sorted(
        items,
        key=lambda item: (
            item[1].order_index,
            str(item[0].updated_at),
            str(item[0].unit_id),
        ),
    )


def _ordered_projection_items(
    active_projection: PathProjection,
) -> list[PathBuildItem]:
    return sorted(
        [
            (item.unit, item.path_config)
            for item in active_projection.items
        ],
        key=lambda item: (
            item[1].order_index,
            str(item[0].updated_at),
            str(item[0].unit_id),
        ),
    )
