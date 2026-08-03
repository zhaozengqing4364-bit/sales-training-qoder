from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.journey import JourneyActivityView, JourneyQueryService
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)


def _snapshot(label: str = "v1") -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人销售基础训练",
        "revision_label": label,
        "stages": [
            {
                "stage_id": "stage-1",
                "sequence": 1,
                "title": "产品基础",
                "objective": "建立产品知识",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-1",
                        "type": "lesson",
                        "title": "学习产品知识",
                        "objective": "理解产品价值",
                        "why_it_matters": "支持客户沟通",
                        "steps": ["学习", "完成检查点"],
                        "success_criteria": ["完成全部检查点"],
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
                    },
                    {
                        "activity_id": "quiz-1",
                        "type": "quiz",
                        "title": "产品知识测验",
                        "objective": "验证产品知识",
                        "why_it_matters": "确保表达准确",
                        "steps": ["阅读规则", "完成答题"],
                        "success_criteria": ["达到通过标准"],
                        "estimated_minutes": 15,
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
            }
        ],
    }


async def _seed_enrollment(test_db) -> tuple[CommandActor, NewcomerEnrollment]:
    now = datetime.now(UTC)
    path = NewcomerPath(
        path_id="path-1",
        organization_id="org-1",
        stable_key="foundation",
        title="新人销售基础训练",
        status="active",
        published_revision_id="revision-1",
        version=3,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id="revision-1",
        path_id=path.path_id,
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
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id="cohort-1",
        organization_id="org-1",
        stable_key="cohort",
        name="新人班",
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="2" * 64,
        creation_fingerprint="3" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    enrollment = NewcomerEnrollment(
        enrollment_id="enrollment-1",
        organization_id="org-1",
        learner_id="learner-1",
        cohort_id=cohort.cohort_id,
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        assigned_by="admin-1",
        assigned_at=now,
        updated_at=now,
    )
    test_db.add_all([path, revision, cohort, enrollment])
    await test_db.flush()
    return (
        CommandActor(
            organization_id="org-1",
            actor_id="learner-1",
            capabilities=frozenset({"newcomer.journey.read"}),
        ),
        enrollment,
    )


@pytest.mark.asyncio
async def test_journey_get_is_zero_write_and_unassigned_is_explicit(test_db) -> None:
    actor = CommandActor(
        organization_id="org-1",
        actor_id="learner-without-enrollment",
        capabilities=frozenset({"newcomer.journey.read"}),
    )
    before = int(
        await test_db.scalar(select(func.count(NewcomerEnrollment.enrollment_id))) or 0
    )

    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)
    after = int(
        await test_db.scalar(select(func.count(NewcomerEnrollment.enrollment_id))) or 0
    )

    assert before == after == 0
    assert journey.status == "not_enrolled"
    assert journey.enrollment is None
    assert journey.primary_action is None
    assert journey.status_reason == "尚未分配新人训练，请联系培训负责人。"


@pytest.mark.asyncio
async def test_journey_uses_frozen_revision_and_returns_one_primary_action(test_db) -> None:
    actor, enrollment = await _seed_enrollment(test_db)
    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)

    assert journey.enrollment is not None
    assert journey.enrollment.revision_id == enrollment.path_revision_id
    assert journey.path is not None
    assert journey.path.revision_label == "v1"
    assert journey.current_activity is not None
    assert journey.current_activity.activity_id == "lesson-1"
    assert journey.primary_action is not None
    assert journey.primary_action.activity_id == "lesson-1"
    assert journey.primary_action.command_type == "start_activity"
    activities = journey.stages[0].activities
    assert [item.status for item in activities] == ["available", "locked"]
    assert activities[1].blocked_reason == "请先完成：学习产品知识"
    assert journey.progress.completed_required == 0
    assert journey.progress.total_required == 2

    with pytest.raises(NewcomerTrainingError) as stale:
        await JourneyQueryService(test_db).get_my_journey(
            actor=actor,
            expected_enrollment_version=enrollment.version + 1,
        )
    assert stale.value.status_code == 412


