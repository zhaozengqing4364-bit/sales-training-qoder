from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from newcomer_training.activity import (
    ActivityAttemptService,
    ActivityOutcomeCommand,
)
from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from task_runtime.models import OutboxEvent


def _snapshot() -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人训练",
        "revision_label": "v1",
        "stages": [
            {
                "stage_id": "stage-1",
                "sequence": 1,
                "title": "基础",
                "objective": "掌握基础",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-1",
                        "type": "lesson",
                        "title": "学习",
                        "objective": "掌握知识",
                        "why_it_matters": "支持销售",
                        "steps": ["阅读", "检查"],
                        "success_criteria": ["检查点完成"],
                        "estimated_minutes": 10,
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
                    },
                    {
                        "activity_id": "quiz-1",
                        "type": "quiz",
                        "title": "测验",
                        "objective": "验证掌握",
                        "why_it_matters": "确保准确",
                        "steps": ["答题"],
                        "success_criteria": ["通过"],
                        "estimated_minutes": 10,
                        "required": True,
                        "prerequisite_activity_ids": ["lesson-1"],
                        "ai_dependency": "optional",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {"quiz_revision_id": "quiz-revision-1"},
                    },
                ],
            },
            {
                "stage_id": "stage-2",
                "sequence": 2,
                "title": "进阶",
                "objective": "在完成基础阶段后继续学习",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-2",
                        "type": "lesson",
                        "title": "进阶学习",
                        "objective": "掌握进阶知识",
                        "why_it_matters": "建立完整销售能力",
                        "steps": ["阅读", "检查"],
                        "success_criteria": ["检查点完成"],
                        "estimated_minutes": 10,
                        "required": True,
                        "prerequisite_activity_ids": [],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 0,
                            "retry_interval_seconds": 0,
                        },
                        "config": {
                            "learning_unit_revision_id": "unit-revision-2",
                            "required_checkpoint_ids": ["checkpoint-2"],
                        },
                    }
                ],
            },
        ],
    }


async def _seed(test_db) -> CommandActor:
    now = datetime.now(UTC)
    path = NewcomerPath(
        path_id="path-1",
        organization_id="org-1",
        stable_key="foundation",
        title="新人训练",
        status="active",
        published_revision_id="revision-1",
        version=1,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id="revision-1",
        path_id="path-1",
        organization_id="org-1",
        revision_no=1,
        revision_label="v1",
        status="published",
        snapshot_json=_snapshot(),
        content_hash="c" * 64,
        version=2,
        save_idempotency_key_hash="d" * 64,
        save_fingerprint="e" * 64,
        publish_idempotency_key_hash="f" * 64,
        publish_fingerprint="1" * 64,
        created_by="admin",
        published_by="admin",
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id="cohort-1",
        organization_id="org-1",
        stable_key="cohort",
        name="新人班",
        path_revision_id="revision-1",
        status="active",
        version=1,
        creation_idempotency_key_hash="2" * 64,
        creation_fingerprint="3" * 64,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    enrollment = NewcomerEnrollment(
        enrollment_id="enrollment-1",
        organization_id="org-1",
        learner_id="learner-1",
        cohort_id="cohort-1",
        path_revision_id="revision-1",
        status="active",
        version=1,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        assigned_by="admin",
        assigned_at=now,
        updated_at=now,
    )
    test_db.add_all([path, revision, cohort, enrollment])
    await test_db.flush()
    return CommandActor(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset({"newcomer.activity.execute"}),
        trace_id="trace-1",
    )


@pytest.mark.asyncio
async def test_attempt_is_scoped_idempotent_and_freezes_activity_snapshot(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)

    first = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-lesson",
    )
    replay = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-lesson",
    )

    assert first == replay
    assert first.attempt_no == 1
    assert first.path_revision_id == "revision-1"
    row = await test_db.get(NewcomerActivityAttempt, first.attempt_id)
    assert row is not None
    assert row.activity_snapshot_json["activity_id"] == "lesson-1"
    assert row.activity_snapshot_json["config"]["learning_unit_revision_id"] == (
        "unit-revision-1"
    )

    with pytest.raises(NewcomerTrainingError) as conflict:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-1",
            expected_enrollment_version=2,
            idempotency_key="start-lesson",
        )
    assert conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"


