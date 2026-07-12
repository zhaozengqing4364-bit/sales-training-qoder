"""Archive impact for LearningContent referenced by orchestration revisions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.revision_service import (
    PATH_LOGICAL_ID,
    PATH_RESOURCE_TYPE,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)


@dataclass(frozen=True, slots=True)
class LearningContentActivityBinding:
    source: str
    revision_id: str
    revision_no: int
    phase_id: str
    module_id: str
    activity_id: str
    activity_title: str


@dataclass(frozen=True, slots=True)
class LearningContentBindingImpact:
    learning_content_id: str
    active_bindings: tuple[LearningContentActivityBinding, ...]
    working_bindings: tuple[LearningContentActivityBinding, ...]
    can_archive: bool
    archive_block_reason: str | None


class LearningContentBindingImpactServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LearningContentBindingImpactService:
    def __init__(self, db: AsyncSession) -> None:
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def get_impact(self, learning_content_id: str) -> LearningContentBindingImpact:
        active = await self._revisions.active_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )
        working = await self._revisions.latest_working_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )
        active_bindings = _bindings(active, learning_content_id, "active_revision")
        working_bindings = _bindings(working, learning_content_id, "working_revision")
        can_archive = not active_bindings and not working_bindings
        return LearningContentBindingImpact(
            learning_content_id=learning_content_id,
            active_bindings=active_bindings,
            working_bindings=working_bindings,
            can_archive=can_archive,
            archive_block_reason=None
            if can_archive
            else "该学习内容仍被训练活动引用，请先在当前路径编辑器中替换绑定并发布。",
        )


def _bindings(
    revision: SalesTrainerAssetRevision | None,
    learning_content_id: str,
    source: str,
) -> tuple[LearningContentActivityBinding, ...]:
    if revision is None:
        return ()
    try:
        payload = TrainingPathPayload.model_validate(revision.payload_json)
    except Exception as exc:
        raise LearningContentBindingImpactServiceError(
            "[NEWCOMER_PATH_CONFIG_INVALID]", "新人训练路径配置非法，无法计算内容影响。", 500
        ) from exc
    return tuple(
        LearningContentActivityBinding(
            source=source,
            revision_id=str(revision.revision_id),
            revision_no=int(revision.revision_no),
            phase_id=phase.phase_id,
            module_id=module.module_id,
            activity_id=activity.activity_id,
            activity_title=activity.title,
        )
        for phase in payload.phases
        for module in phase.modules
        for activity in module.activities
        if activity.type == "lesson"
        and activity.config.learning_content_id == learning_content_id
    )


__all__ = [
    "LearningContentActivityBinding",
    "LearningContentBindingImpact",
    "LearningContentBindingImpactService",
    "LearningContentBindingImpactServiceError",
]