@pytest.mark.asyncio
async def test_failed_quiz_projects_remediation_without_hiding_recent_result(
    test_db,
) -> None:
    actor, enrollment = await _seed_enrollment(test_db)
    now = datetime.now(UTC)
    lesson_attempt = NewcomerActivityAttempt(
        attempt_id="attempt-lesson",
        organization_id="org-1",
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="lesson-1",
        activity_type="lesson",
        attempt_no=1,
        status="completed",
        version=2,
        activity_snapshot_json={"activity_id": "lesson-1", "type": "lesson"},
        idempotency_key_hash="6" * 64,
        command_fingerprint="7" * 64,
        outcome_id="outcome-lesson",
        passed=None,
        evidence_status="recorded",
        reconcile_status="reconciled",
        started_at=now,
        completed_at=now,
    )
    lesson_outcome = NewcomerActivityOutcome(
        outcome_id="outcome-lesson",
        organization_id="org-1",
        attempt_id=lesson_attempt.attempt_id,
        lifecycle_result="completed",
        assessment_result="not_applicable",
        passed=None,
        competency_evidence_refs_json=[],
        source_refs_json=[],
        lineage_json={},
        critical_flags_json=[],
        degradations_json=[],
        version=1,
        produced_at=now,
    )
    quiz_attempt = NewcomerActivityAttempt(
        attempt_id="attempt-quiz",
        organization_id="org-1",
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="quiz-1",
        activity_type="quiz",
        attempt_no=1,
        status="completed",
        version=2,
        activity_snapshot_json={"activity_id": "quiz-1", "type": "quiz"},
        idempotency_key_hash="8" * 64,
        command_fingerprint="9" * 64,
        outcome_id="outcome-quiz",
        score=60,
        max_score=100,
        passed=False,
        evidence_status="recorded",
        reconcile_status="reconciled",
        started_at=now,
        completed_at=now,
    )
    quiz_outcome = NewcomerActivityOutcome(
        outcome_id="outcome-quiz",
        organization_id="org-1",
        attempt_id=quiz_attempt.attempt_id,
        lifecycle_result="completed",
        assessment_result="not_passed",
        score=60,
        max_score=100,
        passed=False,
        competency_evidence_refs_json=[],
        source_refs_json=[],
        lineage_json={},
        critical_flags_json=[],
        degradations_json=[],
        next_action_json={"type": "review_learning", "activity_id": "lesson-1"},
        version=1,
        produced_at=now,
    )
    test_db.add_all(
        [lesson_attempt, lesson_outcome, quiz_attempt, quiz_outcome]
    )
    await test_db.flush()

    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)

    assert journey.current_activity is not None
    assert journey.current_activity.activity_id == "quiz-1"
    assert journey.current_activity.status == "needs_remediation"
    assert journey.primary_action is not None
    assert journey.primary_action.command_type == "start_new_attempt"
    assert journey.recent_outcomes[0].activity_id == "quiz-1"
    assert journey.recent_outcomes[0].passed is False
    assert journey.recent_outcomes[0].score == 60


@pytest.mark.asyncio
async def test_journey_requires_read_capability(test_db) -> None:
    with pytest.raises(NewcomerTrainingError) as denied:
        await JourneyQueryService(test_db).get_my_journey(
            actor=CommandActor(
                organization_id="org-1",
                actor_id="learner-1",
                capabilities=frozenset(),
            )
        )

    assert denied.value.code == "[NEWCOMER_PERMISSION_DENIED]"


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_object", ["revision", "path"])
async def test_journey_blocks_unavailable_frozen_configuration(
    test_db,
    broken_object: str,
) -> None:
    actor, _ = await _seed_enrollment(test_db)
    if broken_object == "revision":
        revision = await test_db.get(NewcomerPathRevision, "revision-1")
        assert revision is not None
        revision.status = "working"
    else:
        path = await test_db.get(NewcomerPath, "path-1")
        assert path is not None
        path.organization_id = "org-2"
    await test_db.flush()

    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)

    assert journey.status == "blocked"
    assert journey.status_label == "训练配置待处理"


def _activity_payload(
    *,
    activity_id: str,
    required: bool = True,
    prerequisites: list[str] | None = None,
) -> dict[str, object]:
    return {
        "activity_id": activity_id,
        "type": "lesson",
        "title": activity_id,
        "objective": "掌握知识",
        "why_it_matters": "支持销售",
        "steps": ["学习"],
        "success_criteria": ["完成"],
        "estimated_minutes": 10,
        "required": required,
        "prerequisite_activity_ids": prerequisites or [],
        "ai_dependency": "none",
        "retry_policy": {"max_attempts": 0, "retry_interval_seconds": 0},
        "config": {
            "learning_unit_revision_id": "unit-revision-1",
            "required_checkpoint_ids": [],
        },
    }


