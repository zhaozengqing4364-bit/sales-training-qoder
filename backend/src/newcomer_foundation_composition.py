"""Application-root adapters between newcomer training, learning, and tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Never, TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import (
    CoachContextReference,
    CoachContextSnapshot,
    CoachProfileSnapshot,
    CoachWeaknessInput,
    RequestCoachAssistanceInput,
    SubmitCoachAnswerInput,
)
from ai_coach.errors import AICoachError
from ai_coach.models import CoachProfileRevision
from ai_coach.ports import (
    CoachActivityOutcomePayload,
    CoachActivityOutcomeWriterPort,
    CoachContextBuilderPort,
)
from ai_coach.runtime import CoachStartContext, StructuredCoachRuntime
from audio_assessment.contracts import (
    ConfirmUploadPartInput,
    CreateUploadSessionInput,
    FinalizeUploadInput,
    SubmissionCommandInput,
)
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.models import AudioActivityResourceRevision
from audio_assessment.ports import (
    AudioObjectStoragePort,
    AudioOutcomePayload,
    AudioOutcomeWriterPort,
)
from audio_assessment.runtime import AudioRuntimeResult, AudioRuntimeService
from audio_assessment.storage import build_audio_object_storage
from common.db.models import Notification
from foundation_readiness_composition import FoundationReadinessProjection
from learning.contracts import LearningActor
from learning.errors import LearningGovernanceError
from learning.lesson_runtime import (
    LessonAttemptContext,
    LessonProgressSummary,
    LessonRuntimeService,
)
from learning.models import (
    LearningLessonAttempt,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningUnitRevision,
)
from learning.ports import ActivityOutcomePayload, ActivityOutcomeWriterPort
from learning.quiz_runtime import (
    QuizAnswerInput,
    QuizAttemptContext,
    QuizRuntimeService,
)
from learning.workspace import (
    LearningWorkspaceProjection,
    LearningWorkspaceQueryService,
)
from newcomer_training.activity import (
    ActivityAttemptService,
    ActivityAttemptSummary,
    ActivityOutcomeCommand,
)
from newcomer_training.application import CommandActor
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
)
from newcomer_training.notifications import (
    FoundationNotificationReadPort,
    NotificationReadState,
    NotificationRecord,
    NotificationSort,
)
from newcomer_training.ports import (
    ActivityRuntimeCommand,
    ActivityRuntimePort,
    ActivityRuntimeResult,
    ActivityRuntimeStart,
    PublishedActivityResourcePort,
)
from task_runtime.registry import TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime


class _AudioRuntimeCommandScope(TypedDict):
    organization_id: str
    learner_id: str
    attempt_id: str
    expected_version: int


class PublishedLearningResourceAdapter(PublishedActivityResourcePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        row: LearningUnitRevision | LearningQuizRevision | None
        if activity_type == "lesson":
            row = await self._session.get(LearningUnitRevision, revision_id)
        elif activity_type == "quiz":
            row = await self._session.get(LearningQuizRevision, revision_id)
        else:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
                "该活动类型尚未注册可发布资源，请先完成对应能力配置。",
                503,
            )
        if (
            row is None
            or row.organization_id != organization_id
            or row.status != "published"
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RESOURCE_UNPUBLISHED]",
                "训练路径引用了未发布或不可访问的学习资源。",
                422,
                details={"activity_type": activity_type},
            )


class PublishedAudioResourceAdapter(PublishedActivityResourcePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        allowed_types = {
            "audio_assessment": {"audio_material", "scoring_scheme"},
            "assignment": {"scenario", "scoring_scheme"},
        }.get(activity_type)
        if allowed_types is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
                "该活动类型尚未注册可发布资源，请先完成对应能力配置。",
                503,
            )
        row = await self._session.get(AudioActivityResourceRevision, revision_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.resource_type not in allowed_types
            or row.status != "published"
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RESOURCE_UNPUBLISHED]",
                "训练路径引用了未发布或不可访问的录音评测资源。",
                422,
                details={"activity_type": activity_type},
            )


class PublishedCoachResourceAdapter(PublishedActivityResourcePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        if activity_type != "ai_coach":
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
                "该活动类型尚未注册可发布资源，请先完成对应能力配置。",
                503,
            )
        row = await self._session.get(CoachProfileRevision, revision_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.status != "published"
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_RESOURCE_UNPUBLISHED]",
                "训练路径引用了未发布或不可访问的教练配置。",
                422,
                details={"activity_type": activity_type},
            )


class FoundationPublishedResourceAdapter(PublishedActivityResourcePort):
    def __init__(self, session: AsyncSession) -> None:
        self._learning = PublishedLearningResourceAdapter(session)
        self._audio = PublishedAudioResourceAdapter(session)
        self._coach = PublishedCoachResourceAdapter(session)

    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        adapter: PublishedActivityResourcePort
        if activity_type in {"lesson", "quiz"}:
            adapter = self._learning
        elif activity_type == "ai_coach":
            adapter = self._coach
        else:
            adapter = self._audio
        await adapter.require_published(
            organization_id=organization_id,
            activity_type=activity_type,
            revision_id=revision_id,
        )


class SQLAlchemyFoundationNotificationReader(FoundationNotificationReadPort):
    """Reads only foundation-owned notification sources for the current user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self,
        *,
        user_id: str,
        read_state: NotificationReadState,
        notification_type: str | None,
        created_from: datetime | None,
        page: int,
        page_size: int,
        sort: NotificationSort,
    ) -> tuple[tuple[NotificationRecord, ...], int]:
        filters = [
            Notification.user_id == user_id,
            Notification.source.like("newcomer_training:%"),
        ]
        if read_state == "read":
            filters.append(Notification.is_read.is_(True))
        elif read_state == "unread":
            filters.append(Notification.is_read.is_(False))
        if notification_type:
            filters.append(Notification.type == notification_type)
        if created_from is not None:
            filters.append(Notification.created_at >= created_from)
        total = int(
            await self._session.scalar(
                select(func.count(Notification.notification_id)).where(*filters)
            )
            or 0
        )
        order = (
            Notification.created_at.asc()
            if sort == "created_at"
            else Notification.created_at.desc()
        )
        rows = list(
            (
                await self._session.execute(
                    select(Notification)
                    .where(*filters)
                    .order_by(order, Notification.notification_id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        return (
            tuple(
                NotificationRecord(
                    notification_id=str(row.notification_id),
                    notification_type=str(row.type),
                    title=str(row.title),
                    content=str(row.content),
                    action_label=(
                        str(row.action_label) if row.action_label else None
                    ),
                    action_path=(str(row.action_path) if row.action_path else None),
                    source=str(row.source) if row.source else None,
                    is_read=bool(row.is_read),
                    created_at=row.created_at,
                )
                for row in rows
            ),
            total,
        )


class FoundationCoachContextBuilder(CoachContextBuilderPort):
    """Build the minimum published, organization-scoped Coach context snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build(
        self,
        *,
        organization_id: str,
        learner_id: str,
        enrollment_id: str,
        path_revision_id: str,
        activity_id: str,
        profile_revision_id: str,
        profile: CoachProfileSnapshot,
    ) -> CoachContextSnapshot:
        del learner_id, path_revision_id, activity_id, profile_revision_id
        references: list[CoachContextReference] = []
        for revision_id in profile.allowed_knowledge_scope:
            revision = await self._session.get(LearningUnitRevision, revision_id)
            if (
                revision is None
                or revision.organization_id != organization_id
                or revision.status not in {"published", "archived"}
            ):
                continue
            snapshot = dict(revision.snapshot_json)
            excerpt_parts = [
                str(item.get("content", ""))
                for key in ("key_concepts", "examples")
                for item in snapshot.get(key, [])
                if isinstance(item, dict) and item.get("content")
            ]
            references.append(
                CoachContextReference(
                    ref_id=f"learning-unit:{revision.revision_id}",
                    resource_type="learning_unit",
                    resource_id=revision.unit_id,
                    revision_id=revision.revision_id,
                    label=str(snapshot.get("title") or "已发布学习内容"),
                    excerpt="\n".join(excerpt_parts)[:8_000] or None,
                )
            )
            anchors = list(
                (
                    await self._session.execute(
                        select(LearningSourceAnchor).where(
                            LearningSourceAnchor.anchor_id.in_(
                                revision.source_anchor_ids_json
                            )
                        )
                    )
                ).scalars()
            )
            references.extend(
                CoachContextReference(
                    ref_id=f"source-anchor:{anchor.anchor_id}",
                    resource_type="source_anchor",
                    resource_id=anchor.anchor_id,
                    revision_id=anchor.source_revision_id,
                    label=anchor.label,
                    excerpt=None,
                )
                for anchor in anchors
                if anchor.organization_id == organization_id
            )
        attempts = list(
            (
                await self._session.execute(
                    select(NewcomerActivityAttempt)
                    .where(NewcomerActivityAttempt.organization_id == organization_id)
                    .where(NewcomerActivityAttempt.enrollment_id == enrollment_id)
                    .where(
                        NewcomerActivityAttempt.activity_type.in_(
                            ("quiz", "audio_assessment")
                        )
                    )
                    .where(NewcomerActivityAttempt.outcome_id.is_not(None))
                )
            ).scalars()
        )
        weaknesses: list[CoachWeaknessInput] = []
        for attempt in attempts:
            if attempt.outcome_id is None:
                continue
            outcome = await self._session.get(
                NewcomerActivityOutcome, attempt.outcome_id
            )
            if outcome is None or outcome.organization_id != organization_id:
                continue
            result_type = (
                "quiz_outcome" if attempt.activity_type == "quiz" else "audio_outcome"
            )
            ref_id = f"activity-outcome:{outcome.outcome_id}"
            score_label = (
                f"{float(outcome.score):.0f} 分"
                if outcome.score is not None
                else "待复核结果"
            )
            references.append(
                CoachContextReference(
                    ref_id=ref_id,
                    resource_type=result_type,
                    resource_id=outcome.outcome_id,
                    revision_id=f"{outcome.outcome_id}:v{outcome.version}",
                    label=(f"{attempt.activity_id} 的{score_label}训练结果"),
                    excerpt=None,
                )
            )
            if outcome.passed is not False:
                continue
            competency_keys = tuple(
                str(item)
                for item in outcome.lineage_json.get("competency_keys", [])
                if str(item) in profile.applicable_competency_keys
            )
            for competency_key in competency_keys:
                weaknesses.append(
                    CoachWeaknessInput(
                        competency_key=competency_key,
                        source_ref_ids=(ref_id,),
                        summary=f"此前{attempt.activity_type}结果尚未达到要求，需针对性巩固。",
                        confidence=(
                            float(outcome.confidence)
                            if outcome.confidence is not None
                            else 1
                        ),
                    )
                )
        unique_references = {item.ref_id: item for item in references}
        if not unique_references:
            raise AICoachError(
                "[COACH_CONTEXT_UNAVAILABLE]",
                "当前训练缺少可验证的学习依据，请联系培训负责人。",
                409,
            )
        return CoachContextSnapshot(
            references=tuple(unique_references.values()),
            weaknesses=tuple(weaknesses[:50]),
            degradations=(
                ()
                if weaknesses
                else ("没有检测到未达标结果，本轮用于巩固已学习能力。",)
            ),
        )


class SQLAlchemyActivityOutcomeWriter(ActivityOutcomeWriterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._service = ActivityAttemptService(session)
        self._readiness = FoundationReadinessProjection(session)

    async def record(self, payload: ActivityOutcomePayload) -> str:
        summary = await self._service.record_outcome(
            command=ActivityOutcomeCommand(
                organization_id=payload.organization_id,
                attempt_id=payload.attempt_id,
                lifecycle_result=payload.lifecycle_result,
                assessment_result=payload.assessment_result,
                result_type=payload.result_type,
                result_id=payload.result_id,
                score=payload.score,
                max_score=payload.max_score,
                passed=payload.passed,
                competency_evidence_refs=payload.competency_evidence_refs,
                source_refs=payload.source_refs,
                lineage=payload.lineage,
                confidence=payload.confidence,
                critical_flags=payload.critical_flags,
                degradations=payload.degradations,
                next_action=payload.next_action,
            ),
            idempotency_key=payload.idempotency_key,
            actor_id=payload.actor_id,
            trace_id=payload.trace_id,
        )
        await self._readiness.project_outcome(
            outcome_id=summary.outcome_id,
            actor_id=payload.actor_id,
            trace_id=payload.trace_id,
        )
        return str(summary.outcome_id)


class SQLAlchemyCoachActivityOutcomeWriter(CoachActivityOutcomeWriterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._delegate = SQLAlchemyActivityOutcomeWriter(session)

    async def record(self, payload: CoachActivityOutcomePayload) -> str:
        return await self._delegate.record(
            ActivityOutcomePayload.model_validate(payload.model_dump(mode="json"))
        )


class SQLAlchemyAudioOutcomeWriter(AudioOutcomeWriterPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = ActivityAttemptService(session)
        self._readiness = FoundationReadinessProjection(session)

    async def record(self, payload: AudioOutcomePayload) -> str:
        attempt = await self._session.get(NewcomerActivityAttempt, payload.attempt_id)
        if attempt is None or attempt.organization_id != payload.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_NOT_FOUND]",
                "训练尝试不存在或不可访问。",
                404,
            )
        summary = await self._service.record_outcome(
            command=ActivityOutcomeCommand(
                organization_id=payload.organization_id,
                attempt_id=payload.attempt_id,
                lifecycle_result="completed",
                assessment_result=payload.assessment_result,
                result_type=payload.result_type,
                result_id=payload.result_id,
                score=payload.score,
                max_score=payload.max_score,
                passed=payload.passed,
                source_refs=payload.source_refs,
                lineage=payload.lineage,
                confidence=payload.confidence,
                critical_flags=payload.critical_flags,
                degradations=payload.degradations,
                next_action=payload.next_action,
                supersedes_outcome_id=(
                    payload.supersedes_outcome_id or attempt.outcome_id
                ),
            ),
            idempotency_key=payload.idempotency_key,
            actor_id=payload.actor_id,
            trace_id=payload.trace_id,
        )
        await self._readiness.project_outcome(
            outcome_id=summary.outcome_id,
            actor_id=payload.actor_id,
            trace_id=payload.trace_id,
        )
        return str(summary.outcome_id)


class FoundationLessonAdministrationService:
    """Atomically invalidates the typed lesson detail and generic attempt state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def invalidate(
        self,
        *,
        newcomer_actor: CommandActor,
        learning_actor: LearningActor,
        attempt_id: str,
        expected_attempt_version: int,
        expected_detail_version: int,
        reason: str,
        idempotency_key: str,
    ) -> tuple[ActivityAttemptSummary, LessonProgressSummary]:
        detail = await self._session.scalar(
            select(LearningLessonAttempt)
            .where(LearningLessonAttempt.attempt_id == attempt_id)
            .limit(1)
        )
        if detail is None or detail.organization_id != newcomer_actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_NOT_FOUND]",
                "训练尝试不存在或不可访问。",
                404,
            )
        lesson = await LessonRuntimeService(self._session).invalidate(
            actor=learning_actor,
            detail_id=detail.detail_id,
            expected_version=expected_detail_version,
            reason=reason,
            idempotency_key=f"{idempotency_key}:lesson",
        )
        attempt = await ActivityAttemptService(self._session).invalidate_attempt(
            actor=newcomer_actor,
            attempt_id=attempt_id,
            expected_attempt_version=expected_attempt_version,
            reason=reason,
            idempotency_key=f"{idempotency_key}:attempt",
        )
        if attempt.outcome_id is not None:
            await FoundationReadinessProjection(
                self._session
            ).project_outcome(
                outcome_id=attempt.outcome_id,
                actor_id=newcomer_actor.actor_id,
                trace_id=newcomer_actor.trace_id,
            )
        return attempt, lesson


class AudioActivityRuntimeAdapter(ActivityRuntimePort):
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_registry: TaskRegistry,
        storage: AudioObjectStoragePort | None = None,
    ) -> None:
        self._session = session
        self._attempts = ActivityAttemptService(session)
        self._runtime = AudioRuntimeService(
            session,
            task_runtime=SQLAlchemyTaskRuntime(session, registry=task_registry),
            storage=storage or build_audio_object_storage(),
        )

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_id: str,
        activity_type: str,
        config: dict[str, Any],
        attempt_id: str | None,
    ) -> ActivityRuntimeResult | None:
        del activity_id, activity_type, config
        try:
            result = await self._runtime.workspace(
                organization_id=organization_id,
                learner_id=learner_id,
                attempt_id=attempt_id,
            )
        except AudioAssessmentError as exc:
            self._raise_newcomer(exc)
        return self._result(result) if result is not None else None

    async def start(self, command: ActivityRuntimeStart) -> ActivityRuntimeResult:
        try:
            result = await self._runtime.start(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                enrollment_id=command.enrollment_id,
                path_revision_id=command.path_revision_id,
                activity_id=command.activity_id,
                activity_type=command.activity_type,
                attempt_id=command.attempt_id,
                config=command.config,
                competency_keys=command.competency_keys,
                idempotency_key=command.idempotency_key,
            )
        except AudioAssessmentError as exc:
            self._raise_newcomer(exc)
        return self._result(result)

    async def execute(
        self,
        command: ActivityRuntimeCommand,
    ) -> ActivityRuntimeResult:
        common: _AudioRuntimeCommandScope = {
            "organization_id": command.organization_id,
            "learner_id": command.learner_id,
            "attempt_id": command.attempt_id,
            "expected_version": command.expected_detail_version,
        }
        try:
            if command.command_type == "create_upload_session":
                result = await self._runtime.create_upload_session(
                    **common,
                    payload=CreateUploadSessionInput.model_validate(command.payload),
                    idempotency_key=command.idempotency_key,
                )
            elif command.command_type == "confirm_upload_part":
                result = await self._runtime.confirm_upload_part(
                    **common,
                    payload=ConfirmUploadPartInput.model_validate(command.payload),
                )
            elif command.command_type == "finalize_upload":
                result = await self._runtime.finalize_upload(
                    **common,
                    payload=FinalizeUploadInput.model_validate(command.payload),
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "retry_stage":
                result = await self._runtime.retry_stage(
                    **common,
                    payload=SubmissionCommandInput.model_validate(command.payload),
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "cancel":
                result = await self._runtime.cancel_run(
                    **common,
                    idempotency_key=command.idempotency_key,
                )
                outcome = await self._attempts.record_outcome(
                    command=ActivityOutcomeCommand(
                        organization_id=command.organization_id,
                        attempt_id=command.attempt_id,
                        lifecycle_result="cancelled",
                        assessment_result=None,
                        result_type="audio_assessment_run",
                        result_id=result.run_id,
                        lineage={"audio_run_id": result.run_id},
                        next_action=None,
                    ),
                    idempotency_key=f"{command.idempotency_key}:outcome",
                    actor_id=command.learner_id,
                    trace_id=command.trace_id,
                )
                await FoundationReadinessProjection(
                    self._session
                ).project_outcome(
                    outcome_id=outcome.outcome_id,
                    actor_id=command.learner_id,
                    trace_id=command.trace_id,
                )
            else:
                raise NewcomerTrainingError(
                    "[NEWCOMER_ACTIVITY_COMMAND_UNSUPPORTED]",
                    "当前录音任务不支持该命令。",
                    422,
                )
        except (AudioAssessmentError, ValueError) as exc:
            if isinstance(exc, AudioAssessmentError):
                self._raise_newcomer(exc)
            raise NewcomerTrainingError(
                "[AUDIO_COMMAND_INVALID]",
                "录音命令内容无效，请刷新后重试。",
                422,
            ) from exc
        return self._result(result)

    @staticmethod
    def _result(result: AudioRuntimeResult) -> ActivityRuntimeResult:
        return ActivityRuntimeResult(
            detail_id=result.run_id,
            detail_status=result.status,
            detail_version=result.version,
            task_id=result.task_id,
            runner=result.runner,
            available_commands=result.available_commands,
        )

    @staticmethod
    def _raise_newcomer(exc: AudioAssessmentError) -> None:
        raise NewcomerTrainingError(
            exc.code,
            exc.message,
            exc.status_code,
            details=exc.details,
        ) from exc


class LearningActivityRuntimeAdapter(ActivityRuntimePort):
    def __init__(self, session: AsyncSession, *, task_registry: TaskRegistry) -> None:
        self._session = session
        self._tasks = SQLAlchemyTaskRuntime(session, registry=task_registry)
        self._outcomes = SQLAlchemyActivityOutcomeWriter(session)

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_id: str,
        activity_type: str,
        config: dict[str, Any],
        attempt_id: str | None,
    ) -> ActivityRuntimeResult | None:
        revision_id = self._revision_id(activity_type, config)
        try:
            projection = await LearningWorkspaceQueryService(self._session).get(
                organization_id=organization_id,
                learner_id=learner_id,
                activity_type=activity_type,
                revision_id=revision_id,
                attempt_id=attempt_id,
                activity_id=activity_id,
            )
        except LearningGovernanceError as exc:
            self._raise_newcomer(exc)
        return self._result(projection)

    async def start(self, command: ActivityRuntimeStart) -> ActivityRuntimeResult:
        try:
            if command.activity_type == "lesson":
                lesson_summary = await LessonRuntimeService(
                    self._session
                ).start_or_resume(
                    context=LessonAttemptContext(
                        organization_id=command.organization_id,
                        learner_id=command.learner_id,
                        enrollment_id=command.enrollment_id,
                        path_revision_id=command.path_revision_id,
                        activity_id=command.activity_id,
                        attempt_id=command.attempt_id,
                        learning_unit_revision_id=str(
                            command.config["learning_unit_revision_id"]
                        ),
                        required_checkpoint_ids=tuple(
                            str(item)
                            for item in command.config["required_checkpoint_ids"]
                        ),
                        relearn_of_detail_id=command.relearn_of_detail_id,
                    ),
                    idempotency_key=command.idempotency_key,
                )
                revision_id = lesson_summary.learning_unit_revision_id
            elif command.activity_type == "quiz":
                quiz_summary = await QuizRuntimeService(
                    self._session,
                    task_runtime=self._tasks,
                    outcomes=self._outcomes,
                ).start_or_resume(
                    context=QuizAttemptContext(
                        organization_id=command.organization_id,
                        learner_id=command.learner_id,
                        enrollment_id=command.enrollment_id,
                        path_revision_id=command.path_revision_id,
                        activity_id=command.activity_id,
                        attempt_id=command.attempt_id,
                        quiz_revision_id=str(command.config["quiz_revision_id"]),
                        trace_id=command.trace_id,
                    ),
                    idempotency_key=command.idempotency_key,
                )
                revision_id = quiz_summary.quiz_revision_id
            else:
                self._unsupported()
            projection = await LearningWorkspaceQueryService(self._session).get(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                activity_type=command.activity_type,
                revision_id=revision_id,
                attempt_id=command.attempt_id,
                activity_id=command.activity_id,
            )
        except (KeyError, TypeError, LearningGovernanceError) as exc:
            if isinstance(exc, LearningGovernanceError):
                self._raise_newcomer(exc)
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_CONFIG_INVALID]",
                "训练活动配置不完整，请联系培训负责人。",
                422,
            ) from exc
        return self._result(projection)

    async def execute(self, command: ActivityRuntimeCommand) -> ActivityRuntimeResult:
        revision_id = self._revision_id(command.activity_type, command.config)
        current = await LearningWorkspaceQueryService(self._session).get(
            organization_id=command.organization_id,
            learner_id=command.learner_id,
            activity_type=command.activity_type,
            revision_id=revision_id,
            attempt_id=command.attempt_id,
            activity_id=command.activity_id,
        )
        if current.detail_id is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_DETAIL_NOT_FOUND]",
                "当前训练记录不存在，请重新进入活动。",
                404,
            )
        try:
            if command.activity_type == "lesson":
                await self._execute_lesson(command, detail_id=current.detail_id)
            elif command.activity_type == "quiz":
                await self._execute_quiz(command, detail_id=current.detail_id)
            else:
                self._unsupported()
            projection = await LearningWorkspaceQueryService(self._session).get(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                activity_type=command.activity_type,
                revision_id=revision_id,
                attempt_id=command.attempt_id,
                activity_id=command.activity_id,
            )
        except (KeyError, TypeError, ValueError, LearningGovernanceError) as exc:
            if isinstance(exc, LearningGovernanceError):
                self._raise_newcomer(exc)
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_COMMAND_INVALID]",
                "训练命令内容无效，请刷新后重试。",
                422,
            ) from exc
        return self._result(projection)

    async def _execute_lesson(
        self, command: ActivityRuntimeCommand, *, detail_id: str
    ) -> None:
        runtime = LessonRuntimeService(self._session)
        if command.command_type == "save_progress":
            await runtime.save_progress(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                detail_id=detail_id,
                completed_checkpoint_ids=tuple(
                    str(item) for item in command.payload["completed_checkpoint_ids"]
                ),
                reading_position=dict(command.payload.get("reading_position", {})),
                expected_version=command.expected_detail_version,
                idempotency_key=command.idempotency_key,
            )
            return
        if command.command_type == "complete":
            summary = await runtime.complete(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                detail_id=detail_id,
                expected_version=command.expected_detail_version,
                idempotency_key=command.idempotency_key,
            )
            await self._outcomes.record(
                ActivityOutcomePayload(
                    organization_id=command.organization_id,
                    actor_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    lifecycle_result="completed",
                    assessment_result="not_applicable",
                    result_type="lesson_attempt",
                    result_id=summary.detail_id,
                    score=None,
                    max_score=None,
                    passed=None,
                    lineage={
                        "learning_unit_revision_id": summary.learning_unit_revision_id,
                        "competency_keys": list(command.competency_keys),
                    },
                    confidence=1.0,
                    next_action=None,
                    idempotency_key=f"lesson-complete:{summary.detail_id}",
                    trace_id=command.trace_id,
                )
            )
            return
        raise LearningGovernanceError(
            "[LESSON_COMMAND_UNSUPPORTED]", "当前学习活动不支持该命令。", 422
        )

    async def _execute_quiz(
        self, command: ActivityRuntimeCommand, *, detail_id: str
    ) -> None:
        runtime = QuizRuntimeService(
            self._session,
            task_runtime=self._tasks,
            outcomes=self._outcomes,
        )
        if command.command_type == "save_answers":
            await runtime.save_answers(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                detail_id=detail_id,
                answers=tuple(
                    QuizAnswerInput.model_validate(item)
                    for item in command.payload["answers"]
                ),
                expected_version=command.expected_detail_version,
                idempotency_key=command.idempotency_key,
            )
            return
        if command.command_type == "submit":
            await runtime.submit(
                organization_id=command.organization_id,
                learner_id=command.learner_id,
                detail_id=detail_id,
                expected_version=command.expected_detail_version,
                idempotency_key=command.idempotency_key,
            )
            return
        raise LearningGovernanceError(
            "[QUIZ_COMMAND_UNSUPPORTED]", "当前测验不支持该命令。", 422
        )

    @staticmethod
    def _revision_id(activity_type: str, config: dict[str, Any]) -> str:
        try:
            if activity_type == "lesson":
                return str(config["learning_unit_revision_id"])
            if activity_type == "quiz":
                return str(config["quiz_revision_id"])
        except KeyError as exc:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_CONFIG_INVALID]",
                "训练活动配置不完整，请联系培训负责人。",
                422,
            ) from exc
        raise NewcomerTrainingError(
            "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
            "当前训练活动运行器尚未启用。",
            503,
        )

    @staticmethod
    def _result(projection: LearningWorkspaceProjection) -> ActivityRuntimeResult:
        return ActivityRuntimeResult(
            detail_id=projection.detail_id or "not-started",
            detail_status=projection.status,
            detail_version=projection.version,
            task_id=projection.task_id,
            runner=projection.runner,
            available_commands=projection.available_commands,
        )

    @staticmethod
    def _raise_newcomer(exc: LearningGovernanceError) -> None:
        raise NewcomerTrainingError(
            exc.code,
            exc.message,
            exc.status_code,
            details=exc.details,
        ) from exc

    @staticmethod
    def _unsupported() -> None:
        raise LearningGovernanceError(
            "[LEARNING_ACTIVITY_TYPE_UNSUPPORTED]",
            "当前训练活动运行器尚未启用。",
            503,
        )


