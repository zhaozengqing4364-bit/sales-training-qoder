from __future__ import annotations

import uuid

import pytest

from common.db.models import User
from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
    NewcomerReleasePlan,
)
from newcomer_training.ports import (
    PublishedActivityResourcePort,
    PublishedCompetencyMappingPort,
    ReleaseDependency,
    ReleaseDependencyPort,
)
from newcomer_training.release import ReleasePlanService


class ReleaseResources(ReleaseDependencyPort, PublishedActivityResourcePort):
    def __init__(self) -> None:
        self.status = "working"
        self.fail_publish = False

    async def inspect(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> ReleaseDependency:
        del organization_id, activity_type
        return ReleaseDependency(
            resource_type="learning_unit",
            resource_id="unit-1",
            revision_id=revision_id,
            label="产品知识",
            status=self.status,
            content_hash="unit-content-v1",
            publish_required=self.status == "working",
            expected_resource_version=1,
        )

    async def inspect_resource(
        self,
        *,
        organization_id: str,
        resource_type: str,
        revision_id: str,
    ) -> ReleaseDependency:
        del resource_type
        return await self.inspect(
            organization_id=organization_id,
            activity_type="lesson",
            revision_id=revision_id,
        )

    async def publish(
        self,
        *,
        organization_id: str,
        actor_id: str,
        capability_set: frozenset[str],
        dependency: ReleaseDependency,
        idempotency_key: str,
        reason: str,
        trace_id: str | None,
    ) -> ReleaseDependency:
        del organization_id, actor_id, capability_set, idempotency_key, reason, trace_id
        if self.fail_publish:
            raise NewcomerTrainingError(
                "[TEST_DEPENDENCY_FAILED]", "资源发布失败。", 422
            )
        self.status = "published"
        return dependency.model_copy(
            update={"status": "published", "publish_required": False}
        )

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        del organization_id, activity_type, revision_id
        if self.status != "published":
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RESOURCE_UNPUBLISHED]", "资源未发布。", 422
            )


class CompetencyMappings(PublishedCompetencyMappingPort):
    async def require_valid(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
    ) -> None:
        del organization_id, path_revision_id, activity_id, activity_type
        if not competency_keys:
            raise NewcomerTrainingError(
                "[COMPETENCY_MAPPING_REQUIRED]", "缺少能力映射。", 422
            )

    async def record_published(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
        actor_id: str,
    ) -> None:
        del (
            organization_id,
            path_revision_id,
            activity_id,
            activity_type,
            competency_keys,
            actor_id,
        )


def _actor(*, organization_id: str = "org-1") -> CommandActor:
    return CommandActor(
        organization_id=organization_id,
        actor_id="release-admin",
        capabilities=frozenset(
            {
                "newcomer.path.manage",
                "newcomer.path.publish",
                "newcomer.cohort.manage",
                "newcomer.enrollment.manage",
            }
        ),
    )


def _draft(label: str) -> PathRevisionDraft:
    return PathRevisionDraft.model_validate(
        {
            "title": "新人销售基础训练",
            "revision_label": label,
            "stages": [
                {
                    "stage_id": "product",
                    "sequence": 1,
                    "title": "产品基础",
                    "objective": "掌握产品价值",
                    "entry_conditions": [],
                    "completion_rule": "all_required",
                    "visibility": "learner",
                    "activities": [
                        {
                            "activity_id": f"lesson-{label}",
                            "type": "lesson",
                            "title": "产品知识",
                            "objective": "能解释产品价值",
                            "why_it_matters": "支持客户沟通",
                            "steps": ["学习", "完成检查点"],
                            "success_criteria": ["完成检查点"],
                            "competency_keys": ["product_knowledge"],
                            "estimated_minutes": 20,
                            "required": True,
                            "prerequisite_activity_ids": [],
                            "ai_dependency": "none",
                            "retry_policy": {
                                "max_attempts": 0,
                                "retry_interval_seconds": 0,
                            },
                            "config": {
                                "learning_unit_revision_id": "unit-revision-1",
                                "required_checkpoint_ids": ["checkpoint-1"],
                            },
                        }
                    ],
                }
            ],
        }
    )


