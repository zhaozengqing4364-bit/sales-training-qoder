"""Read-only projections for the explicit Team organization model."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import Team, TeamMembership


@dataclass(frozen=True, slots=True)
class TeamSummary:
    """Stable public identity for a Team without exposing membership internals."""

    team_id: str
    code: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


async def active_primary_teams_by_user_ids(
    db: AsyncSession,
    user_ids: Iterable[object],
    *,
    now: datetime | None = None,
) -> dict[str, TeamSummary]:
    """Return each user's active primary Team in one query.

    The partial unique index on ``team_memberships`` guarantees at most one
    active primary membership per user. This function deliberately ignores
    inactive Teams so callers never present an obsolete organization as an
    authorization or reporting dimension.
    """

    normalized_user_ids = {str(user_id) for user_id in user_ids if user_id is not None}
    if not normalized_user_ids:
        return {}

    effective_at = now or datetime.now(UTC)
    rows = (
        await db.execute(
            select(TeamMembership.user_id, Team.team_id, Team.code, Team.name)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id.in_(normalized_user_ids),
                TeamMembership.membership_role == "primary",
                TeamMembership.effective_from <= effective_at,
                or_(
                    TeamMembership.effective_to.is_(None),
                    TeamMembership.effective_to > effective_at,
                ),
                Team.is_active.is_(True),
            )
        )
    ).all()
    return {
        str(row.user_id): TeamSummary(
            team_id=str(row.team_id),
            code=str(row.code),
            name=str(row.name),
        )
        for row in rows
    }


async def active_primary_team_for_user(
    db: AsyncSession,
    user_id: object,
    *,
    now: datetime | None = None,
) -> TeamSummary | None:
    """Convenience wrapper for single-user response assembly."""

    teams = await active_primary_teams_by_user_ids(db, [user_id], now=now)
    return teams.get(str(user_id))


__all__ = [
    "TeamSummary",
    "active_primary_team_for_user",
    "active_primary_teams_by_user_ids",
]
