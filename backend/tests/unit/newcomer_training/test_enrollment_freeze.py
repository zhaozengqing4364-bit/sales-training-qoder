from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from common.db.models import User
from newcomer_training.application import (
    CommandActor,
    PathEnrollmentService,
    _SnapshotCompetencyMappings,
)
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerCohort,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerEnrollmentImport,
    NewcomerEnrollmentMigration,
    NewcomerPath,
    NewcomerPathRevision,
)
from newcomer_training.ports import PublishedActivityResourcePort


class PublishedResources(PublishedActivityResourcePort):
    def __init__(self, published: set[tuple[str, str, str]]) -> None:
        self._published = published

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        if (organization_id, activity_type, revision_id) not in self._published:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RESOURCE_UNPUBLISHED]",
                "训练活动引用的资源修订尚未发布。",
                422,
            )


def actor(
    actor_id: str = "admin-1",
    *,
    organization_id: str = "org-1",
    capabilities: frozenset[str] | None = None,
) -> CommandActor:
    return CommandActor(
        organization_id=organization_id,
        actor_id=actor_id,
        capabilities=(
            frozenset(
                {
                    "newcomer.path.manage",
                    "newcomer.path.publish",
                    "newcomer.cohort.manage",
                    "newcomer.enrollment.manage",
                    "newcomer.enrollment.migrate",
                }
            )
            if capabilities is None
            else capabilities
        ),
    )


def draft(label: str) -> PathRevisionDraft:
    return PathRevisionDraft.model_validate(
        {
            "title": "新人销售基础训练",
            "revision_label": label,
            "stages": [
                {
                    "stage_id": "stage-product",
                    "sequence": 1,
                    "title": "产品基础",
                    "objective": "建立产品知识",
                    "entry_conditions": [],
                    "completion_rule": "all_required",
                    "visibility": "learner",
                    "activities": [
                        {
                            "activity_id": "lesson-product",
                            "type": "lesson",
                            "title": "产品知识学习",
                            "objective": "理解产品价值",
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
                                "learning_unit_revision_id": "learning-revision-1",
                                "required_checkpoint_ids": ["checkpoint-1"],
                            },
                        }
                    ],
                }
            ],
        }
    )


async def _learner(test_db, suffix: str) -> User:
    row = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"learner-{suffix}-{uuid.uuid4().hex[:8]}",
        name=f"Learner {suffix}",
        email=f"learner-{suffix}-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
    )
    test_db.add(row)
    await test_db.flush()
    return row


def _published_resources() -> PublishedResources:
    return PublishedResources({("org-1", "lesson", "learning-revision-1")})


async def _published_setup(
    test_db,
    *,
    stable_suffix: str,
) -> tuple[
    PathEnrollmentService,
    CommandActor,
    NewcomerPath,
    NewcomerPathRevision,
    NewcomerCohort,
]:
    service = PathEnrollmentService(
        test_db,
        published_resources=_published_resources(),
    )
    admin = actor()
    path_summary = await service.create_path(
        actor=admin,
        stable_key=f"foundation-{stable_suffix}",
        title="新人销售基础训练",
        idempotency_key=f"create-{stable_suffix}",
    )
    working = await service.save_working_revision(
        actor=admin,
        path_id=path_summary.path_id,
        draft=draft(f"{stable_suffix}-v1"),
        expected_path_version=path_summary.version,
        idempotency_key=f"save-{stable_suffix}",
    )
    published = await service.publish_revision(
        actor=admin,
        revision_id=working.revision_id,
        expected_revision_version=working.version,
        idempotency_key=f"publish-{stable_suffix}",
    )
    cohort_summary = await service.create_cohort(
        actor=admin,
        stable_key=f"cohort-{stable_suffix}",
        name=f"新人班 {stable_suffix}",
        path_revision_id=published.revision_id,
        idempotency_key=f"create-cohort-{stable_suffix}",
    )
    path = await test_db.get(NewcomerPath, path_summary.path_id)
    revision = await test_db.get(NewcomerPathRevision, published.revision_id)
    cohort = await test_db.get(NewcomerCohort, cohort_summary.cohort_id)
    assert path is not None and revision is not None and cohort is not None
    return service, admin, path, revision, cohort


async def _publish_next_revision(
    service: PathEnrollmentService,
    *,
    admin: CommandActor,
    path_id: str,
    suffix: str,
) -> NewcomerPathRevision:
    path = await service.get_path(actor=admin, path_id=path_id)
    working = await service.save_working_revision(
        actor=admin,
        path_id=path_id,
        draft=draft(f"{suffix}-v2"),
        expected_path_version=path.version,
        idempotency_key=f"save-{suffix}-v2",
    )
    await service.publish_revision(
        actor=admin,
        revision_id=working.revision_id,
        expected_revision_version=working.version,
        idempotency_key=f"publish-{suffix}-v2",
    )
    row = await service._load_revision(admin, working.revision_id)
    return row


