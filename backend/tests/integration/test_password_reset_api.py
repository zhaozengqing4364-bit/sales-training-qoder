"""Integration tests for forgot/reset password flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import agent.models  # noqa: F401  # ensure Agent/Persona tables are registered on Base metadata for sqlite tests
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User


async def _create_user(
    db: AsyncSession,
    *,
    email: str,
    is_active: bool = True,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"password_reset_{uuid.uuid4().hex[:8]}",
        name=email.split("@")[0],
        department="QA",
        email=email,
        role="user",
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _fetch_reset_rows(db: AsyncSession):
    result = await db.execute(
        text(
            """
            SELECT user_id, token_hash, expires_at, used_at
            FROM password_reset_tokens
            ORDER BY created_at ASC
            """
        )
    )
    return result.mappings().all()


@pytest.mark.asyncio
async def test_forgot_password_creates_single_active_token_and_returns_generic_success(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(test_db, email="reset-create@example.com")

    response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["message"] == "如果该邮箱已注册，重置链接将发送到您的邮箱"

    rows = await _fetch_reset_rows(test_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == str(user.user_id)
    assert row["token_hash"]
    assert row["used_at"] is None

    expires_at = row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > datetime.now(UTC) + timedelta(minutes=25)
    assert expires_at < datetime.now(UTC) + timedelta(minutes=31)


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_generic_success_without_creating_token(
    async_client,
    test_db: AsyncSession,
) -> None:
    response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing-reset@example.com"},
        headers={"X-Forwarded-For": "203.0.113.11"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["message"] == "如果该邮箱已注册，重置链接将发送到您的邮箱"

    rows = await _fetch_reset_rows(test_db)
    assert rows == []


@pytest.mark.asyncio
async def test_forgot_password_rate_limited_per_ip(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(test_db, email="reset-rate-limit@example.com")
    headers = {"X-Forwarded-For": "203.0.113.12"}

    first = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers=headers,
    )
    second = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 429
    payload = second.json()
    assert payload["detail"]["error"] == "[RATE_LIMIT_EXCEEDED]"


@pytest.mark.asyncio
async def test_reset_password_consumes_token_and_updates_login_password(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "OriginalPass123!")
    monkeypatch.setattr("secrets.token_urlsafe", lambda _: "known-reset-token")

    user = await _create_user(test_db, email="reset-complete@example.com")
    user_email = user.email

    forgot_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user_email},
        headers={"X-Forwarded-For": "203.0.113.13"},
    )
    assert forgot_response.status_code == 200

    reset_response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "known-reset-token", "new_password": "NewPass123!"},
    )
    assert reset_response.status_code == 200, reset_response.text
    assert reset_response.json()["success"] is True

    reused_response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "known-reset-token", "new_password": "AnotherPass123!"},
    )
    assert reused_response.status_code == 400
    assert reused_response.json()["error"] == "[INVALID_RESET_TOKEN]"

    old_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": "OriginalPass123!"},
    )
    assert old_login.status_code == 401

    new_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": "NewPass123!"},
    )
    assert new_login.status_code == 200

    rows = await _fetch_reset_rows(test_db)
    assert len(rows) == 1
    assert rows[0]["used_at"] is not None


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password(
    async_client,
) -> None:
    response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "ignored", "new_password": "short"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "[INVALID_PASSWORD]"