@pytest.mark.asyncio
async def test_attempt_rejects_locked_stale_cross_org_and_cross_learner(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)

    with pytest.raises(NewcomerTrainingError) as locked:
        await service.start_attempt(
            actor=actor,
            activity_id="quiz-1",
            expected_enrollment_version=1,
            idempotency_key="start-quiz",
        )
    assert locked.value.code == "[NEWCOMER_ACTIVITY_LOCKED]"

    with pytest.raises(NewcomerTrainingError) as stage_locked:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-2",
            expected_enrollment_version=1,
            idempotency_key="start-stage-2",
        )
    assert stage_locked.value.code == "[NEWCOMER_ACTIVITY_LOCKED]"
    assert stage_locked.value.details == {"blocked_by": ["学习", "测验"]}

    with pytest.raises(NewcomerTrainingError) as stale:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-1",
            expected_enrollment_version=2,
            idempotency_key="stale-start",
        )
    assert stale.value.status_code == 412

    cross_org = actor.model_copy(update={"organization_id": "org-2"})
    with pytest.raises(NewcomerTrainingError) as hidden:
        await service.start_attempt(
            actor=cross_org,
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="cross-org",
        )
    assert hidden.value.status_code == 404

    other_learner = actor.model_copy(update={"actor_id": "learner-2"})
    with pytest.raises(NewcomerTrainingError) as other:
        await service.start_attempt(
            actor=other_learner,
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="cross-learner",
        )
    assert other.value.status_code == 404


@pytest.mark.asyncio
async def test_outcome_updates_generic_attempt_and_appends_one_domain_event(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    attempt = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-lesson",
    )
    command = ActivityOutcomeCommand(
        organization_id="org-1",
        attempt_id=attempt.attempt_id,
        lifecycle_result="completed",
        assessment_result="not_applicable",
        result_type="lesson_progress",
        result_id="lesson-detail-1",
        score=None,
        max_score=None,
        passed=None,
        source_refs=(
            {"resource_type": "learning_unit_revision", "resource_id": "unit-revision-1"},
        ),
        lineage={"learning_unit_revision_id": "unit-revision-1"},
        next_action=None,
    )
    outcome = await service.record_outcome(
        command=command,
        idempotency_key="complete-lesson",
        actor_id="learner-1",
        trace_id="trace-1",
    )
    replay = await service.record_outcome(
        command=command,
        idempotency_key="complete-lesson",
        actor_id="learner-1",
        trace_id="trace-1",
    )

    assert outcome == replay
    row = await test_db.get(NewcomerActivityAttempt, attempt.attempt_id)
    assert row is not None
    assert row.status == "completed"
    assert row.result_type == "lesson_progress"
    assert row.result_id == "lesson-detail-1"
    assert row.outcome_id == outcome.outcome_id
    persisted = await test_db.get(NewcomerActivityOutcome, outcome.outcome_id)
    assert persisted is not None
    assert persisted.source_refs_json[0]["resource_id"] == "unit-revision-1"
    events = (
        await test_db.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "ActivityOutcomeRecorded"
            )
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].aggregate_id == attempt.attempt_id