def _services(test_db, resources: ReleaseResources):
    mappings = CompetencyMappings()
    path_service = PathEnrollmentService(
        test_db,
        published_resources=resources,
        competency_mappings=mappings,
    )
    release_service = ReleasePlanService(
        test_db,
        dependencies=resources,
        path_service=path_service,
        competency_mappings=mappings,
    )
    return path_service, release_service


async def _create_learner(test_db) -> User:
    suffix = uuid.uuid4().hex[:8]
    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"release-learner-{suffix}",
        name="发布验证学员",
        email=f"release-{suffix}@example.com",
        role="user",
    )
    test_db.add(learner)
    await test_db.flush([learner])
    return learner


@pytest.mark.asyncio
async def test_release_plan_publishes_atomically_and_keeps_enrollment_frozen(
    test_db,
) -> None:
    resources = ReleaseResources()
    path_service, release_service = _services(test_db, resources)
    actor = _actor()
    path = await path_service.create_path(
        actor=actor,
        stable_key="foundation",
        title="新人销售基础训练",
        idempotency_key="create-path",
    )
    revision_one = await path_service.save_working_revision(
        actor=actor,
        path_id=path.path_id,
        draft=_draft("v1"),
        expected_path_version=path.version,
        idempotency_key="save-v1",
    )
    preview_one = await release_service.preview(
        actor=actor,
        path_revision_id=revision_one.revision_id,
        reason="首发版本审核完成",
        idempotency_key="preview-v1",
    )
    assert preview_one.status == "ready"
    published_one = await release_service.publish(
        actor=actor,
        release_plan_id=preview_one.release_plan_id,
        preview_token=preview_one.preview_token,
        impact_hash=preview_one.impact_hash,
        expected_version=preview_one.version,
        idempotency_key="publish-v1",
    )
    assert published_one.status == "published"

    learner = await _create_learner(test_db)
    cohort = await path_service.create_cohort(
        actor=actor,
        stable_key="july",
        name="七月新人班",
        path_revision_id=revision_one.revision_id,
        idempotency_key="create-cohort",
    )
    enrollment = await path_service.enroll(
        actor=actor,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key="enroll",
    )
    current_path = await path_service.get_path(actor=actor, path_id=path.path_id)
    revision_two = await path_service.save_working_revision(
        actor=actor,
        path_id=path.path_id,
        draft=_draft("v2"),
        expected_path_version=current_path.version,
        idempotency_key="save-v2",
    )
    resources.status = "working"
    preview_two = await release_service.preview(
        actor=actor,
        path_revision_id=revision_two.revision_id,
        reason="第二版审核完成",
        idempotency_key="preview-v2",
    )
    assert preview_two.impact_preview["active_enrollments_unchanged"] is True
    published_two = await release_service.publish(
        actor=actor,
        release_plan_id=preview_two.release_plan_id,
        preview_token=preview_two.preview_token,
        impact_hash=preview_two.impact_hash,
        expected_version=preview_two.version,
        idempotency_key="publish-v2",
    )

    frozen = await test_db.get(NewcomerEnrollment, enrollment.enrollment_id)
    assert frozen is not None
    assert frozen.path_revision_id == revision_one.revision_id
    persisted_path = await test_db.get(NewcomerPath, path.path_id)
    assert persisted_path is not None
    assert persisted_path.published_revision_id == revision_two.revision_id
    assert persisted_path.active_release_plan_id == published_two.release_plan_id

    rollback = await release_service.preview_rollback(
        actor=actor,
        active_release_plan_id=published_two.release_plan_id,
        target_release_plan_id=published_one.release_plan_id,
        reason="第二版出现业务阻塞",
    )
    active_plan = await test_db.get(
        NewcomerReleasePlan, published_two.release_plan_id
    )
    assert active_plan is not None
    restored = await release_service.confirm_rollback(
        actor=actor,
        active_release_plan_id=published_two.release_plan_id,
        preview_token=rollback.preview_token,
        impact_hash=rollback.impact_hash,
        expected_version=active_plan.version,
        idempotency_key="rollback-v2",
    )
    assert restored.release_plan_id == published_one.release_plan_id
    assert persisted_path.published_revision_id == revision_one.revision_id
    assert frozen.path_revision_id == revision_one.revision_id


