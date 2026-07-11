"""Immutable read projections used by Training Journey and Readiness application code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class JourneyViewer(Protocol):
    user_id: Any
    role: Any
    department: Any
    is_active: Any


@dataclass(frozen=True, slots=True)
class JourneyLearnerProjection:
    learner_id: str
    name: str | None
    department: str | None
    role: str
    email: str | None
    wechat_user_id: str
    is_active: bool
    created_at: datetime | None

    @property
    def user_id(self) -> str:
        return self.learner_id


@dataclass(frozen=True, slots=True)
class JourneyLearnerPage:
    items: tuple[JourneyLearnerProjection, ...]
    total: int


@dataclass(frozen=True, slots=True)
class JourneyRoleplaySessionProjection:
    session_id: str
    voice_policy_snapshot: Mapping[str, object]


class JourneyReadRepository(Protocol):
    async def learner(self, learner_id: str) -> JourneyLearnerProjection | None: ...

    async def learners(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int | None,
    ) -> JourneyLearnerPage: ...

    async def roleplay_sessions(
        self,
        *,
        learner_ids: frozenset[str],
    ) -> tuple[JourneyRoleplaySessionProjection, ...]: ...


__all__ = [
    "JourneyLearnerPage",
    "JourneyLearnerProjection",
    "JourneyReadRepository",
    "JourneyRoleplaySessionProjection",
    "JourneyViewer",
]
