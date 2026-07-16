from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import TrainingTask, User
from common.teams.service import TeamService
from supervisor.service import SupervisorReviewService, SupervisorServiceError


def _user(*, role: str, name: str) -> User:
    token = uuid.uuid4().hex
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"team-scope-{token}",
        name=name,
        email=f"{token}@example.com",
        role=role,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_team_insights_use_explicit_scope_and_revocation_is_immediate(
    test_db: AsyncSession,
    async_client: AsyncClient,
) -> None:
    admin = _user(role="admin", name="Admin")
    leader = _user(role="training_manager", name="Leader")
    learner = _user(role="user", name="Learner")
    outsider = _user(role="user", name="Outsider")
    test_db.add_all([admin, leader, learner, outsider])
    await test_db.flush()
    team_service = TeamService(test_db)
    team = await team_service.create_team(code="scope-east", name="华东组", actor=admin)
    await team_service.assign_leader(team=team, leader=leader, actor=admin)
    membership = await team_service.assign_primary_member(
        team=team, learner=learner, actor=admin
    )
    test_db.add_all(
        [
            TrainingTask(
                title="成员任务",
                assignee_id=str(learner.user_id),
                scenario_type="sales",
                goal="完成练习",
                status="completed",
                completion_criteria={},
            ),
            TrainingTask(
                title="越权任务",
                assignee_id=str(outsider.user_id),
                scenario_type="sales",
                goal="不可见",
                status="assigned",
                completion_criteria={},
            ),
        ]
    )
    await test_db.commit()

    headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(leader.user_id), 'role': 'training_manager'})}"
    }
    scope_response = await async_client.get(
        "/api/v1/supervisor/team/scope", headers=headers
    )
    assert scope_response.status_code == 200
    workbench_response = await async_client.get(
        f"/api/v1/supervisor/team/workbench?team_id={team.team_id}", headers=headers
    )
    assert workbench_response.status_code == 200
    assert "readiness" not in workbench_response.json()["data"]
    assert "retraining_candidates" not in workbench_response.json()["data"]

    insights = await SupervisorReviewService(test_db).get_team_insights(
        current_user=leader,
        team_id=str(team.team_id),
        date_from=datetime(2026, 1, 1, tzinfo=UTC),
        date_to=datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert insights.completion.total_tasks == 1
    assert insights.completion.completed_tasks == 1
    assert {item.learner_id for item in insights.learners} == {str(learner.user_id)}

    with pytest.raises(SupervisorServiceError) as denied:
        await SupervisorReviewService(test_db).get_team_insights_detail(
            current_user=leader, learner_id=str(outsider.user_id)
        )
    assert denied.value.status_code == 404

    setattr(membership, "effective_to", datetime.now(UTC))
    test_db.add(membership)
    await test_db.commit()
    with pytest.raises(SupervisorServiceError) as revoked:
        await SupervisorReviewService(test_db).get_team_insights_detail(
            current_user=leader, learner_id=str(learner.user_id)
        )
    assert revoked.value.status_code == 404
