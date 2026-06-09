from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User


async def _create_user(
    test_db: AsyncSession,
    *,
    role: str,
    department: str = "销售一部",
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-rbac-{uuid.uuid4().hex[:8]}",
        name=role,
        department=department,
        email=f"{role}-{uuid.uuid4().hex[:6]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_enforce_granular_sales_trainer_rbac(
    async_client,
    test_db: AsyncSession,
) -> None:
    content_admin = await _create_user(test_db, role="content_admin")
    training_lead = await _create_user(test_db, role="support", department="华东销售")
    ops_user = await _create_user(test_db, role="operations")
    learner = await _create_user(test_db, role="user")

    content_questions = await async_client.get(
        "/api/v1/admin/sales-trainer/questions",
        headers=_auth_headers(content_admin),
    )
    assert content_questions.status_code == 200

    content_settings = await async_client.get(
        "/api/v1/admin/sales-trainer/settings",
        headers=_auth_headers(content_admin),
    )
    assert content_settings.status_code == 403

    training_records = await async_client.get(
        "/api/v1/admin/sales-trainer/audio-submissions",
        headers=_auth_headers(training_lead),
    )
    assert training_records.status_code == 200

    ops_settings = await async_client.get(
        "/api/v1/admin/sales-trainer/settings",
        headers=_auth_headers(ops_user),
    )
    assert ops_settings.status_code == 200

    ops_logs = await async_client.get(
        "/api/v1/admin/sales-trainer/operation-logs",
        headers=_auth_headers(ops_user),
    )
    assert ops_logs.status_code == 200

    learner_settings = await async_client.get(
        "/api/v1/admin/sales-trainer/settings",
        headers=_auth_headers(learner),
    )
    assert learner_settings.status_code == 403
