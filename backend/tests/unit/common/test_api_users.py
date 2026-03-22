"""
Tests for Users API endpoints
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User


@pytest.mark.asyncio
async def test_update_current_user_success(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test successful user profile update"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"name": "Updated Name", "department": "Engineering"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == "Updated Name"
    assert data["data"]["department"] == "Engineering"


@pytest.mark.asyncio
async def test_update_user_email_success(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test successful user email update"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"email": "newemail@example.com"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == test_user.name


@pytest.mark.asyncio
async def test_update_user_email_duplicate(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    another_user: User,
    auth_headers: dict,
):
    """Test that duplicate email is rejected"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"email": another_user.email},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "EMAIL_ALREADY_EXISTS" in data["error"]


@pytest.mark.asyncio
async def test_update_user_partial_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test that only provided fields are updated"""
    original_department = test_user.department

    response = await async_client.patch(
        "/api/v1/users/me",
        json={"name": "New Name Only"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == "New Name Only"
    assert data["data"]["department"] == original_department


@pytest.mark.asyncio
async def test_update_user_no_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test update with no fields provided"""
    response = await async_client.patch(
        "/api/v1/users/me", json={}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == test_user.name


@pytest.mark.asyncio
async def test_update_user_unauthorized(
    async_client: AsyncClient,
):
    """Test that unauthorized requests are rejected"""
    response = await async_client.patch(
        "/api/v1/users/me", json={"name": "Unauthorized Update"}
    )

    assert response.status_code in [401, 403]
