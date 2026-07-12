"""Canonical activity-attempt training records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
)


class TrainingRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_records(
        self,
        *,
        user_id: str | None = None,
        team_department: str | None = None,
        status: str | None = None,
        activity_id: str | None = None,
        activity_type: str | None = None,
        phase_id: str | None = None,
        module_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        **_: Any,
    ) -> tuple[list[dict[str, Any]], int]:
        statement = select(NewcomerTrainingActivityAttempt, NewcomerTrainingEnrollment).join(
            NewcomerTrainingEnrollment,
            NewcomerTrainingEnrollment.enrollment_id
            == NewcomerTrainingActivityAttempt.enrollment_id,
        )
        filters = []
        if user_id:
            filters.append(NewcomerTrainingEnrollment.learner_id == user_id)
        if status:
            filters.append(NewcomerTrainingActivityAttempt.status == status)
        if activity_id:
            filters.append(NewcomerTrainingActivityAttempt.activity_id == activity_id)
        if activity_type:
            filters.append(NewcomerTrainingActivityAttempt.activity_type == activity_type)
        if team_department is not None:
            statement = statement.join(
                User, NewcomerTrainingEnrollment.learner_id == User.user_id
            )
            filters.append(User.department == team_department)
        statement = statement.where(*filters)
        rows = list(
            (
                await self._db.execute(
                    statement.order_by(
                        NewcomerTrainingActivityAttempt.created_at.desc(),
                        NewcomerTrainingActivityAttempt.attempt_id.desc(),
                    )
                )
            ).all()
        )
        records = [
            _record(attempt, enrollment)
            for attempt, enrollment in rows
            if _matches_snapshot(
                attempt.activity_snapshot, phase_id=phase_id, module_id=module_id
            )
        ]
        total = len(records)
        return records[offset : offset + limit], total

    async def get_record(
        self, record_type: str, record_id: str
    ) -> dict[str, Any] | None:
        if record_type != "newcomer_activity_attempt":
            return None
        attempt = await self._db.get(NewcomerTrainingActivityAttempt, record_id)
        if attempt is None:
            return None
        enrollment = await self._db.get(
            NewcomerTrainingEnrollment, str(attempt.enrollment_id)
        )
        return _record(attempt, enrollment) if enrollment is not None else None

    async def get_record_for_viewer(
        self,
        record_type: str,
        record_id: str,
        *,
        viewer: User,
        team_department: str | None,
    ) -> dict[str, Any] | None:
        del viewer
        record = await self.get_record(record_type, record_id)
        if record is None or team_department is None:
            return record
        learner = await self._db.get(User, str(record["user_id"]))
        if learner is None or str(learner.department or "") != team_department:
            return None
        return record

    async def get_record_by_evidence_for_viewer(
        self,
        *,
        evidence_type: str,
        evidence_id: str,
        viewer: User,
        team_department: str | None,
    ) -> dict[str, Any] | None:
        attempt = await self._db.scalar(
            select(NewcomerTrainingActivityAttempt).where(
                NewcomerTrainingActivityAttempt.evidence_type == evidence_type,
                NewcomerTrainingActivityAttempt.evidence_id == evidence_id,
            )
        )
        if attempt is None:
            return None
        return await self.get_record_for_viewer(
            "newcomer_activity_attempt",
            str(attempt.attempt_id),
            viewer=viewer,
            team_department=team_department,
        )

    async def get_audio_record(self, submission_id: str) -> dict[str, Any] | None:
        attempt = await self._db.scalar(
            select(NewcomerTrainingActivityAttempt).where(
                NewcomerTrainingActivityAttempt.evidence_type == "audio_submission",
                NewcomerTrainingActivityAttempt.evidence_id == submission_id,
            )
        )
        if attempt is None:
            return None
        return await self.get_record(
            "newcomer_activity_attempt", str(attempt.attempt_id)
        )


def _record(
    attempt: NewcomerTrainingActivityAttempt,
    enrollment: NewcomerTrainingEnrollment,
) -> dict[str, Any]:
    snapshot = dict(attempt.activity_snapshot or {})
    raw_context = snapshot.get("context")
    context: dict[str, Any] = raw_context if isinstance(raw_context, dict) else {}
    return {
        "record_type": "newcomer_activity_attempt",
        "record_id": str(attempt.attempt_id),
        "evidence_id": str(attempt.evidence_id or attempt.attempt_id),
        "user_id": str(enrollment.learner_id),
        "enrollment_id": str(attempt.enrollment_id),
        "path_revision_id": str(attempt.path_revision_id),
        "activity_id": str(attempt.activity_id),
        "activity_type": str(attempt.activity_type),
        "phase_id": context.get("phase_id"),
        "module_id": context.get("module_id"),
        "phase_title": context.get("phase_title"),
        "module_title": context.get("module_title"),
        "activity_title": snapshot.get("title"),
        "status": str(attempt.status),
        "score": float(attempt.score) if attempt.score is not None else None,
        "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
        "passed": bool(attempt.passed) if attempt.passed is not None else None,
        "submitted_at": attempt.created_at,
        "completed_at": attempt.completed_at,
        "evidence_type": attempt.evidence_type,
        "source_evidence_id": attempt.evidence_id,
        "capability_scores": _capability_scores(attempt.result_snapshot),
    }


def _matches_snapshot(
    snapshot: object, *, phase_id: str | None, module_id: str | None
) -> bool:
    value = snapshot if isinstance(snapshot, dict) else {}
    raw_context = value.get("context")
    context: dict[str, Any] = raw_context if isinstance(raw_context, dict) else {}
    return (phase_id is None or context.get("phase_id") == phase_id) and (
        module_id is None or context.get("module_id") == module_id
    )


def _capability_scores(snapshot: object) -> list[dict[str, Any]]:
    value = snapshot if isinstance(snapshot, dict) else {}
    raw_scores = value.get("capability_scores")
    if not isinstance(raw_scores, list):
        return []
    scores: list[dict[str, Any]] = []
    for item in raw_scores:
        if not isinstance(item, dict):
            continue
        key = str(item.get("capability_key") or "").strip()
        score = item.get("score")
        if not key or not isinstance(score, int | float):
            continue
        scores.append({"capability_key": key, "score": float(score)})
    return scores


__all__ = ["TrainingRecordService"]
