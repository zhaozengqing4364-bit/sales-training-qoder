from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import TeamLeaderAssignment, TeamMembership, User
from common.teams import TeamScopePolicy
from common.teams.service import TeamService


async def _user(db: AsyncSession, *, role: str, email: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"team-{uuid.uuid4().hex}",
        name=email.split("@")[0],
        email=email,
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_only_explicit_membership_grants_team_scope(test_db: AsyncSession) -> None:
    admin = await _user(test_db, role="admin", email="admin@team.test")
    leader = await _user(test_db, role="training_manager", email="lead@team.test")
    assigned = await _user(test_db, role="user", email="assigned@team.test")
    unassigned = await _user(test_db, role="user", email="other@team.test")
    service = TeamService(test_db)
    team = await service.create_team(code="east", name="East", actor=admin)
    await service.assign_leader(team=team, leader=leader, actor=admin)
    await service.assign_primary_member(team=team, learner=assigned, actor=admin)
    await test_db.commit()

    policy = TeamScopePolicy(test_db)
    assert await policy.can_view_learner(leader, str(assigned.user_id)) is True
    assert await policy.can_view_learner(leader, str(unassigned.user_id)) is False


@pytest.mark.asyncio
async def test_primary_relationship_uniqueness_is_database_enforced(
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", email="admin2@team.test")
    leader_a = await _user(test_db, role="training_manager", email="a@team.test")
    leader_b = await _user(test_db, role="training_manager", email="b@team.test")
    learner = await _user(test_db, role="user", email="learner@team.test")
    service = TeamService(test_db)
    team_a = await service.create_team(code="a", name="A", actor=admin)
    team_b = await service.create_team(code="b", name="B", actor=admin)
    await service.assign_leader(team=team_a, leader=leader_a, actor=admin)
    await service.assign_primary_member(team=team_a, learner=learner, actor=admin)
    await test_db.commit()
    team_a_id = str(team_a.team_id)
    team_b_id = str(team_b.team_id)
    learner_id = str(learner.user_id)
    leader_b_id = str(leader_b.user_id)
    admin_id = str(admin.user_id)

    test_db.add(
        TeamMembership(
            team_id=team_b_id,
            user_id=learner_id,
            membership_role="primary",
            created_by=admin_id,
        )
    )
    with pytest.raises(IntegrityError):
        await test_db.commit()
    await test_db.rollback()

    test_db.add(
        TeamLeaderAssignment(
            team_id=team_a_id,
            leader_user_id=leader_b_id,
            assignment_role="primary",
            created_by=admin_id,
        )
    )
    with pytest.raises(IntegrityError):
        await test_db.commit()
