from __future__ import annotations

import uuid

import pytest

from common.db.models import User
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.graph import PathIssue
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService


class _ResourceValidator:
    def __init__(self, issues: tuple[PathIssue, ...] = ()) -> None:
        self._issues = issues

    async def validate(self, payload: TrainingPathPayload) -> tuple[PathIssue, ...]:
        return self._issues


def _payload(title: str = "新人训练路径") -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": title,
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "入门",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "产品 A",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "assignment-1",
                                    "type": "assignment",
                                    "title": "总结",
                                    "order_index": 1,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


async def _admin(test_db) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"orchestration-admin-{suffix}",
        name="编排管理员",
        email=f"orchestration-{suffix}@example.com",
        role="admin",
    )
    test_db.add(user)
    await test_db.flush()
    return user


@pytest.mark.asyncio
async def test_should_allow_resource_incomplete_draft_but_block_publish(test_db):
    actor = await _admin(test_db)
    issue = PathIssue(
        code="exam_paper_not_published",
        message="产品 A 小测没有已发布考卷。",
        object_id="quiz-1",
        field_path="phases[0].modules[0].activities[0].config.exam_paper_id",
    )
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator((issue,))
    )

    draft = await service.save_draft(
        payload=_payload(), actor=actor, reason="编辑产品训练"
    )
    preview = await service.validate_draft()

    assert draft.status == "working"
    assert preview.can_publish is False
    assert preview.issues[0].field_path.endswith("config.exam_paper_id")
    with pytest.raises(Exception) as error:
        await service.publish(actor=actor, reason="发布")
    assert getattr(error.value, "code", None) == "[NEWCOMER_PATH_VALIDATION_FAILED]"


@pytest.mark.asyncio
async def test_should_restore_history_as_new_draft_not_move_active_pointer(test_db):
    actor = await _admin(test_db)
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )
    first_draft = await service.save_draft(
        payload=_payload("版本一"), actor=actor, reason="版本一"
    )
    await service.publish(actor=actor, reason="发布版本一")
    second_draft = await service.save_draft(
        payload=_payload("版本二"), actor=actor, reason="版本二"
    )
    await service.publish(actor=actor, reason="发布版本二")

    restored = await service.restore_as_draft(
        revision_id=str(first_draft.revision_id), actor=actor, reason="恢复版本一"
    )
    active = await service.active_revision()

    assert active is not None
    assert active.revision_id == second_draft.revision_id
    assert restored.status == "working"
    assert restored.payload_json["title"] == "版本一"