@pytest.mark.asyncio
async def test_unbound_working_activity_saves_but_validation_blocks_publish(
    test_db,
) -> None:
    service = PathEnrollmentService(test_db, published_resources=PublishedResources(set()))
    admin = actor()
    path = await service.create_path(
        actor=admin,
        stable_key="draft-with-later-binding",
        title="待补资源的训练路径",
        idempotency_key="create-unbound-path",
    )
    payload = draft("未完成")
    raw = payload.model_dump(mode="json")
    raw["stages"][0]["activities"][0]["config"] = {
        "learning_unit_revision_id": "",
        "required_checkpoint_ids": [],
    }
    saved = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=PathRevisionDraft.model_validate(raw),
        expected_path_version=path.version,
        idempotency_key="save-unbound-path",
    )

    result = await service.validate_working_revision(
        actor=admin,
        path_id=path.path_id,
    )

    assert saved.status == "working"
    assert result.valid is False
    assert [issue.code for issue in result.issues] == ["activity_resource_required"]
    assert result.issues[0].field.endswith("learning_unit_revision_id")


@pytest.mark.asyncio
async def test_publish_keeps_existing_enrollment_frozen_until_explicit_migration(
    test_db,
) -> None:
    resources = PublishedResources(
        {("org-1", "lesson", "learning-revision-1")}
    )
    service = PathEnrollmentService(test_db, published_resources=resources)
    admin = actor()
    learner = await _learner(test_db, "freeze")

    path = await service.create_path(
        actor=admin,
        stable_key="foundation-standard",
        title="新人销售基础训练",
        idempotency_key="create-path",
    )
    revision_one = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("v1"),
        expected_path_version=path.version,
        idempotency_key="save-v1",
    )
    revision_one = await service.publish_revision(
        actor=admin,
        revision_id=revision_one.revision_id,
        expected_revision_version=revision_one.version,
        idempotency_key="publish-v1",
    )
    cohort = await service.create_cohort(
        actor=admin,
        stable_key="2026-july",
        name="2026 年 7 月新人班",
        path_revision_id=revision_one.revision_id,
        idempotency_key="create-cohort",
    )
    enrollment = await service.enroll(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key="enroll-learner",
    )

    path = await service.get_path(
        actor=admin, path_id=path.path_id
    )
    revision_two = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("v2"),
        expected_path_version=path.version,
        idempotency_key="save-v2",
    )
    await service.publish_revision(
        actor=admin,
        revision_id=revision_two.revision_id,
        expected_revision_version=revision_two.version,
        idempotency_key="publish-v2",
    )
    await test_db.flush()

    frozen = await test_db.get(NewcomerEnrollment, enrollment.enrollment_id)
    assert frozen is not None
    assert frozen.path_revision_id == revision_one.revision_id

    preview = await service.preview_revision_migration(
        actor=admin,
        enrollment_ids=[enrollment.enrollment_id],
        target_revision_id=revision_two.revision_id,
        reason="切换到已审核的新训练版本",
    )
    await test_db.flush()
    assert frozen.path_revision_id == revision_one.revision_id
    assert preview.eligible_count == 1
    assert preview.failure_count == 0

    result = await service.confirm_revision_migration(
        actor=admin,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="migrate-learner",
    )
    replay = await service.confirm_revision_migration(
        actor=admin,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="migrate-learner",
    )
    await test_db.flush()

    assert result == replay
    assert result.migrated_count == 1
    assert result.failure_count == 0
    assert frozen.path_revision_id == revision_two.revision_id
    assert frozen.version == enrollment.version + 1
    audits = (
        await test_db.execute(
            select(NewcomerCommandAudit).where(
                NewcomerCommandAudit.command == "migrate_enrollment_revision"
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].result == "succeeded"


@pytest.mark.asyncio
async def test_unpublished_cross_org_permission_and_stale_writes_are_rejected(
    test_db,
) -> None:
    service = PathEnrollmentService(
        test_db,
        published_resources=PublishedResources(
            {("org-1", "lesson", "learning-revision-1")}
        ),
    )
    admin = actor()
    path = await service.create_path(
        actor=admin,
        stable_key="foundation-standard",
        title="新人销售基础训练",
        idempotency_key="create-path",
    )
    working = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("v1"),
        expected_path_version=path.version,
        idempotency_key="save-v1",
    )

    with pytest.raises(NewcomerTrainingError) as unpublished:
        await service.create_cohort(
            actor=admin,
            stable_key="cohort-1",
            name="新人班",
            path_revision_id=working.revision_id,
            idempotency_key="cohort-unpublished",
        )
    assert unpublished.value.code == "[NEWCOMER_PATH_REVISION_UNPUBLISHED]"

    with pytest.raises(NewcomerTrainingError) as stale:
        await service.save_working_revision(
            actor=admin,
            path_id=path.path_id,
            draft=draft("stale"),
            expected_path_version=path.version,
            idempotency_key="save-stale",
        )
    assert stale.value.status_code == 412

    with pytest.raises(NewcomerTrainingError) as forbidden:
        await service.get_path(
            actor=actor(
                "learner",
                capabilities=frozenset(),
            ),
            path_id=path.path_id,
        )
    assert forbidden.value.status_code == 403

    with pytest.raises(NewcomerTrainingError) as hidden_cross_org:
        await service.get_path(
            actor=actor(organization_id="org-2"),
            path_id=path.path_id,
        )
    assert hidden_cross_org.value.status_code == 404


@pytest.mark.asyncio
async def test_enrollment_import_previews_partial_results_and_replays_idempotently(
    test_db,
) -> None:
    service = PathEnrollmentService(
        test_db,
        published_resources=PublishedResources(
            {("org-1", "lesson", "learning-revision-1")}
        ),
    )
    admin = actor()
    path = await service.create_path(
        actor=admin,
        stable_key="import-path",
        title="新人训练",
        idempotency_key="import-create-path",
    )
    revision = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("import-v1"),
        expected_path_version=path.version,
        idempotency_key="import-save-path",
    )
    revision = await service.publish_revision(
        actor=admin,
        revision_id=revision.revision_id,
        expected_revision_version=revision.version,
        idempotency_key="import-publish-path",
    )
    cohort = await service.create_cohort(
        actor=admin,
        stable_key="import-cohort",
        name="批量分配班级",
        path_revision_id=revision.revision_id,
        idempotency_key="import-create-cohort",
    )
    existing = await _learner(test_db, "existing")
    new_learner = await _learner(test_db, "new")
    await service.enroll(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_id=str(existing.user_id),
        idempotency_key="import-existing-enrollment",
    )

    preview = await service.preview_enrollment_import(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_ids=[str(existing.user_id), str(new_learner.user_id)],
        reason="七月新人批量入班",
    )
    assert preview.eligible_count == 1
    assert preview.failure_count == 1

    result = await service.confirm_enrollment_import(
        actor=admin,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="confirm-import",
    )
    replay = await service.confirm_enrollment_import(
        actor=admin,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="confirm-import",
    )
    assert result == replay
    assert result.succeeded_count == 1
    assert result.failure_count == 1
    assert {item.status for item in result.items} == {"succeeded", "failed"}

    paused = await service.update_cohort_status(
        actor=admin,
        cohort_id=cohort.cohort_id,
        target_status="paused",
        expected_version=cohort.version,
        reason="暂缓新学员分配",
        idempotency_key="pause-import-cohort",
    )
    assert paused.status == "paused"
    with pytest.raises(NewcomerTrainingError) as inactive:
        await service.enroll(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_id=str(uuid.uuid4()),
            idempotency_key="blocked-while-paused",
        )
    assert inactive.value.code == "[NEWCOMER_COHORT_INACTIVE]"


