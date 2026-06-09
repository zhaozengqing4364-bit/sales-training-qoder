from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioSubmission,
    SalesTrainerOperationLog,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.quiz_service import QuizService
from sales_trainer.services.training_record_lineage import (
    training_record_lineage_fields,
)


class TrainingRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audio = AudioSubmissionService(db)
        self._quiz = QuizService(db)
        self._logs = OperationLogService(db)

    async def list_records(
        self,
        *,
        user_id: str | None = None,
        unit_id: str | None = None,
        material_version_id: str | None = None,
        team_department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        audio_records, audio_total = await self._list_audio_records(
            user_id=user_id,
            unit_id=unit_id,
            material_version_id=material_version_id,
            team_department=team_department,
        )
        quiz_records, quiz_total = await self._list_quiz_records(
            user_id=user_id,
            unit_id=unit_id,
            team_department=team_department,
            include=material_version_id is None,
        )
        records = sorted(
            [*audio_records, *quiz_records],
            key=lambda item: item.get("submitted_at") or "",
            reverse=True,
        )
        return records[offset : offset + limit], audio_total + quiz_total

    async def get_audio_record(self, submission_id: str) -> dict[str, Any] | None:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            return None
        return await self._serialize_audio_record(submission, include_logs=True)

    async def _list_audio_records(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        material_version_id: str | None,
        team_department: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(SalesTrainerAudioSubmission)
        count_stmt = select(func.count()).select_from(SalesTrainerAudioSubmission)
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if unit_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.unit_id == unit_id)
            count_stmt = count_stmt.where(SalesTrainerAudioSubmission.unit_id == unit_id)
        if material_version_id:
            stmt = stmt.where(
                SalesTrainerAudioSubmission.confirmed_material_version_id
                == material_version_id
            )
            count_stmt = count_stmt.where(
                SalesTrainerAudioSubmission.confirmed_material_version_id
                == material_version_id
            )
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerAudioSubmission.user_id == User.user_id)
            count_stmt = count_stmt.join(
                User,
                SalesTrainerAudioSubmission.user_id == User.user_id,
            )
            stmt = stmt.where(User.department == team_department)
            count_stmt = count_stmt.where(User.department == team_department)
        result = await self._db.execute(
            stmt.order_by(SalesTrainerAudioSubmission.created_at.desc()).limit(500)
        )
        total = await self._db.scalar(count_stmt)
        records = [
            await self._serialize_audio_record(submission, include_logs=False)
            for submission in result.scalars().all()
        ]
        return records, int(total or 0)

    async def _list_quiz_records(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        team_department: str | None,
        include: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        if not include:
            return [], 0
        stmt = select(SalesTrainerQuizAttempt)
        count_stmt = select(func.count()).select_from(SalesTrainerQuizAttempt)
        if user_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerQuizAttempt.user_id == user_id)
        if unit_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.unit_id == unit_id)
            count_stmt = count_stmt.where(SalesTrainerQuizAttempt.unit_id == unit_id)
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerQuizAttempt.user_id == User.user_id)
            count_stmt = count_stmt.join(
                User,
                SalesTrainerQuizAttempt.user_id == User.user_id,
            )
            stmt = stmt.where(User.department == team_department)
            count_stmt = count_stmt.where(User.department == team_department)
        result = await self._db.execute(
            stmt.order_by(SalesTrainerQuizAttempt.submitted_at.desc()).limit(500)
        )
        total = await self._db.scalar(count_stmt)
        records = [
            await self._serialize_quiz_record(attempt)
            for attempt in result.scalars().all()
        ]
        return records, int(total or 0)

    async def _serialize_audio_record(
        self,
        submission: SalesTrainerAudioSubmission,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        unit = await self._db.get(SalesTrainerUnit, submission.unit_id) if submission.unit_id else None
        user = await self._db.get(User, submission.user_id)
        audio_payload = await self._audio.serialize_submission(submission)
        logs = await self._target_logs(
            "sales_trainer_audio_submission",
            submission.submission_id,
        ) if include_logs else []
        score = audio_payload.get("score_result") or {}
        lineage = training_record_lineage_fields(audio_payload)
        return {
            "record_id": submission.submission_id,
            "record_type": "audio_submission",
            **lineage,
            "unit_id": submission.unit_id or "",
            "unit_name": unit.name if unit else None,
            "unit_type": unit.unit_type if unit else "audio_scoring",
            "user_id": submission.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "status": submission.status,
            "score": score.get("total_score") if isinstance(score, dict) else None,
            "max_score": 100,
            "passed": score.get("passed") if isinstance(score, dict) else None,
            "submitted_at": submission.created_at,
            "material_snapshot": submission.material_snapshot,
            "score_scheme_snapshot": submission.score_scheme_snapshot,
            "task_brief_snapshot": submission.task_brief_snapshot,
            "audio_submission": audio_payload,
            "quiz_attempt": None,
            "operation_logs": logs,
        }

    async def _serialize_quiz_record(
        self,
        attempt: SalesTrainerQuizAttempt,
    ) -> dict[str, Any]:
        unit = await self._db.get(SalesTrainerUnit, attempt.unit_id)
        user = await self._db.get(User, attempt.user_id)
        quiz_payload = await self._quiz.serialize_attempt(attempt)
        lineage = training_record_lineage_fields(quiz_payload)
        return {
            "record_id": attempt.attempt_id,
            "record_type": "quiz_attempt",
            **lineage,
            "unit_id": attempt.unit_id,
            "unit_name": unit.name if unit else None,
            "unit_type": unit.unit_type if unit else "quiz",
            "user_id": attempt.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "status": attempt.status,
            "score": float(attempt.total_score) if attempt.total_score is not None else None,
            "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
            "passed": attempt.passed,
            "submitted_at": attempt.submitted_at,
            "material_snapshot": None,
            "score_scheme_snapshot": None,
            "task_brief_snapshot": None,
            "audio_submission": None,
            "quiz_attempt": quiz_payload,
            "operation_logs": [],
        }

    async def _target_logs(
        self,
        target_type: str,
        target_id: str,
    ) -> list[dict[str, Any]]:
        logs, _ = await self._logs.list_logs(
            target_type=target_type,
            target_id=target_id,
            limit=100,
        )
        return [_serialize_operation_log(log) for log in logs]


def _serialize_operation_log(log: SalesTrainerOperationLog) -> dict[str, Any]:
    return {
        "log_id": log.log_id,
        "actor_id": log.actor_id,
        "actor_role": log.actor_role,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "request_id": log.request_id,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "metadata": log.metadata_json or {},
        "created_at": log.created_at,
    }
