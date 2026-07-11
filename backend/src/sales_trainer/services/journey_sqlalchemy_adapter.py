"""SQLAlchemy adapter for the Training Journey read-projection seam."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import DEV_LOGIN_EMAIL, DEV_LOGIN_WECHAT_USER_ID
from common.db.model_registry.identity import User
from common.db.model_registry.training import PracticeSession
from sales_trainer.services.journey_read_repository import (
    JourneyLearnerPage,
    JourneyLearnerProjection,
    JourneyRoleplaySessionProjection,
)


def _freeze_json_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return MappingProxyType({})

    def freeze(item: object) -> object:
        if isinstance(item, Mapping):
            return MappingProxyType(
                {str(key): freeze(child) for key, child in item.items()}
            )
        if isinstance(item, (list, tuple)):
            return tuple(freeze(child) for child in item)
        return item

    return MappingProxyType({str(key): freeze(child) for key, child in value.items()})


def _team_visible_learner_role_filter() -> Any:
    learner_filter = User.role == "user"
    if os.getenv("ENVIRONMENT", "development").strip().lower() != "development":
        return learner_filter
    return or_(
        learner_filter,
        and_(
            User.role == "admin",
            or_(
                User.email == DEV_LOGIN_EMAIL,
                User.wechat_user_id == DEV_LOGIN_WECHAT_USER_ID,
            ),
        ),
    )


class SqlAlchemyJourneyReadRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def learner(self, learner_id: str) -> JourneyLearnerProjection | None:
        row = await self._db.get(User, learner_id)
        return self._learner_projection(row) if row is not None else None

    async def learners(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int | None,
    ) -> JourneyLearnerPage:
        if team_department is not None and department and department != team_department:
            return JourneyLearnerPage(items=(), total=0)
        effective_department = team_department or department
        filters = [_team_visible_learner_role_filter(), User.is_active.is_(True)]
        if effective_department:
            filters.append(User.department == effective_department)
        total = int(
            await self._db.scalar(
                select(func.count()).select_from(User).where(*filters)
            )
            or 0
        )
        statement = (
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.user_id.asc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._db.execute(statement)
        return JourneyLearnerPage(
            items=tuple(
                self._learner_projection(row) for row in result.scalars().all()
            ),
            total=total,
        )

    async def roleplay_sessions(
        self,
        *,
        learner_ids: frozenset[str],
    ) -> tuple[JourneyRoleplaySessionProjection, ...]:
        if not learner_ids:
            return ()
        result = await self._db.execute(
            select(PracticeSession)
            .where(
                PracticeSession.user_id.in_(learner_ids),
                PracticeSession.voice_mode == "stepfun_realtime",
            )
            .order_by(PracticeSession.session_id.asc())
        )
        return tuple(
            JourneyRoleplaySessionProjection(
                session_id=str(row.session_id),
                voice_policy_snapshot=_freeze_json_mapping(row.voice_policy_snapshot),
            )
            for row in result.scalars().all()
        )

    @staticmethod
    def _learner_projection(row: User) -> JourneyLearnerProjection:
        return JourneyLearnerProjection(
            learner_id=str(row.user_id),
            name=str(row.name) if row.name is not None else None,
            department=str(row.department) if row.department is not None else None,
            role=str(row.role or ""),
            email=str(row.email) if row.email is not None else None,
            wechat_user_id=str(row.wechat_user_id or ""),
            is_active=row.is_active is not False,
            created_at=cast(datetime | None, row.created_at),
        )


__all__ = ["SqlAlchemyJourneyReadRepository"]