@pytest.mark.asyncio
async def test_release_failure_preserves_old_version_and_records_failed_plan(
    test_db,
) -> None:
    resources = ReleaseResources()
    path_service, release_service = _services(test_db, resources)
    actor = _actor()
    path = await path_service.create_path(
        actor=actor,
        stable_key="failure-path",
        title="新人训练",
        idempotency_key="create",
    )
    first = await path_service.save_working_revision(
        actor=actor,
        path_id=path.path_id,
        draft=_draft("stable"),
        expected_path_version=path.version,
        idempotency_key="save-stable",
    )
    first_preview = await release_service.preview(
        actor=actor,
        path_revision_id=first.revision_id,
        reason="稳定版",
        idempotency_key="preview-stable",
    )
    first_plan = await release_service.publish(
        actor=actor,
        release_plan_id=first_preview.release_plan_id,
        preview_token=first_preview.preview_token,
        impact_hash=first_preview.impact_hash,
        expected_version=first_preview.version,
        idempotency_key="publish-stable",
    )
    current = await path_service.get_path(actor=actor, path_id=path.path_id)
    second = await path_service.save_working_revision(
        actor=actor,
        path_id=path.path_id,
        draft=_draft("broken"),
        expected_path_version=current.version,
        idempotency_key="save-broken",
    )
    resources.status = "working"
    preview = await release_service.preview(
        actor=actor,
        path_revision_id=second.revision_id,
        reason="失败验证",
        idempotency_key="preview-broken",
    )
    resources.fail_publish = True

    with pytest.raises(NewcomerTrainingError) as failed:
        await release_service.publish(
            actor=actor,
            release_plan_id=preview.release_plan_id,
            preview_token=preview.preview_token,
            impact_hash=preview.impact_hash,
            expected_version=preview.version,
            idempotency_key="publish-broken",
        )
    assert failed.value.code == "[NEWCOMER_RELEASE_PUBLISH_FAILED]"

    persisted_path = await test_db.get(NewcomerPath, path.path_id)
    failed_plan = await test_db.get(NewcomerReleasePlan, preview.release_plan_id)
    broken_revision = await test_db.get(NewcomerPathRevision, second.revision_id)
    assert persisted_path is not None
    assert failed_plan is not None
    assert broken_revision is not None
    assert persisted_path.published_revision_id == first.revision_id
    assert persisted_path.active_release_plan_id == first_plan.release_plan_id
    assert failed_plan.status == "failed"
    assert broken_revision.status == "working"


@pytest.mark.asyncio
async def test_release_plan_rejects_stale_version_cross_org_and_missing_capability(
    test_db,
) -> None:
    resources = ReleaseResources()
    path_service, release_service = _services(test_db, resources)
    actor = _actor()
    path = await path_service.create_path(
        actor=actor,
        stable_key="guarded",
        title="新人训练",
        idempotency_key="guarded-create",
    )
    revision = await path_service.save_working_revision(
        actor=actor,
        path_id=path.path_id,
        draft=_draft("guarded"),
        expected_path_version=path.version,
        idempotency_key="guarded-save",
    )
    preview = await release_service.preview(
        actor=actor,
        path_revision_id=revision.revision_id,
        reason="并发保护",
        idempotency_key="guarded-preview",
    )

    with pytest.raises(NewcomerTrainingError) as stale:
        await release_service.publish(
            actor=actor,
            release_plan_id=preview.release_plan_id,
            preview_token=preview.preview_token,
            impact_hash=preview.impact_hash,
            expected_version=preview.version + 1,
            idempotency_key="stale",
        )
    assert stale.value.status_code == 412

    cross_org = await release_service.list_plans(
        actor=_actor(organization_id="org-2")
    )
    assert cross_org == ()

    denied = CommandActor(
        organization_id="org-1",
        actor_id="viewer",
        capabilities=frozenset(),
    )
    with pytest.raises(NewcomerTrainingError) as forbidden:
        await release_service.preview(
            actor=denied,
            path_revision_id=revision.revision_id,
            reason="不允许",
            idempotency_key="denied",
        )
    assert forbidden.value.status_code == 403