@pytest.mark.asyncio
async def test_path_and_working_revision_idempotency_covers_update_and_replacement(
    test_db,
) -> None:
    service = PathEnrollmentService(
        test_db,
        published_resources=_published_resources(),
    )
    admin = actor()
    path = await service.create_path(
        actor=admin,
        stable_key="branch-path",
        title="新人训练",
        idempotency_key="create-branch-path",
    )
    replayed_path = await service.create_path(
        actor=admin,
        stable_key="branch-path",
        title="新人训练",
        idempotency_key="create-branch-path",
    )
    assert replayed_path.path_id == path.path_id
    with pytest.raises(NewcomerTrainingError) as path_conflict:
        await service.create_path(
            actor=admin,
            stable_key="branch-path",
            title="不同标题",
            idempotency_key="different-create-key",
        )
    assert path_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    first = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("branch-v1"),
        expected_path_version=path.version,
        idempotency_key="save-branch-v1",
    )
    replayed = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("branch-v1"),
        expected_path_version=path.version,
        idempotency_key="save-branch-v1",
    )
    assert replayed == first
    with pytest.raises(NewcomerTrainingError) as revision_conflict:
        await service.save_working_revision(
            actor=admin,
            path_id=path.path_id,
            draft=draft("different-replay"),
            expected_path_version=path.version,
            idempotency_key="save-branch-v1",
        )
    assert revision_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    current_path = await service.get_path(actor=admin, path_id=path.path_id)
    updated = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("branch-v2"),
        expected_path_version=current_path.version,
        idempotency_key="save-branch-v2",
    )
    assert updated.revision_id == first.revision_id
    persisted_working = await test_db.get(NewcomerPathRevision, updated.revision_id)
    assert persisted_working is not None
    persisted_working.status = "archived"
    await test_db.flush([persisted_working])

    current_path = await service.get_path(actor=admin, path_id=path.path_id)
    replacement = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("branch-v3"),
        expected_path_version=current_path.version,
        idempotency_key="save-branch-v3",
    )
    assert replacement.revision_id != updated.revision_id