@pytest.mark.asyncio
async def test_admin_invalidation_preserves_outcome_and_reopens_activity(test_db) -> None:
    learner = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    attempt = await service.start_attempt(
        actor=learner,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-lesson",
    )
    outcome = await service.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id="org-1",
            attempt_id=attempt.attempt_id,
            lifecycle_result="completed",
            assessment_result="not_applicable",
            result_type="lesson_progress",
            result_id="lesson-detail-1",
            lineage={"learning_unit_revision_id": "unit-revision-1"},
            next_action=None,
        ),
        idempotency_key="complete-lesson",
        actor_id="learner-1",
        trace_id="trace-1",
    )
    completed = await test_db.get(NewcomerActivityAttempt, attempt.attempt_id)
    assert completed is not None
    completed_version = completed.version
    admin = CommandActor(
        organization_id="org-1",
        actor_id="training-admin",
        capabilities=frozenset({"newcomer.activity.invalidate"}),
        trace_id="trace-admin",
    )

    invalidated = await service.invalidate_attempt(
        actor=admin,
        attempt_id=attempt.attempt_id,
        expected_attempt_version=completed_version,
        reason="来源修订无效，需要重新学习",
        idempotency_key="invalidate-lesson",
    )
    replay = await service.invalidate_attempt(
        actor=admin,
        attempt_id=attempt.attempt_id,
        expected_attempt_version=completed_version,
        reason="来源修订无效，需要重新学习",
        idempotency_key="invalidate-lesson",
    )

    assert invalidated.status == "invalidated"
    assert replay == invalidated
    persisted_outcome = await test_db.get(
        NewcomerActivityOutcome, outcome.outcome_id
    )
    assert persisted_outcome is not None
    assert persisted_outcome.lifecycle_result == "completed"
    replacement = await service.start_attempt(
        actor=learner,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-relearn",
    )
    assert replacement.attempt_no == 2


@pytest.mark.asyncio
async def test_retry_policy_rejects_early_retry_and_completed_replay(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    lesson = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-lesson",
    )
    await service.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id="org-1",
            attempt_id=lesson.attempt_id,
            lifecycle_result="completed",
            assessment_result="not_applicable",
            result_type="lesson_progress",
            result_id="lesson-detail-1",
            lineage={"learning_unit_revision_id": "unit-revision-1"},
            next_action=None,
        ),
        idempotency_key="complete-lesson",
        actor_id="learner-1",
        trace_id="trace-1",
    )

    with pytest.raises(NewcomerTrainingError) as completed:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="duplicate-completed-lesson",
        )
    assert completed.value.code == "[NEWCOMER_ACTIVITY_ALREADY_COMPLETED]"

    quiz = await service.start_attempt(
        actor=actor,
        activity_id="quiz-1",
        expected_enrollment_version=1,
        idempotency_key="start-quiz",
    )
    await service.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id="org-1",
            attempt_id=quiz.attempt_id,
            lifecycle_result="completed",
            assessment_result="not_passed",
            result_type="quiz_result",
            result_id="quiz-detail-1",
            score=60,
            max_score=100,
            passed=False,
            lineage={"quiz_revision_id": "quiz-revision-1"},
            next_action={"type": "retry_quiz"},
        ),
        idempotency_key="complete-quiz",
        actor_id="learner-1",
        trace_id="trace-1",
    )

    with pytest.raises(NewcomerTrainingError) as retry_wait:
        await service.start_attempt(
            actor=actor,
            activity_id="quiz-1",
            expected_enrollment_version=1,
            idempotency_key="retry-quiz-too-soon",
        )
    assert retry_wait.value.code == "[NEWCOMER_ACTIVITY_RETRY_NOT_READY]"
    assert retry_wait.value.details["retry_after_seconds"] > 0

    persisted = await test_db.get(NewcomerActivityAttempt, quiz.attempt_id)
    assert persisted is not None
    persisted.completed_at = datetime.now(UTC) - timedelta(seconds=301)
    await test_db.flush([persisted])
    retry = await service.start_attempt(
        actor=actor,
        activity_id="quiz-1",
        expected_enrollment_version=1,
        idempotency_key="retry-quiz-ready",
    )
    assert retry.attempt_no == 2


