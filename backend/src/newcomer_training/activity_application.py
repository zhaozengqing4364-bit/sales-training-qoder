"""Single learner activity workspace and closed command orchestration."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import (
    RequestCoachAssistanceInput,
    SubmitCoachAnswerInput,
)
from audio_assessment.contracts import (
    ConfirmUploadPartInput,
    CreateUploadSessionInput,
    FinalizeUploadInput,
    SubmissionCommandInput,
)
from newcomer_training.activity import ActivityAttemptService, ActivityAttemptSummary
from newcomer_training.application import CommandActor
from newcomer_training.contracts import ActivityDefinitionValue, PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerPathRevision,
)
from newcomer_training.ports import (
    ActivityRuntimeCommand,
    ActivityRuntimePort,
    ActivityRuntimeResult,
    ActivityRuntimeStart,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class StartPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relearn_of_detail_id: str | None = Field(default=None, max_length=160)


class StartActivityCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["start", "start_relearn"]
    attempt_id: None = None
    expected_enrollment_version: int = Field(ge=1)
    expected_attempt_version: None = None
    payload: StartPayload = Field(default_factory=StartPayload)


class LessonProgressPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    completed_checkpoint_ids: tuple[str, ...] = Field(max_length=100)
    reading_position: dict[str, Any] = Field(default_factory=dict)


class SaveLessonProgressCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["save_progress"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: LessonProgressPayload


class EmptyPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CompleteLessonCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["complete"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class QuizAnswerPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_revision_id: str = Field(min_length=1, max_length=160)
    selected_option_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    text_answer: str | None = Field(default=None, max_length=20_000)


class SaveQuizAnswersPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    answers: tuple[QuizAnswerPayload, ...] = Field(min_length=1, max_length=200)


class SaveQuizAnswersCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["save_answers"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: SaveQuizAnswersPayload


class SubmitQuizCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["submit"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class CreateAudioUploadSessionCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["create_upload_session"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: CreateUploadSessionInput


class ConfirmAudioUploadPartCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["confirm_upload_part"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: ConfirmUploadPartInput


class FinalizeAudioUploadCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["finalize_upload"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: FinalizeUploadInput


class RetryAudioStageCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["retry_stage"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: SubmissionCommandInput


class CancelAudioRunCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["cancel"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class SubmitCoachAnswerCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["submit_coach_answer"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: SubmitCoachAnswerInput


class ContinueCoachCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["continue_coach"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class RetryCoachCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["retry_coach"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


class RequestCoachAssistanceCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: Literal["request_coach_assistance"]
    attempt_id: str = Field(min_length=1, max_length=160)
    expected_enrollment_version: None = None
    expected_attempt_version: int = Field(ge=1)
    payload: RequestCoachAssistanceInput


ActivityCommandValue = Annotated[
    StartActivityCommand
    | SaveLessonProgressCommand
    | CompleteLessonCommand
    | SaveQuizAnswersCommand
    | SubmitQuizCommand
    | CreateAudioUploadSessionCommand
    | ConfirmAudioUploadPartCommand
    | FinalizeAudioUploadCommand
    | RetryAudioStageCommand
    | CancelAudioRunCommand
    | SubmitCoachAnswerCommand
    | ContinueCoachCommand
    | RetryCoachCommand
    | RequestCoachAssistanceCommand,
    Field(discriminator="command_type"),
]


class ActivityWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["activity_workspace_v1"] = "activity_workspace_v1"
    generated_at: datetime
    data_freshness: Literal["fresh"] = "fresh"
    capabilities: tuple[str, ...]
    enrollment_version: int
    activity: dict[str, Any]
    attempt: ActivityAttemptSummary | None
    runner: dict[str, Any]
    task: dict[str, Any] | None
    outcome: dict[str, Any] | None
    available_commands: tuple[str, ...]
    recovery: dict[str, Any]


class ActivityApplicationService:
    """Coordinates one generic attempt with exactly one typed activity runtime."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        runtime: ActivityRuntimePort,
    ) -> None:
        self._session = session
        self._runtime = runtime
        self._attempts = ActivityAttemptService(session)

    async def get_workspace(
        self,
        *,
        actor: CommandActor,
        activity_id: str,
    ) -> ActivityWorkspace:
        self._require_execute(actor)
        enrollment, activity = await self._load_activity(
            actor=actor,
            activity_id=activity_id,
            lock_enrollment=False,
        )
        latest = await self._latest_attempt(enrollment.enrollment_id, activity_id)
        runtime = await self._runtime.workspace(
            organization_id=actor.organization_id,
            learner_id=actor.actor_id,
            activity_id=activity.activity_id,
            activity_type=str(activity.type),
            config=activity.config.model_dump(mode="json"),
            attempt_id=latest.attempt_id if latest is not None else None,
        )
        return await self._workspace(
            enrollment_version=enrollment.version,
            activity=activity,
            attempt=latest,
            runtime=runtime,
        )

    async def execute(
        self,
        *,
        actor: CommandActor,
        activity_id: str,
        command: ActivityCommandValue,
        idempotency_key: str,
    ) -> ActivityWorkspace:
        self._require_execute(actor)
        enrollment, activity = await self._load_activity(
            actor=actor,
            activity_id=activity_id,
            lock_enrollment=True,
        )
        self._validate_command_type(activity, command.command_type)
        if isinstance(command, StartActivityCommand):
            attempt_summary = await self._attempts.start_attempt(
                actor=actor,
                activity_id=activity_id,
                expected_enrollment_version=command.expected_enrollment_version,
                idempotency_key=idempotency_key,
                allow_relearn=command.command_type == "start_relearn",
            )
            runtime_result = await self._runtime.start(
                ActivityRuntimeStart(
                    organization_id=actor.organization_id,
                    learner_id=actor.actor_id,
                    enrollment_id=enrollment.enrollment_id,
                    path_revision_id=enrollment.path_revision_id,
                    activity_id=activity.activity_id,
                    activity_type=str(activity.type),
                    attempt_id=attempt_summary.attempt_id,
                    config=activity.config.model_dump(mode="json"),
                    competency_keys=activity.competency_keys,
                    idempotency_key=idempotency_key,
                    trace_id=actor.trace_id,
                    relearn_of_detail_id=command.payload.relearn_of_detail_id,
                )
            )
            attempt = await self._load_attempt(actor, attempt_summary.attempt_id)
        else:
            attempt = await self._load_attempt(
                actor, command.attempt_id, for_update=True
            )
            if attempt.activity_id != activity.activity_id:
                raise NewcomerTrainingError(
                    "[NEWCOMER_ACTIVITY_ATTEMPT_MISMATCH]",
                    "训练记录与当前活动不匹配。",
                    409,
                )
            if attempt.status in {"completed", "failed", "cancelled"}:
                raise NewcomerTrainingError(
                    "[NEWCOMER_ATTEMPT_STATE_CONFLICT]",
                    "当前训练记录已经结束，不能继续执行该命令。",
                    409,
                )
            runtime_result = await self._runtime.execute(
                ActivityRuntimeCommand(
                    organization_id=actor.organization_id,
                    learner_id=actor.actor_id,
                    attempt_id=attempt.attempt_id,
                    activity_id=activity.activity_id,
                    activity_type=str(activity.type),
                    command_type=command.command_type,
                    expected_detail_version=command.expected_attempt_version,
                    payload=command.payload.model_dump(mode="json"),
                    config=activity.config.model_dump(mode="json"),
                    competency_keys=activity.competency_keys,
                    idempotency_key=idempotency_key,
                    trace_id=actor.trace_id,
                )
            )
            await self._audit_runtime_command(
                actor=actor,
                attempt=attempt,
                command_type=command.command_type,
                idempotency_key=idempotency_key,
                detail_version=runtime_result.detail_version,
            )
        attempt = await self._load_attempt(actor, attempt.attempt_id, populate=True)
        if (
            runtime_result.task_id is not None
            and attempt.task_id is None
            and attempt.status in {"started", "in_progress", "submitted"}
        ):
            await self._attempts.mark_processing(
                organization_id=actor.organization_id,
                attempt_id=attempt.attempt_id,
                task_id=runtime_result.task_id,
                expected_attempt_version=attempt.version,
            )
            attempt = await self._load_attempt(actor, attempt.attempt_id, populate=True)
        return await self._workspace(
            enrollment_version=enrollment.version,
            activity=activity,
            attempt=attempt,
            runtime=runtime_result,
        )

    async def _load_activity(
        self,
        *,
        actor: CommandActor,
        activity_id: str,
        lock_enrollment: bool,
    ) -> tuple[NewcomerEnrollment, ActivityDefinitionValue]:
        query = (
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == actor.organization_id)
            .where(NewcomerEnrollment.learner_id == actor.actor_id)
            .where(NewcomerEnrollment.status == "active")
            .limit(1)
        )
        if lock_enrollment:
            query = query.with_for_update()
        enrollment = await self._session.scalar(query)
        if enrollment is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_NOT_FOUND]",
                "尚未分配可执行的新人训练。",
                404,
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
        await self._attempts.require_activity_unlocked(
            enrollment=enrollment,
            draft=draft,
            activity_id=activity.activity_id,
        )
        return enrollment, activity

    async def _latest_attempt(
        self, enrollment_id: str, activity_id: str
    ) -> NewcomerActivityAttempt | None:
        row: NewcomerActivityAttempt | None = await self._session.scalar(
            select(NewcomerActivityAttempt)
            .where(NewcomerActivityAttempt.enrollment_id == enrollment_id)
            .where(NewcomerActivityAttempt.activity_id == activity_id)
            .order_by(desc(NewcomerActivityAttempt.attempt_no))
            .limit(1)
        )
        return row

    async def _load_attempt(
        self,
        actor: CommandActor,
        attempt_id: str,
        *,
        for_update: bool = False,
        populate: bool = False,
    ) -> NewcomerActivityAttempt:
        query = select(NewcomerActivityAttempt).where(
            NewcomerActivityAttempt.attempt_id == attempt_id
        )
        if for_update:
            query = query.with_for_update()
        if populate:
            query = query.execution_options(populate_existing=True)
        row = await self._session.scalar(query.limit(1))
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_NOT_FOUND]",
                "训练记录不存在或不可访问。",
                404,
            )
        enrollment = await self._session.get(NewcomerEnrollment, row.enrollment_id)
        if enrollment is None or enrollment.learner_id != actor.actor_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ATTEMPT_NOT_FOUND]",
                "训练记录不存在或不可访问。",
                404,
            )
        return row

    async def _workspace(
        self,
        *,
        enrollment_version: int,
        activity: ActivityDefinitionValue,
        attempt: NewcomerActivityAttempt | None,
        runtime: ActivityRuntimeResult | None,
    ) -> ActivityWorkspace:
        outcome = None
        if attempt is not None and attempt.outcome_id is not None:
            row = await self._session.get(NewcomerActivityOutcome, attempt.outcome_id)
            if row is not None:
                outcome = {
                    "lifecycle_result": row.lifecycle_result,
                    "assessment_result": row.assessment_result,
                    "score": float(row.score) if row.score is not None else None,
                    "max_score": (
                        float(row.max_score) if row.max_score is not None else None
                    ),
                    "passed": row.passed,
                    "next_action": row.next_action_json,
                    "produced_at": row.produced_at,
                }
        task = (
            {"task_id": runtime.task_id, "state": "processing"}
            if runtime is not None and runtime.task_id is not None
            else None
        )
        return ActivityWorkspace(
            generated_at=_now(),
            capabilities=("view_activity", "execute_activity"),
            enrollment_version=enrollment_version,
            activity={
                "id": activity.activity_id,
                "type": str(activity.type),
                "title": activity.title,
                "objective": activity.objective,
                "why_it_matters": activity.why_it_matters,
                "steps": list(activity.steps),
                "success_criteria": list(activity.success_criteria),
                "estimated_minutes": activity.estimated_minutes,
            },
            attempt=(
                ActivityAttemptSummary.model_validate(attempt)
                if attempt is not None
                else None
            ),
            runner=(
                {
                    **runtime.runner,
                    "detail_id": runtime.detail_id,
                    "status": runtime.detail_status,
                    "version": runtime.detail_version,
                }
                if runtime is not None
                else {}
            ),
            task=task,
            outcome=outcome,
            available_commands=(
                runtime.available_commands if runtime is not None else ("start",)
            ),
            recovery={
                "input_preserved": True,
                "refresh_on_version_conflict": True,
                "retry_from_current_activity": True,
            },
        )

    async def _audit_runtime_command(
        self,
        *,
        actor: CommandActor,
        attempt: NewcomerActivityAttempt,
        command_type: str,
        idempotency_key: str,
        detail_version: int,
    ) -> None:
        key_hash = _secret_hash(idempotency_key)
        existing = await self._session.scalar(
            select(NewcomerCommandAudit.audit_id)
            .where(NewcomerCommandAudit.object_id == attempt.attempt_id)
            .where(NewcomerCommandAudit.command == command_type)
            .where(NewcomerCommandAudit.idempotency_key_hash == key_hash)
            .limit(1)
        )
        if existing is not None:
            return
        row = NewcomerCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability="newcomer.activity.execute",
            object_type="activity_attempt",
            object_id=attempt.attempt_id,
            command=command_type,
            before_version=attempt.version,
            after_version=attempt.version,
            idempotency_key_hash=key_hash,
            expected_version=None,
            actual_version=None,
            trace_id=actor.trace_id,
            result="succeeded",
            details_json={"detail_version": detail_version},
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])

    @staticmethod
    def _validate_command_type(
        activity: ActivityDefinitionValue, command_type: str
    ) -> None:
        allowed = {
            "lesson": {"start", "start_relearn", "save_progress", "complete"},
            "quiz": {"start", "save_answers", "submit"},
            "audio_assessment": {
                "start",
                "create_upload_session",
                "confirm_upload_part",
                "finalize_upload",
                "retry_stage",
                "cancel",
            },
            "assignment": {
                "start",
                "create_upload_session",
                "confirm_upload_part",
                "finalize_upload",
                "retry_stage",
                "cancel",
            },
            "ai_coach": {
                "start",
                "submit_coach_answer",
                "continue_coach",
                "retry_coach",
                "request_coach_assistance",
                "cancel",
            },
        }.get(str(activity.type), set())
        if command_type not in allowed:
            raise NewcomerTrainingError(
                "[NEWCOMER_ACTIVITY_COMMAND_UNSUPPORTED]",
                "当前训练活动不支持该命令。",
                422,
            )

    @staticmethod
    def _require_execute(actor: CommandActor) -> None:
        if "newcomer.activity.execute" not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]",
                "没有执行训练活动的权限。",
                403,
            )


__all__ = [
    "ActivityApplicationService",
    "ActivityCommandValue",
    "ActivityWorkspace",
    "CancelAudioRunCommand",
    "ContinueCoachCommand",
    "ConfirmAudioUploadPartCommand",
    "CompleteLessonCommand",
    "CreateAudioUploadSessionCommand",
    "FinalizeAudioUploadCommand",
    "RequestCoachAssistanceCommand",
    "RetryCoachCommand",
    "RetryAudioStageCommand",
    "SaveLessonProgressCommand",
    "SaveQuizAnswersCommand",
    "StartActivityCommand",
    "SubmitCoachAnswerCommand",
    "SubmitQuizCommand",
]
