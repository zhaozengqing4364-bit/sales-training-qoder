from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from competency_evidence.application import CompetencyEvidenceService
from competency_evidence.contracts import CompetencyEvidenceProjection
from competency_evidence.identifiers import (
    STANDARD_COMPETENCIES,
    STANDARD_COMPETENCY_KEYS,
)
from competency_evidence.models import CompetencyEvidenceRecord
from foundation_readiness_composition import FoundationReadinessProjection
from learning.ports import ActivityOutcomePayload
from newcomer_foundation_composition import SQLAlchemyActivityOutcomeWriter
from newcomer_training.activity import (
    ActivityAttemptService,
    ActivityAttemptSummary,
    ActivityOutcomeCommand,
    ActivityOutcomeSummary,
)
from newcomer_training.application import CommandActor
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from readiness.application import ReadinessService
from readiness.contracts import (
    AISummaryDraft,
    AISummaryFact,
    AppealInput,
    AppealResolutionInput,
    CalibrationSessionInput,
    ExceptionDecisionPreviewInput,
    ReadinessActivityInput,
    ReadinessActor,
    ReadinessProjectionInput,
    RetrainingAssignmentInput,
    ReviewDecisionInput,
)
from readiness.errors import ReadinessError
from readiness.models import (
    ReadinessAISummary,
    ReadinessCommandAudit,
    ReadinessDossier,
    ReadinessExceptionPreview,
    ReadinessRetrainingAssignment,
    ReadinessReviewDecision,
)
from readiness.policy import evaluate_readiness


def _path_snapshot() -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人销售基础训练",
        "revision_label": "首发版",
        "stages": [
            {
                "stage_id": "foundation",
                "sequence": 1,
                "title": "基础训练",
                "objective": "完成首发基础能力训练",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-foundation",
                        "type": "lesson",
                        "title": "销售基础学习",
                        "objective": "掌握七项销售基础能力",
                        "why_it_matters": "为后续真实销售工作建立共同基础",
                        "steps": ["阅读", "完成检查点"],
                        "success_criteria": ["完成全部检查点"],
                        "competency_keys": list(STANDARD_COMPETENCY_KEYS),
                        "estimated_minutes": 20,
                        "required": True,
                        "prerequisite_activity_ids": [],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 1,
                            "retry_interval_seconds": 0,
                        },
                        "config": {
                            "learning_unit_revision_id": "unit-r1",
                            "required_checkpoint_ids": ["checkpoint-1"],
                        },
                    }
                ],
            }
        ],
    }


