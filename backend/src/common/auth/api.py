"""
Authentication API - Login, logout, and token management

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""

import hmac
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import (
    authenticate_wechat,
    build_wecom_authorization_url,
    clear_auth_session_cookie,
    clear_wecom_oauth_flow_cookies,
    create_access_token,
    get_current_user,
    get_frontend_base_url,
    get_wecom_oauth_return_to_cookie_name,
    get_wecom_oauth_state_cookie_name,
    get_wecom_provider_diagnostics,
    is_dev_login_enabled,
    mark_user_logged_in,
    pwd_context,
    resolve_bearer_or_cookie_token,
    security,
    set_auth_session_cookie,
    set_wecom_oauth_flow_cookies,
    should_enforce_csrf,
    upsert_wecom_user,
    validate_csrf_request,
    verify_token,
)
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from common.rate_limit.api_limiter import rate_limit
from common.services.password_reset import (
    PASSWORD_RESET_RATE_LIMIT_CALLS,
    PASSWORD_RESET_RATE_LIMIT_PERIOD_SECONDS,
    InvalidResetPasswordTokenError,
    PasswordResetService,
)

logger = get_logger(__name__)

router = APIRouter()

AUTH_FORMALIZATION_SURFACE = {
    "password_reset_service": "common.services.password_reset.PasswordResetService",
    "password_reset_model": "common.db.models.PasswordResetToken",
    "password_reset_migrations": (
        "026_password_reset_tokens",
        "027_reset_lifecycle_delivery",
        "028_reset_single_active_token",
    ),
    "runtime_schema_authority": "alembic-only; startup verification is read-only",
    "login_credential_authority": "User.hashed_password",
    "legacy_environment_passwords_read": False,
}


# ========== Schemas ==========


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""

    token: str
    new_password: str


class ChangeTemporaryPasswordRequest(BaseModel):
    """First-login password replacement using a limited credential."""

    new_password: str


class LoginUserResponse(BaseModel):
    """User info in login response"""

    id: str
    name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    """Login response schema"""

    token: str
    user: LoginUserResponse
    requires_password_change: bool = False


class LogoutResponse(BaseModel):
    """Logout response schema"""

    message: str = "Logged out successfully"


# ========== Helper Functions ==========


def success_response(data: Any, trace_id: str | None = None) -> dict[str, Any]:
    """Create unified success response"""
    return {
        "success": True,
        "data": data
        if isinstance(data, dict)
        else data.model_dump()
        if hasattr(data, "model_dump")
        else data,
        "trace_id": trace_id or get_trace_id(),
    }


def error_response(
    error_code: str,
    message: str | None = None,
    trace_id: str | None = None,
    status_code: int = 400,
) -> JSONResponse:
    """Create unified error response with explicit HTTP status."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_code,
            "message": message or error_code,
            "trace_id": trace_id or get_trace_id(),
        },
    )


