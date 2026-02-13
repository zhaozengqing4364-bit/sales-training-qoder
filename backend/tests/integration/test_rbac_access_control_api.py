"""
Integration tests for Story 1.4 RBAC access control boundaries.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    role: str,
    is_active: bool = True,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"rbac_{uuid.uuid4().hex[:8]}",
        name=email.split("@")[0],
        department="QA",
        email=email,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_admin_endpoint_requires_authentication_and_trace_id(
    async_client,
) -> None:
    response = await async_client.get("/api/v1/admin/users")

    assert response.status_code == 401
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_admin_endpoint_rejects_non_admin_with_trace_id(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="rbac-user@example.com",
        role="user",
        is_active=True,
    )
    token = create_access_token(data={"sub": str(user.user_id)})

    response = await async_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_training_endpoint_requires_authentication_and_trace_id(
    async_client,
) -> None:
    response = await async_client.get("/api/v1/training-categories")

    assert response.status_code == 401
    body = response.json()
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_training_endpoint_allows_authenticated_user(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="rbac-training@example.com",
        role="user",
        is_active=True,
    )
    token = create_access_token(data={"sub": str(user.user_id)})

    response = await async_client.get(
        "/api/v1/training-categories",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_admin_presentations_requires_authentication_and_trace_id(
    async_client,
) -> None:
    response = await async_client.get("/api/v1/admin/presentations")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_admin_presentations_rejects_non_admin_with_trace_id(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="rbac-presentation-user@example.com",
        role="user",
        is_active=True,
    )
    token = create_access_token(data={"sub": str(user.user_id)})

    response = await async_client.get(
        "/api/v1/admin/presentations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body
    assert "ADMIN_REQUIRED" in body.get("message", "")


@pytest.mark.asyncio
async def test_admin_knowledge_requires_authentication_and_trace_id(
    async_client,
) -> None:
    response = await async_client.get("/api/v1/admin/knowledge?page=1&page_size=1")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_admin_knowledge_rejects_non_admin_with_trace_id(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="rbac-knowledge-user@example.com",
        role="user",
        is_active=True,
    )
    token = create_access_token(data={"sub": str(user.user_id)})

    response = await async_client.get(
        "/api/v1/admin/knowledge?page=1&page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body
    assert "ADMIN_REQUIRED" in body.get("message", "")


@pytest.mark.asyncio
async def test_admin_knowledge_alias_rejects_non_admin_with_trace_id(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="rbac-knowledge-alias-user@example.com",
        role="user",
        is_active=True,
    )
    token = create_access_token(data={"sub": str(user.user_id)})

    response = await async_client.get(
        "/api/v1/admin/knowledge-bases?page=1&page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "trace_id" in body
    assert "ADMIN_REQUIRED" in body.get("message", "")