async def _seed(test_db: AsyncSession) -> tuple[CommandActor, ReadinessActor]:
    now = datetime.now(UTC)
    learner = User(
        user_id="learner-readiness",
        wechat_user_id="learner-readiness",
        name="新人小周",
        role="user",
    )
    path = NewcomerPath(
        path_id="path-readiness",
        organization_id="org-readiness",
        stable_key="foundation",
        title="新人销售基础训练",
        status="active",
        published_revision_id="path-r1",
        version=1,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id="path-r1",
        path_id=path.path_id,
        organization_id=path.organization_id,
        revision_no=1,
        revision_label="首发版",
        status="published",
        snapshot_json=_path_snapshot(),
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
        cohort_id="cohort-readiness",
        organization_id=path.organization_id,
        stable_key="launch",
        name="首发新人班",
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="2" * 64,
        creation_fingerprint="3" * 64,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    enrollment = NewcomerEnrollment(
        enrollment_id="enrollment-readiness",
        organization_id=path.organization_id,
        learner_id=learner.user_id,
        cohort_id=cohort.cohort_id,
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        assigned_by="admin",
        assigned_at=now,
        updated_at=now,
    )
    test_db.add_all([learner, path, revision, cohort, enrollment])
    await test_db.flush()
    learner_actor = CommandActor(
        organization_id=path.organization_id,
        actor_id=learner.user_id,
        capabilities=frozenset({"newcomer.activity.execute"}),
        trace_id="trace-learner",
    )
    reviewer = ReadinessActor(
        organization_id=path.organization_id,
        actor_id="reviewer-1",
        capabilities=frozenset(
            {
                "readiness.queue.read",
                "readiness.dossier.read",
                "readiness.review",
                "readiness.retraining.assign",
                "readiness.appeal.resolve",
                "readiness.calibration",
                "readiness.rebuild",
                "readiness.export",
            }
        ),
        unrestricted_scope=True,
        trace_id="trace-reviewer",
    )
    return learner_actor, reviewer


async def _record_outcome(
    test_db: AsyncSession,
    *,
    learner: CommandActor,
    start_key: str,
    outcome_key: str,
    score: float = 90,
    allow_relearn: bool = False,
    supersedes_outcome_id: str | None = None,
) -> tuple[ActivityAttemptSummary, ActivityOutcomeSummary]:
    attempts = ActivityAttemptService(test_db)
    attempt = await attempts.start_attempt(
        actor=learner,
        activity_id="lesson-foundation",
        expected_enrollment_version=1,
        idempotency_key=start_key,
        allow_relearn=allow_relearn,
    )
    outcome = await attempts.record_outcome(
        command=ActivityOutcomeCommand(
            organization_id=learner.organization_id,
            attempt_id=attempt.attempt_id,
            lifecycle_result="completed",
            assessment_result="passed" if score >= 60 else "not_passed",
            result_type="lesson_progress",
            result_id=f"detail-{outcome_key}",
            score=score,
            max_score=100,
            passed=score >= 60,
            lineage={"competency_keys": list(STANDARD_COMPETENCY_KEYS)},
            next_action=None,
            supersedes_outcome_id=supersedes_outcome_id,
        ),
        idempotency_key=outcome_key,
        actor_id=learner.actor_id,
        trace_id=learner.trace_id,
    )
    return attempt, outcome


@pytest.mark.asyncio
async def test_standard_catalog_and_outcome_evidence_are_stable_and_idempotent(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-1",
        outcome_key="outcome-1",
    )
    projector = FoundationReadinessProjection(test_db)
    first = await projector.project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
        trace_id=learner.trace_id,
    )
    replay = await projector.project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
        trace_id=learner.trace_id,
    )

    evidence = list((await test_db.scalars(select(CompetencyEvidenceRecord))).all())
    assert [item.title for item in STANDARD_COMPETENCIES] == [
        "产品知识",
        "客户理解",
        "需求发现",
        "价值表达",
        "异议处理",
        "流程与合规",
        "沟通结构",
    ]
    assert len(evidence) == 7
    assert len({item.competency_revision_id for item in evidence}) == 7
    assert first["summary"]["eligibility"]["eligible"] is True
    assert replay["snapshot_id"] == first["snapshot_id"]
    queue = await ReadinessService(test_db).list_queue(
        actor=reviewer,
        cohort_id="cohort-readiness",
        waiting_hours_gte=0,
    )
    assert queue["items"][0]["primary_action"]["href"] == (
        f"/admin/newcomer-training/reviews/{first['dossier_id']}"
    )
    excluded = await ReadinessService(test_db).list_queue(
        actor=reviewer,
        cohort_id="another-cohort",
    )
    assert excluded["total"] == 0
    rebuilt = await projector.rebuild_enrollment(
        organization_id=learner.organization_id,
        enrollment_id="enrollment-readiness",
        actor_id=reviewer.actor_id,
        force_refresh=True,
    )
    assert rebuilt["competencies"] == first["competencies"]
    assert rebuilt["evidence"] == first["evidence"]
    assert rebuilt["summary"]["eligibility"] == first["summary"]["eligibility"]


