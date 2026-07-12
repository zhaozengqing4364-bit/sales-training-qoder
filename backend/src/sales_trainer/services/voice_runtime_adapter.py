"""Narrow adapter for governed voice-runtime profiles owned by agent."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import VoiceRuntimeProfile


async def active_voice_runtime_ids(
    db: AsyncSession, values: set[str]
) -> set[str]:
    if not values:
        return set()
    rows = await db.scalars(
        select(VoiceRuntimeProfile.id).where(
            VoiceRuntimeProfile.id.in_(values),
            VoiceRuntimeProfile.is_active.is_(True),
        )
    )
    return {str(value) for value in rows}


async def get_voice_runtime_profile(db: AsyncSession, profile_id: str) -> Any:
    return await db.get(VoiceRuntimeProfile, profile_id)


__all__ = ["active_voice_runtime_ids", "get_voice_runtime_profile"]
