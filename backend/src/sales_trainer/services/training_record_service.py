from __future__ import annotations

from collections import defaultdict
from typing import Any, cast

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import json_dict_or_empty, orm_scalar
from common.services.runtime_outcome_projection import (
    RuntimeOutcomeProjection,
    RuntimeOutcomeProjectionService,
)
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAiCoachSession,
    SalesTrainerAudioSubmission,
    SalesTrainerBusinessEtiquetteQuizAttempt,
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
BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE = "business_etiquette_quiz_attempt"
REALTIME_ROLEPLAY_RECORD_TYPE = "realtime_roleplay_session"
REALTIME_ROLEPLAY_OWNER = "sales_trainer"


class TrainingRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audio = AudioSubmissionService(db)
        self._quiz = QuizService(db)
        self._logs = OperationLogService(db)
        self._runtime_outcomes = RuntimeOutcomeProjectionService(db)

    async def list_records(
        self,
        *,
        user_id: str | None = None,
        unit_id: str | None = None,
        material_version_id: str | None = None,
        team_department: str | None = None,
        training_stage: str | None = None,
        module_key: str | None = None,
        learner_level: str | None = None,
        role_level: str | None = None,
        status: str | None = None,
        activity_id: str | None = None,
        activity_type: str | None = None,
        phase_id: str | None = None,
        module_id: str | None = None,
        viewer: User | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        advanced_filter = _advanced_record_filter_present(
            training_stage=training_stage,
            module_key=module_key,
            learner_level=learner_level,
            role_level=role_level,
            status=status,
            activity_id=activity_id,
            activity_type=activity_type,
            phase_id=phase_id,
            module_id=module_id,
        )
        keys, total = await self._record_window(
            user_id=user_id,
            unit_id=unit_id,
            material_version_id=material_version_id,
            team_department=team_department,
            limit=None if advanced_filter else limit,
            offset=0 if advanced_filter else offset,
        )
        records = await self._serialize_window(keys, include_logs=False)
        policy, _ = await resolve_phase2_policy(self._db)
        enriched = await SalesTrainerPhase2ProjectionService(
            self._db,
            policy=policy,
        ).enrich_records(records)
        enriched = await self._attach_journey_context(
            enriched,
            viewer=viewer,
            team_department=team_department,
        )
        if advanced_filter:
            enriched = [
                record
                for record in enriched
                if _record_matches_filters(
                    record,
                    training_stage=training_stage,
                    module_key=module_key,
                    learner_level=learner_level,
                    role_level=role_level,
                    status=status,
                    activity_id=activity_id,
                    activity_type=activity_type,
                    phase_id=phase_id,
                    module_id=module_id,
                )
            ]
            return enriched[offset : offset + limit], len(enriched)
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
        elif record_type == BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE:
            business_attempt = await self._db.get(
                SalesTrainerBusinessEtiquetteQuizAttempt,
                record_id,
            )
            if business_attempt is None:
                return None
            record = await self._serialize_business_etiquette_quiz_record(
                business_attempt,
                include_logs=True,
            )
        elif record_type == REALTIME_ROLEPLAY_RECORD_TYPE:
            projection = await self._runtime_outcomes.get_completed_external_binding(
                owner=REALTIME_ROLEPLAY_OWNER,
                source_record_id=record_id,
            )
            if projection is None:
                return None
            record = await self._serialize_realtime_record(
                projection,
                include_logs=True,
            )
        elif record_type == "newcomer_activity_attempt":
            activity_attempt = await self._db.get(
                NewcomerTrainingActivityAttempt, record_id
            )
            if activity_attempt is None:
                return None
            record = await self._serialize_activity_attempt(activity_attempt)
        else:
            return None
        policy, _ = await resolve_phase2_policy(self._db)
        return cast(
            dict[str, Any] | None,
            await SalesTrainerPhase2ProjectionService(
                self._db,
                policy=policy,
            ).enrich_record_from_database(record),
        )

    async def get_record_for_viewer(
        self,
        record_type: str,
        record_id: str,
        *,
        viewer: User,
        team_department: str | None,
    ) -> dict[str, Any] | None:
        record = await self.get_record(record_type, record_id)
        if record is None:
            return None
        if (
            team_department is not None
            and record.get("user_department") != team_department
        ):
            return None
        enriched = await self._attach_journey_context(
            [record],
            viewer=viewer,
            team_department=team_department,
        )
        if enriched:
            return enriched[0]
        return record

    async def get_audio_record(self, submission_id: str) -> dict[str, Any] | None:
        return await self.get_record("audio_submission", submission_id)

    async def _record_window(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        material_version_id: str | None,
        team_department: str | None,
        limit: int | None,
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
        branches.append(
            self._activity_attempt_window_select(
                user_id=user_id,
                team_department=team_department,
            )
        )
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
                branches.append(
                    self._business_etiquette_quiz_window_select(
                        user_id=user_id,
                        team_department=team_department,
                    )
                )
                branches.append(
                    self._runtime_outcomes.completed_external_binding_window_select(
                        owner=REALTIME_ROLEPLAY_OWNER,
                        record_type=REALTIME_ROLEPLAY_RECORD_TYPE,
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
        stmt = select(combined.c.record_type, combined.c.record_id).order_by(
            combined.c.submitted_at.desc(),
            combined.c.record_type.asc(),
            combined.c.record_id.desc(),
        )
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        keys = [(str(row.record_type), str(row.record_id)) for row in result.all()]
        return keys, total

    def _activity_attempt_window_select(
        self, *, user_id: str | None, team_department: str | None
    ) -> Any:
        stmt = select(
            literal("newcomer_activity_attempt").label("record_type"),
            NewcomerTrainingActivityAttempt.attempt_id.label("record_id"),
            NewcomerTrainingActivityAttempt.created_at.label("submitted_at"),
        ).join(
            NewcomerTrainingEnrollment,
            NewcomerTrainingEnrollment.enrollment_id
            == NewcomerTrainingActivityAttempt.enrollment_id,
        )
        if user_id:
            stmt = stmt.where(NewcomerTrainingEnrollment.learner_id == user_id)
        if team_department is not None:
            stmt = stmt.join(
                User, NewcomerTrainingEnrollment.learner_id == User.user_id
            ).where(User.department == team_department)
        return stmt

    def _audio_window_select(
        self,
        *,
        user_id: str | None,
        unit_id: str | None,
        material_version_id: str | None,
        team_department: str | None,
    ) -> Any:
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
    ) -> Any:
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
    ) -> Any:
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

    def _business_etiquette_quiz_window_select(
        self,
        *,
        user_id: str | None,
        team_department: str | None,
    ) -> Any:
        stmt = select(
            literal(BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE).label("record_type"),
            SalesTrainerBusinessEtiquetteQuizAttempt.attempt_id.label("record_id"),
            SalesTrainerBusinessEtiquetteQuizAttempt.submitted_at.label("submitted_at"),
        )
        if user_id:
            stmt = stmt.where(
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == user_id
            )
        if team_department is not None:
            stmt = stmt.join(
                User,
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == User.user_id,
            )
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
            audio_result = await self._db.execute(
                select(SalesTrainerAudioSubmission).where(
                    SalesTrainerAudioSubmission.submission_id.in_(audio_ids)
                )
            )
            for submission in audio_result.scalars().all():
                submission_id = orm_scalar(submission.submission_id, str)
                serialized[
                    ("audio_submission", submission_id)
                ] = await self._serialize_audio_record(
                    submission,
                    include_logs=include_logs,
                )
        if quiz_ids := ids_by_type.get("quiz_attempt"):
            quiz_result = await self._db.execute(
                select(SalesTrainerQuizAttempt).where(
                    SalesTrainerQuizAttempt.attempt_id.in_(quiz_ids)
                )
            )
            for attempt in quiz_result.scalars().all():
                attempt_id = orm_scalar(attempt.attempt_id, str)
                serialized[
                    ("quiz_attempt", attempt_id)
                ] = await self._serialize_quiz_record(
                    attempt,
                    include_logs=include_logs,
                )
        if ai_coach_ids := ids_by_type.get("ai_coach_session"):
            ai_coach_result = await self._db.execute(
                select(SalesTrainerAiCoachSession).where(
                    SalesTrainerAiCoachSession.session_id.in_(ai_coach_ids)
                )
            )
            for session in ai_coach_result.scalars().all():
                session_id = orm_scalar(session.session_id, str)
                serialized[
                    ("ai_coach_session", session_id)
                ] = await self._serialize_ai_coach_record(
                    session,
                    include_logs=include_logs,
                )
        if business_quiz_ids := ids_by_type.get(BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE):
            business_quiz_result = await self._db.execute(
                select(SalesTrainerBusinessEtiquetteQuizAttempt).where(
                    SalesTrainerBusinessEtiquetteQuizAttempt.attempt_id.in_(
                        business_quiz_ids
                    )
                )
            )
            for business_attempt in business_quiz_result.scalars().all():
                attempt_id = orm_scalar(business_attempt.attempt_id, str)
                serialized[
                    (BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE, attempt_id)
                ] = await self._serialize_business_etiquette_quiz_record(
                    business_attempt,
                    include_logs=include_logs,
                )
        if realtime_ids := ids_by_type.get(REALTIME_ROLEPLAY_RECORD_TYPE):
            projections = (
                await self._runtime_outcomes.list_completed_external_bindings_by_ids(
                    owner=REALTIME_ROLEPLAY_OWNER,
                    source_record_ids=realtime_ids,
                )
            )
            for projection in projections:
                serialized[
                    (REALTIME_ROLEPLAY_RECORD_TYPE, projection.source_record_id)
                ] = await self._serialize_realtime_record(
                    projection,
                    include_logs=include_logs,
                )
        if activity_attempt_ids := ids_by_type.get("newcomer_activity_attempt"):
            result = await self._db.execute(
                select(NewcomerTrainingActivityAttempt).where(
                    NewcomerTrainingActivityAttempt.attempt_id.in_(activity_attempt_ids)
                )
            )
            for activity_attempt in result.scalars().all():
                attempt_id = str(activity_attempt.attempt_id)
                serialized[
                    ("newcomer_activity_attempt", attempt_id)
                ] = await self._serialize_activity_attempt(activity_attempt)
        return [serialized[key] for key in keys if key in serialized]

    async def _serialize_activity_attempt(
        self, attempt: NewcomerTrainingActivityAttempt
    ) -> dict[str, Any]:
        enrollment = await self._db.get(
            NewcomerTrainingEnrollment, str(attempt.enrollment_id)
        )
        snapshot = json_dict_or_empty(attempt.activity_snapshot)
        return {
            "record_type": "newcomer_activity_attempt",
            "record_id": str(attempt.attempt_id),
            "evidence_id": str(attempt.evidence_id or attempt.attempt_id),
            "user_id": str(enrollment.learner_id) if enrollment else None,
            "enrollment_id": str(attempt.enrollment_id),
            "path_revision_id": str(attempt.path_revision_id),
            "activity_id": str(attempt.activity_id),
            "activity_type": str(attempt.activity_type),
            "phase_id": _snapshot_context_value(snapshot, "phase_id"),
            "module_id": _snapshot_context_value(snapshot, "module_id"),
            "phase_title": _snapshot_context_value(snapshot, "phase_title"),
            "module_title": _snapshot_context_value(snapshot, "module_title"),
            "activity_title": snapshot.get("title"),
            "status": str(attempt.status),
            "score": float(attempt.score) if attempt.score is not None else None,
            "max_score": float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            "passed": bool(attempt.passed) if attempt.passed is not None else None,
            "submitted_at": attempt.created_at,
            "completed_at": attempt.completed_at,
            "evidence_type": attempt.evidence_type,
            "source_evidence_id": attempt.evidence_id,
        }

    async def _attach_journey_context(
        self,
        records: list[dict[str, Any]],
        *,
        viewer: User | None,
        team_department: str | None,
    ) -> list[dict[str, Any]]:
        if not records or viewer is None:
            return records
        from sales_trainer.services.training_journey_service import (
            TrainingJourneyError,
            TrainingJourneyService,
        )

        service = TrainingJourneyService(self._db)
        journeys_by_user: dict[str, dict[str, Any] | None] = {}
        for record in records:
            learner_id = str(record.get("user_id") or "")
            if not learner_id or learner_id in journeys_by_user:
                continue
            try:
                journeys_by_user[learner_id] = await service.get_admin_journey(
                    learner_id,
                    viewer=viewer,
                    team_department=team_department,
                )
            except TrainingJourneyError:
                journeys_by_user[learner_id] = None
        for record in records:
            journey = journeys_by_user.get(str(record.get("user_id") or ""))
            if journey is None:
                continue
            record["training_stage"] = journey.get("training_stage")
            record["learner_level"] = journey.get("learner_level")
            record["role_level"] = journey.get("role_level")
            _attach_training_context_to_logs(record, journey)
        return records

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
                orm_scalar(submission.submission_id, str),
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
            "business_etiquette_quiz_attempt": None,
            "realtime_roleplay_session": None,
            "operation_logs": logs,
        }

    async def _serialize_realtime_record(
        self,
        projection: RuntimeOutcomeProjection,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        user = await self._db.get(User, projection.user_id)
        snapshot = projection.snapshot if isinstance(projection.snapshot, dict) else {}
        binding = snapshot.get("external_binding")
        binding = binding if isinstance(binding, dict) else {}
        logs = (
            await self._target_logs(
                "sales_trainer_realtime_roleplay_session",
                projection.source_record_id,
            )
            if include_logs
            else []
        )
        return {
            "record_id": projection.source_record_id,
            "record_type": REALTIME_ROLEPLAY_RECORD_TYPE,
            "path_key": _optional_str(binding.get("path_key")),
            "path_revision_id": projection.path_revision_id,
            "path_revision_no": projection.path_revision_no,
            "module_key": projection.module_key,
            "legacy_snapshot_only": False,
            "unit_id": "",
            "unit_name": None,
            "unit_type": "realtime_roleplay",
            "user_id": projection.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "status": projection.status,
            "score": projection.score,
            "max_score": projection.max_score,
            "passed": projection.passed,
            "submitted_at": projection.completed_at or projection.submitted_at,
            "material_snapshot": None,
            "score_scheme_snapshot": None,
            "task_brief_snapshot": None,
            "audio_submission": None,
            "quiz_attempt": None,
            "ai_coach_session": None,
            "business_etiquette_quiz_attempt": None,
            "realtime_roleplay_session": {
                "session_id": projection.source_record_id,
                "module_key": projection.module_key,
                "status": projection.status,
                "score": projection.score,
                "max_score": projection.max_score,
                "passed": projection.passed,
                "submitted_at": projection.submitted_at,
                "completed_at": projection.completed_at,
                "external_binding": binding,
                "snapshot": snapshot,
            },
            "operation_logs": logs,
        }

    async def _serialize_ai_coach_record(
        self,
        session: SalesTrainerAiCoachSession,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        user = await self._db.get(User, session.user_id)
        path_config = json_dict_or_empty(session.path_config_snapshot)
        lineage = training_record_lineage_fields(path_config)
        logs = (
            await self._target_logs(
                "sales_trainer_ai_coach_session",
                orm_scalar(session.session_id, str),
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
                "path_key": session.path_key,
                "path_revision_id": session.path_revision_id,
                "path_revision_no": session.path_revision_no,
                "article_snapshot": session.article_snapshot,
                "path_config_snapshot": session.path_config_snapshot,
                "config_snapshot": session.config_snapshot,
                "coach_state": session.coach_state,
                "prompt_template_id": session.prompt_template_id,
                "prompt_revision_id": session.prompt_revision_id,
                "prompt_contract_hash": session.prompt_contract_hash,
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
            "business_etiquette_quiz_attempt": None,
            "realtime_roleplay_session": None,
            "operation_logs": logs,
        }

    async def _serialize_business_etiquette_quiz_record(
        self,
        attempt: SalesTrainerBusinessEtiquetteQuizAttempt,
        *,
        include_logs: bool,
    ) -> dict[str, Any]:
        user = await self._db.get(User, attempt.user_id)
        logs = (
            await self._target_logs(
                "business_etiquette_unit_quiz_attempt",
                orm_scalar(attempt.attempt_id, str),
            )
            if include_logs
            else []
        )
        payload = {
            "attempt_id": attempt.attempt_id,
            "training_pack_key": attempt.training_pack_key,
            "learning_unit_key": attempt.learning_unit_key,
            "learning_unit_title": attempt.learning_unit_title,
            "user_id": attempt.user_id,
            "path_revision_id": attempt.path_revision_id,
            "path_revision_no": attempt.path_revision_no,
            "training_pack_revision_id": attempt.training_pack_revision_id,
            "training_pack_revision_no": attempt.training_pack_revision_no,
            "capability_snapshot": attempt.capability_snapshot or {},
            "question_snapshots": attempt.question_snapshots or [],
            "answers": attempt.answers_snapshot or [],
            "capability_scores": attempt.capability_scores or [],
            "weak_capability_keys": attempt.weak_capability_keys or [],
            "recommended_chapter_orders": attempt.recommended_chapter_orders or [],
            "total_score": float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            "max_score": float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            "passed": attempt.passed,
            "status": attempt.status,
            "submitted_at": attempt.submitted_at,
        }
        legacy_snapshot_only = not (
            attempt.path_revision_id and attempt.path_revision_no
        )
        return {
            "record_id": attempt.attempt_id,
            "record_type": BUSINESS_ETIQUETTE_QUIZ_RECORD_TYPE,
            "path_key": "newcomer_training_path_v1",
            "path_revision_id": attempt.path_revision_id,
            "path_revision_no": attempt.path_revision_no,
            "module_key": "business_skills",
            "legacy_snapshot_only": legacy_snapshot_only,
            "unit_id": attempt.learning_unit_key,
            "unit_name": attempt.learning_unit_title,
            "unit_type": "business_etiquette_quiz",
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
            "quiz_attempt": None,
            "ai_coach_session": None,
            "business_etiquette_quiz_attempt": payload,
            "realtime_roleplay_session": None,
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
                orm_scalar(attempt.attempt_id, str),
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
            "business_etiquette_quiz_attempt": None,
            "realtime_roleplay_session": None,
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


def _attach_training_context_to_logs(
    record: dict[str, Any],
    journey: dict[str, Any],
) -> None:
    logs = record.get("operation_logs")
    if not isinstance(logs, list):
        return
    context = _training_context_from_journey(journey)
    for log in logs:
        if isinstance(log, dict):
            log["training_context"] = context


def _training_context_from_journey(journey: dict[str, Any]) -> dict[str, Any]:
    return {
        "path_key": journey.get("path_key"),
        "path_revision_id": journey.get("path_revision_id"),
        "path_revision_no": journey.get("path_revision_no"),
        "training_stage": journey.get("training_stage"),
        "learner_level": journey.get("learner_level"),
        "role_level": journey.get("role_level"),
    }


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _advanced_record_filter_present(
    *,
    training_stage: str | None,
    module_key: str | None,
    learner_level: str | None,
    role_level: str | None,
    status: str | None,
    activity_id: str | None,
    activity_type: str | None,
    phase_id: str | None,
    module_id: str | None,
) -> bool:
    return any(
        _normalise_filter_value(value)
        for value in (
            training_stage,
            module_key,
            learner_level,
            role_level,
            status,
            activity_id,
            activity_type,
            phase_id,
            module_id,
        )
    )


def _record_matches_filters(
    record: dict[str, Any],
    *,
    training_stage: str | None,
    module_key: str | None,
    learner_level: str | None,
    role_level: str | None,
    status: str | None,
    activity_id: str | None,
    activity_type: str | None,
    phase_id: str | None,
    module_id: str | None,
) -> bool:
    training_stage = _normalise_filter_value(training_stage)
    module_key = _normalise_filter_value(module_key)
    learner_level = _normalise_filter_value(learner_level)
    role_level = _normalise_filter_value(role_level)
    status = _normalise_filter_value(status)
    activity_id = _normalise_filter_value(activity_id)
    activity_type = _normalise_filter_value(activity_type)
    phase_id = _normalise_filter_value(phase_id)
    module_id = _normalise_filter_value(module_id)
    if training_stage and record.get("training_stage") != training_stage:
        return False
    if module_key and record.get("module_key") != module_key:
        return False
    if status and record.get("status") != status:
        return False
    if activity_id and record.get("activity_id") != activity_id:
        return False
    if activity_type and record.get("activity_type") != activity_type:
        return False
    if phase_id and record.get("phase_id") != phase_id:
        return False
    if module_id and record.get("module_id") != module_id:
        return False
    if learner_level:
        level = record.get("learner_level")
        if not isinstance(level, dict) or level.get("level_key") != learner_level:
            return False
    if role_level:
        level = record.get("role_level")
        if not isinstance(level, dict) or level.get("level_key") != role_level:
            return False
    return True


def _snapshot_context_value(snapshot: dict[str, Any], key: str) -> Any:
    context = snapshot.get("context")
    if isinstance(context, dict) and key in context:
        return context.get(key)
    return snapshot.get(key)


def _normalise_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
