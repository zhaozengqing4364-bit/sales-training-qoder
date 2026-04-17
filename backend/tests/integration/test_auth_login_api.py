"""
Integration tests for controlled auth login and token issuance.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

import agent.models  # noqa: F401  # ensure Agent/Persona tables are registered on Base metadata for sqlite tests
from common.auth.api import AUTH_FORMALIZATION_SURFACE
from common.auth.service import (
    AUTH_CSRF_COOKIE_NAME,
    AUTH_CSRF_HEADER_NAME,
    AUTH_SESSION_COOKIE_NAME,
    get_wecom_oauth_return_to_cookie_name,
    get_wecom_oauth_state_cookie_name,
    verify_token,
)
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


async def _fetch_reset_rows(db: AsyncSession):
    result = await db.execute(
        text(
            """
            SELECT
                user_id,
                token_hash,
                expires_at,
                used_at,
                invalidated_at,
                invalidation_reason,
                delivery_status,
                delivery_attempted_at,
                delivery_error
            FROM password_reset_tokens
            ORDER BY created_at ASC
            """
        )
    )
    return result.mappings().all()


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
async def test_login_sets_http_only_cookie_and_cookie_auth_works(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-cookie@example.com",
        role="user",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )

    assert response.status_code == 200
    set_cookie_header = response.headers.get("set-cookie", "")
    assert f"{AUTH_SESSION_COOKIE_NAME}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/" in set_cookie_header

    me_response = await async_client.get("/api/v1/users/me")
    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["success"] is True
    assert me_body["data"]["id"] == str(user.user_id)
    assert me_body["data"]["email"] == user.email


@pytest.mark.asyncio
async def test_login_in_non_development_forces_secure_session_and_csrf_cookies(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_SECURE", "false")
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-secure-cookie@example.com",
        role="user",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )

    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_cookie_header = next(
        header
        for header in set_cookie_headers
        if header.startswith(f"{AUTH_SESSION_COOKIE_NAME}=")
    )
    csrf_cookie_header = next(
        header
        for header in set_cookie_headers
        if header.startswith(f"{AUTH_CSRF_COOKIE_NAME}=")
    )
    assert "Secure" in session_cookie_header
    assert "Secure" in csrf_cookie_header
    assert (
        "SameSite=lax" in session_cookie_header
        or "SameSite=Lax" in session_cookie_header
    )


@pytest.mark.asyncio
async def test_logout_requires_matching_csrf_header_for_cookie_session(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-logout-cookie@example.com",
        role="user",
        is_active=True,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )
    assert login_response.status_code == 200
    csrf_token = async_client.cookies.get(AUTH_CSRF_COOKIE_NAME)
    assert csrf_token

    rejected_logout = await async_client.post("/api/v1/auth/logout")
    assert rejected_logout.status_code == 403
    rejected_payload = rejected_logout.json()
    assert rejected_payload["detail"]["error"] == "[CSRF_VALIDATION_FAILED]"

    logout_response = await async_client.post(
        "/api/v1/auth/logout",
        headers={AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert logout_response.status_code == 200
    logout_cookie_headers = logout_response.headers.get_list("set-cookie")
    logout_cookie_header = next(
        header
        for header in logout_cookie_headers
        if header.startswith(f"{AUTH_SESSION_COOKIE_NAME}=")
    )
    assert (
        "Max-Age=0" in logout_cookie_header
        or "expires=" in logout_cookie_header.lower()
    )

    me_response = await async_client.get("/api/v1/users/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_cookie_session_unsafe_write_requires_global_csrf_header(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-global-csrf@example.com",
        role="user",
        is_active=True,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )
    assert login_response.status_code == 200
    csrf_token = async_client.cookies.get(AUTH_CSRF_COOKIE_NAME)
    assert csrf_token

    missing_header_response = await async_client.patch(
        "/api/v1/users/me",
        json={"department": "Missing CSRF"},
    )
    assert missing_header_response.status_code == 403
    assert missing_header_response.json()["detail"]["error"] == "[CSRF_VALIDATION_FAILED]"

    mismatched_header_response = await async_client.patch(
        "/api/v1/users/me",
        json={"department": "Bad CSRF"},
        headers={AUTH_CSRF_HEADER_NAME: "not-the-cookie-token"},
    )
    assert missing_csrf_response.status_code == 403
    assert missing_csrf_response.json()["detail"]["error"] == "[CSRF_VALIDATION_FAILED]"

    accepted_response = await async_client.patch(
        "/api/v1/users/me",
        json={"department": "QA-CSRF"},
        headers={AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert accepted_response.status_code == 200
    assert accepted_response.json()["data"]["department"] == "QA-CSRF"


@pytest.mark.asyncio
async def test_bearer_unsafe_write_skips_cookie_csrf_layer(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-bearer-csrf-bypass@example.com",
        role="user",
        is_active=True,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["token"]
    assert async_client.cookies.get(AUTH_SESSION_COOKIE_NAME)

    accepted_response = await async_client.patch(
        "/api/v1/users/me",
        json={"department": "QA-Bearer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted_response.status_code == 200
    assert accepted_response.json()["data"]["department"] == "QA-Bearer"


@pytest.mark.asyncio
async def test_login_shared_password_fallback_exposes_compatibility_diagnostic_header(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "Password123!")
    user = await _create_user(
        test_db,
        email="auth-shared-password-compat@example.com",
        role="user",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Auth-Compatibility-Mode") == "shared_password"
    assert response.headers.get("X-Auth-Authority") == "compatibility_env_password"


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
async def test_auth_providers_report_explicit_dev_fallback_when_wecom_is_not_configured(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in (
        "WECOM_CORP_ID",
        "WECOM_SECRET",
        "WECOM_AGENT_ID",
        "WECHAT_CORP_ID",
        "WECHAT_SECRET",
        "WECHAT_AGENT_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    response = await async_client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["environment"] == "development"
    assert payload["data"]["wecom"]["enabled"] is False
    assert payload["data"]["wecom"]["configured"] is False
    assert "未配置" in payload["data"]["wecom"]["message"]
    assert payload["data"]["dev_fallback"]["enabled"] is True
    assert payload["data"]["dev_fallback"]["login_url"].endswith(
        "/api/v1/auth/dev-login"
    )
    assert "development" in payload["data"]["dev_fallback"]["message"].lower()


@pytest.mark.asyncio
async def test_wecom_callback_exchanges_code_sets_cookie_and_redirects_to_frontend(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("WECHAT_CORP_ID", "corp-id")
    monkeypatch.setenv("WECHAT_SECRET", "corp-secret")
    monkeypatch.setenv("WECHAT_AGENT_ID", "100001")
    monkeypatch.setenv("AUTH_FRONTEND_BASE_URL", "http://localhost:3445")

    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/cgi-bin/gettoken":
            assert request.url.params["corpid"] == "corp-id"
            assert request.url.params["corpsecret"] == "corp-secret"
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "access_token": "token-123",
                    "expires_in": 7200,
                },
            )
        if request.url.path == "/cgi-bin/auth/getuserinfo":
            assert request.url.params["code"] == "callback-code-1"
            return httpx.Response(
                200, json={"errcode": 0, "errmsg": "ok", "userid": "wecom-user-1"}
            )
        if request.url.path == "/cgi-bin/user/get":
            assert request.url.params["userid"] == "wecom-user-1"
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "userid": "wecom-user-1",
                    "name": "企业微信成员",
                    "department": [42],
                    "email": "wecom-user@example.com",
                },
            )
        raise AssertionError(
            f"unexpected WeCom request: {request.method} {request.url}"
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "common.auth.service._create_wecom_http_client",
        lambda: httpx.AsyncClient(
            transport=transport, base_url="https://qyapi.weixin.qq.com"
        ),
    )

    start_response = await async_client.get(
        "/api/v1/auth/wecom/start?return_to=/training",
        follow_redirects=False,
    )

    assert start_response.status_code in {302, 307}
    authorize_url = start_response.headers["location"]
    authorize_query = parse_qs(urlparse(authorize_url).query)
    state = authorize_query["state"][0]
    async_client.cookies.set(get_wecom_oauth_state_cookie_name(), state)
    async_client.cookies.set(get_wecom_oauth_return_to_cookie_name(), "/training")

    callback_response = await async_client.get(
        f"/api/v1/auth/wecom/callback?code=callback-code-1&state={state}",
        follow_redirects=False,
    )

    assert callback_response.status_code in {302, 303, 307}
    assert callback_response.headers["location"] == "http://localhost:3445/training"

    set_cookie_headers = callback_response.headers.get_list("set-cookie")
    session_cookie_header = next(
        header
        for header in set_cookie_headers
        if header.startswith(f"{AUTH_SESSION_COOKIE_NAME}=")
    )
    assert "HttpOnly" in session_cookie_header
    session_token = callback_response.cookies.get(AUTH_SESSION_COOKIE_NAME)
    assert session_token
    async_client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)

    me_response = await async_client.get("/api/v1/users/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["success"] is True
    assert me_payload["data"]["email"] == "wecom-user@example.com"
    assert me_payload["data"]["display_name"] == "企业微信成员"

    stored_user = (
        await test_db.execute(select(User).where(User.wechat_user_id == "wecom-user-1"))
    ).scalar_one()
    assert stored_user.email == "wecom-user@example.com"
    assert stored_user.name == "企业微信成员"
    assert stored_user.department == "42"
    assert str(stored_user.last_login)

    assert seen_paths == [
        "/cgi-bin/gettoken",
        "/cgi-bin/auth/getuserinfo",
        "/cgi-bin/user/get",
    ]


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


@pytest.mark.asyncio
async def test_dev_login_is_explicitly_disabled_outside_development(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = await async_client.post("/api/v1/auth/dev-login")

    assert response.status_code == 403
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "[DEV_LOGIN_DISABLED]"


@pytest.mark.asyncio
async def test_dev_login_sets_http_only_cookie_and_allows_cookie_auth(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = await async_client.post("/api/v1/auth/dev-login")

    assert response.status_code == 200
    set_cookie_header = response.headers.get("set-cookie", "")
    assert f"{AUTH_SESSION_COOKIE_NAME}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header

    me_response = await async_client.get("/api/v1/users/me")
    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["success"] is True
    assert me_body["data"]["email"] == "dev@example.com"


@pytest.mark.asyncio
async def test_forgot_password_reissues_token_without_marking_previous_one_as_consumed(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issued_tokens = iter(["first-reset-token", "second-reset-token"])
    monkeypatch.setattr("secrets.token_urlsafe", lambda _: next(issued_tokens))
    user = await _create_user(
        test_db,
        email="auth-reset-reissue@example.com",
        role="user",
        is_active=True,
    )

    first_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.30"},
    )
    second_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.31"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    rows = await _fetch_reset_rows(test_db)
    assert len(rows) == 2
    assert rows[0]["user_id"] == str(user.user_id)
    assert rows[0]["used_at"] is None
    assert rows[0]["invalidated_at"] is not None
    assert rows[0]["invalidation_reason"] == "superseded"
    assert rows[0]["delivery_status"] == "sent"
    assert rows[1]["used_at"] is None
    assert rows[1]["invalidated_at"] is None
    assert rows[1]["delivery_status"] == "sent"


@pytest.mark.asyncio
async def test_forgot_password_success_includes_rate_limit_headers(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="auth-reset-headers@example.com",
        role="user",
        is_active=True,
    )

    response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.32"},
    )

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "1"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["X-RateLimit-Reset"]) >= int(
        datetime.now(UTC).timestamp()
    )


@pytest.mark.asyncio
async def test_forgot_password_rate_limit_rejects_second_request_for_same_ip(
    async_client,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(
        test_db,
        email="auth-reset-rate-limit@example.com",
        role="user",
        is_active=True,
    )
    headers = {"X-Forwarded-For": "203.0.113.320"}

    first_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers=headers,
    )
    second_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    payload = second_response.json()
    assert payload["detail"]["error"] == "[RATE_LIMIT_EXCEEDED]"
    assert payload["detail"]["message"]
    assert second_response.headers.get("x-trace-id")


@pytest.mark.asyncio
async def test_forgot_password_delivery_failure_still_returns_generic_success(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _create_user(
        test_db,
        email="auth-reset-delivery-failure@example.com",
        role="user",
        is_active=True,
    )

    async def _boom(self, *, recipient: str, reset_url: str) -> None:
        raise RuntimeError(f"delivery offline for {recipient} -> {reset_url}")

    monkeypatch.setattr(
        "common.services.password_reset.ConsoleEmailService.send_password_reset_email",
        _boom,
    )

    response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.33"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["message"] == "如果该邮箱已注册，重置链接将发送到您的邮箱"

    rows = await _fetch_reset_rows(test_db)
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(user.user_id)
    assert rows[0]["delivery_status"] == "failed"
    assert rows[0]["delivery_attempted_at"] is not None
    assert "RuntimeError: delivery offline" in str(rows[0]["delivery_error"])


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token_and_preserves_new_login_boundary(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "OriginalPass123!")
    monkeypatch.setattr("secrets.token_urlsafe", lambda _: "expired-reset-token")
    user = await _create_user(
        test_db,
        email="auth-reset-expired@example.com",
        role="user",
        is_active=True,
    )

    forgot_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user.email},
        headers={"X-Forwarded-For": "203.0.113.34"},
    )
    assert forgot_response.status_code == 200

    await test_db.execute(
        text(
            "UPDATE password_reset_tokens SET expires_at = :expired_at WHERE user_id = :user_id"
        ),
        {
            "expired_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "user_id": str(user.user_id),
        },
    )
    await test_db.commit()

    reset_response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "expired-reset-token", "new_password": "NewPass123!"},
    )

    assert reset_response.status_code == 400
    payload = reset_response.json()
    assert payload["success"] is False
    assert payload["error"] == "[INVALID_RESET_TOKEN]"

    rows = await _fetch_reset_rows(test_db)
    assert len(rows) == 1
    assert rows[0]["used_at"] is None
    assert rows[0]["invalidation_reason"] == "expired"
    assert rows[0]["invalidated_at"] is not None

    old_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "OriginalPass123!"},
    )
    assert old_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_success_sets_managed_password_and_rejects_reuse(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_USER_PASSWORDS_JSON", raising=False)
    monkeypatch.setenv("AUTH_SHARED_PASSWORD", "OriginalPass123!")
    monkeypatch.setattr("secrets.token_urlsafe", lambda _: "managed-reset-token")
    user = await _create_user(
        test_db,
        email="auth-reset-managed@example.com",
        role="user",
        is_active=True,
    )
    user_email = user.email

    forgot_response = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": user_email},
        headers={"X-Forwarded-For": "203.0.113.35"},
    )
    assert forgot_response.status_code == 200

    reset_response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "managed-reset-token", "new_password": "NewPass123!"},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["success"] is True

    reused_response = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "managed-reset-token", "new_password": "AnotherPass123!"},
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
    assert rows[0]["invalidated_at"] is None
    assert rows[0]["delivery_status"] == "sent"


def test_auth_recovery_request_path_keeps_runtime_ddl_out_of_handlers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    auth_api_source = (repo_root / "src/common/auth/api.py").read_text(encoding="utf-8")
    password_reset_source = (
        repo_root / "src/common/services/password_reset.py"
    ).read_text(encoding="utf-8")

    assert (
        AUTH_FORMALIZATION_SURFACE["runtime_ddl_owner"] == "common.db.session.init_db"
    )
    assert "PasswordResetService" in auth_api_source
    for forbidden_snippet in ("create_all(", "CREATE TABLE", "create table"):
        assert forbidden_snippet not in auth_api_source
        assert forbidden_snippet not in password_reset_source
        assert forbidden_snippet not in auth_api_source
        assert forbidden_snippet not in password_reset_source
