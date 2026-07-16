"""Write-side application service for explicit team relationships."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.roles import ROLE_TRAINING_MANAGER
from common.db.models import Team, TeamLeaderAssignment, TeamMembership, User


class TeamDomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TeamService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_team(
        self, *, code: str, name: str, actor: User, team_id: str | None = None
    ) -> Team:
        normalized_code = code.strip().lower()
        if not normalized_code or not name.strip():
            raise TeamDomainError("[INVALID_TEAM]", "团队编码和名称不能为空。")
        existing = await self.db.scalar(
            select(Team).where(Team.code == normalized_code)
        )
        if existing is not None:
            raise TeamDomainError("[TEAM_CODE_EXISTS]", "团队编码已存在。")
        values: dict[str, object] = {
            "code": normalized_code,
            "name": name.strip(),
            "created_by": str(actor.user_id),
        }
        if team_id is not None:
            values["team_id"] = team_id
        team = Team(**values)
        self.db.add(team)
        await self.db.flush()
        return team

    async def assign_primary_member(
        self,
        *,
        team: Team,
        learner: User,
        actor: User,
        effective_at: datetime | None = None,
    ) -> TeamMembership:
        now = effective_at or datetime.now(UTC)
        current = await self.db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == str(learner.user_id),
                TeamMembership.membership_role == "primary",
                TeamMembership.effective_to.is_(None),
            )
        )
        if current is not None and str(current.team_id) == str(team.team_id):
            return current
        if current is not None:
            current.effective_to = now
        membership = TeamMembership(
            team_id=str(team.team_id),
            user_id=str(learner.user_id),
            membership_role="primary",
            effective_from=now,
            created_by=str(actor.user_id),
        )
        self.db.add(membership)
        await self.db.flush()
        return membership

    async def assign_leader(
        self,
        *,
        team: Team,
        leader: User,
        actor: User,
        assignment_role: str = "primary",
        effective_at: datetime | None = None,
    ) -> TeamLeaderAssignment:
        if str(leader.role).strip().lower() != ROLE_TRAINING_MANAGER:
            raise TeamDomainError(
                "[TEAM_LEADER_ROLE_REQUIRED]",
                "只有培训管理员账号可以设置为销售组长。",
            )
        if assignment_role not in {"primary", "proxy"}:
            raise TeamDomainError("[INVALID_LEADER_ROLE]", "组长关系类型无效。")
        now = effective_at or datetime.now(UTC)
        current_query = select(TeamLeaderAssignment).where(
            TeamLeaderAssignment.team_id == str(team.team_id),
            TeamLeaderAssignment.assignment_role == assignment_role,
            TeamLeaderAssignment.effective_to.is_(None),
        )
        if assignment_role == "proxy":
            current_query = current_query.where(
                TeamLeaderAssignment.leader_user_id == str(leader.user_id)
            )
        current = await self.db.scalar(current_query)
        if current is not None and str(current.leader_user_id) == str(leader.user_id):
            return current
        if current is not None and assignment_role == "primary":
            current.effective_to = now
        assignment = TeamLeaderAssignment(
            team_id=str(team.team_id),
            leader_user_id=str(leader.user_id),
            assignment_role=assignment_role,
            effective_from=now,
            created_by=str(actor.user_id),
        )
        self.db.add(assignment)
        await self.db.flush()
        return assignment