@pytest.mark.parametrize(
    "updates",
    [
        {"score": 1, "max_score": None},
        {"max_score": 0},
        {"lifecycle_result": "failed", "passed": True},
    ],
)
def test_outcome_command_rejects_invalid_score_shapes(
    updates: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "organization_id": "org-1",
        "attempt_id": "attempt-1",
        "lifecycle_result": "completed",
        "assessment_result": "not_applicable",
        "result_type": "lesson_progress",
        "result_id": "lesson-detail-1",
        "lineage": {},
        "next_action": None,
    }
    payload.update(updates)

    with pytest.raises(ValidationError):
        ActivityOutcomeCommand.model_validate(payload)


@pytest.mark.asyncio
async def test_start_attempt_requires_capability(test_db) -> None:
    with pytest.raises(NewcomerTrainingError) as denied:
        await ActivityAttemptService(test_db).start_attempt(
            actor=CommandActor(
                organization_id="org-1",
                actor_id="learner-1",
                capabilities=frozenset(),
            ),
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="denied-start",
        )

    assert denied.value.code == "[NEWCOMER_PERMISSION_DENIED]"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["revision", "activity"])
async def test_start_attempt_rejects_unavailable_revision_and_unknown_activity(
    test_db,
    failure: str,
) -> None:
    actor = await _seed(test_db)
    if failure == "revision":
        revision = await test_db.get(NewcomerPathRevision, "revision-1")
        assert revision is not None
        revision.status = "working"
        await test_db.flush([revision])
        activity_id = "lesson-1"
        expected = "[NEWCOMER_PATH_REVISION_UNAVAILABLE]"
    else:
        activity_id = "missing-activity"
        expected = "[NEWCOMER_ACTIVITY_NOT_FOUND]"

    with pytest.raises(NewcomerTrainingError) as error:
        await ActivityAttemptService(test_db).start_attempt(
            actor=actor,
            activity_id=activity_id,
            expected_enrollment_version=1,
            idempotency_key=f"start-{failure}",
        )
    assert error.value.code == expected


@pytest.mark.asyncio
async def test_start_attempt_rejects_in_progress_and_attempt_limit(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-limited-lesson",
    )

    with pytest.raises(NewcomerTrainingError) as in_progress:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="start-second-active-lesson",
        )
    assert in_progress.value.code == "[NEWCOMER_ACTIVITY_ATTEMPT_IN_PROGRESS]"

    await service.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id="org-1",
            attempt_id=started.attempt_id,
            lifecycle_result="failed",
            assessment_result="not_applicable",
            result_type="lesson_progress",
            result_id="failed-lesson-detail",
            lineage={},
            next_action=None,
        ),
        idempotency_key="fail-limited-lesson",
        actor_id=actor.actor_id,
        trace_id=actor.trace_id,
    )
    revision = await test_db.get(NewcomerPathRevision, "revision-1")
    assert revision is not None
    snapshot = dict(revision.snapshot_json)
    snapshot["stages"] = [dict(stage) for stage in snapshot["stages"]]
    first_stage = snapshot["stages"][0]
    first_stage["activities"] = [
        dict(activity) for activity in first_stage["activities"]
    ]
    first_stage["activities"][0]["retry_policy"] = {
        "max_attempts": 1,
        "retry_interval_seconds": 1,
    }
    revision.snapshot_json = snapshot
    await test_db.flush([revision])

    with pytest.raises(NewcomerTrainingError) as limited:
        await service.start_attempt(
            actor=actor,
            activity_id="lesson-1",
            expected_enrollment_version=1,
            idempotency_key="start-over-limit",
        )
    assert limited.value.code == "[NEWCOMER_ACTIVITY_ATTEMPT_LIMIT_REACHED]"


