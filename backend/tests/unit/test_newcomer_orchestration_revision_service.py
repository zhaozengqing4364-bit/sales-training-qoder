from __future__ import annotations

import uuid

import pytest

from common.db.models import User
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.graph import PathIssue
from sales_trainer.orchestration.repository import EnrollmentRepository
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService
from sales_trainer.services.operation_log_service import OperationLogService


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
        revision_id=str(first_draft.revision_id),
        actor=actor,
        reason="恢复版本一",
        expected_revision_id=str(second_draft.revision_id),
    )
    active = await service.active_revision()

    assert active is not None
    assert active.revision_id == second_draft.revision_id
    assert restored.status == "working"
    assert restored.payload_json["title"] == "版本一"


@pytest.mark.asyncio
async def test_should_reject_stale_expected_revision_when_restoring(test_db):
    actor = await _admin(test_db)
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )
    source = await service.save_draft(
        payload=_payload("历史版本"), actor=actor, reason="历史版本"
    )
    current = await service.publish(actor=actor, reason="发布历史版本")

    with pytest.raises(NewcomerOrchestrationError) as error:
        await service.restore_as_draft(
            revision_id=str(source.revision_id),
            actor=actor,
            reason="陈旧页面恢复",
            expected_revision_id="stale-revision",
        )

    assert error.value.code == "[NEWCOMER_PATH_REVISION_CONFLICT]"
    assert (await service.active_revision()).revision_id == current.revision.revision_id


@pytest.mark.asyncio
async def test_should_validate_candidate_without_creating_a_revision(test_db):
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )

    result = await service.validate_candidate(_payload("仅检查，不保存"))

    assert result.can_publish is True
    assert await service.working_revision() is None
    assert await service.active_revision() is None


@pytest.mark.asyncio
async def test_should_reject_stale_expected_revision_when_saving(test_db):
    actor = await _admin(test_db)
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )
    first = await service.save_draft(
        payload=_payload("版本一"), actor=actor, reason="版本一"
    )

    with pytest.raises(NewcomerOrchestrationError) as error:
        await service.save_draft(
            payload=_payload("陈旧编辑"),
            actor=actor,
            reason="陈旧编辑",
            expected_revision_id="stale-revision",
        )

    assert error.value.code == "[NEWCOMER_PATH_REVISION_CONFLICT]"
    assert (await service.working_revision()).revision_id == first.revision_id


@pytest.mark.asyncio
async def test_should_publish_candidate_atomically_after_validation(test_db):
    actor = await _admin(test_db)
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )
    initial = await service.save_draft(
        payload=_payload("待替换草稿"), actor=actor, reason="初始草稿"
    )

    result = await service.publish_candidate(
        payload=_payload("直接发布候选"),
        expected_revision_id=str(initial.revision_id),
        actor=actor,
        reason="确认发布候选",
    )

    assert result.revision.status == "published"
    assert result.revision.payload_json["title"] == "直接发布候选"
    assert await service.working_revision() is None
    assert (await service.active_revision()).revision_id == result.revision.revision_id


@pytest.mark.asyncio
async def test_should_sync_all_active_enrollments_when_new_path_is_published(test_db):
    actor = await _admin(test_db)
    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"sync-learner-{uuid.uuid4().hex[:8]}",
        name="同步学员",
        email=f"sync-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
    )
    test_db.add(learner)
    await test_db.flush()
    service = TrainingPathRevisionService(
        test_db, resource_validator=_ResourceValidator()
    )
    first = await service.save_draft(
        payload=_payload("版本一"), actor=actor, reason="版本一"
    )
    await service.publish(actor=actor, reason="发布版本一")
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(learner.user_id),
        path_id="default",
        path_revision_id=str(first.revision_id),
    )
    second = await service.save_draft(
        payload=_payload("版本二"), actor=actor, reason="版本二"
    )

    result = await service.publish(actor=actor, reason="同步全员")
    await test_db.refresh(enrollment)

    assert enrollment.path_revision_id == result.revision.revision_id
    assert enrollment.path_revision_id == second.revision_id
    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="newcomer_training_path",
        target_id=str(result.revision.revision_id),
    )
    publish_log = next(
        log for log in logs if log.action == "newcomer_path.published"
    )
    assert publish_log.metadata_json["rollout_scope"] == "all_active_learners"
    assert publish_log.metadata_json["synced_enrollment_count"] == 1