@pytest.mark.asyncio
async def test_publish_replay_immutability_validation_and_detached_working_pointer(
    test_db,
) -> None:
    service = PathEnrollmentService(
        test_db,
        published_resources=_published_resources(),
    )
    admin = actor()
    path = await service.create_path(
        actor=admin,
        stable_key="publish-branches",
        title="新人训练",
        idempotency_key="create-publish-branches",
    )
    working = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("publish-v1"),
        expected_path_version=path.version,
        idempotency_key="save-publish-v1",
    )
    with pytest.raises(NewcomerTrainingError) as blank_reason:
        await service.publish_revision(
            actor=admin,
            revision_id=working.revision_id,
            expected_revision_version=working.version,
            idempotency_key="publish-v1",
            reason="  ",
        )
    assert blank_reason.value.code == "[NEWCOMER_PUBLISH_REASON_REQUIRED]"

    published = await service.publish_revision(
        actor=admin,
        revision_id=working.revision_id,
        expected_revision_version=working.version,
        idempotency_key="publish-v1",
        reason="完成发布检查",
    )
    replay = await service.publish_revision(
        actor=admin,
        revision_id=working.revision_id,
        expected_revision_version=working.version,
        idempotency_key="publish-v1",
        reason="完成发布检查",
    )
    assert replay == published
    with pytest.raises(NewcomerTrainingError) as immutable:
        await service.publish_revision(
            actor=admin,
            revision_id=working.revision_id,
            expected_revision_version=working.version,
            idempotency_key="publish-v1-again",
            reason="再次发布",
        )
    assert immutable.value.code == "[NEWCOMER_PATH_REVISION_IMMUTABLE]"

    unbound_path = await service.create_path(
        actor=admin,
        stable_key="publish-unbound",
        title="待补资源",
        idempotency_key="create-publish-unbound",
    )
    unbound_payload = draft("publish-unbound").model_dump(mode="json")
    unbound_payload["stages"][0]["activities"][0]["config"][
        "learning_unit_revision_id"
    ] = ""
    unbound = await service.save_working_revision(
        actor=admin,
        path_id=unbound_path.path_id,
        draft=PathRevisionDraft.model_validate(unbound_payload),
        expected_path_version=unbound_path.version,
        idempotency_key="save-publish-unbound",
    )
    with pytest.raises(NewcomerTrainingError) as invalid:
        await service.publish_revision(
            actor=admin,
            revision_id=unbound.revision_id,
            expected_revision_version=unbound.version,
            idempotency_key="publish-unbound",
        )
    assert invalid.value.code == "[NEWCOMER_PATH_VALIDATION_FAILED]"

    detached_path = await service.create_path(
        actor=admin,
        stable_key="publish-detached",
        title="独立工作指针",
        idempotency_key="create-publish-detached",
    )
    detached_working = await service.save_working_revision(
        actor=admin,
        path_id=detached_path.path_id,
        draft=draft("detached-v1"),
        expected_path_version=detached_path.version,
        idempotency_key="save-publish-detached",
    )
    detached_row = await test_db.get(NewcomerPath, detached_path.path_id)
    assert detached_row is not None
    detached_row.working_revision_id = None
    await test_db.flush([detached_row])
    detached_published = await service.publish_revision(
        actor=admin,
        revision_id=detached_working.revision_id,
        expected_revision_version=detached_working.version,
        idempotency_key="publish-detached",
    )
    assert detached_published.status == "published"


@pytest.mark.asyncio
async def test_validation_and_private_loaders_cover_missing_configuration(
    test_db,
) -> None:
    service = PathEnrollmentService(
        test_db,
        published_resources=_published_resources(),
    )
    admin = actor()
    with pytest.raises(NewcomerTrainingError) as missing_path:
        await service.validate_working_revision(actor=admin, path_id="missing-path")
    assert missing_path.value.code == "[NEWCOMER_PATH_NOT_FOUND]"

    empty_path = await service.create_path(
        actor=admin,
        stable_key="empty-working",
        title="尚无修订",
        idempotency_key="create-empty-working",
    )
    with pytest.raises(NewcomerTrainingError) as missing_working:
        await service.validate_working_revision(
            actor=admin,
            path_id=empty_path.path_id,
        )
    assert missing_working.value.code == "[NEWCOMER_PATH_WORKING_REVISION_NOT_FOUND]"

    no_competency = draft("missing-competency").model_dump(mode="json")
    no_competency["stages"][0]["activities"][0]["competency_keys"] = []
    saved = await service.save_working_revision(
        actor=admin,
        path_id=empty_path.path_id,
        draft=PathRevisionDraft.model_validate(no_competency),
        expected_path_version=empty_path.version,
        idempotency_key="save-missing-competency",
    )
    validation = await service.validate_working_revision(
        actor=admin,
        path_id=empty_path.path_id,
    )
    assert saved.status == "working"
    assert "competency_mapping_required" in {item.code for item in validation.issues}

    with pytest.raises(NewcomerTrainingError) as fallback_mapping:
        await _SnapshotCompetencyMappings().require_valid(
            organization_id="org-1",
            path_revision_id=saved.revision_id,
            activity_id="lesson-product",
            activity_type="lesson",
            competency_keys=(),
        )
    assert fallback_mapping.value.code == "[COMPETENCY_MAPPING_REQUIRED]"

    for loader, object_id in (
        (service._load_path_for_update, "missing-path"),
        (service._load_revision, "missing-revision"),
        (service._load_revision_for_update, "missing-revision-for-update"),
    ):
        with pytest.raises(NewcomerTrainingError):
            await loader(admin, object_id)

    assert service._is_expired(datetime.now() - timedelta(seconds=1)) is True