@pytest.mark.asyncio
async def test_production_outcome_writer_projects_evidence_and_dossier_in_one_unit(
    test_db: AsyncSession,
) -> None:
    learner, _ = await _seed(test_db)
    attempt = await ActivityAttemptService(test_db).start_attempt(
        actor=learner,
        activity_id="lesson-foundation",
        expected_enrollment_version=1,
        idempotency_key="start-writer",
    )
    payload = ActivityOutcomePayload(
        organization_id=learner.organization_id,
        actor_id=learner.actor_id,
        attempt_id=attempt.attempt_id,
        lifecycle_result="completed",
        assessment_result="passed",
        result_type="lesson_progress",
        result_id="lesson-detail-writer",
        score=90,
        max_score=100,
        passed=True,
        lineage={"competency_keys": list(STANDARD_COMPETENCY_KEYS)},
        idempotency_key="writer-outcome",
        trace_id=learner.trace_id,
    )
    writer = SQLAlchemyActivityOutcomeWriter(test_db)
    outcome_id = await writer.record(payload)
    replay_id = await writer.record(payload)

    evidence = list((await test_db.scalars(select(CompetencyEvidenceRecord))).all())
    dossier = await test_db.scalar(select(ReadinessDossier))
    assert replay_id == outcome_id
    assert len(evidence) == 7
    assert dossier is not None
    assert dossier.current_snapshot_id is not None


@pytest.mark.asyncio
async def test_evidence_invalidation_is_append_only_idempotent_and_rebuildable(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-invalidate",
        outcome_key="outcome-invalidate",
    )
    projector = FoundationReadinessProjection(test_db)
    dossier = await projector.project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    product_evidence = next(
        item
        for item in dossier["evidence"]
        if item["competency_key"] == "product_knowledge"
    )
    service = CompetencyEvidenceService(test_db)
    invalidated = await service.invalidate(
        organization_id=learner.organization_id,
        evidence_id=product_evidence["evidence_id"],
        actor_id=reviewer.actor_id,
        reason="来源内容修订被确认无效。",
        idempotency_key="invalidate-evidence",
        trace_id=reviewer.trace_id,
    )
    replay = await service.invalidate(
        organization_id=learner.organization_id,
        evidence_id=product_evidence["evidence_id"],
        actor_id=reviewer.actor_id,
        reason="来源内容修订被确认无效。",
        idempotency_key="invalidate-evidence",
        trace_id=reviewer.trace_id,
    )
    rebuilt = await projector.rebuild_enrollment(
        organization_id=learner.organization_id,
        enrollment_id="enrollment-readiness",
        actor_id=reviewer.actor_id,
        force_refresh=True,
    )

    assert invalidated.validity == "invalidated"
    assert replay.evidence_id == invalidated.evidence_id
    assert rebuilt["summary"]["eligibility"]["eligible"] is False
    assert "product_knowledge" in rebuilt["summary"]["eligibility"][
        "competency_gaps"
    ]


