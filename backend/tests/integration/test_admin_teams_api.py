from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from common.teams.service import TeamService


def _user(*, role: str, name: str, email: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin-team-{uuid.uuid4().hex}",
        name=name,
        email=email,
        role=role,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_should_return_named_leaders_and_members_for_admin_configuration(
    test_db: AsyncSession,
    async_client: AsyncClient,
) -> None:
    admin = _user(role="admin", name="平台管理员", email="admin@qoder.ai")
    leader = _user(role="training_manager", name="华东组长", email="leader@qoder.ai")
    learner = _user(role="user", name="销售学员", email="learner@qoder.ai")
    test_db.add_all([admin, leader, learner])
    await test_db.flush()
    service = TeamService(test_db)
    team = await service.create_team(code="east-sales", name="华东销售组", actor=admin)
    await service.assign_leader(team=team, leader=leader, actor=admin)
    await service.assign_primary_member(team=team, learner=learner, actor=admin)
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/teams",
        headers={
            "Authorization": f"Bearer {create_access_token({'sub': str(admin.user_id), 'role': 'admin'})}"
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["team_id"] == str(team.team_id)
    assert item["leader_user_ids"] == [str(leader.user_id)]
    assert item["leaders"] == [
        {
            "user_id": str(leader.user_id),
            "name": "华东组长",
            "email": "leader@qoder.ai",
            "assignment_role": "primary",
        }
    ]
    assert item["member_count"] == 1
    assert item["members"] == [
        {
            "user_id": str(learner.user_id),
            "name": "销售学员",
            "email": "learner@qoder.ai",
            "membership_role": "primary",
        }
    ]