def _invalid_credentials_response() -> JSONResponse:
    """Return secure, non-enumerable auth failure response."""
    return error_response(
        "[INVALID_CREDENTIALS]",
        "账号或凭证无效",
        status_code=401,
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bool(pwd_context.verify(plain_password, hashed_password))


def hash_password(password: str) -> str:
    """Hash a password"""
    return str(pwd_context.hash(password))


def _set_login_authority_headers(
    response: Response,
    *,
    compatibility_mode: str | None,
    authority: str,
) -> None:
    response.headers["X-Auth-Authority"] = authority
    if compatibility_mode:
        response.headers["X-Auth-Compatibility-Mode"] = compatibility_mode


def _build_absolute_api_url(request: Request, path: str) -> str:
    return f"{str(request.base_url).rstrip('/')}{path}"


def _sanitize_return_to(value: str | None) -> str:
    normalized = (value or "/").strip() or "/"
    if not normalized.startswith("/") or normalized.startswith("//"):
        return "/"
    return normalized


def _build_frontend_url(path: str) -> str:
    base_url = str(get_frontend_base_url())
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{normalized_path}"


def _auth_error_redirect(error_code: str) -> str:
    return _build_frontend_url(f"/login?authError={error_code}")


# ========== Endpoints ==========


@router.post("/auth/login")
@rate_limit(calls=10, period=60, scope="login")
async def login(
    request: Request, credentials: LoginRequest, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """
    Controlled login endpoint.
    Validates an existing active account and its managed password,
    then issues JWT with role claim.
    """
    try:
        # Find user by email
        normalized_email = str(credentials.email).strip().lower()
        result = await db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        user = result.scalar_one_or_none()

        # Secure failure response to prevent user/account state enumeration
        if user is None or not getattr(user, "is_active", False):
            return _invalid_credentials_response()
        user_hashed_pw = getattr(user, "hashed_password", None)
        if not user_hashed_pw or not verify_password(
            credentials.password, user_hashed_pw
        ):
            return _invalid_credentials_response()

        credential_status = getattr(user, "credential_status", "active") or "active"
        if credential_status == "temporary":
            expires_at = getattr(user, "temporary_password_expires_at", None)
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at <= datetime.now(UTC):
                    return error_response(
                        "[TEMPORARY_PASSWORD_EXPIRED]",
                        "临时密码已过期，请联系管理员重置。",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

        # Temporary credentials receive only a password-change token.
        user_role = getattr(user, "role", None) or "user"
        requires_password_change = credential_status in {"temporary", "reset_required"}
        token = create_access_token(
            data={
                "sub": str(user.user_id),
                "role": user_role,
                "scope": "password_change" if requires_password_change else "business",
                "credential_version": getattr(user, "credential_version", 1),
            }
        )

        # Update last login
        setattr(user, "last_login", datetime.now(UTC))
        await db.commit()

        # Build response
        login_response = LoginResponse(
            token=token,
            user=LoginUserResponse(
                id=str(user.user_id),
                name=user.name or "用户",
                email=user.email or "",
                role=user_role,
            ),
            requires_password_change=requires_password_change,
        )

        logger.info(
            "User logged in",
            user_id=str(user.user_id),
            user_email=user.email,
            role=user_role,
            auth_authority="managed_user_password",
        )
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response(login_response.model_dump()),
        )
        set_auth_session_cookie(response, token)
        _set_login_authority_headers(
            response,
            compatibility_mode=None,
            authority="managed_user_password",
        )
        return response

    except SQLAlchemyError as e:
        logger.error(
            "Login failed",
            auth_email=credentials.email,
            error_type=type(e).__name__,
        )
        return error_response("[LOGIN_FAILED]", "登录失败，请稍后重试")


@router.post("/auth/change-temporary-password")
async def change_temporary_password(
    body: ChangeTemporaryPasswordRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Replace a temporary password and issue the first business session."""
    token = resolve_bearer_or_cookie_token(
        credentials=credentials,
        request=request,
    )
    if not token:
        return error_response(
            "[TEMPORARY_CREDENTIAL_REQUIRED]",
            "请先使用临时密码登录。",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        payload = verify_token(token)
    except InvalidTokenError:
        return error_response(
            "[INVALID_TOKEN]",
            "临时登录凭证已失效，请重新登录。",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if payload.get("scope") != "password_change":
        return error_response(
            "[TEMPORARY_CREDENTIAL_REQUIRED]",
            "当前登录凭证不能执行首次改密。",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if (
        len(body.new_password) < 8
        or not any(c.isalpha() for c in body.new_password)
        or not any(c.isdigit() for c in body.new_password)
    ):
        return error_response(
            "[INVALID_PASSWORD]",
            "新密码至少 8 位，并包含字母和数字。",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_id = str(payload.get("sub") or "").strip()
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return error_response(
            "[AUTH_USER_NOT_FOUND]",
            "账号不存在或已停用。",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if getattr(user, "credential_status", "active") not in {
        "temporary",
        "reset_required",
    }:
        return error_response(
            "[PASSWORD_CHANGE_ALREADY_COMPLETED]",
            "临时密码已经失效，请使用新密码登录。",
            status_code=status.HTTP_409_CONFLICT,
        )
    if int(payload.get("credential_version", 1)) != int(
        getattr(user, "credential_version", 1)
    ):
        return error_response(
            "[INVALID_TOKEN]",
            "临时登录凭证已失效，请重新登录。",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user.hashed_password = pwd_context.hash(body.new_password)
    user.credential_status = "active"
    user.temporary_password_expires_at = None
    user.password_changed_at = datetime.now(UTC)
    user.credential_version = int(getattr(user, "credential_version", 1)) + 1
    user.last_login = datetime.now(UTC)
    await db.commit()

    business_token = create_access_token(
        data={
            "sub": str(user.user_id),
            "role": user.role or "user",
            "scope": "business",
            "credential_version": user.credential_version,
        }
    )
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=success_response(
            LoginResponse(
                token=business_token,
                user=LoginUserResponse(
                    id=str(user.user_id),
                    name=user.name or "用户",
                    email=user.email or "",
                    role=user.role or "user",
                ),
            ).model_dump()
        ),
    )
    set_auth_session_cookie(response, business_token)
    return response


@router.post("/auth/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    User logout endpoint

    Clears server-side token state (if any).
    Client should also clear the stored token.

    Requirements: 1.2
    """
    try:
        if should_enforce_csrf(request):
            validate_csrf_request(request)

        # In a stateless JWT setup, logout is handled client-side
        # If using token blacklist or refresh tokens, would invalidate here

        # For now, just log the logout event
        logger.info(
            "User logged out",
            user_id=str(current_user.user_id),
            user_email=current_user.email,
        )

        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response({"message": "登出成功"}),
        )
        clear_auth_session_cookie(response)
        return response

    except (SQLAlchemyError, ValueError) as e:
        logger.error(
            "Logout failed",
            user_id=str(current_user.user_id),
            user_email=current_user.email,
            error_type=type(e).__name__,
        )
        return error_response("[LOGOUT_FAILED]", "登出失败")


@router.get("/auth/providers")
async def get_auth_providers(request: Request) -> dict[str, Any]:
    wecom = get_wecom_provider_diagnostics()
    dev_fallback_enabled = is_dev_login_enabled()
    return success_response(
        {
            "environment": os.getenv("ENVIRONMENT", "development").strip().lower()
            or "development",
            "wecom": {
                "enabled": wecom["enabled"],
                "configured": wecom["configured"],
                "login_url": _build_absolute_api_url(
                    request, "/api/v1/auth/wecom/start?return_to=%2F"
                ),
                "message": wecom["message"],
            },
            "dev_fallback": {
                "enabled": dev_fallback_enabled,
                "login_url": _build_absolute_api_url(request, "/api/v1/auth/dev-login"),
                "message": "仅 development 环境可用的开发者登录。"
                if dev_fallback_enabled
                else "开发者登录默认关闭，且不会在生产环境暴露。",
            },
        }
    )


@router.get("/auth/wecom/start", name="wecom_start")
async def start_wecom_login(request: Request) -> Response:
    wecom = get_wecom_provider_diagnostics()
    if not wecom["configured"]:
        return error_response(
            "[WECOM_SSO_UNAVAILABLE]",
            wecom["message"],
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    state = uuid.uuid4().hex
    return_to = _sanitize_return_to(request.query_params.get("return_to"))
    authorize_url = build_wecom_authorization_url(
        redirect_uri=str(request.url_for("wecom_callback")),
        state=state,
    )
    response = RedirectResponse(
        url=authorize_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    set_wecom_oauth_flow_cookies(response, state=state, return_to=return_to)
    return response


@router.get("/auth/wecom/callback", name="wecom_callback")
async def handle_wecom_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    expected_state = (
        request.cookies.get(get_wecom_oauth_state_cookie_name()) or ""
    ).strip()
    return_to = _sanitize_return_to(
        request.cookies.get(get_wecom_oauth_return_to_cookie_name())
    )
    wecom = get_wecom_provider_diagnostics()

    def redirect_with_error(error_code: str) -> RedirectResponse:
        response = RedirectResponse(
            url=_auth_error_redirect(error_code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        clear_wecom_oauth_flow_cookies(response)
        return response

    if not wecom["configured"]:
        return redirect_with_error("wecom-unavailable")

    normalized_state = (state or "").strip()
    normalized_code = (code or "").strip()
    if (
        not normalized_code
        or not normalized_state
        or not expected_state
        or not hmac.compare_digest(expected_state, normalized_state)
    ):
        return redirect_with_error("wecom-state-invalid")

    try:
        profile = await authenticate_wechat(normalized_code)
        user = await upsert_wecom_user(db, profile)
        if not getattr(user, "is_active", False):
            return redirect_with_error("wecom-user-disabled")
        user = await mark_user_logged_in(db, user)
    except (SQLAlchemyError, ValueError, httpx.HTTPError) as exc:
        logger.error(
            "WeCom callback failed",
            error_type=type(exc).__name__,
        )
        await db.rollback()
        return redirect_with_error("wecom-callback-failed")

    user_role = getattr(user, "role", None) or "user"
    token = create_access_token(
        data={
            "sub": str(user.user_id),
            "role": user_role,
        }
    )
    response = RedirectResponse(
        url=_build_frontend_url(return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    set_auth_session_cookie(response, token)
    clear_wecom_oauth_flow_cookies(response)
    _set_login_authority_headers(
        response,
        compatibility_mode=None,
        authority="wecom_sso",
    )
    return response


# ========== Password Reset ==========


@router.post("/auth/forgot-password")
@rate_limit(
    calls=PASSWORD_RESET_RATE_LIMIT_CALLS,
    period=PASSWORD_RESET_RATE_LIMIT_PERIOD_SECONDS,
    scope="ip",
)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Request a password reset token.
    Always returns success to prevent email enumeration.
    Rate-limited to 1 request per minute per IP.
    """
    del request

    try:
        service = PasswordResetService(db)
        await service.request_password_reset(body.email)
    except SQLAlchemyError as e:
        logger.error(
            "Forgot password failed",
            auth_email=body.email,
            error_type=type(e).__name__,
        )
        await db.rollback()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=success_response(
            {"message": "如果该邮箱已注册，重置链接将发送到您的邮箱"}
        ),
    )


@router.post("/auth/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Reset password using a valid reset token.
    Token must not be expired or already used.
    """
    try:
        service = PasswordResetService(db)
        await service.reset_password(body.token, body.new_password)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response({"message": "密码重置成功"}),
        )
    except ValueError as exc:
        await db.rollback()
        if str(exc).startswith("密码至少需要"):
            return error_response(
                "[INVALID_PASSWORD]",
                str(exc),
                status_code=400,
            )
        return error_response("[RESET_FAILED]", "密码重置失败，请稍后重试")
    except InvalidResetPasswordTokenError:
        await db.rollback()
        return error_response(
            "[INVALID_RESET_TOKEN]",
            "重置链接无效或已过期，请重新申请",
            status_code=400,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Reset password failed",
            error_type=type(e).__name__,
        )
        return error_response("[RESET_FAILED]", "密码重置失败，请稍后重试")
