from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import LearningContent
from curriculum_practice.schemas import LearningContentRevisionState
from curriculum_practice.services.learning_content_revision_payloads import (
    LEARNING_CONTENT_RESOURCE_TYPE,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    SalesTrainerAssetRevisionService,
)


async def learning_content_revision_state(
    db: AsyncSession,
    content: LearningContent,
) -> LearningContentRevisionState:
    revisions = SalesTrainerAssetRevisionService(db)
    logical_id = str(content.learning_content_id)
    active = await revisions.active_revision(
        resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
        logical_id=logical_id,
    )
    working = await revisions.latest_working_revision(
        resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
        logical_id=logical_id,
    )
    has_working = working is not None
    status = str(content.status)
    if status == "archived":
        edit_target = "archived_locked"
        publish_label = "已归档"
        save_copy = "已归档学习内容不可编辑。"
    elif status == "published":
        edit_target = "working_revision"
        publish_label = "发布修订" if has_working else "当前无待发布修订"
        save_copy = "已保存为待发布修订，发布修订后才会影响学员端。"
    else:
        edit_target = "draft_record"
        publish_label = "发布"
        save_copy = "已保存草稿。"

    return LearningContentRevisionState(
        active_revision_id=str(active.revision_id) if active is not None else None,
        active_revision_no=active.revision_no if active is not None else None,
        working_revision_id=str(working.revision_id) if working is not None else None,
        working_revision_no=working.revision_no if working is not None else None,
        has_unpublished_revision=has_working,
        edit_target=edit_target,
        publish_label=publish_label,
        save_result_copy=save_copy,
    )
