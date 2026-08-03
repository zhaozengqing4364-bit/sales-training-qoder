from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.teams.policy import TeamDataScope
from sales_trainer.models import SalesTrainerOperationLog


class OperationLogService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        *,
        actor: User | None,
        action: str,
        target_type: str,
        target_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesTrainerOperationLog:
        log = SalesTrainerOperationLog(
            actor_id=str(actor.user_id) if actor is not None else None,
            actor_role=str(getattr(actor, "role", "")) if actor is not None else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata or {},
        )
        self._db.add(log)
        await self._db.flush()
        return log

    async def list_logs(
        self,
        *,
        actor_id: str | None = None,
        team_scope: TeamDataScope | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerOperationLog], int]:
        stmt = select(SalesTrainerOperationLog)
        count_stmt = select(func.count()).select_from(SalesTrainerOperationLog)
        if actor_id:
            stmt = stmt.where(SalesTrainerOperationLog.actor_id == actor_id)
            count_stmt = count_stmt.where(SalesTrainerOperationLog.actor_id == actor_id)
        if team_scope is not None and not team_scope.unrestricted:
            stmt = stmt.where(
                SalesTrainerOperationLog.actor_id.in_(team_scope.learner_ids)
            )
            count_stmt = count_stmt.where(
                SalesTrainerOperationLog.actor_id.in_(team_scope.learner_ids)
            )
        if target_type:
            stmt = stmt.where(SalesTrainerOperationLog.target_type == target_type)
            count_stmt = count_stmt.where(
                SalesTrainerOperationLog.target_type == target_type
            )
        if target_id:
            stmt = stmt.where(SalesTrainerOperationLog.target_id == target_id)
            count_stmt = count_stmt.where(SalesTrainerOperationLog.target_id == target_id)

        result = await self._db.execute(
            stmt.order_by(SalesTrainerOperationLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)