def _projection_draft(
    *,
    stages: list[dict[str, object]],
) -> PathRevisionDraft:
    return PathRevisionDraft.model_validate(
        {
            "title": "新人训练",
            "revision_label": "v1",
            "stages": stages,
        }
    )


def _attempt(status: str, *, attempt_id: str = "attempt-1") -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=attempt_id,
        status=status,
        version=1,
    )


def _outcome(
    *,
    passed: bool | None = None,
    lifecycle_result: str = "completed",
    outcome_id: str = "outcome-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        outcome_id=outcome_id,
        passed=passed,
        lifecycle_result=lifecycle_result,
    )


def test_projection_covers_optional_locked_awaiting_and_blocked_states() -> None:
    draft = _projection_draft(
        stages=[
            {
                "stage_id": "stage-1",
                "sequence": 1,
                "title": "阶段一",
                "objective": "目标一",
                "completion_rule": "all_activities",
                "activities": [_activity_payload(activity_id="optional", required=False)],
            },
            {
                "stage_id": "stage-2",
                "sequence": 2,
                "title": "阶段二",
                "objective": "目标二",
                "activities": [_activity_payload(activity_id="review")],
            },
        ]
    )
    waiting_attempt = _attempt("submitted", attempt_id="attempt-review")

    state = JourneyQueryService.project_state(
        draft=draft,
        latest_attempt={"review": waiting_attempt},
        outcome_by_attempt={},
    )

    assert state.stage_views[1].status == "locked"
    assert state.status == "active"

    optional_attempt = _attempt("completed", attempt_id="attempt-optional")
    blocked = JourneyQueryService.project_state(
        draft=_projection_draft(
            stages=[
                {
                    "stage_id": "stage-optional",
                    "sequence": 1,
                    "title": "可选阶段",
                    "objective": "完成可选活动",
                    "activities": [
                        _activity_payload(activity_id="optional", required=False)
                    ],
                }
            ]
        ),
        latest_attempt={"optional": optional_attempt},
        outcome_by_attempt={"attempt-optional": _outcome()},
    )
    assert blocked.status == "blocked"

    single = _projection_draft(
        stages=[
            {
                "stage_id": "stage-review",
                "sequence": 1,
                "title": "复核",
                "objective": "等待结果",
                "activities": [_activity_payload(activity_id="review")],
            }
        ]
    )
    waiting = JourneyQueryService.project_state(
        draft=single,
        latest_attempt={"review": waiting_attempt},
        outcome_by_attempt={},
    )
    assert waiting.status == "awaiting_review"


@pytest.mark.parametrize(
    ("attempt_status", "outcome", "expected_status"),
    [
        ("invalidated", None, "invalidated"),
        ("submitted", None, "awaiting_review"),
        ("started", None, "in_progress"),
        ("failed", None, "retryable"),
        ("completed", _outcome(), "completed"),
        (
            "completed",
            _outcome(lifecycle_result="failed"),
            "retryable",
        ),
    ],
)
def test_activity_view_projects_every_terminal_and_recovery_state(
    attempt_status: str,
    outcome: SimpleNamespace | None,
    expected_status: str,
) -> None:
    activity = SimpleNamespace(
        activity_id="lesson-1",
        type="lesson",
        title="学习",
        objective="目标",
        estimated_minutes=10,
        required=True,
    )

    view = JourneyQueryService._activity_view(
        activity=activity,
        attempt=_attempt(attempt_status),
        outcome=outcome,
        blocked_titles=[],
        stage_unavailable=False,
    )

    assert view.status == expected_status


def test_completion_and_primary_action_negative_branches_are_explicit() -> None:
    assert JourneyQueryService._is_completed(_attempt("started"), None) is False
    assert (
        JourneyQueryService._primary_action(
            JourneyActivityView(
                activity_id="lesson-1",
                type="lesson",
                title="学习",
                objective="目标",
                status="locked",
                status_label="尚未解锁",
                estimated_minutes=10,
                required=True,
            )
        )
        is None
    )