@pytest.mark.asyncio
async def test_mark_processing_rejects_stale_and_terminal_attempts(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-processing-guard",
    )

    with pytest.raises(NewcomerTrainingError) as stale:
        await service.mark_processing(
            organization_id="org-1",
            attempt_id=started.attempt_id,
            task_id="task-1",
            expected_attempt_version=started.version + 1,
        )
    assert stale.value.code == "[NEWCOMER_VERSION_CONFLICT]"

    row = await test_db.get(NewcomerActivityAttempt, started.attempt_id)
    assert row is not None
    row.status = "completed"
    await test_db.flush([row])
    with pytest.raises(NewcomerTrainingError) as terminal:
        await service.mark_processing(
            organization_id="org-1",
            attempt_id=started.attempt_id,
            task_id="task-1",
            expected_attempt_version=row.version,
        )
    assert terminal.value.code == "[NEWCOMER_ATTEMPT_STATE_CONFLICT]"


@pytest.mark.asyncio
async def test_record_outcome_rejects_replay_lineage_and_terminal_conflicts(
    test_db,
) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-outcome-guards",
    )
    base = ActivityOutcomeCommand(
        organization_id="org-1",
        attempt_id=started.attempt_id,
        lifecycle_result="completed",
        assessment_result="not_applicable",
        result_type="lesson_progress",
        result_id="lesson-detail-1",
        lineage={},
        next_action=None,
    )
    persisted = await service.record_outcome(
        command=base,
        idempotency_key="outcome-replay-key",
        actor_id=actor.actor_id,
        trace_id=actor.trace_id,
    )

    with pytest.raises(NewcomerTrainingError) as replay_conflict:
        await service.record_outcome(
            command=base.model_copy(update={"result_id": "changed-detail"}),
            idempotency_key="outcome-replay-key",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
        )
    assert replay_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    with pytest.raises(NewcomerTrainingError) as lineage_conflict:
        await service.record_outcome(
            command=base.model_copy(update={"supersedes_outcome_id": "wrong-outcome"}),
            idempotency_key="outcome-lineage-key",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
        )
    assert lineage_conflict.value.code == "[NEWCOMER_OUTCOME_LINEAGE_CONFLICT]"
    assert persisted.outcome_id != "wrong-outcome"


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["started", "cancelled"])
async def test_record_outcome_rejects_missing_lineage_or_terminal_without_outcome(
    test_db,
    terminal_status: str,
) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key=f"start-{terminal_status}-lineage",
    )
    row = await test_db.get(NewcomerActivityAttempt, started.attempt_id)
    assert row is not None
    row.status = terminal_status
    await test_db.flush([row])
    command = ActivityOutcomeCommand(
        organization_id="org-1",
        attempt_id=started.attempt_id,
        lifecycle_result="cancelled",
        assessment_result="not_applicable",
        result_type="lesson_progress",
        result_id=f"{terminal_status}-detail",
        lineage={},
        next_action=None,
        supersedes_outcome_id=("missing-outcome" if terminal_status == "started" else None),
    )

    with pytest.raises(NewcomerTrainingError) as conflict:
        await service.record_outcome(
            command=command,
            idempotency_key=f"record-{terminal_status}-lineage",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
        )
    expected = (
        "[NEWCOMER_OUTCOME_LINEAGE_CONFLICT]"
        if terminal_status == "started"
        else "[NEWCOMER_ATTEMPT_STATE_CONFLICT]"
    )
    assert conflict.value.code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", ["failed", "invalidated", "cancelled"])
async def test_record_outcome_sets_every_terminal_lifecycle(
    test_db,
    lifecycle: str,
) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=actor,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key=f"start-{lifecycle}-outcome",
    )

    await service.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id="org-1",
            attempt_id=started.attempt_id,
            lifecycle_result=lifecycle,
            assessment_result="not_applicable",
            result_type="lesson_progress",
            result_id=f"{lifecycle}-detail",
            lineage={},
            next_action=None,
        ),
        idempotency_key=f"record-{lifecycle}-outcome",
        actor_id=actor.actor_id,
        trace_id=actor.trace_id,
    )

    row = await test_db.get(NewcomerActivityAttempt, started.attempt_id)
    assert row is not None
    assert row.status == lifecycle
    if lifecycle == "failed":
        assert row.failed_at is not None
    elif lifecycle == "invalidated":
        assert row.invalidated_at is not None


