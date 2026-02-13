"""
Integration tests for controlled auth login and token issuance.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import verify_token
from common.db.models import User


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    role: str,
    is_active: bool,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"login_{uuid.uuid4().hex[:8]}",
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
async def test_login_success_issues_token_with_role_claim(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-success@example.com",
        role="admin",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "trace_id" in body
    assert body["data"]["user"]["role"] == "admin"

    token = body["data"]["token"]
    claims = verify_token(token)
    assert claims["sub"] == str(user.user_id)
    assert claims["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_secure_error(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-wrong-pwd@example.com",
        role="user",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[INVALID_CREDENTIALS]"
    assert "trace_id" in body
    assert "database" not in body["message"].lower()


@pytest.mark.asyncio
async def test_login_disabled_user_returns_secure_error_without_leak(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-disabled@example.com",
        role="user",
        is_active=False,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[INVALID_CREDENTIALS]"
    assert "trace_id" in body
    assert "disabled" not in body["message"].lower()


@pytest.mark.asyncio
async def test_login_unknown_email_returns_same_secure_error_code(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    count_before = (
        await test_db.execute(select(func.count()).select_from(User))
    ).scalar() or 0

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown-user@example.com", "password": "Password123!"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[INVALID_CREDENTIALS]"
    assert "trace_id" in body
    count_after = (
        await test_db.execute(select(func.count()).select_from(User))
    ).scalar() or 0
    assert count_after == count_before


@pytest.mark.asyncio
async def test_login_returns_503_when_credentials_not_configured(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_SHARED_PASSWORD", raising=False)
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "auth-missing-config@example.com", "password": "whatever"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[AUTH_SERVICE_UNAVAILABLE]"
    assert "trace_id" in body


@pytest.mark.asyncio
async def test_login_user_specific_password_mapping_isolation(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_SHARED_PASSWORD", raising=False)
    monkeypatch.setenv(
        "AUTH_USER_PASSWORDS_JSON",
        json.dumps(
            {
                "auth-map-admin@example.com": "AdminPass123!",
                "auth-map-user@example.com": "UserPass123!",
            }
        ),
    )

    admin_user = await _create_user(
        test_db,
        email="auth-map-admin@example.com",
        role="admin",
        is_active=True,
    )
    await _create_user(
        test_db,
        email="auth-map-user@example.com",
        role="user",
        is_active=True,
    )

    success_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "AdminPass123!"},
    )
    assert success_response.status_code == 200

    fail_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "UserPass123!"},
    )
    assert fail_response.status_code == 401
    assert fail_response.json()["error"] == "[INVALID_CREDENTIALS]"


@pytest.mark.asyncio
async def test_login_falls_back_to_shared_password_when_user_not_in_override_map(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "SharedPass123!")
    monkeypatch.setenv(
        "AUTH_USER_PASSWORDS_JSON",
        json.dumps(
            {
                "mapped-user@example.com": "MappedPass123!",
            }
        ),
    )

    target_user = await _create_user(
        test_db,
        email="fallback-shared@example.com",
        role="admin",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": target_user.email, "password": "SharedPass123!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["user"]["role"] == "admin"