@pytest.mark.asyncio
async def test_cohort_and_enrollment_cover_identity_scope_and_active_guards(
    test_db,
) -> None:
    service, admin, _, revision, cohort = await _published_setup(
        test_db,
        stable_suffix="identity",
    )
    cohort_replay = await service.create_cohort(
        actor=admin,
        stable_key="cohort-identity",
        name="新人班 identity",
        path_revision_id=revision.revision_id,
        idempotency_key="create-cohort-identity",
    )
    assert cohort_replay.cohort_id == cohort.cohort_id
    with pytest.raises(NewcomerTrainingError) as cohort_conflict:
        await service.create_cohort(
            actor=admin,
            stable_key="cohort-identity",
            name="不同班次名称",
            path_revision_id=revision.revision_id,
            idempotency_key="different-cohort-key",
        )
    assert cohort_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    with pytest.raises(NewcomerTrainingError) as missing_cohort:
        await service.enroll(
            actor=admin,
            cohort_id="missing-cohort",
            learner_id=str(uuid.uuid4()),
            idempotency_key="enroll-missing-cohort",
        )
    assert missing_cohort.value.code == "[NEWCOMER_COHORT_NOT_FOUND]"

    learner = await _learner(test_db, "identity")
    revision.status = "working"
    await test_db.flush([revision])
    with pytest.raises(NewcomerTrainingError) as unpublished:
        await service.enroll(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_id=str(learner.user_id),
            idempotency_key="enroll-unpublished-cohort",
        )
    assert unpublished.value.code == "[NEWCOMER_PATH_REVISION_UNPUBLISHED]"
    revision.status = "published"
    await test_db.flush([revision])

    with pytest.raises(NewcomerTrainingError) as missing_learner:
        await service.enroll(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_id=str(uuid.uuid4()),
            idempotency_key="enroll-missing-learner",
        )
    assert missing_learner.value.code == "[NEWCOMER_LEARNER_NOT_FOUND]"
    inactive_learner = await _learner(test_db, "inactive")
    inactive_learner.is_active = False
    await test_db.flush([inactive_learner])
    with pytest.raises(NewcomerTrainingError) as inactive:
        await service.enroll(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_id=str(inactive_learner.user_id),
            idempotency_key="enroll-inactive-learner",
        )
    assert inactive.value.code == "[NEWCOMER_LEARNER_NOT_FOUND]"

    enrollment = await service.enroll(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key="enroll-identity-learner",
    )
    replay = await service.enroll(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key="enroll-identity-learner",
    )
    assert replay == enrollment
    with pytest.raises(NewcomerTrainingError) as enrollment_conflict:
        await service.enroll(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_id=str(learner.user_id),
            idempotency_key="different-enrollment-key",
        )
    assert enrollment_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    second_cohort = await service.create_cohort(
        actor=admin,
        stable_key="cohort-identity-second",
        name="第二新人班",
        path_revision_id=revision.revision_id,
        idempotency_key="create-cohort-identity-second",
    )
    with pytest.raises(NewcomerTrainingError) as already_active:
        await service.enroll(
            actor=admin,
            cohort_id=second_cohort.cohort_id,
            learner_id=str(learner.user_id),
            idempotency_key="enroll-second-active",
        )
    assert already_active.value.code == "[NEWCOMER_LEARNER_ALREADY_ENROLLED]"


