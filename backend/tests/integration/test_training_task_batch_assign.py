from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import TrainingTask, User
from curriculum_practice.models import PracticeTemplate


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _user(db: AsyncSession, *, role: str = "user", department: str | None = "Sales") -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"batch_assign_{uuid.uuid4().hex[:10]}",
        name="Batch Assign User",
        department=department,
        email=f"batch-assign-{uuid.uuid4().hex[:10]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _curriculum_plan() -> dict[str, Any]:
    return {
        "name": "学习-考核-实战训练",
        "stages": [
            {"template_stage_key": "study", "stage_type": "study"},
            {"template_stage_key": "exam", "stage_type": "exam"},
            {"template_stage_key": "practice", "stage_type": "practice"},
        ],
    }


async def _template(
    db: AsyncSession,
    *,
    status: str = "published",
    curriculum_plan: dict[str, Any] | None = None,
) -> PracticeTemplate:
    template = PracticeTemplate(
        template_id=str(uuid.uuid4()),
        name="三阶段训练模板",
        scenario_type="sales",
        mode="mixed_path",
        agent_id=str(uuid.uuid4()),
        persona_id=str(uuid.uuid4()),
        runtime_profile_id=str(uuid.uuid4()),
        voice_mode="stepfun_realtime",
        scoring_ruleset_id=str(uuid.uuid4()),
        knowledge_base_refs=[],
        curriculum_plan=curriculum_plan if curriculum_plan is not None else _curriculum_plan(),
        status=status,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


def _payload(template: PracticeTemplate, user_ids: list[str]) -> dict[str, Any]:
    return {
        "user_ids": user_ids,
        "template_id": str(template.template_id),
        "curriculum_plan_id": str(template.template_id),
        "title": "学习-考核-实战训练",
        "scenario_type": "sales",
        "goal": "完成三阶段训练闭环",
        "completion_criteria": {"required_stages": ["study", "exam", "practice"]},
    }


@pytest.mark.asyncio
async def test_batch_assign_creates_training_task_for_same_department_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Sales")
    template = await _template(test_db)

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assigned_count"] == 1
    assert data["skipped_count"] == 0
    assert data["failed_count"] == 0
    task_id = data["assigned"][0]["task_id"]

    task = await test_db.get(TrainingTask, task_id)
    assert task is not None
    assert task.assignee_id == str(assignee.user_id)
    assert task.practice_template_id == str(template.template_id)
    assert task.curriculum_plan_id == str(template.template_id)


@pytest.mark.asyncio
async def test_batch_assign_skips_existing_template_assignment_without_duplicate(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Sales")
    template = await _template(test_db)
    existing = TrainingTask(
        title="已有训练",
        assignee_id=str(assignee.user_id),
        scenario_type="sales",
        goal="已有训练目标",
        completion_criteria={},
        practice_template_id=str(template.template_id),
        curriculum_plan_id=str(template.template_id),
        source="batch_assign",
        status="assigned",
    )
    test_db.add(existing)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assigned_count"] == 0
    assert data["skipped"] == [
        {"user_id": str(assignee.user_id), "reason": "[TRAINING_TASK_ALREADY_ASSIGNED]"}
    ]
    rows = (
        await test_db.execute(
            select(TrainingTask).where(
                TrainingTask.assignee_id == str(assignee.user_id),
                TrainingTask.practice_template_id == str(template.template_id),
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_batch_assign_reports_cross_department_user_as_failed(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Customer Success")
    template = await _template(test_db)

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["failed_count"] == 1
    assert data["failed"] == [
        {"user_id": str(assignee.user_id), "reason": "[DEPARTMENT_SCOPE_VIOLATION]"}
    ]


@pytest.mark.asyncio
async def test_batch_assign_reports_unpublished_template_for_each_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Sales")
    template = await _template(test_db, status="draft")

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["failed_count"] == 1
    assert data["failed"][0]["reason"] == "[PRACTICE_TEMPLATE_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_batch_assign_reports_invalid_template_id_for_each_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Sales")
    payload = {
        "user_ids": [str(assignee.user_id)],
        "template_id": "not-a-template-id",
        "curriculum_plan_id": "not-a-template-id",
        "title": "学习-考核-实战训练",
        "scenario_type": "sales",
        "goal": "完成三阶段训练闭环",
    }

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=payload,
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["failed_count"] == 1
    assert data["failed"][0]["reason"] == "[PRACTICE_TEMPLATE_INVALID]"


@pytest.mark.asyncio
async def test_batch_assign_reports_invalid_curriculum_plan(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin", department="Sales")
    assignee = await _user(test_db, department="Sales")
    template = await _template(test_db, curriculum_plan={"name": "缺少阶段", "stages": []})

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["failed_count"] == 1
    assert data["failed"][0]["reason"] == "[CURRICULUM_PLAN_INVALID]"


@pytest.mark.asyncio
async def test_batch_assign_rejects_normal_user_without_management_role(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    requester = await _user(test_db, role="user", department="Sales")
    assignee = await _user(test_db, department="Sales")
    template = await _template(test_db)

    response = await async_client.post(
        "/api/v1/training-tasks/batch-assign",
        json=_payload(template, [str(assignee.user_id)]),
        headers=_auth_headers(requester),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "[ROLE_REQUIRED]"