@pytest.mark.asyncio
async def test_regrade_supersedes_history_and_marks_frozen_snapshot_stale(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    attempt, first_outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-1",
        outcome_key="outcome-1",
    )
    projector = FoundationReadinessProjection(test_db)
    dossier = await projector.project_outcome(
        outcome_id=first_outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    service = ReadinessService(test_db)
    approval = await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=ReviewDecisionInput(
            decision_type="approve_foundation_ready",
            expected_dossier_version=dossier["dossier_version"],
            snapshot_id=dossier["snapshot_id"],
            reason="七项能力证据完整，确认基础训练达标。",
            competency_keys=STANDARD_COMPETENCY_KEYS,
            evidence_ids=tuple(item["evidence_id"] for item in dossier["evidence"]),
        ),
        idempotency_key="approve-1",
    )
    approved_dossier = await service.get_by_id(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
    )
    learner_readiness = ReadinessActor(
        organization_id=learner.organization_id,
        actor_id=learner.actor_id,
        capabilities=frozenset({"readiness.self.read", "readiness.appeal.submit"}),
        learner_ids=frozenset({learner.actor_id}),
    )
    learner_projection = await service.get_by_enrollment(
        actor=learner_readiness,
        enrollment_id="enrollment-readiness",
        learner_safe=True,
    )
    assert "notes" not in learner_projection["human_decision"]
    assert "lineage" not in learner_projection["evidence"][0]
    assert "source_refs" not in learner_projection["evidence"][0]
    appeal = await service.submit_appeal(
        actor=learner_readiness,
        enrollment_id="enrollment-readiness",
        command=AppealInput(
            target_type="decision",
            target_id=approval["decision_id"],
            dossier_version=approved_dossier["dossier_version"],
            reason_category="score_error",
            statement="评分事实需要重评。",
        ),
        idempotency_key="appeal-regrade",
    )
    pending_regrade = await service.resolve_appeal(
        actor=reviewer,
        appeal_id=appeal["appeal_id"],
        command=AppealResolutionInput(
            expected_version=appeal["version"],
            action="request_regrade",
            resolution="同意重新评分。",
        ),
    )
    current_attempt = await test_db.get(NewcomerActivityAttempt, attempt.attempt_id)
    assert current_attempt is not None
    regrade = await ActivityAttemptService(test_db).record_outcome(
        command=ActivityOutcomeCommand(
            organization_id=learner.organization_id,
            attempt_id=attempt.attempt_id,
            lifecycle_result="completed",
            assessment_result="passed",
            result_type="lesson_progress",
            result_id="detail-regrade",
            score=95,
            max_score=100,
            passed=True,
            lineage={"competency_keys": list(STANDARD_COMPETENCY_KEYS)},
            next_action=None,
            supersedes_outcome_id=first_outcome.outcome_id,
        ),
        idempotency_key="outcome-regrade",
        actor_id="reviewer-1",
        trace_id="trace-regrade",
    )
    stale = await projector.project_outcome(
        outcome_id=regrade.outcome_id,
        actor_id="reviewer-1",
        trace_id="trace-regrade",
    )
    history = list(
        (
            await test_db.scalars(
                select(CompetencyEvidenceRecord).where(
                    CompetencyEvidenceRecord.competency_key == "product_knowledge"
                )
            )
        ).all()
    )
    assert stale["snapshot_stale"] is True
    assert len(history) == 2
    assert history[1].supersedes_evidence_id == history[0].evidence_id

    reopened_appeal = await service.resolve_appeal(
        actor=reviewer,
        appeal_id=appeal["appeal_id"],
        command=AppealResolutionInput(
            expected_version=pending_regrade["version"],
            action="reopen_review",
            resolution="重评结果已到达，重新复核当前快照。",
        ),
    )
    assert reopened_appeal["status"] == "resolved"

    rebuilt = await projector.rebuild_enrollment(
        organization_id=learner.organization_id,
        enrollment_id="enrollment-readiness",
        actor_id=reviewer.actor_id,
        force_refresh=True,
    )
    assert rebuilt["snapshot_stale"] is False
    assert rebuilt["summary"]["eligibility"]["eligible"] is True


@pytest.mark.asyncio
async def test_decision_replay_is_idempotent_and_stale_versions_are_rejected(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-1",
        outcome_key="outcome-1",
    )
    dossier = await FoundationReadinessProjection(test_db).project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    command = ReviewDecisionInput(
        decision_type="approve_foundation_ready",
        expected_dossier_version=dossier["dossier_version"],
        snapshot_id=dossier["snapshot_id"],
        reason="七项能力证据完整，人工确认达标。",
        competency_keys=STANDARD_COMPETENCY_KEYS,
        evidence_ids=tuple(item["evidence_id"] for item in dossier["evidence"]),
    )
    service = ReadinessService(test_db)
    first = await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=command,
        idempotency_key="decision-replay",
    )
    replay = await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=command,
        idempotency_key="decision-replay",
    )
    competing_reviewer = reviewer.model_copy(update={"actor_id": "reviewer-2"})
    with pytest.raises(ReadinessError) as conflict:
        await service.record_decision(
            actor=competing_reviewer,
            dossier_id=dossier["dossier_id"],
            command=command,
            idempotency_key="decision-competing",
        )

    decisions = list((await test_db.scalars(select(ReadinessReviewDecision))).all())
    denied_conflict = await test_db.scalar(
        select(ReadinessCommandAudit)
        .where(
            ReadinessCommandAudit.command == "record_review_decision",
            ReadinessCommandAudit.result == "denied",
        )
        .order_by(ReadinessCommandAudit.occurred_at.desc())
        .limit(1)
    )
    assert replay["decision_id"] == first["decision_id"]
    assert conflict.value.code == "[DOSSIER_VERSION_CONFLICT]"
    assert len(decisions) == 1
    assert denied_conflict is not None
    assert denied_conflict.details_json["actual_version"] == dossier["dossier_version"] + 1


