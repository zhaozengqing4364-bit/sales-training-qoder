from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAudioSubmission,
    SalesTrainerOperationLog,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.phase2_policy import resolve_phase2_policy
from sales_trainer.services.phase2_projection_service import (
    SalesTrainerPhase2ProjectionService,
)
from sales_trainer.services.quiz_service import QuizService
from sales_trainer.services.training_record_lineage import (
    training_record_lineage_fields,
)

RecordKey = tuple[str, str]


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
        keys, total = await self._record_window(
            user_id=user_id,
            unit_id=unit_id,
            material_version_id=material_version_id,
            team_department=team_department,
            limit=limit,
            offset=offset,
        )
        records = await self._serialize_window(keys, include_logs=False)
        policy, _ = await resolve_phase2_policy(self._db)
        enriched = await SalesTrainerPhase2ProjectionService(
            self._db,
            policy=policy,
        ).enrich_records(records)
        return enriched, total

    async def get_record(
        self,
        record_type: str,
        record_id: str,
    ) -> dict[str, Any] | None:
        if record_type == "audio_submission":
            submission = await self._db.get(SalesTrainerAudioSubmission, record_id)
            if submission is None:
                return None
            record = await self._serialize_audio_record(submission, include_logs=True)
        elif record_type == "quiz_attempt":
            attempt = await self._db.get(SalesTrainerQuizAttempt, record_id)
            if attempt is None:
                return None
            record = await self._serialize_quiz_record(attempt, include_logs=True)
        elif record_type == "ai_coach_session":
            session = await self._db.get(SalesTrainerAiCoachSession, record_id)
            if session is None:
                return None
            record = await self._serialize_ai_coach_record(session, include_logs=True)
        else:
            return None
        policy, _ = await resolve_phase2_policy(self._db)
        return await SalesTrainerPhase2ProjectionService(
            self._db,
            policy=policy,
        ).enrich_record_from_database(record)

    async def get_audio_record(self, submission_id: str) -> dict[str, Any] | None:
        return await self.get_record("audio_submission", submission_id)

    async def _record_window(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        material_version_id: str | None,
        team_department: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RecordKey], int]:
        branches = [
            self._audio_window_select(
                user_id=user_id,
                unit_id=unit_id,
                material_version_id=material_version_id,
                team_department=team_department,
            )
        ]
        if material_version_id is None:
            branches.append(
                self._quiz_window_select(
                    user_id=user_id,
                    unit_id=unit_id,
                    team_department=team_department,
                )
            )
            if unit_id is None:
                branches.append(
                    self._ai_coach_window_select(
                        user_id=user_id,
                        team_department=team_department,
                    )
                )
        combined = (
            branches[0].subquery()
            if len(branches) == 1
            else union_all(*branches).subquery()
        )
        total = int(
            await self._db.scalar(select(func.count()).select_from(combined)) or 0
        )
        if total == 0:
            return [], 0
        result = await self._db.execute(
            select(combined.c.record_type, combined.c.record_id)
            .order_by(
                combined.c.submitted_at.desc(),
                combined.c.record_type.asc(),
                combined.c.record_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        keys = [
            (str(row.record_type), str(row.record_id))
            for row in result.all()
        ]
        return keys, total

    def _audio_window_select(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        material_version_id: str | None,
        team_department: str | None,
    ):
        stmt = select(
            literal("audio_submission").label("record_type"),
            SalesTrainerAudioSubmission.submission_id.label("record_id"),
            SalesTrainerAudioSubmission.created_at.label("submitted_at"),
        )
        if user_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.user_id == user_id)
        if unit_id:
            stmt = stmt.where(SalesTrainerAudioSubmission.unit_id == unit_id)
        if material_version_id:
            stmt = stmt.where(
                SalesTrainerAudioSubmission.confirmed_material_version_id
                == material_version_id
            )
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerAudioSubmission.user_id == User.user_id)
            stmt = stmt.where(User.department == team_department)
        return stmt

    def _quiz_window_select(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        team_department: str | None,
    ):
        stmt = select(
            literal("quiz_attempt").label("record_type"),
            SalesTrainerQuizAttempt.attempt_id.label("record_id"),
            SalesTrainerQuizAttempt.submitted_at.label("submitted_at"),
        )
        if user_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.user_id == user_id)
        if unit_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.unit_id == unit_id)
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerQuizAttempt.user_id == User.user_id)
            stmt = stmt.where(User.department == team_department)
        return stmt

    def _ai_coach_window_select(
        self,
        *,
        user_id: str | None,
        team_department: str | None,
    ):
        stmt = select(
            literal("ai_coach_session").label("record_type"),
            SalesTrainerAiCoachSession.session_id.label("record_id"),
            SalesTrainerAiCoachSession.created_at.label("submitted_at"),
        )
        if user_id:
            stmt = stmt.where(SalesTrainerAiCoachSession.user_id == user_id)
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerAiCoachSession.user_id == User.user_id)
            stmt = stmt.where(User.department == team_department)
        return stmt

    async def _serialize_window(
        self,
        keys: list[RecordKey],
        *,
        include_logs: bool,
    ) -> list[dict[str, Any]]:
        if not keys:
            return []
        ids_by_type: dict[str, list[str]] = defaultdict(list)
        for record_type, record_id in keys:
            ids_by_type[record_type].append(record_id)

        serialized: dict[RecordKey, dict[str, Any]] = {}
        if audio_ids := ids_by_type.get("audio_submission"):
            result = await self._db.execute(
                select(SalesTrainerAudioSubmission).where(
                    SalesTrainerAudioSubmission.submission_id.in_(audio_ids)
                )
            )
            for submission in result.scalars().all():
                serialized[("audio_submission", submission.submission_id)] = (
                    await self._serialize_audio_record(
                        submission,
                        include_logs=include_logs,
                    )
                )
        if quiz_ids := ids_by_type.get("quiz_attempt"):
            result = await self._db.execute(
                select(SalesTrainerQuizAttempt).where(
                    SalesTrainerQuizAttempt.attempt_id.in_(quiz_ids)
                )
            )
            for attempt in result.scalars().all():
                serialized[("quiz_attempt", attempt.attempt_id)] = (
                    await self._serialize_quiz_record(
                        attempt,
                        include_logs=include_logs,
                    )
                )
        if ai_coach_ids := ids_by_type.get("ai_coach_session"):
            result = await self._db.execute(
                select(SalesTrainerAiCoachSession).where(
                    SalesTrainerAiCoachSession.session_id.in_(ai_coach_ids)
                )
            )
            for session in result.scalars().all():
                serialized[("ai_coach_session", session.session_id)] = (
                    await self._serialize_ai_coach_record(
                        session,
                        include_logs=include_logs,
                    )
                )
        return [serialized[key] for key in keys if key in serialized]

    async def _serialize_audio_record(
        self,
        submission: SalesTrainerAudioSubmission,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        unit = (
            await self._db.get(SalesTrainerUnit, submission.unit_id)
            if submission.unit_id
            else None
        )
        user = await self._db.get(User, submission.user_id)
        audio_payload = await self._audio.serialize_submission(submission)
        logs = (
            await self._target_logs(
                "sales_trainer_audio_submission",
                submission.submission_id,
            )
            if include_logs
            else []
        )
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
            "ai_coach_session": None,
            "operation_logs": logs,
        }

    async def _serialize_ai_coach_record(
        self,
        session: SalesTrainerAiCoachSession,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        user = await self._db.get(User, session.user_id)
        path_config = (
            session.path_config_snapshot
            if isinstance(session.path_config_snapshot, dict)
            else {}
        )
        lineage = training_record_lineage_fields(path_config)
        logs = (
            await self._target_logs(
                "sales_trainer_ai_coach_session",
                session.session_id,
            )
            if include_logs
            else []
        )
        return {
            "record_id": session.session_id,
            "record_type": "ai_coach_session",
            **lineage,
            "unit_id": "",
            "unit_name": None,
            "unit_type": "ai_coach",
            "user_id": session.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "status": session.status,
            "score": float(session.total_score)
            if session.total_score is not None
            else None,
            "max_score": float(session.max_score)
            if session.max_score is not None
            else None,
            "passed": session.mastery_state == "mastered"
            if session.mastery_state
            else None,
            "submitted_at": session.created_at,
            "material_snapshot": None,
            "score_scheme_snapshot": None,
            "task_brief_snapshot": None,
            "audio_submission": None,
            "quiz_attempt": None,
            "ai_coach_session": {
                "session_id": session.session_id,
                "module_key": session.module_key,
                "mastery_state": session.mastery_state,
                "total_score": float(session.total_score)
                if session.total_score is not None
                else None,
                "max_score": float(session.max_score)
                if session.max_score is not None
                else None,
                "status": session.status,
                "trace_id": session.trace_id,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            },
            "operation_logs": logs,
        }

    async def _serialize_quiz_record(
        self,
        attempt: SalesTrainerQuizAttempt,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        unit = await self._db.get(SalesTrainerUnit, attempt.unit_id)
        user = await self._db.get(User, attempt.user_id)
        quiz_payload = await self._quiz.serialize_attempt(attempt)
        logs = (
            await self._target_logs(
                "sales_trainer_quiz_attempt",
                attempt.attempt_id,
            )
            if include_logs
            else []
        )
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
            "score": float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            "max_score": float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            "passed": attempt.passed,
            "submitted_at": attempt.submitted_at,
            "material_snapshot": None,
            "score_scheme_snapshot": None,
            "task_brief_snapshot": None,
            "audio_submission": None,
            "quiz_attempt": quiz_payload,
            "ai_coach_session": None,
            "operation_logs": logs,
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