@pytest.mark.asyncio
async def test_cohort_status_covers_reason_lookup_replay_noop_and_illegal_transition(
    test_db,
) -> None:
    service, admin, _, _, cohort = await _published_setup(
        test_db,
        stable_suffix="cohort-status",
    )
    with pytest.raises(NewcomerTrainingError) as reason_required:
        await service.update_cohort_status(
            actor=admin,
            cohort_id=cohort.cohort_id,
            target_status="paused",
            expected_version=cohort.version,
            reason="  ",
            idempotency_key="blank-cohort-reason",
        )
    assert reason_required.value.code == "[NEWCOMER_COHORT_REASON_REQUIRED]"
    with pytest.raises(NewcomerTrainingError) as missing:
        await service.update_cohort_status(
            actor=admin,
            cohort_id="missing-cohort",
            target_status="paused",
            expected_version=1,
            reason="暂停",
            idempotency_key="missing-cohort-status",
        )
    assert missing.value.code == "[NEWCOMER_COHORT_NOT_FOUND]"

    paused = await service.update_cohort_status(
        actor=admin,
        cohort_id=cohort.cohort_id,
        target_status="paused",
        expected_version=cohort.version,
        reason="暂停分配",
        idempotency_key="pause-cohort-status",
    )
    replay = await service.update_cohort_status(
        actor=admin,
        cohort_id=cohort.cohort_id,
        target_status="paused",
        expected_version=1,
        reason="暂停分配",
        idempotency_key="pause-cohort-status",
    )
    assert replay == paused
    with pytest.raises(NewcomerTrainingError) as replay_conflict:
        await service.update_cohort_status(
            actor=admin,
            cohort_id=cohort.cohort_id,
            target_status="active",
            expected_version=1,
            reason="恢复分配",
            idempotency_key="pause-cohort-status",
        )
    assert replay_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    noop = await service.update_cohort_status(
        actor=admin,
        cohort_id=cohort.cohort_id,
        target_status="paused",
        expected_version=paused.version,
        reason="保持暂停",
        idempotency_key="noop-paused-cohort",
    )
    assert noop.status == "paused"

    cohort.status = "cancelled"
    await test_db.flush([cohort])
    with pytest.raises(NewcomerTrainingError) as illegal:
        await service.update_cohort_status(
            actor=admin,
            cohort_id=cohort.cohort_id,
            target_status="active",
            expected_version=cohort.version,
            reason="尝试恢复已取消班次",
            idempotency_key="illegal-cohort-transition",
        )
    assert illegal.value.code == "[NEWCOMER_COHORT_STATE_CONFLICT]"


@pytest.mark.asyncio
async def test_enrollment_import_covers_input_preview_and_confirmation_guards(
    test_db,
) -> None:
    service, admin, _, _, cohort = await _published_setup(
        test_db,
        stable_suffix="import-guards",
    )
    with pytest.raises(NewcomerTrainingError) as empty:
        await service.preview_enrollment_import(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_ids=[],
            reason="批量分配",
        )
    assert empty.value.code == "[NEWCOMER_ENROLLMENT_IMPORT_EMPTY]"
    with pytest.raises(NewcomerTrainingError) as reason_required:
        await service.preview_enrollment_import(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_ids=[str(uuid.uuid4())],
            reason="  ",
        )
    assert reason_required.value.code == "[NEWCOMER_ENROLLMENT_IMPORT_REASON_REQUIRED]"

    cohort.status = "paused"
    await test_db.flush([cohort])
    with pytest.raises(NewcomerTrainingError) as inactive:
        await service.preview_enrollment_import(
            actor=admin,
            cohort_id=cohort.cohort_id,
            learner_ids=[str(uuid.uuid4())],
            reason="暂停期间不可分配",
        )
    assert inactive.value.code == "[NEWCOMER_COHORT_INACTIVE]"
    cohort.status = "active"
    await test_db.flush([cohort])

    missing_preview = await service.preview_enrollment_import(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_ids=[str(uuid.uuid4())],
        reason="检查缺失学员",
    )
    assert missing_preview.items[0].reason == "learner_not_found_or_inactive"

    with pytest.raises(NewcomerTrainingError) as missing_batch:
        await service.confirm_enrollment_import(
            actor=admin,
            preview_token="missing-token",
            impact_hash="missing-impact",
            idempotency_key="confirm-missing-import",
        )
    assert missing_batch.value.code == "[NEWCOMER_ENROLLMENT_IMPORT_NOT_FOUND]"

    expired_learner = await _learner(test_db, "import-expired")
    expired_preview = await service.preview_enrollment_import(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_ids=[str(expired_learner.user_id)],
        reason="过期预览",
    )
    expired_batch = await test_db.get(
        NewcomerEnrollmentImport,
        expired_preview.import_id,
    )
    assert expired_batch is not None
    expired_batch.expires_at = datetime.now() - timedelta(seconds=1)
    await test_db.flush([expired_batch])
    with pytest.raises(NewcomerTrainingError) as expired:
        await service.confirm_enrollment_import(
            actor=admin,
            preview_token=expired_preview.preview_token,
            impact_hash=expired_preview.impact_hash,
            idempotency_key="confirm-expired-import",
        )
    assert expired.value.code == "[NEWCOMER_ENROLLMENT_IMPORT_EXPIRED]"

    mismatch_learner = await _learner(test_db, "import-impact")
    mismatch_preview = await service.preview_enrollment_import(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_ids=[str(mismatch_learner.user_id)],
        reason="影响不一致",
    )
    with pytest.raises(NewcomerTrainingError) as impact_mismatch:
        await service.confirm_enrollment_import(
            actor=admin,
            preview_token=mismatch_preview.preview_token,
            impact_hash="different-impact",
            idempotency_key="confirm-impact-mismatch",
        )
    assert impact_mismatch.value.code == "[NEWCOMER_ENROLLMENT_IMPORT_IMPACT_MISMATCH]"

    valid_learner = await _learner(test_db, "import-valid")
    valid_preview = await service.preview_enrollment_import(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_ids=[str(valid_learner.user_id)],
        reason="正式批量分配",
    )
    result = await service.confirm_enrollment_import(
        actor=admin,
        preview_token=valid_preview.preview_token,
        impact_hash=valid_preview.impact_hash,
        idempotency_key="confirm-valid-import",
    )
    assert result.succeeded_count == 1
    with pytest.raises(NewcomerTrainingError) as replay_conflict:
        await service.confirm_enrollment_import(
            actor=admin,
            preview_token=valid_preview.preview_token,
            impact_hash=valid_preview.impact_hash,
            idempotency_key="different-confirm-import",
        )
    assert replay_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"