@pytest.mark.asyncio
async def test_exception_approval_requires_same_durable_preview_and_confirmation(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-exception",
        outcome_key="outcome-exception",
        score=40,
    )
    dossier = await FoundationReadinessProjection(test_db).project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    service = ReadinessService(test_db)
    preview_input = ExceptionDecisionPreviewInput(
        expected_dossier_version=dossier["dossier_version"],
        snapshot_id=dossier["snapshot_id"],
        reason="基于线下已核验材料批准例外，相关缺口将在入岗后继续补齐。",
        notes="线下核验记录由培训负责人保管。",
        competency_keys=STANDARD_COMPETENCY_KEYS,
        evidence_ids=tuple(item["evidence_id"] for item in dossier["evidence"]),
    )
    preview = await service.preview_exception_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=preview_input,
        idempotency_key="exception-preview",
    )
    replay = await service.preview_exception_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=preview_input,
        idempotency_key="exception-preview",
    )
    assert replay["preview_token"] == preview["preview_token"]
    assert preview["impact"]["overridden_competency_gaps"]

    changed = ReviewDecisionInput(
        decision_type="exception_approved",
        expected_dossier_version=dossier["dossier_version"],
        snapshot_id=dossier["snapshot_id"],
        reason="提交时改变了例外理由。",
        notes=preview_input.notes,
        competency_keys=STANDARD_COMPETENCY_KEYS,
        evidence_ids=preview_input.evidence_ids,
        exception_confirmed=True,
        preview_token=preview["preview_token"],
        impact_hash=preview["impact_hash"],
    )
    with pytest.raises(ReadinessError) as changed_error:
        await service.record_decision(
            actor=reviewer,
            dossier_id=dossier["dossier_id"],
            command=changed,
            idempotency_key="exception-changed",
        )
    assert changed_error.value.code == "[READINESS_EXCEPTION_IMPACT_CHANGED]"

    decision = await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=ReviewDecisionInput(
            decision_type="exception_approved",
            expected_dossier_version=dossier["dossier_version"],
            snapshot_id=dossier["snapshot_id"],
            reason=preview_input.reason,
            notes=preview_input.notes,
            competency_keys=STANDARD_COMPETENCY_KEYS,
            evidence_ids=preview_input.evidence_ids,
            exception_confirmed=True,
            preview_token=preview["preview_token"],
            impact_hash=preview["impact_hash"],
        ),
        idempotency_key="exception-approved",
    )
    preview_row = await test_db.get(
        ReadinessExceptionPreview,
        preview["preview_id"],
    )
    assert decision["decision_type"] == "exception_approved"
    assert preview_row is not None
    assert preview_row.status == "consumed"


