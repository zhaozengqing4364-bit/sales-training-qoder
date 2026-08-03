"""Application-root composition for ActivityOutcome -> Evidence -> Dossier."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from competency_evidence.application import CompetencyEvidenceService
from competency_evidence.contracts import OutcomeEvidenceInput
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from readiness.application import ReadinessService
from readiness.contracts import (
    ReadinessActivityInput,
    ReadinessProjectionInput,
)
from readiness.errors import ReadinessError
from readiness.models import ReadinessDossier
from task_runtime.outbox import OutboxEnvelope


def _now() -> datetime:
    return datetime.now(UTC)


def _string_refs(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        {str(key): str(item) for key, item in row.items()}
        for row in value
        if isinstance(row, dict)
    )


class FoundationReadinessProjection:
    """The only cross-domain adapter for readiness projection inputs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._evidence = CompetencyEvidenceService(session)
        self._readiness = ReadinessService(session)

    async def project_outcome(
        self,
        *,
        outcome_id: str,
        actor_id: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        outcome_input = await self._outcome_input(
            outcome_id=outcome_id,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        await self._evidence.append_outcome(outcome_input)
        projection_input = await self._projection_input(
            organization_id=outcome_input.organization_id,
            enrollment_id=outcome_input.enrollment_id,
        )
        return await self._readiness.project(
            projection_input,
            actor_id=actor_id,
            trace_id=trace_id,
        )

    async def rebuild_enrollment(
        self,
        *,
        organization_id: str,
        enrollment_id: str,
        actor_id: str,
        trace_id: str | None = None,
        force_refresh: bool = True,
    ) -> dict[str, Any]:
        outcomes = list(
            (
                await self._session.execute(
                    select(NewcomerActivityOutcome)
                    .join(
                        NewcomerActivityAttempt,
                        NewcomerActivityAttempt.attempt_id
                        == NewcomerActivityOutcome.attempt_id,
                    )
                    .where(
                        NewcomerActivityAttempt.organization_id == organization_id
                    )
                    .where(NewcomerActivityAttempt.enrollment_id == enrollment_id)
                    .order_by(
                        NewcomerActivityOutcome.produced_at.asc(),
                        NewcomerActivityOutcome.version.asc(),
                        NewcomerActivityOutcome.outcome_id.asc(),
                    )
                )
            ).scalars()
        )
        inputs = tuple(
            [
                await self._outcome_input(
                    outcome_id=outcome.outcome_id,
                    actor_id=actor_id,
                    trace_id=trace_id,
                )
                for outcome in outcomes
            ]
        )
        await self._evidence.rebuild(inputs)
        projection_input = await self._projection_input(
            organization_id=organization_id,
            enrollment_id=enrollment_id,
        )
        return await self._readiness.project(
            projection_input,
            actor_id=actor_id,
            trace_id=trace_id,
            force_refresh=force_refresh,
        )

    async def ensure_learner_dossier(
        self,
        *,
        organization_id: str,
        learner_id: str,
        actor_id: str,
        trace_id: str | None = None,
    ) -> ReadinessDossier:
        enrollment = await self._session.scalar(
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == organization_id)
            .where(NewcomerEnrollment.learner_id == learner_id)
            .where(NewcomerEnrollment.status.in_(("active", "completed")))
            .order_by(desc(NewcomerEnrollment.assigned_at))
            .limit(1)
        )
        if enrollment is None:
            raise ReadinessError(
                "[DOSSIER_ENROLLMENT_NOT_FOUND]",
                "尚未分配可生成训练档案的新人训练。",
                404,
            )
        dossier = await self._session.scalar(
            select(ReadinessDossier)
            .where(ReadinessDossier.organization_id == organization_id)
            .where(ReadinessDossier.enrollment_id == enrollment.enrollment_id)
            .limit(1)
        )
        if dossier is None:
            await self.rebuild_enrollment(
                organization_id=organization_id,
                enrollment_id=enrollment.enrollment_id,
                actor_id=actor_id,
                trace_id=trace_id,
                force_refresh=False,
            )
            dossier = await self._session.scalar(
                select(ReadinessDossier)
                .where(ReadinessDossier.organization_id == organization_id)
                .where(ReadinessDossier.enrollment_id == enrollment.enrollment_id)
                .limit(1)
            )
        if dossier is None:
            raise ReadinessError(
                "[DOSSIER_PROJECTION_FAILED]",
                "训练档案暂时无法生成，请稍后重试。",
                503,
            )
        return dossier

    async def require_published_retraining_activity(
        self,
        *,
        organization_id: str,
        dossier_id: str,
        activity_id: str,
        target_competency_keys: tuple[str, ...],
    ) -> None:
        dossier = await self._session.get(ReadinessDossier, dossier_id)
        if dossier is None or dossier.organization_id != organization_id:
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]", "训练档案不存在或不可访问。", 404
            )
        revision = await self._session.get(
            NewcomerPathRevision,
            dossier.path_revision_id,
        )
        if (
            revision is None
            or revision.organization_id != organization_id
            or revision.status not in {"published", "archived"}
        ):
            raise ReadinessError(
                "[RETRAINING_ACTIVITY_UNAVAILABLE]",
                "当前训练版本不可用于补充训练。",
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
            raise ReadinessError(
                "[RETRAINING_ACTIVITY_UNAVAILABLE]",
                "所选训练活动不属于当前已发布训练版本。",
                422,
            )
        if not set(target_competency_keys).intersection(activity.competency_keys):
            raise ReadinessError(
                "[RETRAINING_COMPETENCY_MISMATCH]",
                "所选训练活动未覆盖本次需要补充的能力。",
                422,
            )

    async def _outcome_input(
        self,
        *,
        outcome_id: str,
        actor_id: str,
        trace_id: str | None,
    ) -> OutcomeEvidenceInput:
        outcome = await self._session.get(NewcomerActivityOutcome, outcome_id)
        if outcome is None:
            raise ReadinessError(
                "[ACTIVITY_OUTCOME_NOT_FOUND]", "训练结果不存在。", 404
            )
        attempt = await self._session.get(NewcomerActivityAttempt, outcome.attempt_id)
        if attempt is None or attempt.organization_id != outcome.organization_id:
            raise ReadinessError(
                "[ACTIVITY_OUTCOME_SCOPE_INVALID]",
                "训练结果缺少有效的训练尝试关联。",
                409,
            )
        enrollment = await self._session.get(NewcomerEnrollment, attempt.enrollment_id)
        if enrollment is None or enrollment.organization_id != outcome.organization_id:
            raise ReadinessError(
                "[ACTIVITY_OUTCOME_SCOPE_INVALID]",
                "训练结果缺少有效的训练分配关联。",
                409,
            )
        lineage = dict(outcome.lineage_json or {})
        raw_keys = lineage.get("competency_keys")
        if not isinstance(raw_keys, list | tuple):
            raw_keys = attempt.activity_snapshot_json.get("competency_keys", [])
        competency_keys = tuple(
            dict.fromkeys(str(item).strip() for item in raw_keys if str(item).strip())
        )
        if not competency_keys:
            raise ReadinessError(
                "[COMPETENCY_MAPPING_REQUIRED]",
                "训练结果缺少已发布的能力映射。",
                409,
                details={"activity_id": attempt.activity_id},
            )
        return OutcomeEvidenceInput(
            organization_id=outcome.organization_id,
            learner_id=enrollment.learner_id,
            enrollment_id=enrollment.enrollment_id,
            path_revision_id=enrollment.path_revision_id,
            activity_id=attempt.activity_id,
            activity_type=attempt.activity_type,
            competency_keys=competency_keys,
            attempt_id=attempt.attempt_id,
            outcome_id=outcome.outcome_id,
            outcome_version=outcome.version,
            supersedes_outcome_id=outcome.supersedes_outcome_id,
            lifecycle_result=outcome.lifecycle_result,
            assessment_result=outcome.assessment_result,
            score=float(outcome.score) if outcome.score is not None else None,
            max_score=(
                float(outcome.max_score) if outcome.max_score is not None else None
            ),
            passed=outcome.passed,
            source_refs=_string_refs(outcome.source_refs_json),
            lineage=lineage,
            confidence=(
                float(outcome.confidence) if outcome.confidence is not None else None
            ),
            critical_flags=tuple(outcome.critical_flags_json or []),
            degradations=tuple(outcome.degradations_json or []),
            produced_at=outcome.produced_at,
            actor_id=actor_id,
            trace_id=trace_id,
        )

    async def _projection_input(
        self,
        *,
        organization_id: str,
        enrollment_id: str,
    ) -> ReadinessProjectionInput:
        enrollment = await self._session.get(NewcomerEnrollment, enrollment_id)
        if enrollment is None or enrollment.organization_id != organization_id:
            raise ReadinessError(
                "[DOSSIER_ENROLLMENT_NOT_FOUND]",
                "训练分配不存在或不可访问。",
                404,
            )
        revision = await self._session.get(
            NewcomerPathRevision,
            enrollment.path_revision_id,
        )
        cohort = await self._session.get(NewcomerCohort, enrollment.cohort_id)
        learner = await self._session.get(User, enrollment.learner_id)
        if (
            revision is None
            or revision.organization_id != organization_id
            or revision.status not in {"published", "archived"}
            or cohort is None
            or cohort.organization_id != organization_id
            or learner is None
        ):
            raise ReadinessError(
                "[DOSSIER_SOURCE_UNAVAILABLE]",
                "训练档案所需的路径、班次或学员资料不完整。",
                409,
            )
        path = await self._session.get(NewcomerPath, revision.path_id)
        if path is None or path.organization_id != organization_id:
            raise ReadinessError(
                "[DOSSIER_SOURCE_UNAVAILABLE]",
                "训练档案所需的训练路径不存在。",
                409,
            )
        draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        attempts = list(
            (
                await self._session.execute(
                    select(NewcomerActivityAttempt)
                    .where(NewcomerActivityAttempt.organization_id == organization_id)
                    .where(NewcomerActivityAttempt.enrollment_id == enrollment_id)
                    .where(
                        NewcomerActivityAttempt.path_revision_id
                        == enrollment.path_revision_id
                    )
                    .order_by(
                        NewcomerActivityAttempt.activity_id.asc(),
                        desc(NewcomerActivityAttempt.attempt_no),
                    )
                )
            ).scalars()
        )
        latest_attempt: dict[str, NewcomerActivityAttempt] = {}
        for attempt in attempts:
            latest_attempt.setdefault(attempt.activity_id, attempt)
        outcome_ids = tuple(
            attempt.outcome_id
            for attempt in latest_attempt.values()
            if attempt.outcome_id is not None
        )
        outcomes = (
            {
                row.outcome_id: row
                for row in (
                    await self._session.scalars(
                        select(NewcomerActivityOutcome).where(
                            NewcomerActivityOutcome.outcome_id.in_(outcome_ids)
                        )
                    )
                ).all()
            }
            if outcome_ids
            else {}
        )
        activities: list[ReadinessActivityInput] = []
        for stage in sorted(draft.stages, key=lambda item: item.sequence):
            for activity in stage.activities:
                latest = latest_attempt.get(activity.activity_id)
                outcome = (
                    outcomes.get(str(latest.outcome_id))
                    if latest is not None and latest.outcome_id is not None
                    else None
                )
                status = "not_started"
                if latest is not None:
                    status = latest.status
                if outcome is not None and outcome.lifecycle_result == "completed":
                    status = "completed"
                activities.append(
                    ReadinessActivityInput(
                        activity_id=activity.activity_id,
                        activity_type=str(activity.type),
                        title=activity.title,
                        required=activity.required,
                        status=status,
                        latest_attempt_id=(latest.attempt_id if latest else None),
                        latest_outcome_id=(outcome.outcome_id if outcome else None),
                        latest_outcome_version=(outcome.version if outcome else None),
                        latest_outcome_at=(outcome.produced_at if outcome else None),
                        processing=(
                            latest is not None
                            and latest.status in {"submitted", "processing"}
                        ),
                    )
                )
        evidence = await self._evidence.list_for_enrollment(
            organization_id=organization_id,
            enrollment_id=enrollment_id,
        )
        return ReadinessProjectionInput(
            organization_id=organization_id,
            learner_id=enrollment.learner_id,
            learner_name=learner.name,
            enrollment_id=enrollment.enrollment_id,
            cohort_id=cohort.cohort_id,
            cohort_name=cohort.name,
            path_revision_id=revision.revision_id,
            path_title=draft.title or path.title,
            path_revision_label=revision.revision_label,
            enrollment_status=enrollment.status,
            activities=tuple(activities),
            evidence=evidence,
            generated_at=_now(),
        )


async def project_activity_outcome_event(
    event: OutboxEnvelope,
    session: AsyncSession,
) -> None:
    """Effect-once compatible handler for durable event-driven reconciliation."""

    if event.event_type != "ActivityOutcomeRecorded":
        return
    outcome_id = str(event.payload.get("outcome_id") or "")
    if not outcome_id:
        raise ReadinessError(
            "[ACTIVITY_OUTCOME_EVENT_INVALID]",
            "训练结果事件缺少 outcome_id。",
            422,
        )
    await FoundationReadinessProjection(session).project_outcome(
        outcome_id=outcome_id,
        actor_id=event.actor_id or "system:readiness-projection",
        trace_id=event.trace_id,
    )


__all__ = [
    "FoundationReadinessProjection",
    "project_activity_outcome_event",
]