@pytest.mark.asyncio
async def test_migration_preview_covers_input_target_and_item_classification(
    test_db,
) -> None:
    service, admin, path, revision_one, cohort_one = await _published_setup(
        test_db,
        stable_suffix="migration-preview",
    )
    revision_two = await _publish_next_revision(
        service,
        admin=admin,
        path_id=path.path_id,
        suffix="migration-preview",
    )
    with pytest.raises(NewcomerTrainingError) as empty:
        await service.preview_revision_migration(
            actor=admin,
            enrollment_ids=[],
            target_revision_id=revision_two.revision_id,
            reason="迁移",
        )
    assert empty.value.code == "[NEWCOMER_MIGRATION_EMPTY]"
    with pytest.raises(NewcomerTrainingError) as reason_required:
        await service.preview_revision_migration(
            actor=admin,
            enrollment_ids=["enrollment-1"],
            target_revision_id=revision_two.revision_id,
            reason="  ",
        )
    assert reason_required.value.code == "[NEWCOMER_MIGRATION_REASON_REQUIRED]"

    current_path = await service.get_path(actor=admin, path_id=path.path_id)
    unpublished = await service.save_working_revision(
        actor=admin,
        path_id=path.path_id,
        draft=draft("migration-preview-working"),
        expected_path_version=current_path.version,
        idempotency_key="save-migration-preview-working",
    )
    with pytest.raises(NewcomerTrainingError) as target_unpublished:
        await service.preview_revision_migration(
            actor=admin,
            enrollment_ids=["enrollment-1"],
            target_revision_id=unpublished.revision_id,
            reason="不能迁移到工作版本",
        )
    assert target_unpublished.value.code == "[NEWCOMER_PATH_REVISION_UNPUBLISHED]"

    eligible_learner = await _learner(test_db, "migration-eligible")
    inactive_learner = await _learner(test_db, "migration-inactive")
    target_learner = await _learner(test_db, "migration-target")
    eligible = await service.enroll(
        actor=admin,
        cohort_id=cohort_one.cohort_id,
        learner_id=str(eligible_learner.user_id),
        idempotency_key="enroll-migration-eligible",
    )
    inactive = await service.enroll(
        actor=admin,
        cohort_id=cohort_one.cohort_id,
        learner_id=str(inactive_learner.user_id),
        idempotency_key="enroll-migration-inactive",
    )
    inactive_row = await test_db.get(NewcomerEnrollment, inactive.enrollment_id)
    assert inactive_row is not None
    inactive_row.status = "completed"
    target_cohort = await service.create_cohort(
        actor=admin,
        stable_key="cohort-migration-target",
        name="目标版本班次",
        path_revision_id=revision_two.revision_id,
        idempotency_key="create-cohort-migration-target",
    )
    already_target = await service.enroll(
        actor=admin,
        cohort_id=target_cohort.cohort_id,
        learner_id=str(target_learner.user_id),
        idempotency_key="enroll-migration-target",
    )
    await test_db.flush([inactive_row])

    preview = await service.preview_revision_migration(
        actor=admin,
        enrollment_ids=[
            "missing-enrollment",
            inactive.enrollment_id,
            already_target.enrollment_id,
            eligible.enrollment_id,
        ],
        target_revision_id=revision_two.revision_id,
        reason="分类迁移对象",
    )
    reasons = {item.enrollment_id: item.reason for item in preview.items}
    assert reasons == {
        "missing-enrollment": "not_found_or_out_of_scope",
        inactive.enrollment_id: "enrollment_not_active",
        already_target.enrollment_id: "already_on_target_revision",
        eligible.enrollment_id: None,
    }
    assert revision_one.revision_id != revision_two.revision_id


