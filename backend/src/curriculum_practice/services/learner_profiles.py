from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from curriculum_practice.models import LearnerProfile
from curriculum_practice.services.orm_payload_typing import set_orm_field

DEFAULT_LEARNER_LEVEL = "conservative"


class LearnerProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_for_user(self, user_id: str) -> Result[LearnerProfile]:
        profile = await self._db.get(LearnerProfile, user_id)
        if profile is None:
            profile = LearnerProfile(user_id=user_id, effective_level=DEFAULT_LEARNER_LEVEL)
            self._db.add(profile)
            await self._db.commit()
            await self._db.refresh(profile)
        return Result.ok(profile)

    async def record_self_assessment(
        self, user_id: str, level: str
    ) -> Result[LearnerProfile]:
        result = await self.get_or_create_for_user(user_id)
        if not result.is_success or result.value is None:
            return result
        profile = result.value
        set_orm_field(profile, "self_assessed_level", level)
        set_orm_field(profile, "self_assessed_at", datetime.now(UTC))
        if profile.admin_overridden_level is None:
            set_orm_field(profile, "effective_level", level)
        await self._db.commit()
        await self._db.refresh(profile)
        return Result.ok(profile)

    async def apply_admin_override(
        self, user_id: str, level: str, *, actor_id: str
    ) -> Result[LearnerProfile]:
        result = await self.get_or_create_for_user(user_id)
        if not result.is_success or result.value is None:
            return result
        profile = result.value
        set_orm_field(profile, "admin_overridden_level", level)
        set_orm_field(profile, "effective_level", level)
        set_orm_field(profile, "overridden_by", actor_id)
        set_orm_field(profile, "overridden_at", datetime.now(UTC))
        await self._db.commit()
        await self._db.refresh(profile)
        return Result.ok(profile)