class CoachActivityRuntimeAdapter(ActivityRuntimePort):
    def __init__(self, session: AsyncSession, *, task_registry: TaskRegistry) -> None:
        self._runtime = StructuredCoachRuntime(
            session,
            tasks=SQLAlchemyTaskRuntime(session, registry=task_registry),
            context_builder=FoundationCoachContextBuilder(session),
            outcomes=SQLAlchemyCoachActivityOutcomeWriter(session),
        )

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_id: str,
        activity_type: str,
        config: dict[str, Any],
        attempt_id: str | None,
    ) -> ActivityRuntimeResult | None:
        del activity_id
        if activity_type != "ai_coach":
            self._unsupported()
        try:
            projection = await self._runtime.workspace(
                organization_id=organization_id,
                learner_id=learner_id,
                profile_revision_id=str(config["coach_profile_revision_id"]),
                attempt_id=attempt_id,
            )
        except (KeyError, TypeError, AICoachError) as exc:
            self._raise(exc)
        return self._result(projection)

    async def start(self, command: ActivityRuntimeStart) -> ActivityRuntimeResult:
        if command.activity_type != "ai_coach":
            self._unsupported()
        try:
            projection = await self._runtime.start_or_resume(
                context=CoachStartContext(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    enrollment_id=command.enrollment_id,
                    path_revision_id=command.path_revision_id,
                    activity_id=command.activity_id,
                    attempt_id=command.attempt_id,
                    profile_revision_id=str(
                        command.config["coach_profile_revision_id"]
                    ),
                    competency_keys=command.competency_keys,
                    trace_id=command.trace_id,
                ),
                idempotency_key=command.idempotency_key,
            )
        except (KeyError, TypeError, ValueError, AICoachError) as exc:
            self._raise(exc)
        return self._result(projection)

    async def execute(self, command: ActivityRuntimeCommand) -> ActivityRuntimeResult:
        if command.activity_type != "ai_coach":
            self._unsupported()
        if command.expected_detail_version is None:
            raise NewcomerTrainingError(
                "[COACH_VERSION_REQUIRED]",
                "训练命令缺少版本，请刷新后重试。",
                412,
            )
        try:
            if command.command_type == "submit_coach_answer":
                projection = await self._runtime.submit_answer(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    payload=SubmitCoachAnswerInput.model_validate(command.payload),
                    expected_version=command.expected_detail_version,
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "continue_coach":
                projection = await self._runtime.continue_training(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    expected_version=command.expected_detail_version,
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "retry_coach":
                projection = await self._runtime.retry_failed(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    expected_version=command.expected_detail_version,
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "request_coach_assistance":
                projection = await self._runtime.request_assistance(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    payload=RequestCoachAssistanceInput.model_validate(command.payload),
                    expected_version=command.expected_detail_version,
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            elif command.command_type == "cancel":
                projection = await self._runtime.cancel(
                    organization_id=command.organization_id,
                    learner_id=command.learner_id,
                    attempt_id=command.attempt_id,
                    expected_version=command.expected_detail_version,
                    idempotency_key=command.idempotency_key,
                    trace_id=command.trace_id,
                )
            else:
                raise AICoachError(
                    "[COACH_COMMAND_UNSUPPORTED]",
                    "当前教练训练不支持该命令。",
                    422,
                )
        except (TypeError, ValueError, AICoachError) as exc:
            self._raise(exc)
        return self._result(projection)

    @staticmethod
    def _result(projection: Any) -> ActivityRuntimeResult:
        return ActivityRuntimeResult(
            detail_id=projection.session_id or "not-started",
            detail_status=projection.status,
            detail_version=projection.version,
            task_id=projection.task_id,
            runner=projection.runner,
            available_commands=projection.available_commands,
        )

    @staticmethod
    def _raise(exc: Exception) -> Never:
        if isinstance(exc, AICoachError):
            raise NewcomerTrainingError(
                exc.code,
                exc.message,
                exc.status_code,
                details=exc.details,
            ) from exc
        raise NewcomerTrainingError(
            "[COACH_COMMAND_INVALID]",
            "教练训练命令内容无效，请刷新后重试。",
            422,
        ) from exc

    @staticmethod
    def _unsupported() -> Never:
        raise NewcomerTrainingError(
            "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
            "当前训练活动运行器尚未启用。",
            503,
        )


class FoundationActivityRuntimeAdapter(ActivityRuntimePort):
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_registry: TaskRegistry,
        audio_storage: AudioObjectStoragePort | None = None,
    ) -> None:
        self._learning = LearningActivityRuntimeAdapter(
            session,
            task_registry=task_registry,
        )
        self._audio = AudioActivityRuntimeAdapter(
            session,
            task_registry=task_registry,
            storage=audio_storage,
        )
        self._coach = CoachActivityRuntimeAdapter(
            session,
            task_registry=task_registry,
        )

    def _adapter(self, activity_type: str) -> ActivityRuntimePort:
        if activity_type in {"lesson", "quiz"}:
            return self._learning
        if activity_type in {"audio_assessment", "assignment"}:
            return self._audio
        if activity_type == "ai_coach":
            return self._coach
        raise NewcomerTrainingError(
            "[NEWCOMER_ACTIVITY_RUNTIME_UNAVAILABLE]",
            "当前训练活动运行器尚未启用。",
            503,
        )

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_id: str,
        activity_type: str,
        config: dict[str, Any],
        attempt_id: str | None,
    ) -> ActivityRuntimeResult | None:
        return await self._adapter(activity_type).workspace(
            organization_id=organization_id,
            learner_id=learner_id,
            activity_id=activity_id,
            activity_type=activity_type,
            config=config,
            attempt_id=attempt_id,
        )

    async def start(self, command: ActivityRuntimeStart) -> ActivityRuntimeResult:
        return await self._adapter(command.activity_type).start(command)

    async def execute(
        self,
        command: ActivityRuntimeCommand,
    ) -> ActivityRuntimeResult:
        return await self._adapter(command.activity_type).execute(command)


__all__ = [
    "AudioActivityRuntimeAdapter",
    "CoachActivityRuntimeAdapter",
    "FoundationActivityRuntimeAdapter",
    "FoundationCoachContextBuilder",
    "FoundationLessonAdministrationService",
    "FoundationPublishedResourceAdapter",
    "LearningActivityRuntimeAdapter",
    "PublishedAudioResourceAdapter",
    "PublishedCoachResourceAdapter",
    "PublishedLearningResourceAdapter",
    "SQLAlchemyActivityOutcomeWriter",
    "SQLAlchemyAudioOutcomeWriter",
    "SQLAlchemyCoachActivityOutcomeWriter",
    "SQLAlchemyFoundationNotificationReader",
]