@pytest.mark.asyncio
async def test_migration_confirmation_covers_all_preview_and_concurrency_guards(
    test_db,
) -> None:
    service, admin, path, _, cohort = await _published_setup(
        test_db,
        stable_suffix="migration-confirm",
    )
    target = await _publish_next_revision(
        service,
        admin=admin,
        path_id=path.path_id,
        suffix="migration-confirm",
    )
    learner = await _learner(test_db, "migration-confirm")
    enrollment_summary = await service.enroll(
        actor=admin,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key="enroll-migration-confirm",
    )
    enrollment = await test_db.get(
        NewcomerEnrollment,
        enrollment_summary.enrollment_id,
    )
    assert enrollment is not None

    async def preview(reason: str):
        return await service.preview_revision_migration(
            actor=admin,
            enrollment_ids=[enrollment.enrollment_id],
            target_revision_id=target.revision_id,
            reason=reason,
        )

    with pytest.raises(NewcomerTrainingError) as missing:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token="missing-token",
            impact_hash="missing-impact",
            idempotency_key="confirm-missing-migration",
        )
    assert missing.value.code == "[NEWCOMER_MIGRATION_PREVIEW_NOT_FOUND]"

    expired_preview = await preview("过期预览")
    expired_row = await test_db.get(
        NewcomerEnrollmentMigration,
        expired_preview.migration_id,
    )
    assert expired_row is not None
    expired_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await test_db.flush([expired_row])
    with pytest.raises(NewcomerTrainingError) as expired:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=expired_preview.preview_token,
            impact_hash=expired_preview.impact_hash,
            idempotency_key="confirm-expired-migration",
        )
    assert expired.value.code == "[NEWCOMER_MIGRATION_PREVIEW_EXPIRED]"

    impact_preview = await preview("影响校验")
    with pytest.raises(NewcomerTrainingError) as impact:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=impact_preview.preview_token,
            impact_hash="different-impact",
            idempotency_key="confirm-impact-migration",
        )
    assert impact.value.code == "[NEWCOMER_MIGRATION_IMPACT_MISMATCH]"

    reason_preview = await preview("固定迁移依据")
    with pytest.raises(NewcomerTrainingError) as reason_mismatch:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=reason_preview.preview_token,
            impact_hash=reason_preview.impact_hash,
            idempotency_key="confirm-reason-migration",
            reason="不同迁移依据",
        )
    assert reason_mismatch.value.code == "[NEWCOMER_MIGRATION_CONFIRM_MISMATCH]"

    identity_preview = await preview("对象校验")
    with pytest.raises(NewcomerTrainingError) as object_mismatch:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=identity_preview.preview_token,
            impact_hash=identity_preview.impact_hash,
            idempotency_key="confirm-object-migration",
            expected_enrollment_id="different-enrollment",
        )
    assert object_mismatch.value.code == "[NEWCOMER_MIGRATION_CONFIRM_MISMATCH]"

    version_preview = await preview("版本校验")
    with pytest.raises(NewcomerTrainingError) as version_mismatch:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=version_preview.preview_token,
            impact_hash=version_preview.impact_hash,
            idempotency_key="confirm-version-migration",
            expected_enrollment_id=enrollment.enrollment_id,
            expected_enrollment_version=enrollment.version + 1,
        )
    assert version_mismatch.value.code == "[NEWCOMER_VERSION_CONFLICT]"

    changed_preview = await preview("并发校验")
    enrollment.version += 1
    await test_db.flush([enrollment])
    changed = await service.confirm_revision_migration(
        actor=admin,
        preview_token=changed_preview.preview_token,
        impact_hash=changed_preview.impact_hash,
        idempotency_key="confirm-changed-migration",
    )
    assert changed.failure_count == 1
    assert changed.items[0].reason == "enrollment_changed_since_preview"

    success_preview = await preview("正式迁移")
    success = await service.confirm_revision_migration(
        actor=admin,
        preview_token=success_preview.preview_token,
        impact_hash=success_preview.impact_hash,
        idempotency_key="confirm-success-migration",
        expected_enrollment_id=enrollment.enrollment_id,
        expected_enrollment_version=enrollment.version,
        reason="正式迁移",
    )
    assert success.migrated_count == 1
    with pytest.raises(NewcomerTrainingError) as replay_conflict:
        await service.confirm_revision_migration(
            actor=admin,
            preview_token=success_preview.preview_token,
            impact_hash=success_preview.impact_hash,
            idempotency_key="different-success-migration",
        )
    assert replay_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    noneligible_preview = await preview("重复目标版本")
    assert noneligible_preview.items[0].status == "failed"
    noneligible = await service.confirm_revision_migration(
        actor=admin,
        preview_token=noneligible_preview.preview_token,
        impact_hash=noneligible_preview.impact_hash,
        idempotency_key="confirm-noneligible-migration",
    )
    assert noneligible.failure_count == 1