@pytest.mark.asyncio
async def test_human_review_retraining_and_appeal_close_the_loop(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-1",
        outcome_key="outcome-1",
    )
    projector = FoundationReadinessProjection(test_db)
    dossier = await projector.project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    service = ReadinessService(test_db)
    non_human = reviewer.model_copy(update={"actor_id": "system", "is_human": False})
    with pytest.raises(ReadinessError) as denied:
        await service.record_decision(
            actor=non_human,
            dossier_id=dossier["dossier_id"],
            command=ReviewDecisionInput(
                decision_type="approve_foundation_ready",
                expected_dossier_version=dossier["dossier_version"],
                snapshot_id=dossier["snapshot_id"],
                reason="自动批准",
            ),
            idempotency_key="system-approval",
        )
    assert denied.value.code == "[READINESS_HUMAN_REVIEW_REQUIRED]"
    denied_audits = list(
        (
            await test_db.scalars(
                select(ReadinessCommandAudit).where(
                    ReadinessCommandAudit.command == "record_review_decision"
                )
            )
        ).all()
    )
    assert denied_audits and denied_audits[-1].result == "denied"

    with pytest.raises(ReadinessError) as missing_references:
        await service.record_decision(
            actor=reviewer,
            dossier_id=dossier["dossier_id"],
            command=ReviewDecisionInput(
                decision_type="approve_foundation_ready",
                expected_dossier_version=dossier["dossier_version"],
                snapshot_id=dossier["snapshot_id"],
                reason="缺少冻结证据引用的决定不得保存。",
            ),
            idempotency_key="approval-without-references",
        )
    assert missing_references.value.code == "[DOSSIER_DECISION_REFERENCES_REQUIRED]"

    await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=ReviewDecisionInput(
            decision_type="request_retraining",
            expected_dossier_version=dossier["dossier_version"],
            snapshot_id=dossier["snapshot_id"],
            reason="请再完成一次价值表达训练。",
            competency_keys=("value_expression",),
        ),
        idempotency_key="request-retraining",
    )
    persisted = await test_db.get(ReadinessDossier, dossier["dossier_id"])
    assert persisted is not None
    assignment = await service.assign_retraining(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=RetrainingAssignmentInput(
            expected_dossier_version=persisted.version,
            snapshot_id=dossier["snapshot_id"],
            activity_source="existing_published",
            activity_id="lesson-foundation",
            activity_title="销售基础学习",
            target_competency_keys=("value_expression",),
            reason="补充一次新的价值表达结果。",
            completion_rule={"rule": "new_terminal_outcome_after_assignment"},
        ),
        idempotency_key="assign-retraining",
    )
    _, retry_outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-relearn",
        outcome_key="outcome-relearn",
        score=96,
        allow_relearn=True,
    )
    reopened = await projector.project_outcome(
        outcome_id=retry_outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    assignment_row = await test_db.get(
        ReadinessRetrainingAssignment,
        assignment["assignment_id"],
    )
    assert assignment_row is not None
    assert assignment_row.status == "completed"
    assert reopened["snapshot_stale"] is True
    completion_audit = await test_db.scalar(
        select(ReadinessCommandAudit).where(
            ReadinessCommandAudit.command == "complete_retraining",
            ReadinessCommandAudit.object_id == assignment["assignment_id"],
        )
    )
    assert completion_audit is not None

    refreshed = await projector.rebuild_enrollment(
        organization_id=learner.organization_id,
        enrollment_id="enrollment-readiness",
        actor_id=reviewer.actor_id,
        force_refresh=True,
    )
    learner_readiness = ReadinessActor(
        organization_id=learner.organization_id,
        actor_id=learner.actor_id,
        capabilities=frozenset({"readiness.self.read", "readiness.appeal.submit"}),
        learner_ids=frozenset({learner.actor_id}),
    )
    appeal = await service.submit_appeal(
        actor=learner_readiness,
        enrollment_id="enrollment-readiness",
        command=AppealInput(
            target_type="evidence",
            target_id=refreshed["evidence"][-1]["evidence_id"],
            dossier_version=refreshed["dossier_version"],
            reason_category="fact_error",
            statement="训练事实需要再次核对。",
        ),
        idempotency_key="appeal-1",
    )
    assert appeal["status"] == "submitted"


@pytest.mark.asyncio
async def test_ai_summary_failure_is_non_blocking_and_denials_are_audited(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-1",
        outcome_key="outcome-1",
    )
    dossier = await FoundationReadinessProjection(test_db).project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    service = ReadinessService(test_db)
    failed = await service.record_ai_summary(
        actor_id=reviewer.actor_id,
        dossier_id=dossier["dossier_id"],
        snapshot_id=dossier["snapshot_id"],
        draft=None,
        error_code="provider_timeout",
    )
    rejected = await service.record_ai_summary(
        actor_id=reviewer.actor_id,
        dossier_id=dossier["dossier_id"],
        snapshot_id=dossier["snapshot_id"],
        draft=AISummaryDraft(
            facts=(AISummaryFact(text="缺少引用", evidence_ids=("unknown",)),),
            calculations=(),
            inferences=(),
            recommendations=(),
            limitations=(),
        ),
    )
    ready = await service.record_ai_summary(
        actor_id=reviewer.actor_id,
        dossier_id=dossier["dossier_id"],
        snapshot_id=dossier["snapshot_id"],
        draft=AISummaryDraft(
            facts=(
                AISummaryFact(
                    text="七项能力均有当前有效证据。",
                    evidence_ids=(dossier["evidence"][0]["evidence_id"],),
                ),
            ),
            calculations=(),
            inferences=(),
            recommendations=(),
            limitations=(),
        ),
    )
    still_eligible = await service.get_by_id(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
    )
    assert failed["status"] == "failed"
    assert rejected["status"] == "rejected"
    assert ready["status"] == "ready"
    assert still_eligible["summary"]["eligibility"]["eligible"] is True

    learner_readiness = ReadinessActor(
        organization_id=learner.organization_id,
        actor_id=learner.actor_id,
        capabilities=frozenset({"readiness.self.read", "readiness.appeal.submit"}),
        learner_ids=frozenset({learner.actor_id}),
    )
    learner_projection = await service.get_by_enrollment(
        actor=learner_readiness,
        enrollment_id="enrollment-readiness",
        learner_safe=True,
    )
    assert "draft" not in learner_projection["ai_assessment"]
    assert "evidence_ids" not in learner_projection["ai_assessment"]

    cross_org = reviewer.model_copy(update={"organization_id": "other-org"})
    with pytest.raises(ReadinessError):
        await service.record_decision(
            actor=cross_org,
            dossier_id=dossier["dossier_id"],
            command=ReviewDecisionInput(
                decision_type="request_more_evidence",
                expected_dossier_version=dossier["dossier_version"],
                snapshot_id=dossier["snapshot_id"],
                reason="越权请求不得保存。",
            ),
            idempotency_key="cross-org-decision",
        )
    with pytest.raises(ReadinessError):
        await service.export_dossier(
            actor=cross_org,
            dossier_id=dossier["dossier_id"],
        )
    audits = list(
        (
            await test_db.scalars(
                select(ReadinessCommandAudit).where(
                    ReadinessCommandAudit.result == "denied"
                )
            )
        ).all()
    )
    assert {item.command for item in audits} >= {
        "record_review_decision",
        "export_dossier",
    }


@pytest.mark.asyncio
async def test_calibration_persists_distribution_and_actions_without_overwriting_history(
    test_db: AsyncSession,
) -> None:
    learner, reviewer = await _seed(test_db)
    _, outcome = await _record_outcome(
        test_db,
        learner=learner,
        start_key="start-calibration",
        outcome_key="outcome-calibration",
    )
    dossier = await FoundationReadinessProjection(test_db).project_outcome(
        outcome_id=outcome.outcome_id,
        actor_id=learner.actor_id,
    )
    service = ReadinessService(test_db)
    evidence_id = dossier["evidence"][0]["evidence_id"]
    summary = await service.record_ai_summary(
        actor_id=reviewer.actor_id,
        dossier_id=dossier["dossier_id"],
        snapshot_id=dossier["snapshot_id"],
        draft=AISummaryDraft(
            facts=(
                AISummaryFact(
                    text="当前证据可用于复核校准。",
                    evidence_ids=(evidence_id,),
                ),
            ),
            calculations=(),
            inferences=(),
            recommendations=(),
            limitations=(),
        ),
    )
    decision = await service.record_decision(
        actor=reviewer,
        dossier_id=dossier["dossier_id"],
        command=ReviewDecisionInput(
            decision_type="request_more_evidence",
            expected_dossier_version=dossier["dossier_version"],
            snapshot_id=dossier["snapshot_id"],
            reason="将该样本纳入复核校准。",
            competency_keys=("product_knowledge",),
            evidence_ids=(evidence_id,),
        ),
        idempotency_key="calibration-decision",
    )
    calibration = await service.create_calibration_session(
        actor=reviewer,
        command=CalibrationSessionInput(
            competency_key="product_knowledge",
            sample_evidence_ids=(evidence_id,),
            action_items=("统一产品知识证据引用说明。",),
        ),
    )

    summary_row = await test_db.get(ReadinessAISummary, summary["summary_id"])
    decision_row = await test_db.get(
        ReadinessReviewDecision,
        decision["decision_id"],
    )
    assert calibration["decision_distribution"] == {"request_more_evidence": 1}
    assert calibration["action_items"] == ["统一产品知识证据引用说明。"]
    assert summary_row is not None and summary_row.status == "ready"
    assert decision_row is not None and decision_row.status == "recorded"


def test_policy_excludes_unscorable_evidence_and_never_averages_away_shortfall() -> None:
    now = datetime.now(UTC)

    def evidence(
        key: str,
        *,
        evidence_id: str,
        result: str = "passed",
        validity: str = "valid",
        score: float = 90,
        version: int = 1,
    ) -> CompetencyEvidenceProjection:
        return CompetencyEvidenceProjection(
            evidence_id=evidence_id,
            organization_id="org",
            learner_id="learner",
            enrollment_id="enrollment",
            competency_revision_id=f"revision-{key}",
            competency_key=key,
            competency_title=key,
            source_activity_id=f"activity-{key}",
            attempt_id=f"attempt-{evidence_id}",
            outcome_id=f"outcome-{evidence_id}",
            outcome_version=version,
            evidence_type="quiz",
            evidence_role="knowledge",
            observed_score=score,
            observed_max_score=100,
            observed_result=result,
            confidence=1,
            quality="verified" if validity == "valid" else "unscorable",
            validity=validity,
            source_refs=(),
            lineage={},
            critical_flags=(),
            degradations=(),
            supersedes_evidence_id=None,
            observed_at=now,
        )

    base = [
        evidence(key, evidence_id=f"valid-{key}")
        for key in STANDARD_COMPETENCY_KEYS
    ]
    base.append(
        evidence(
            "product_knowledge",
            evidence_id="unscorable-product",
            validity="pending_review",
            version=2,
        )
    )
    common = {
        "organization_id": "org",
        "learner_id": "learner",
        "learner_name": "新人",
        "enrollment_id": "enrollment",
        "cohort_id": "cohort",
        "path_revision_id": "path-r1",
        "path_title": "基础训练",
        "path_revision_label": "v1",
        "enrollment_status": "active",
        "activities": (
            ReadinessActivityInput(
                activity_id="required",
                activity_type="quiz",
                title="必修",
                required=True,
                status="completed",
            ),
        ),
        "generated_at": now,
    }
    quality_blocked = evaluate_readiness(
        ReadinessProjectionInput(**common, evidence=tuple(base))
    )
    product = next(
        item
        for item in quality_blocked.competencies
        if item.competency_key == "product_knowledge"
    )
    assert product.status == "quality_review"
    assert quality_blocked.eligibility.eligible is False

    shortfall = [item for item in base if item.evidence_id != "unscorable-product"]
    shortfall.append(
        evidence(
            "product_knowledge",
            evidence_id="latest-product-shortfall",
            result="not_passed",
            score=40,
            version=3,
        )
    )
    not_ready = evaluate_readiness(
        ReadinessProjectionInput(**common, evidence=tuple(shortfall))
    )
    product = next(
        item
        for item in not_ready.competencies
        if item.competency_key == "product_knowledge"
    )
    assert product.status == "gap"
    assert not_ready.eligibility.eligible is False
