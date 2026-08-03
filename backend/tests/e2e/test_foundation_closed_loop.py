from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from foundation_readiness_composition import FoundationReadinessProjection
from foundation_standard_pack import install_or_verify_standard_pack
from newcomer_training.activity import ActivityAttemptService, ActivityOutcomeCommand
from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.models import NewcomerPathRevision
from readiness.application import ReadinessService
from readiness.contracts import ReadinessActor, ReviewDecisionInput


@pytest.mark.asyncio
@pytest.mark.integration
async def test_new_learner_completes_five_activity_types_and_human_review(
    test_db: AsyncSession,
) -> None:
    organization_id = f"foundation-e2e-{uuid.uuid4().hex[:8]}"
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"foundation-admin-{uuid.uuid4().hex}",
        name="首发闭环管理员",
        email=f"foundation-admin-{uuid.uuid4().hex}@example.invalid",
        role="admin",
        is_active=True,
    )
    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"foundation-learner-{uuid.uuid4().hex}",
        name="首发闭环学员",
        email=f"foundation-learner-{uuid.uuid4().hex}@example.invalid",
        role="user",
        is_active=True,
    )
    test_db.add_all([admin, learner])
    await test_db.flush([admin, learner])

    pack = await install_or_verify_standard_pack(
        test_db,
        organization_id=organization_id,
        actor_id=admin.user_id,
    )
    admin_actor = CommandActor(
        organization_id=organization_id,
        actor_id=admin.user_id,
        capabilities=frozenset(
            {
                "newcomer.cohort.manage",
                "newcomer.enrollment.manage",
            }
        ),
        trace_id="foundation-e2e-admin",
    )
    enrollment_service = PathEnrollmentService(test_db)
    cohort = await enrollment_service.create_cohort(
        actor=admin_actor,
        stable_key="foundation-e2e-cohort",
        name="首发闭环班级",
        path_revision_id=pack.path_revision_id,
        idempotency_key="foundation-e2e-cohort-create",
    )
    enrollment = await enrollment_service.enroll(
        actor=admin_actor,
        cohort_id=cohort.cohort_id,
        learner_id=learner.user_id,
        idempotency_key="foundation-e2e-enroll",
    )

    revision = await test_db.get(NewcomerPathRevision, pack.path_revision_id)
    assert revision is not None
    draft = PathRevisionDraft.model_validate(revision.snapshot_json)
    activities = [
        activity
        for stage in draft.stages
        for activity in stage.activities
    ]
    activity_types = {str(activity.type) for activity in activities}
    assert activity_types == {
        "lesson",
        "quiz",
        "audio_assessment",
        "ai_coach",
        "assignment",
    }

    learner_actor = CommandActor(
        organization_id=organization_id,
        actor_id=learner.user_id,
        capabilities=frozenset({"newcomer.activity.execute"}),
        trace_id="foundation-e2e-learner",
    )
    attempts = ActivityAttemptService(test_db)
    projector = FoundationReadinessProjection(test_db)
    dossier: dict[str, object] | None = None
    for index, activity in enumerate(activities, start=1):
        attempt = await attempts.start_attempt(
            actor=learner_actor,
            activity_id=activity.activity_id,
            expected_enrollment_version=enrollment.version,
            idempotency_key=f"foundation-e2e-start-{index}",
        )
        outcome = await attempts.record_outcome(
            command=ActivityOutcomeCommand(
                organization_id=organization_id,
                attempt_id=attempt.attempt_id,
                lifecycle_result="completed",
                assessment_result="passed",
                result_type=f"{activity.type}_result",
                result_id=f"foundation-e2e-result-{index}",
                score=90,
                max_score=100,
                passed=True,
                source_refs=(
                    {
                        "ref_type": "path_revision",
                        "ref_id": pack.path_revision_id,
                    },
                ),
                lineage={
                    "competency_keys": list(activity.competency_keys),
                    "activity_type": str(activity.type),
                    "path_revision_id": pack.path_revision_id,
                },
                confidence=0.95,
                next_action=None,
            ),
            idempotency_key=f"foundation-e2e-outcome-{index}",
            actor_id=learner.user_id,
            trace_id=learner_actor.trace_id,
        )
        dossier = await projector.project_outcome(
            outcome_id=outcome.outcome_id,
            actor_id=learner.user_id,
            trace_id=learner_actor.trace_id,
        )

    assert dossier is not None
    assert dossier["status"] == "ready_for_review"
    summary = dossier["summary"]
    assert isinstance(summary, dict)
    eligibility = summary["eligibility"]
    assert isinstance(eligibility, dict)
    assert eligibility["eligible"] is True

    reviewer = ReadinessActor(
        organization_id=organization_id,
        actor_id=admin.user_id,
        capabilities=frozenset(
            {
                "readiness.queue.read",
                "readiness.dossier.read",
                "readiness.review",
            }
        ),
        unrestricted_scope=True,
        is_human=True,
        trace_id="foundation-e2e-reviewer",
    )
    evidence = dossier["evidence"]
    assert isinstance(evidence, list)
    readiness = ReadinessService(test_db)
    decision = await readiness.record_decision(
        actor=reviewer,
        dossier_id=str(dossier["dossier_id"]),
        command=ReviewDecisionInput(
            decision_type="approve_foundation_ready",
            expected_dossier_version=int(dossier["dossier_version"]),
            snapshot_id=str(dossier["snapshot_id"]),
            reason="五类首发活动均已完成，七项能力证据完整，人工确认达标。",
            competency_keys=pack.competency_keys,
            evidence_ids=tuple(str(item["evidence_id"]) for item in evidence),
        ),
        idempotency_key="foundation-e2e-human-approval",
    )

    assert decision["decision_type"] == "approve_foundation_ready"
    decided = await readiness.get_by_id(
        actor=reviewer,
        dossier_id=str(dossier["dossier_id"]),
    )
    assert decided["status"] == "decided"
    assert decided["human_decision"]["decision_type"] == (
        "approve_foundation_ready"
    )
