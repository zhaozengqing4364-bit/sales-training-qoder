"""Authoritative object-level scope for team readers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.roles import (
    SALES_TRAINER_LEARNER_ROLES,
    TRAINING_MANAGER_ROLES,
    is_platform_admin_role,
    normalize_role,
)
from common.db.models import Team, TeamLeaderAssignment, TeamMembership, User


@dataclass(frozen=True, slots=True)
class TeamDataScope:
    """Resolved object scope passed from policy into read/write services."""

    unrestricted: bool
    team_ids: frozenset[str]
    learner_ids: frozenset[str]

    @classmethod
    def unrestricted_scope(cls) -> TeamDataScope:
        return cls(unrestricted=True, team_ids=frozenset(), learner_ids=frozenset())

    @classmethod
    def restricted(
        cls,
        *,
        team_ids: set[str] | frozenset[str] = frozenset(),
        learner_ids: set[str] | frozenset[str] = frozenset(),
    ) -> TeamDataScope:
        return cls(
            unrestricted=False,
            team_ids=frozenset(team_ids),
            learner_ids=frozenset(learner_ids),
        )

    def allows_learner(self, learner_id: object) -> bool:
        return self.unrestricted or str(learner_id) in self.learner_ids

    def allows_team(self, team_id: object) -> bool:
        return self.unrestricted or str(team_id) in self.team_ids


class TeamScopePolicy:
    """Resolve team and learner scope without consulting department strings."""

    def __init__(self, db: AsyncSession, *, now: datetime | None = None) -> None:
        self.db = db
        self.now = now or datetime.now(UTC)

    @staticmethod
    def has_unrestricted_scope(actor: User) -> bool:
        return is_platform_admin_role(getattr(actor, "role", None))

    @staticmethod
    def is_team_leader(actor: User) -> bool:
        return normalize_role(getattr(actor, "role", None)) in TRAINING_MANAGER_ROLES

    @staticmethod
    def is_learner(actor: User) -> bool:
        return normalize_role(getattr(actor, "role", None)) in SALES_TRAINER_LEARNER_ROLES

    async def authorized_team_ids(self, actor: User) -> set[str] | None:
        if self.has_unrestricted_scope(actor):
            return None
        if not self.is_team_leader(actor):
            return set()
        if os.getenv("EXPLICIT_TEAM_SCOPE_ENABLED", "true").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            # Safe rollback: disabling the new relation model never restores the
            # former department-string authorization. Team readers fail closed.
            return set()
        rows = await self.db.scalars(
            select(TeamLeaderAssignment.team_id)
            .join(Team, Team.team_id == TeamLeaderAssignment.team_id)
            .where(
                TeamLeaderAssignment.leader_user_id == str(actor.user_id),
                TeamLeaderAssignment.effective_from <= self.now,
                or_(
                    TeamLeaderAssignment.effective_to.is_(None),
                    TeamLeaderAssignment.effective_to > self.now,
                ),
                Team.is_active.is_(True),
            )
        )
        return {str(team_id) for team_id in rows.all()}

    async def authorized_learner_ids(self, actor: User) -> set[str] | None:
        if self.is_learner(actor):
            return {str(actor.user_id)}
        team_ids = await self.authorized_team_ids(actor)
        if team_ids is None:
            return None
        if not team_ids:
            return set()
        rows = await self.db.scalars(
            select(TeamMembership.user_id).where(
                TeamMembership.team_id.in_(team_ids),
                TeamMembership.effective_from <= self.now,
                or_(
                    TeamMembership.effective_to.is_(None),
                    TeamMembership.effective_to > self.now,
                ),
            )
        )
        return {str(user_id) for user_id in rows.all()}

    async def resolve(self, actor: User) -> TeamDataScope:
        if self.has_unrestricted_scope(actor):
            return TeamDataScope.unrestricted_scope()
        if self.is_learner(actor):
            return TeamDataScope.restricted(learner_ids={str(actor.user_id)})
        team_ids = await self.authorized_team_ids(actor)
        if not team_ids:
            return TeamDataScope.restricted()
        rows = await self.db.scalars(
            select(TeamMembership.user_id).where(
                TeamMembership.team_id.in_(team_ids),
                TeamMembership.effective_from <= self.now,
                or_(
                    TeamMembership.effective_to.is_(None),
                    TeamMembership.effective_to > self.now,
                ),
            )
        )
        return TeamDataScope.restricted(
            team_ids=team_ids,
            learner_ids={str(user_id) for user_id in rows.all()},
        )

    async def can_view_learner(self, actor: User, learner_id: str) -> bool:
        learner_ids = await self.authorized_learner_ids(actor)
        return learner_ids is None or str(learner_id) in learner_ids

    async def require_team(self, actor: User, team_id: str) -> bool:
        team_ids = await self.authorized_team_ids(actor)
        return team_ids is None or str(team_id) in team_ids


__all__ = ["TeamDataScope", "TeamScopePolicy"]
