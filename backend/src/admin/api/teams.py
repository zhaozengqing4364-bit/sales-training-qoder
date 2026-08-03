"""Administrative APIs for explicit team relationships."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.roles import ROLE_TRAINING_MANAGER
from common.auth.service import get_current_admin_user
from common.db.models import SystemLog, Team, TeamLeaderAssignment, TeamMembership, User
from common.db.session import get_db
from common.teams.service import TeamDomainError, TeamService

router = APIRouter(prefix="/admin/teams", tags=["admin-teams"])


class TeamCreateRequest(BaseModel):
    code: str
    name: str
    primary_leader_user_id: str

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class TeamMemberAssignRequest(BaseModel):
    learner_user_id: str


class TeamLeaderAssignRequest(BaseModel):
    leader_user_id: str
    assignment_role: str = "primary"


def _team_payload(
    team: Team,
    leaders: list[dict[str, Any]],
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "team_id": str(team.team_id),
        "code": team.code,
        "name": team.name,
        "is_active": bool(team.is_active),
        "leader_user_ids": [leader["user_id"] for leader in leaders],
        "leaders": leaders,
        "members": members,
        "member_count": len(members),
    }


def _audit(
    db: AsyncSession, *, actor: User, action: str, details: dict[str, Any]
) -> None:
    db.add(
        SystemLog(
            action=action,
            user_id=str(actor.user_id),
            user_identifier=actor.email or actor.name or str(actor.user_id),
            status="success",
            details=json.dumps(details, ensure_ascii=False),
        )
    )


@router.get("")
async def list_teams(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    del current_user
    teams = list((await db.scalars(select(Team).order_by(Team.name, Team.code))).all())
    now = datetime.now(UTC)
    team_ids = [str(team.team_id) for team in teams]
    leaders_by_team: dict[str, list[dict[str, Any]]] = {
        team_id: [] for team_id in team_ids
    }
    members_by_team: dict[str, list[dict[str, Any]]] = {
        team_id: [] for team_id in team_ids
    }
    if team_ids:
        leader_rows = (
            await db.execute(
                select(TeamLeaderAssignment, User)
                .join(User, User.user_id == TeamLeaderAssignment.leader_user_id)
                .where(
                    TeamLeaderAssignment.team_id.in_(team_ids),
                    TeamLeaderAssignment.effective_from <= now,
                    or_(
                        TeamLeaderAssignment.effective_to.is_(None),
                        TeamLeaderAssignment.effective_to > now,
                    ),
                )
                .order_by(
                    TeamLeaderAssignment.team_id,
                    TeamLeaderAssignment.assignment_role,
                    User.name,
                )
            )
        ).all()
        for assignment, user in leader_rows:
            leaders_by_team[str(assignment.team_id)].append(
                {
                    "user_id": str(user.user_id),
                    "name": user.name,
                    "email": user.email,
                    "assignment_role": assignment.assignment_role,
                }
            )

        member_rows = (
            await db.execute(
                select(TeamMembership, User)
                .join(User, User.user_id == TeamMembership.user_id)
                .where(
                    TeamMembership.team_id.in_(team_ids),
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_to.is_(None),
                        TeamMembership.effective_to > now,
                    ),
                )
                .order_by(TeamMembership.team_id, User.name, User.email)
            )
        ).all()
        for membership, user in member_rows:
            members_by_team[str(membership.team_id)].append(
                {
                    "user_id": str(user.user_id),
                    "name": user.name,
                    "email": user.email,
                    "membership_role": membership.membership_role,
                }
            )

    items = [
        _team_payload(
            team,
            leaders_by_team[str(team.team_id)],
            members_by_team[str(team.team_id)],
        )
        for team in teams
    ]
    return {"success": True, "data": {"items": items, "total": len(items)}}


@router.get("/leader-candidates")
async def list_leader_candidates(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    del current_user
    users = (
        await db.scalars(
            select(User)
            .where(User.role == ROLE_TRAINING_MANAGER, User.is_active.is_(True))
            .order_by(User.name, User.email)
        )
    ).all()
    return {
        "success": True,
        "data": {
            "items": [
                {"user_id": str(user.user_id), "name": user.name, "email": user.email}
                for user in users
            ]
        },
    }


@router.post("")
async def create_team(
    payload: TeamCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    leader = await db.get(User, payload.primary_leader_user_id)
    if leader is None:
        raise HTTPException(status_code=404, detail="[TEAM_LEADER_NOT_FOUND]")
    service = TeamService(db)
    try:
        team = await service.create_team(
            code=payload.code, name=payload.name, actor=current_user
        )
        await service.assign_leader(team=team, leader=leader, actor=current_user)
    except TeamDomainError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=exc.code) from exc
    _audit(
        db,
        actor=current_user,
        action="admin.team.created",
        details={"team_id": str(team.team_id), "code": team.code},
    )
    await db.commit()
    return {
        "success": True,
        "data": _team_payload(
            team,
            [
                {
                    "user_id": str(leader.user_id),
                    "name": leader.name,
                    "email": leader.email,
                    "assignment_role": "primary",
                }
            ],
            [],
        ),
    }


@router.post("/{team_id}/members")
async def assign_member(
    team_id: str,
    payload: TeamMemberAssignRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    team = await db.get(Team, team_id)
    learner = await db.get(User, payload.learner_user_id)
    if team is None or learner is None:
        raise HTTPException(status_code=404, detail="[TEAM_OR_LEARNER_NOT_FOUND]")
    membership = await TeamService(db).assign_primary_member(
        team=team, learner=learner, actor=current_user
    )
    _audit(
        db,
        actor=current_user,
        action="admin.team.member.assigned",
        details={"team_id": team_id, "learner_user_id": str(learner.user_id)},
    )
    await db.commit()
    return {"success": True, "data": {"membership_id": str(membership.membership_id)}}


@router.post("/{team_id}/leaders")
async def assign_leader(
    team_id: str,
    payload: TeamLeaderAssignRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    team = await db.get(Team, team_id)
    leader = await db.get(User, payload.leader_user_id)
    if team is None or leader is None:
        raise HTTPException(status_code=404, detail="[TEAM_OR_LEADER_NOT_FOUND]")
    try:
        assignment = await TeamService(db).assign_leader(
            team=team,
            leader=leader,
            actor=current_user,
            assignment_role=payload.assignment_role,
        )
    except TeamDomainError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=exc.code) from exc
    _audit(
        db,
        actor=current_user,
        action="admin.team.leader.assigned",
        details={
            "team_id": team_id,
            "leader_user_id": str(leader.user_id),
            "assignment_role": payload.assignment_role,
        },
    )
    await db.commit()
    return {"success": True, "data": {"assignment_id": str(assignment.assignment_id)}}
