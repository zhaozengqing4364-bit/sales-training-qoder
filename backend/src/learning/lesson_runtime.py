"""Versioned lesson progress with checkpoints, invalidation, and relearning."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Never

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.contracts import LearningActor
from learning.errors import LearningGovernanceError
from learning.models import LearningLessonAttempt, LearningLessonCommand


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class LessonAttemptContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    enrollment_id: str = Field(min_length=1, max_length=160)
    path_revision_id: str = Field(min_length=1, max_length=160)
    activity_id: str = Field(min_length=1, max_length=160)
    attempt_id: str = Field(min_length=1, max_length=160)
    learning_unit_revision_id: str = Field(min_length=1, max_length=160)
    required_checkpoint_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    relearn_of_detail_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def require_unique_checkpoints(self) -> LessonAttemptContext:
        if len(set(self.required_checkpoint_ids)) != len(self.required_checkpoint_ids):
            raise ValueError("required_checkpoint_ids must be unique")
        return self


class LessonProgressSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str
    attempt_id: str
    organization_id: str
    learner_id: str
    enrollment_id: str
    activity_id: str
    learning_unit_revision_id: str
    status: str
    version: int
    required_checkpoint_ids: tuple[str, ...]
    completed_checkpoint_ids: tuple[str, ...]
    reading_position: dict[str, Any]
    relearn_of_detail_id: str | None
    started_at: datetime
    last_saved_at: datetime
    completed_at: datetime | None
    invalidated_at: datetime | None


class LessonRuntimeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_or_resume(
        self, *, context: LessonAttemptContext, idempotency_key: str
    ) -> LessonProgressSummary:
        fingerprint = _canonical_hash(context.model_dump(mode="json"))
        existing = await self._session.scalar(
            select(LearningLessonAttempt)
            .where(LearningLessonAttempt.attempt_id == context.attempt_id)
            .limit(1)
        )
        if existing is not None:
            if (
                existing.organization_id != context.organization_id
                or existing.learner_id != context.learner_id
            ):
                self._not_found()
            if (
                existing.start_idempotency_key_hash != _secret_hash(idempotency_key)
                or existing.start_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return self._summary(existing)
        if context.relearn_of_detail_id is not None:
            prior = await self._session.get(
                LearningLessonAttempt, context.relearn_of_detail_id
            )
            if (
                prior is None
                or prior.organization_id != context.organization_id
                or prior.learner_id != context.learner_id
                or prior.activity_id != context.activity_id
                or prior.status != "invalidated"
            ):
                raise LearningGovernanceError(
                    "[LESSON_RELEARN_SOURCE_INVALID]",
                    "只能基于已失效的同一学习活动开始重新学习。",
                    409,
                )
        now = _now()
        row = LearningLessonAttempt(
            detail_id=_id(),
            organization_id=context.organization_id,
            learner_id=context.learner_id,
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity_id,
            attempt_id=context.attempt_id,
            learning_unit_revision_id=context.learning_unit_revision_id,
            status="in_progress",
            version=1,
            required_checkpoint_ids_json=list(context.required_checkpoint_ids),
            completed_checkpoint_ids_json=[],
            reading_position_json={},
            relearn_of_detail_id=context.relearn_of_detail_id,
            start_idempotency_key_hash=_secret_hash(idempotency_key),
            start_fingerprint=fingerprint,
            started_at=now,
            last_saved_at=now,
        )
        self._session.add(row)
        await self._session.flush([row])
        return self._summary(row)

    async def save_progress(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
        completed_checkpoint_ids: tuple[str, ...],
        reading_position: dict[str, Any],
        expected_version: int,
        idempotency_key: str,
    ) -> LessonProgressSummary:
        request = {
            "completed_checkpoint_ids": list(completed_checkpoint_ids),
            "reading_position": reading_position,
            "expected_version": expected_version,
        }
        row = await self._load_for_update(
            organization_id=organization_id,
            learner_id=learner_id,
            detail_id=detail_id,
        )
        replay = await self._command_replay(
            organization_id=organization_id,
            detail_id=detail_id,
            command_type="save_progress",
            idempotency_key=idempotency_key,
            request=request,
        )
        if replay is not None:
            return replay
        self._require_version(row.version, expected_version)
        if row.status != "in_progress":
            raise LearningGovernanceError(
                "[LESSON_STATE_CONFLICT]", "当前学习记录不能继续保存。", 409
            )
        required = set(row.required_checkpoint_ids_json)
        completed = set(completed_checkpoint_ids)
        if not completed.issubset(required):
            raise LearningGovernanceError(
                "[LESSON_CHECKPOINT_INVALID]", "提交了不属于当前学习修订的检查点。", 422
            )
        if not set(row.completed_checkpoint_ids_json).issubset(completed):
            raise LearningGovernanceError(
                "[LESSON_CHECKPOINT_REGRESSION]", "已完成的检查点不能被静默撤销。", 409
            )
        row.completed_checkpoint_ids_json = [
            item for item in row.required_checkpoint_ids_json if item in completed
        ]
        row.reading_position_json = reading_position
        row.version += 1
        row.last_saved_at = _now()
        await self._session.flush([row])
        await self._record_command(
            row=row,
            command_type="save_progress",
            idempotency_key=idempotency_key,
            request=request,
        )
        return self._summary(row)

    async def complete(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
        expected_version: int,
        idempotency_key: str,
    ) -> LessonProgressSummary:
        request = {"expected_version": expected_version}
        row = await self._load_for_update(
            organization_id=organization_id,
            learner_id=learner_id,
            detail_id=detail_id,
        )
        replay = await self._command_replay(
            organization_id=organization_id,
            detail_id=detail_id,
            command_type="complete",
            idempotency_key=idempotency_key,
            request=request,
        )
        if replay is not None:
            return replay
        self._require_version(row.version, expected_version)
        if row.status != "in_progress":
            raise LearningGovernanceError(
                "[LESSON_STATE_CONFLICT]", "当前学习记录不能提交完成。", 409
            )
        missing = set(row.required_checkpoint_ids_json) - set(
            row.completed_checkpoint_ids_json
        )
        if missing:
            raise LearningGovernanceError(
                "[LESSON_CHECKPOINTS_INCOMPLETE]",
                "请先完成全部必修检查点。",
                409,
                details={"missing_checkpoint_ids": sorted(missing)},
            )
        row.status = "completed"
        row.version += 1
        row.completed_at = _now()
        row.last_saved_at = row.completed_at
        await self._session.flush([row])
        await self._record_command(
            row=row,
            command_type="complete",
            idempotency_key=idempotency_key,
            request=request,
        )
        return self._summary(row)

    async def invalidate(
        self,
        *,
        actor: LearningActor,
        detail_id: str,
        expected_version: int,
        reason: str,
        idempotency_key: str,
    ) -> LessonProgressSummary:
        if "learning.lesson.invalidate" not in actor.capabilities:
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]", "没有失效学习结果的权限。", 403
            )
        if not reason.strip():
            raise LearningGovernanceError(
                "[LESSON_INVALIDATION_REASON_REQUIRED]", "请填写失效原因。", 422
            )
        request = {"expected_version": expected_version, "reason": reason.strip()}
        row = await self._session.scalar(
            select(LearningLessonAttempt)
            .where(LearningLessonAttempt.detail_id == detail_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != actor.organization_id:
            self._not_found()
        replay = await self._command_replay(
            organization_id=actor.organization_id,
            detail_id=detail_id,
            command_type="invalidate",
            idempotency_key=idempotency_key,
            request=request,
        )
        if replay is not None:
            return replay
        self._require_version(row.version, expected_version)
        if row.status == "invalidated":
            raise LearningGovernanceError(
                "[LESSON_STATE_CONFLICT]", "该学习结果已经失效。", 409
            )
        row.status = "invalidated"
        row.version += 1
        row.invalidation_reason = reason.strip()
        row.invalidated_at = _now()
        row.last_saved_at = row.invalidated_at
        await self._session.flush([row])
        await self._record_command(
            row=row,
            command_type="invalidate",
            idempotency_key=idempotency_key,
            request=request,
        )
        return self._summary(row)

    async def _command_replay(
        self,
        *,
        organization_id: str,
        detail_id: str,
        command_type: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> LessonProgressSummary | None:
        command = await self._session.scalar(
            select(LearningLessonCommand)
            .where(LearningLessonCommand.detail_id == detail_id)
            .where(LearningLessonCommand.command_type == command_type)
            .where(
                LearningLessonCommand.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if command is None:
            return None
        if command.organization_id != organization_id:
            self._not_found()
        if command.request_fingerprint != _canonical_hash(request):
            self._idempotency_conflict()
        replay: LessonProgressSummary = LessonProgressSummary.model_validate(
            command.result_snapshot_json
        )
        return replay

    async def _record_command(
        self,
        *,
        row: LearningLessonAttempt,
        command_type: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> None:
        self._session.add(
            LearningLessonCommand(
                command_id=_id(),
                detail_id=row.detail_id,
                organization_id=row.organization_id,
                command_type=command_type,
                idempotency_key_hash=_secret_hash(idempotency_key),
                request_fingerprint=_canonical_hash(request),
                result_version=row.version,
                result_snapshot_json=self._summary(row).model_dump(mode="json"),
                created_at=_now(),
            )
        )
        await self._session.flush()

    async def _load_for_update(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
    ) -> LearningLessonAttempt:
        row = await self._session.scalar(
            select(LearningLessonAttempt)
            .where(LearningLessonAttempt.detail_id == detail_id)
            .with_for_update()
            .limit(1)
        )
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            self._not_found()
        return row

    @staticmethod
    def _summary(row: LearningLessonAttempt) -> LessonProgressSummary:
        return LessonProgressSummary(
            detail_id=row.detail_id,
            attempt_id=row.attempt_id,
            organization_id=row.organization_id,
            learner_id=row.learner_id,
            enrollment_id=row.enrollment_id,
            activity_id=row.activity_id,
            learning_unit_revision_id=row.learning_unit_revision_id,
            status=row.status,
            version=row.version,
            required_checkpoint_ids=tuple(row.required_checkpoint_ids_json),
            completed_checkpoint_ids=tuple(row.completed_checkpoint_ids_json),
            reading_position=dict(row.reading_position_json),
            relearn_of_detail_id=row.relearn_of_detail_id,
            started_at=row.started_at,
            last_saved_at=row.last_saved_at,
            completed_at=row.completed_at,
            invalidated_at=row.invalidated_at,
        )

    @staticmethod
    def _require_version(actual: int, expected: int) -> None:
        if actual != expected:
            raise LearningGovernanceError(
                "[LEARNING_VERSION_CONFLICT]",
                "学习进度已更新，请刷新后重试。",
                412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _not_found() -> Never:
        raise LearningGovernanceError(
            "[LESSON_PROGRESS_NOT_FOUND]", "学习进度不存在或不可访问。", 404
        )

    @staticmethod
    def _idempotency_conflict() -> Never:
        raise LearningGovernanceError(
            "[LEARNING_IDEMPOTENCY_CONFLICT]", "相同幂等键对应了不同学习命令。", 409
        )


__all__ = ["LessonAttemptContext", "LessonProgressSummary", "LessonRuntimeService"]
