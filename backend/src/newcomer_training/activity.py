"""Generic ActivityAttempt and normalized ActivityOutcome application service."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerPathRevision,
)
from task_runtime.outbox import DomainEvent, SQLAlchemyOutboxWriter


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class ActivityAttemptSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    attempt_id: str
    organization_id: str
    enrollment_id: str
    path_revision_id: str
    activity_id: str
    activity_type: str
    attempt_no: int
    status: str
    version: int
    task_id: str | None
    outcome_id: str | None


class ActivityOutcomeCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    attempt_id: str = Field(min_length=1, max_length=160)
    lifecycle_result: Literal["completed", "failed", "invalidated", "cancelled"]
    assessment_result: Literal[
        "passed", "not_passed", "not_applicable", "needs_review"
    ] | None = None
    result_type: str = Field(min_length=1, max_length=120)
    result_id: str = Field(min_length=1, max_length=160)
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    competency_evidence_refs: tuple[dict[str, str], ...] = ()
    source_refs: tuple[dict[str, str], ...] = ()
    lineage: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_flags: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    next_action: dict[str, Any] | None
    supersedes_outcome_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_score_shape(self) -> ActivityOutcomeCommand:
        if self.score is not None and self.max_score is None:
            raise ValueError("max_score is required when score is present")
        if self.max_score is not None and self.max_score <= 0:
            raise ValueError("max_score must be positive")
        if self.passed is True and self.lifecycle_result != "completed":
            raise ValueError("only a completed result can pass")
        return self


class ActivityOutcomeSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    outcome_id: str
    attempt_id: str
    lifecycle_result: str
    assessment_result: str | None
    score: float | None
    max_score: float | None
    passed: bool | None
    version: int


class ActivityAttemptService:
    """Owns generic attempt allocation, snapshots, and normalized outcomes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._outbox = SQLAlchemyOutboxWriter(session)

    async def start_attempt(
        self,
        *,
        actor: CommandActor,
        activity_id: str,
        expected_enrollment_version: int,
        idempotency_key: str,
        allow_relearn: bool = False,
    ) -> ActivityAttemptSummary:
        if "newcomer.activity.execute" not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有执行训练活动的权限。", 403
            )
        enrollment = await self._session.scalar(
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == actor.organization_id)
            .where(NewcomerEnrollment.learner_id == actor.actor_id)
            .where(NewcomerEnrollment.status == "active")
            .with_for_update()
            .limit(1)
        )
        if enrollment is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_NOT_FOUND]",
                "尚未分配可执行的新人训练。",
                404,
            )
        fingerprint_payload = {
            "command": "start_attempt",
            "organization_id": actor.organization_id,
            "learner_id": actor.actor_id,
            "enrollment_id": enrollment.enrollment_id,
            "activity_id": activity_id,
            "expected_enrollment_version": expected_enrollment_version,
        }
        if allow_relearn:
            fingerprint_payload["allow_relearn"] = True
        fingerprint = _canonical_hash(fingerprint_payload)
        replay = await self._session.scalar(
            select(NewcomerActivityAttempt)
            .where(NewcomerActivityAttempt.organization_id == actor.organization_id)
            .where(
                NewcomerActivityAttempt.enrollment_id == enrollment.enrollment_id
            )
            .where(NewcomerActivityAttempt.activity_id == activity_id)
            .where(
                NewcomerActivityAttempt.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.command_fingerprint != fingerprint:
                self._idempotency_conflict()
            return ActivityAttemptSummary.model_validate(replay)
        if enrollment.version != expected_enrollment_version:
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                "训练分配已更新，请刷新后继续。",
                412,
                details={
                    "expected_version": expected_enrollment_version,
                    "actual_version": enrollment.version,
                },
            )
        revision = await self._session.get(
            NewcomerPathRevision, enrollment.path_revision_id
        )
        if (
            revision is None
            or revision.organization_id != actor.organization_id
            or revision.status not in {"published", "archived"}
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_UNAVAILABLE]",
                "当前训练版本不可用，请联系培训负责人。",
                409,
            )
        draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        activity = next(
            (
                item
                for stage in draft.stages
                for item in stage.activities
                if item.activity_id == activity_id
            ),
            None,
        )
        if activity is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_NOT_FOUND]",
                "训练活动不存在或不属于当前训练版本。",
                404,
            )
        await self.require_activity_unlocked(
            enrollment=enrollment,
            draft=draft,
            activity_id=activity.activity_id,
        )
        in_progress = await self._session.scalar(
            select(NewcomerActivityAttempt)
            .where(
                NewcomerActivityAttempt.enrollment_id == enrollment.enrollment_id
            )
            .where(NewcomerActivityAttempt.activity_id == activity_id)
            .where(
                NewcomerActivityAttempt.status.in_(
                    ("started", "in_progress", "submitted", "processing")
                )
            )
            .limit(1)
        )
        if in_progress is not None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_ATTEMPT_IN_PROGRESS]",
                "该训练活动已有进行中的尝试，请继续原尝试。",
                409,
                details={"attempt_id": in_progress.attempt_id},
            )
        latest = await self._session.scalar(
            select(NewcomerActivityAttempt)
            .where(
                NewcomerActivityAttempt.enrollment_id == enrollment.enrollment_id
            )
            .where(NewcomerActivityAttempt.activity_id == activity_id)
            .order_by(desc(NewcomerActivityAttempt.attempt_no))
            .limit(1)
        )
        latest_no = latest.attempt_no if latest is not None else 0
        max_attempts = activity.retry_policy.max_attempts
        if not allow_relearn and max_attempts > 0 and latest_no >= max_attempts:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_ATTEMPT_LIMIT_REACHED]",
                "该训练活动已达到最大尝试次数，请联系培训负责人。",
                409,
            )
        if (
            not allow_relearn
            and latest is not None
            and latest.status == "completed"
            and latest.passed is not False
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_ALREADY_COMPLETED]",
                "该训练活动已经完成，无需重复提交。",
                409,
                details={"attempt_id": latest.attempt_id},
            )
        retry_interval_seconds = activity.retry_policy.retry_interval_seconds
        if (
            not allow_relearn
            and latest is not None
            and retry_interval_seconds > 0
            and (
                latest.status in {"failed", "cancelled"}
                or (latest.status == "completed" and latest.passed is False)
            )
        ):
            ended_at = (
                latest.completed_at
                or latest.failed_at
                or latest.submitted_at
                or latest.started_at
            )
            if ended_at.tzinfo is None:
                ended_at = ended_at.replace(tzinfo=UTC)
            retry_available_at = ended_at.astimezone(UTC) + timedelta(
                seconds=retry_interval_seconds
            )
            now = _now()
            if retry_available_at > now:
                raise NewcomerTrainingError(
                    "[NEWCOMER_ACTIVITY_RETRY_NOT_READY]",
                    "尚未到可重试时间，请稍后再试。",
                    409,
                    details={
                        "retry_after_seconds": ceil(
                            (retry_available_at - now).total_seconds()
                        ),
                        "retry_available_at": retry_available_at.isoformat(),
                    },
                )
        snapshot = activity.model_dump(mode="json")
        snapshot["path_revision_id"] = revision.revision_id
        snapshot["path_revision_content_hash"] = revision.content_hash
        row = NewcomerActivityAttempt(
            attempt_id=_id(),
            organization_id=actor.organization_id,
            enrollment_id=enrollment.enrollment_id,
            path_revision_id=enrollment.path_revision_id,
            activity_id=activity.activity_id,
            activity_type=str(activity.type),
            attempt_no=latest_no + 1,
            status="started",
            version=1,
            activity_snapshot_json=snapshot,
            idempotency_key_hash=_secret_hash(idempotency_key),
            command_fingerprint=fingerprint,
            evidence_status="pending",
            reconcile_status="pending",
            started_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        await self._audit_start(
            actor=actor,
            attempt=row,
            idempotency_key=idempotency_key,
            expected_enrollment_version=expected_enrollment_version,
        )
        return ActivityAttemptSummary.model_validate(row)

    async def mark_processing(
        self,
        *,
        organization_id: str,
        attempt_id: str,
        task_id: str,
        expected_attempt_version: int,
    ) -> ActivityAttemptSummary:
        attempt = await self._load_attempt_for_update(
            organization_id=organization_id, attempt_id=attempt_id
        )
        if attempt.version != expected_attempt_version:
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                "训练尝试已更新，请刷新后继续。",
                412,
            )
        if attempt.status not in {"started", "in_progress", "submitted"}:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_STATE_CONFLICT]",
                "当前尝试状态不能进入后台处理。",
                409,
            )
        attempt.status = "processing"
        attempt.task_id = task_id
        attempt.submitted_at = attempt.submitted_at or _now()
        attempt.version += 1
        await self._session.flush([attempt])
        return ActivityAttemptSummary.model_validate(attempt)

    async def record_outcome(
        self,
        *,
        command: ActivityOutcomeCommand,
        idempotency_key: str,
        actor_id: str,
        trace_id: str | None,
    ) -> ActivityOutcomeSummary:
        attempt = await self._load_attempt_for_update(
            organization_id=command.organization_id,
            attempt_id=command.attempt_id,
        )
        fingerprint = _canonical_hash(command.model_dump(mode="json"))
        existing = await self._session.scalar(
            select(NewcomerActivityOutcome)
            .where(NewcomerActivityOutcome.attempt_id == attempt.attempt_id)
            .where(
                NewcomerActivityOutcome.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if existing is not None:
            if (
                existing.result_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return ActivityOutcomeSummary.model_validate(existing)
        current = (
            await self._session.get(NewcomerActivityOutcome, attempt.outcome_id)
            if attempt.outcome_id is not None
            else None
        )
        if current is None and command.supersedes_outcome_id is not None:
            raise NewcomerTrainingError(
                "[NEWCOMER_OUTCOME_LINEAGE_CONFLICT]",
                "训练结果修订引用与当前结果不一致。",
                409,
            )
        if current is not None and command.supersedes_outcome_id != current.outcome_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_OUTCOME_LINEAGE_CONFLICT]",
                "训练结果已更新，请基于最新结果重新执行。",
                409,
                details={"current_outcome_id": current.outcome_id},
            )
        if current is None and attempt.status in {
            "completed",
            "failed",
            "invalidated",
            "cancelled",
        }:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_STATE_CONFLICT]",
                "该训练尝试已经结束，不能覆盖原结果。",
                409,
            )
        now = _now()
        status_by_result = {
            "completed": "completed",
            "failed": "failed",
            "invalidated": "invalidated",
            "cancelled": "cancelled",
        }
        attempt.status = status_by_result[command.lifecycle_result]
        attempt.version += 1
        attempt.result_type = command.result_type
        attempt.result_id = command.result_id
        attempt.score = command.score
        attempt.max_score = command.max_score
        attempt.passed = command.passed
        attempt.evidence_status = "pending"
        attempt.reconcile_status = "outcome_recorded"
        if command.lifecycle_result == "completed":
            attempt.completed_at = now
        elif command.lifecycle_result == "failed":
            attempt.failed_at = now
        elif command.lifecycle_result == "invalidated":
            attempt.invalidated_at = now
        outcome = NewcomerActivityOutcome(
            outcome_id=_id(),
            organization_id=command.organization_id,
            attempt_id=attempt.attempt_id,
            idempotency_key_hash=_secret_hash(idempotency_key),
            result_fingerprint=fingerprint,
            lifecycle_result=command.lifecycle_result,
            assessment_result=command.assessment_result,
            score=command.score,
            max_score=command.max_score,
            passed=command.passed,
            competency_evidence_refs_json=list(command.competency_evidence_refs),
            source_refs_json=list(command.source_refs),
            lineage_json=command.lineage,
            confidence=command.confidence,
            critical_flags_json=list(command.critical_flags),
            degradations_json=list(command.degradations),
            next_action_json=command.next_action,
            version=(current.version + 1 if current is not None else 1),
            supersedes_outcome_id=(
                current.outcome_id if current is not None else None
            ),
            produced_at=now,
        )
        attempt.outcome_id = outcome.outcome_id
        self._session.add(outcome)
        await self._session.flush([attempt, outcome])
        await self._outbox.append(
            DomainEvent(
                event_type="ActivityOutcomeRecorded",
                schema_version=1,
                occurred_at=now,
                organization_id=command.organization_id,
                actor_id=actor_id,
                trace_id=trace_id,
                correlation_id=attempt.attempt_id,
                causation_id=attempt.task_id,
                idempotency_key=(
                    f"activity-outcome:{attempt.attempt_id}:{outcome.version}"
                ),
                aggregate_type="activity_attempt",
                aggregate_id=attempt.attempt_id,
                aggregate_version=attempt.version,
                payload={
                    "outcome_id": outcome.outcome_id,
                    "activity_id": attempt.activity_id,
                    "activity_type": attempt.activity_type,
                    "lifecycle_result": outcome.lifecycle_result,
                    "assessment_result": outcome.assessment_result,
                },
            )
        )
        return ActivityOutcomeSummary.model_validate(outcome)

    async def invalidate_attempt(
        self,
        *,
        actor: CommandActor,
        attempt_id: str,
        expected_attempt_version: int,
        reason: str,
        idempotency_key: str,
    ) -> ActivityAttemptSummary:
        if "newcomer.activity.invalidate" not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]",
                "没有失效训练结果的权限。",
                403,
            )
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_INVALIDATION_REASON_REQUIRED]",
                "请填写失效原因。",
                422,
            )
        fingerprint = _canonical_hash(
            {
                "attempt_id": attempt_id,
                "expected_attempt_version": expected_attempt_version,
                "reason": reason.strip(),
            }
        )
        replay = await self._session.scalar(
            select(NewcomerCommandAudit)
            .where(NewcomerCommandAudit.organization_id == actor.organization_id)
            .where(NewcomerCommandAudit.object_type == "activity_attempt")
            .where(NewcomerCommandAudit.object_id == attempt_id)
            .where(NewcomerCommandAudit.command == "invalidate_activity_attempt")
            .where(
                NewcomerCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.details_json.get("request_fingerprint") != fingerprint:
                self._idempotency_conflict()
            row = await self._load_attempt_for_update(
                organization_id=actor.organization_id,
                attempt_id=attempt_id,
            )
            return ActivityAttemptSummary.model_validate(row)
        attempt = await self._load_attempt_for_update(
            organization_id=actor.organization_id,
            attempt_id=attempt_id,
        )
        if attempt.version != expected_attempt_version:
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                "训练尝试已更新，请刷新后重试。",
                412,
                details={
                    "expected_version": expected_attempt_version,
                    "actual_version": attempt.version,
                },
            )
        if attempt.status not in {
            "started",
            "in_progress",
            "submitted",
            "processing",
            "completed",
            "failed",
        }:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_STATE_CONFLICT]",
                "当前训练尝试不能失效。",
                409,
            )
        previous_outcome = (
            await self._session.get(NewcomerActivityOutcome, attempt.outcome_id)
            if attempt.outcome_id is not None
            else None
        )
        now = _now()
        before = attempt.version
        attempt.status = "invalidated"
        attempt.version += 1
        attempt.invalidated_at = now
        attempt.evidence_status = "pending"
        attempt.reconcile_status = "outcome_recorded"
        invalidated_outcome = NewcomerActivityOutcome(
            outcome_id=_id(),
            organization_id=actor.organization_id,
            attempt_id=attempt.attempt_id,
            idempotency_key_hash=_secret_hash(f"{idempotency_key}:outcome"),
            result_fingerprint=_canonical_hash(
                {
                    "command": "invalidate_activity_outcome",
                    "attempt_id": attempt.attempt_id,
                    "reason": reason.strip(),
                    "supersedes_outcome_id": (
                        previous_outcome.outcome_id if previous_outcome else None
                    ),
                }
            ),
            lifecycle_result="invalidated",
            assessment_result=None,
            score=(previous_outcome.score if previous_outcome else attempt.score),
            max_score=(
                previous_outcome.max_score if previous_outcome else attempt.max_score
            ),
            passed=False,
            competency_evidence_refs_json=(
                list(previous_outcome.competency_evidence_refs_json)
                if previous_outcome
                else []
            ),
            source_refs_json=(
                list(previous_outcome.source_refs_json) if previous_outcome else []
            ),
            lineage_json={
                **(
                    dict(previous_outcome.lineage_json)
                    if previous_outcome
                    else {}
                ),
                "competency_keys": list(
                    attempt.activity_snapshot_json.get("competency_keys", [])
                ),
                "invalidation_reason": reason.strip(),
            },
            confidence=None,
            critical_flags_json=[],
            degradations_json=["该训练结果已由管理员失效。"],
            next_action_json={
                "label": "重新完成训练",
                "command_type": "start_relearn",
            },
            version=(previous_outcome.version + 1 if previous_outcome else 1),
            supersedes_outcome_id=(
                previous_outcome.outcome_id if previous_outcome else None
            ),
            produced_at=now,
        )
        attempt.outcome_id = invalidated_outcome.outcome_id
        self._session.add(invalidated_outcome)
        await self._session.flush([attempt, invalidated_outcome])
        audit = NewcomerCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability="newcomer.activity.invalidate",
            object_type="activity_attempt",
            object_id=attempt.attempt_id,
            command="invalidate_activity_attempt",
            before_version=before,
            after_version=attempt.version,
            idempotency_key_hash=_secret_hash(idempotency_key),
            expected_version=expected_attempt_version,
            actual_version=attempt.version,
            reason=reason.strip(),
            trace_id=actor.trace_id,
            result="succeeded",
            details_json={"request_fingerprint": fingerprint},
            occurred_at=now,
        )
        self._session.add(audit)
        await self._outbox.append(
            DomainEvent(
                event_type="ActivityOutcomeRecorded",
                schema_version=1,
                occurred_at=now,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                trace_id=actor.trace_id,
                correlation_id=attempt.attempt_id,
                causation_id=(
                    previous_outcome.outcome_id if previous_outcome else None
                ),
                idempotency_key=(
                    f"activity-outcome:{attempt.attempt_id}:"
                    f"{invalidated_outcome.version}"
                ),
                aggregate_type="activity_attempt",
                aggregate_id=attempt.attempt_id,
                aggregate_version=attempt.version,
                payload={
                    "outcome_id": invalidated_outcome.outcome_id,
                    "activity_id": attempt.activity_id,
                    "activity_type": attempt.activity_type,
                    "lifecycle_result": "invalidated",
                    "assessment_result": None,
                },
            )
        )
        await self._outbox.append(
            DomainEvent(
                event_type="ActivityOutcomeInvalidated",
                schema_version=1,
                occurred_at=now,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                trace_id=actor.trace_id,
                correlation_id=attempt.attempt_id,
                causation_id=(
                    previous_outcome.outcome_id if previous_outcome else None
                ),
                idempotency_key=f"activity-invalidation:{attempt.attempt_id}:{attempt.version}",
                aggregate_type="activity_attempt",
                aggregate_id=attempt.attempt_id,
                aggregate_version=attempt.version,
                payload={
                    "activity_id": attempt.activity_id,
                    "outcome_id": invalidated_outcome.outcome_id,
                    "supersedes_outcome_id": (
                        previous_outcome.outcome_id if previous_outcome else None
                    ),
                    "reason": reason.strip(),
                },
            )
        )
        await self._session.flush([audit, invalidated_outcome])
        return ActivityAttemptSummary.model_validate(attempt)

    async def require_activity_unlocked(
        self,
        *,
        enrollment: NewcomerEnrollment,
        draft: PathRevisionDraft,
        activity_id: str,
    ) -> set[str]:
        """Apply the same stage and prerequisite gate to GET and command paths."""

        completed = await self.completed_activity_ids(enrollment)
        stages = sorted(draft.stages, key=lambda item: item.sequence)
        target_stage_index: int | None = None
        target_activity: Any | None = None
        for stage_index, stage in enumerate(stages):
            for activity in stage.activities:
                if activity.activity_id == activity_id:
                    target_stage_index = stage_index
                    target_activity = activity
                    break
            if target_activity is not None:
                break
        if target_activity is None or target_stage_index is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_NOT_FOUND]",
                "训练活动不存在或不属于当前训练版本。",
                404,
            )

        blocked_ids: list[str] = []
        for stage in stages[:target_stage_index]:
            gated_activities = (
                stage.activities
                if str(stage.completion_rule) == "all_activities"
                else tuple(item for item in stage.activities if item.required)
            )
            blocked_ids.extend(
                item.activity_id
                for item in gated_activities
                if item.activity_id not in completed
            )
        blocked_ids.extend(
            item
            for item in target_activity.prerequisite_activity_ids
            if item not in completed
        )
        blocked_ids = list(dict.fromkeys(blocked_ids))
        if blocked_ids:
            title_by_id = {
                item.activity_id: item.title
                for stage in stages
                for item in stage.activities
            }
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_LOCKED]",
                "请先完成前置训练活动。",
                409,
                details={
                    "blocked_by": [
                        title_by_id.get(item, item) for item in blocked_ids
                    ]
                },
            )
        return completed

    async def completed_activity_ids(
        self, enrollment: NewcomerEnrollment
    ) -> set[str]:
        rows = await self._session.execute(
            select(NewcomerActivityAttempt.activity_id)
            .join(
                NewcomerActivityOutcome,
                NewcomerActivityOutcome.outcome_id
                == NewcomerActivityAttempt.outcome_id,
            )
            .where(
                NewcomerActivityAttempt.enrollment_id == enrollment.enrollment_id
            )
            .where(
                NewcomerActivityAttempt.path_revision_id
                == enrollment.path_revision_id
            )
            .where(NewcomerActivityAttempt.status == "completed")
            .where(NewcomerActivityOutcome.lifecycle_result == "completed")
            .where(
                (NewcomerActivityOutcome.passed.is_(True))
                | (NewcomerActivityOutcome.passed.is_(None))
            )
        )
        return set(rows.scalars())

    async def _load_attempt_for_update(
        self, *, organization_id: str, attempt_id: str
    ) -> NewcomerActivityAttempt:
        row = await self._session.scalar(
            select(NewcomerActivityAttempt)
            .where(NewcomerActivityAttempt.attempt_id == attempt_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_NOT_FOUND]",
                "训练尝试不存在或不可访问。",
                404,
            )
        return row

    async def _audit_start(
        self,
        *,
        actor: CommandActor,
        attempt: NewcomerActivityAttempt,
        idempotency_key: str,
        expected_enrollment_version: int,
    ) -> None:
        row = NewcomerCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability="newcomer.activity.execute",
            object_type="activity_attempt",
            object_id=attempt.attempt_id,
            command="start_activity_attempt",
            before_version=None,
            after_version=attempt.version,
            idempotency_key_hash=_secret_hash(idempotency_key),
            expected_version=expected_enrollment_version,
            actual_version=expected_enrollment_version,
            trace_id=actor.trace_id,
            result="succeeded",
            details_json={
                "activity_id": attempt.activity_id,
                "path_revision_id": attempt.path_revision_id,
            },
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])

    @staticmethod
    def _idempotency_conflict() -> None:
        raise NewcomerTrainingError(
            "[NEWCOMER_IDEMPOTENCY_CONFLICT]",
            "相同幂等键对应了不同的训练命令。",
            409,
        )


__all__ = [
    "ActivityAttemptService",
    "ActivityAttemptSummary",
    "ActivityOutcomeCommand",
    "ActivityOutcomeSummary",
]