@pytest.mark.asyncio
async def test_invalidation_rejects_permission_reason_version_state_and_replay(
    test_db,
) -> None:
    learner = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    started = await service.start_attempt(
        actor=learner,
        activity_id="lesson-1",
        expected_enrollment_version=1,
        idempotency_key="start-invalidation-guards",
    )
    denied_actor = CommandActor(
        organization_id="org-1",
        actor_id="admin",
        capabilities=frozenset(),
    )
    admin = denied_actor.model_copy(
        update={"capabilities": frozenset({"newcomer.activity.invalidate"})}
    )

    with pytest.raises(NewcomerTrainingError) as denied:
        await service.invalidate_attempt(
            actor=denied_actor,
            attempt_id=started.attempt_id,
            expected_attempt_version=started.version,
            reason="失效",
            idempotency_key="denied-invalidation",
        )
    assert denied.value.code == "[NEWCOMER_PERMISSION_DENIED]"

    with pytest.raises(NewcomerTrainingError) as missing_reason:
        await service.invalidate_attempt(
            actor=admin,
            attempt_id=started.attempt_id,
            expected_attempt_version=started.version,
            reason="  ",
            idempotency_key="missing-invalidation-reason",
        )
    assert missing_reason.value.code == "[NEWCOMER_INVALIDATION_REASON_REQUIRED]"

    with pytest.raises(NewcomerTrainingError) as stale:
        await service.invalidate_attempt(
            actor=admin,
            attempt_id=started.attempt_id,
            expected_attempt_version=started.version + 1,
            reason="版本冲突",
            idempotency_key="stale-invalidation",
        )
    assert stale.value.code == "[NEWCOMER_VERSION_CONFLICT]"

    await service.invalidate_attempt(
        actor=admin,
        attempt_id=started.attempt_id,
        expected_attempt_version=started.version,
        reason="正式失效",
        idempotency_key="successful-invalidation",
    )
    with pytest.raises(NewcomerTrainingError) as replay_conflict:
        await service.invalidate_attempt(
            actor=admin,
            attempt_id=started.attempt_id,
            expected_attempt_version=started.version,
            reason="不同失效依据",
            idempotency_key="successful-invalidation",
        )
    assert replay_conflict.value.code == "[NEWCOMER_IDEMPOTENCY_CONFLICT]"

    with pytest.raises(NewcomerTrainingError) as terminal:
        await service.invalidate_attempt(
            actor=admin,
            attempt_id=started.attempt_id,
            expected_attempt_version=started.version + 1,
            reason="再次失效",
            idempotency_key="terminal-invalidation",
        )
    assert terminal.value.code == "[NEWCOMER_ATTEMPT_STATE_CONFLICT]"


@pytest.mark.asyncio
async def test_attempt_lookup_and_unlock_hide_missing_objects(test_db) -> None:
    actor = await _seed(test_db)
    service = ActivityAttemptService(test_db)
    enrollment = await test_db.get(NewcomerEnrollment, "enrollment-1")
    revision = await test_db.get(NewcomerPathRevision, "revision-1")
    assert enrollment is not None and revision is not None

    with pytest.raises(NewcomerTrainingError) as missing_activity:
        await service.require_activity_unlocked(
            enrollment=enrollment,
            draft=PathRevisionDraft.model_validate(revision.snapshot_json),
            activity_id="missing-activity",
        )
    assert missing_activity.value.code == "[NEWCOMER_ACTIVITY_NOT_FOUND]"

    with pytest.raises(NewcomerTrainingError) as missing_attempt:
        await service._load_attempt_for_update(
            organization_id=actor.organization_id,
            attempt_id="missing-attempt",
        )
    assert missing_attempt.value.code == "[NEWCOMER_ATTEMPT_NOT_FOUND]"
