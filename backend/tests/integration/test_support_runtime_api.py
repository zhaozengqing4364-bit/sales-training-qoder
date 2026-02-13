"""
Integration tests for Story 1.5 support runtime read-only endpoints.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import SystemLog, User


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    role: str,
    is_active: bool = True,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"support_{uuid.uuid4().hex[:8]}",
        name=email.split("@")[0],
        department="Support",
        email=email,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_support_runtime_overview_requires_authentication(async_client) -> None:
    response = await async_client.get("/api/v1/support/runtime/overview")

    assert response.status_code == 401
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_support_role_can_read_runtime_overview_and_faults(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-reader@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    overview_response = await async_client.get(
        "/api/v1/support/runtime/overview",
        headers=headers,
    )
    assert overview_response.status_code == 200
    overview_body = overview_response.json()
    assert overview_body["success"] is True
    assert "trace_id" in overview_body
    assert "session_health" in overview_body["data"]

    faults_response = await async_client.get(
        "/api/v1/support/runtime/faults?limit=10",
        headers=headers,
    )
    assert faults_response.status_code == 200
    faults_body = faults_response.json()
    assert faults_body["success"] is True
    assert "trace_id" in faults_body
    assert "items" in faults_body["data"]


@pytest.mark.asyncio
async def test_support_role_is_rejected_for_admin_write_operations(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-no-write@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    response = await async_client.delete(
        f"/api/v1/admin/training-records/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_non_support_user_is_rejected_from_support_runtime(
    async_client,
    test_db: AsyncSession,
) -> None:
    normal_user = await _create_user(
        test_db,
        email="normal-user@example.com",
        role="user",
    )
    token = create_access_token(data={"sub": str(normal_user.user_id)})

    response = await async_client.get(
        "/api/v1/support/runtime/overview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_support_runtime_faults_only_returns_failed_or_warning_by_default(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-fault-filter@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    # Prepare mixed statuses
    test_db.add_all(
        [
            SystemLog(
                action="support.test.success",
                user_identifier="system",
                status="success",
                created_at=datetime.now(UTC),
            ),
            SystemLog(
                action="support.test.failed",
                user_identifier="system",
                status="failed",
                created_at=datetime.now(UTC),
            ),
            SystemLog(
                action="support.test.warning",
                user_identifier="system",
                status="warning",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/support/runtime/faults?limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items
    assert all(item["status"] in {"failed", "warning"} for item in items)


@pytest.mark.asyncio
async def test_support_runtime_faults_rejects_invalid_status_filter(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-invalid-filter@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    response = await async_client.get(
        "/api/v1/support/runtime/faults?status=success",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"] == "[INVALID_STATUS_FILTER]"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_support_role_is_rejected_for_admin_publish_operations(
    async_client,
    test_db: AsyncSession,
) -> None:
    support_user = await _create_user(
        test_db,
        email="support-no-publish@example.com",
        role="support",
    )
    token = create_access_token(data={"sub": str(support_user.user_id)})

    response = await async_client.post(
        f"/api/v1/admin/agents/{uuid.uuid4()}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body
