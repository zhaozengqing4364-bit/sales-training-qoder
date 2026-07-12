"""Persistence adapters for pinned enrollments and unified activity attempts."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
)
from sales_trainer.orchestration.errors import NewcomerOrchestrationError


class EnrollmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create(
        self, *, learner_id: str, path_id: str, path_revision_id: str
    ) -> NewcomerTrainingEnrollment:
        existing = await self.active_for_learner(learner_id=learner_id, path_id=path_id)
        if existing is not None:
            return existing
        try:
            async with self._db.begin_nested():
                enrollment = NewcomerTrainingEnrollment(
                    learner_id=learner_id,
                    path_id=path_id,
                    path_revision_id=path_revision_id,
                    status="active",
                )
                self._db.add(enrollment)
                await self._db.flush()
            return enrollment
        except IntegrityError:
            existing = await self.active_for_learner(
                learner_id=learner_id, path_id=path_id
            )
            if existing is not None:
                return existing
            raise

    async def active_for_learner(
        self, *, learner_id: str, path_id: str
    ) -> NewcomerTrainingEnrollment | None:
        return cast(
            NewcomerTrainingEnrollment | None,
            await self._db.scalar(
                select(NewcomerTrainingEnrollment).where(
                    NewcomerTrainingEnrollment.learner_id == learner_id,
                    NewcomerTrainingEnrollment.path_id == path_id,
                    NewcomerTrainingEnrollment.status == "active",
                )
            ),
        )


class AttemptRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        enrollment_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        activity_snapshot: dict[str, Any],
        client_token: str,
    ) -> NewcomerTrainingActivityAttempt:
        existing = await self._by_client_token(client_token)
        if existing is not None:
            return existing
        try:
            async with self._db.begin_nested():
                latest_no = await self._db.scalar(
                    select(func.max(NewcomerTrainingActivityAttempt.attempt_no))
                    .where(
                        NewcomerTrainingActivityAttempt.enrollment_id == enrollment_id,
                        NewcomerTrainingActivityAttempt.activity_id == activity_id,
                    )
                    .with_for_update()
                )
                attempt = NewcomerTrainingActivityAttempt(
                    enrollment_id=enrollment_id,
                    path_revision_id=path_revision_id,
                    activity_id=activity_id,
                    activity_type=activity_type,
                    attempt_no=int(latest_no or 0) + 1,
                    client_token=client_token,
                    activity_snapshot=activity_snapshot,
                )
                self._db.add(attempt)
                await self._db.flush()
            return attempt
        except IntegrityError:
            existing = await self._by_client_token(client_token)
            if existing is not None:
                return existing
            raise

    async def _by_client_token(
        self, client_token: str
    ) -> NewcomerTrainingActivityAttempt | None:
        return cast(
            NewcomerTrainingActivityAttempt | None,
            await self._db.scalar(
                select(NewcomerTrainingActivityAttempt).where(
                    NewcomerTrainingActivityAttempt.client_token == client_token
                )
            ),
        )

    async def latest_for_activity(
        self, *, enrollment_id: str, activity_id: str
    ) -> NewcomerTrainingActivityAttempt | None:
        return cast(
            NewcomerTrainingActivityAttempt | None,
            await self._db.scalar(
                select(NewcomerTrainingActivityAttempt)
                .where(
                    NewcomerTrainingActivityAttempt.enrollment_id == enrollment_id,
                    NewcomerTrainingActivityAttempt.activity_id == activity_id,
                )
                .order_by(NewcomerTrainingActivityAttempt.attempt_no.desc())
                .limit(1)
            ),
        )

    async def attach_evidence(
        self, *, attempt_id: str, evidence_type: str, evidence_id: str, status: str
    ) -> NewcomerTrainingActivityAttempt:
        attempt = await self._db.get(NewcomerTrainingActivityAttempt, attempt_id)
        if attempt is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_ATTEMPT_NOT_FOUND]", "训练记录不存在。", 404
            )
        setattr(attempt, "evidence_type", evidence_type)
        setattr(attempt, "evidence_id", evidence_id)
        setattr(attempt, "status", status)
        await self._db.flush()
        return attempt


__all__ = ["AttemptRepository", "EnrollmentRepository"]
