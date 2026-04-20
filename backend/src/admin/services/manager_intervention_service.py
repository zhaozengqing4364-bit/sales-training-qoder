"""Write-side service for manager intervention workflow rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ManagerIntervention, PracticeSession, User
from common.db.schemas import (
    ManagerInterventionCreate,
    ManagerInterventionDueState,
    ManagerInterventionListResponse,
    ManagerInterventionReminderRequest,
    ManagerInterventionReminderStatus,
    ManagerInterventionResponse,
    ManagerInterventionUpdate,
)
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class ManagerInterventionWriteService:
    """Own manager_interventions write/read workflow rules behind route handlers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_interventions(
        self,
        *,
        user_id: str | None,
        limit: int,
    ) -> ManagerInterventionListResponse:
        query = select(ManagerIntervention)
        count_query = select(func.count()).select_from(ManagerIntervention)
        if user_id:
            await self._get_target_user(user_id=user_id)
            query = query.where(ManagerIntervention.user_id == user_id)
            count_query = count_query.where(ManagerIntervention.user_id == user_id)

        query = query.order_by(ManagerIntervention.created_at.desc()).limit(limit)
        rows = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar() or 0

        return ManagerInterventionListResponse(
            items=[ManagerInterventionResponse.model_validate(row) for row in rows],
            total=int(total),
        )

    async def create_intervention(
        self,
        *,
        payload: ManagerInterventionCreate,
        current_user: User,
    ) -> ManagerIntervention:
        target_user_id = str(payload.user_id)
        await self._get_target_user(user_id=target_user_id)

        resolving_session_id = (
            str(payload.resolving_session_id) if payload.resolving_session_id is not None else None
        )
        if resolving_session_id:
            await self._validate_resolving_session(
                intervention_user_id=target_user_id,
                resolving_session_id=resolving_session_id,
            )

        due_state, reminder_status, reminder_sent_at = self._normalize_state(
            due_state=payload.due_state.value,
            reminder_status=payload.reminder_status.value,
            resolving_session_id=resolving_session_id,
        )

        intervention = ManagerIntervention(
            manager_user_id=str(current_user.user_id),
            user_id=target_user_id,
            issue_family=payload.issue_family,
            note=payload.note,
            due_state=due_state,
            reminder_status=reminder_status,
            reminder_sent_at=reminder_sent_at,
            resolving_session_id=resolving_session_id,
        )
        self.db.add(intervention)
        await self.db.commit()
        await self.db.refresh(intervention)

        logger.info(
            "manager_intervention_created",
            intervention_id=str(intervention.intervention_id),
            manager_user_id=str(current_user.user_id),
            target_user_id=target_user_id,
            issue_family=intervention.issue_family,
            due_state=intervention.due_state,
        )
        return intervention

    async def update_intervention(
        self,
        *,
        intervention_id: str,
        payload: ManagerInterventionUpdate,
    ) -> ManagerIntervention:
        intervention = await self._get_intervention(intervention_id=intervention_id)
        fields_set = set(payload.model_fields_set)
        if not fields_set:
            raise HTTPException(status_code=400, detail="[INTERVENTION_EMPTY_UPDATE]")

        if "note" in fields_set:
            intervention.note = payload.note

        if "reminder_status" in fields_set:
            intervention.reminder_status = payload.reminder_status.value
            if payload.reminder_status == ManagerInterventionReminderStatus.SENT:
                intervention.reminder_sent_at = datetime.now(UTC)
            else:
                intervention.reminder_sent_at = None

        if "resolving_session_id" in fields_set:
            intervention.resolving_session_id = (
                str(payload.resolving_session_id)
                if payload.resolving_session_id is not None
                else None
            )
            if intervention.resolving_session_id:
                await self._validate_resolving_session(
                    intervention_user_id=str(intervention.user_id),
                    resolving_session_id=str(intervention.resolving_session_id),
                )

        requested_due_state = (
            payload.due_state.value if payload.due_state is not None else intervention.due_state
        )
        due_state, reminder_status, reminder_sent_at = self._normalize_state(
            due_state=requested_due_state,
            reminder_status=str(intervention.reminder_status),
            resolving_session_id=(
                str(intervention.resolving_session_id)
                if intervention.resolving_session_id is not None
                else None
            ),
        )
        intervention.due_state = due_state
        intervention.reminder_status = reminder_status
        if reminder_sent_at is not None:
            intervention.reminder_sent_at = reminder_sent_at
        intervention.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(intervention)
        return intervention

    async def remind_user(
        self,
        *,
        payload: ManagerInterventionReminderRequest,
        current_user: User,
    ) -> dict[str, Any]:
        target_user_id = str(payload.user_id)
        await self._get_target_user(user_id=target_user_id)

        reminder_id = str(uuid.uuid4())
        intervention: ManagerIntervention | None = None
        if payload.intervention_id is not None:
            intervention = await self._get_intervention(
                intervention_id=str(payload.intervention_id),
            )
            if str(intervention.user_id) != target_user_id:
                raise HTTPException(status_code=400, detail="[INTERVENTION_USER_MISMATCH]")
        else:
            intervention = await self._latest_open_intervention_for_user(user_id=target_user_id)

        if intervention is not None:
            if payload.note is not None:
                intervention.note = payload.note
            intervention.reminder_status = ManagerInterventionReminderStatus.SENT.value
            intervention.reminder_sent_at = datetime.now(UTC)
            if intervention.due_state != ManagerInterventionDueState.RESOLVED.value:
                intervention.due_state = ManagerInterventionDueState.DUE.value
            intervention.updated_at = datetime.now(UTC)
            await self.db.commit()

        logger.info(
            "manager_lite_reminder_logged",
            reminder_id=reminder_id,
            intervention_id=(
                str(intervention.intervention_id) if intervention is not None else None
            ),
            sender_user_id=str(current_user.user_id),
            target_user_id=target_user_id,
            note=(payload.note or "").strip(),
        )
        return {
            "sent": True,
            "reminder_id": reminder_id,
            "user_id": target_user_id,
            "intervention_id": (
                str(intervention.intervention_id) if intervention is not None else None
            ),
        }

    async def _get_target_user(self, *, user_id: str) -> User:
        user = await self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")
        return user

    async def _get_intervention(self, *, intervention_id: str) -> ManagerIntervention:
        intervention = await self.db.get(ManagerIntervention, intervention_id)
        if not intervention:
            raise HTTPException(status_code=404, detail="[INTERVENTION_NOT_FOUND]")
        return intervention

    async def _validate_resolving_session(
        self,
        *,
        intervention_user_id: str,
        resolving_session_id: str,
    ) -> None:
        session = await self.db.get(PracticeSession, resolving_session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail="[INTERVENTION_RESOLVING_SESSION_NOT_FOUND]",
            )
        if str(session.user_id) != intervention_user_id:
            raise HTTPException(
                status_code=400,
                detail="[INTERVENTION_RESOLVING_SESSION_USER_MISMATCH]",
            )

    async def _latest_open_intervention_for_user(
        self,
        *,
        user_id: str,
    ) -> ManagerIntervention | None:
        result = await self.db.execute(
            select(ManagerIntervention)
            .where(
                ManagerIntervention.user_id == user_id,
                ManagerIntervention.due_state != ManagerInterventionDueState.RESOLVED.value,
            )
            .order_by(ManagerIntervention.updated_at.desc(), ManagerIntervention.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_state(
        *,
        due_state: str,
        reminder_status: str,
        resolving_session_id: str | None,
    ) -> tuple[str, str, datetime | None]:
        if resolving_session_id:
            return (
                ManagerInterventionDueState.RESOLVED.value,
                reminder_status,
                None
                if reminder_status == ManagerInterventionReminderStatus.NOT_SENT.value
                else datetime.now(UTC),
            )

        if due_state == ManagerInterventionDueState.RESOLVED.value:
            raise HTTPException(
                status_code=400,
                detail="[INTERVENTION_RESOLVING_SESSION_REQUIRED]",
            )

        normalized_due_state = due_state
        reminder_sent_at: datetime | None = None
        if reminder_status == ManagerInterventionReminderStatus.SENT.value:
            reminder_sent_at = datetime.now(UTC)
            if normalized_due_state == ManagerInterventionDueState.PENDING.value:
                normalized_due_state = ManagerInterventionDueState.DUE.value

        return normalized_due_state, reminder_status, reminder_sent_at
