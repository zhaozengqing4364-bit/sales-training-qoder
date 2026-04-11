"""
Authentication API - Login, logout, and token management

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""
import hmac
import json
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import (
    clear_auth_session_cookie,
    create_access_token,
    get_current_user,
    set_auth_session_cookie,
    pwd_context,
)
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from common.rate_limit.api_limiter import rate_limit
from common.services.password_reset import (
    InvalidResetPasswordTokenError,
    PASSWORD_RESET_RATE_LIMIT_CALLS,
    PASSWORD_RESET_RATE_LIMIT_PERIOD_SECONDS,
    PasswordResetService,
)

logger = get_logger(__name__)

router = APIRouter()

AUTH_SHARED_PASSWORD_ENV = "AUTH_SHARED_PASSWORD"
AUTH_USER_PASSWORDS_ENV = "AUTH_USER_PASSWORDS_JSON"


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


class LogoutResponse(BaseModel):
    """Logout response schema"""
    message: str = "Logged out successfully"


# ========== Helper Functions ==========

def success_response(data, trace_id: str = None):
    """Create unified success response"""
    return {
        "success": True,
        "data": data if isinstance(data, dict) else data.model_dump() if hasattr(data, 'model_dump') else data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str = None, trace_id: str = None, status_code: int = 400):
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


def _invalid_credentials_response():
    """Return secure, non-enumerable auth failure response."""
    return error_response(
        "[INVALID_CREDENTIALS]",
        "账号或凭证无效",
        status_code=401,
    )


def _get_auth_shared_password() -> str | None:
    """Read configured shared login password for controlled auth."""
    configured = os.getenv(AUTH_SHARED_PASSWORD_ENV, "").strip()
    return configured or None


def _get_auth_user_passwords() -> dict[str, str] | None:
    """Read optional per-user password mapping from env."""
    raw = os.getenv(AUTH_USER_PASSWORDS_ENV, "").strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid AUTH_USER_PASSWORDS_JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("invalid AUTH_USER_PASSWORDS_JSON")

    normalized: dict[str, str] = {}
    for key, value in parsed.items():
        email_key = str(key).strip().lower()
        password_value = str(value).strip()
        if email_key and password_value:
            normalized[email_key] = password_value
    return normalized


def get_auth_config_diagnostics() -> dict[str, Any]:
    """Return non-sensitive auth configuration diagnostics for startup logs."""
    shared_password = _get_auth_shared_password()
    diagnostics: dict[str, Any] = {
        "shared_password_configured": bool(shared_password),
        "user_override_count": 0,
        "user_overrides_valid": True,
        "credentials_ready": bool(shared_password),
    }

    try:
        user_passwords = _get_auth_user_passwords()
    except ValueError:
        diagnostics["user_overrides_valid"] = False
        diagnostics["credentials_ready"] = bool(shared_password)
        return diagnostics

    if user_passwords:
        diagnostics["user_override_count"] = len(user_passwords)
        diagnostics["credentials_ready"] = True

    return diagnostics


def _is_valid_password(provided_password: str, expected_password: str) -> bool:
    """Constant-time password comparison for configured credentials."""
    return hmac.compare_digest(provided_password, expected_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# ========== Endpoints ==========

@router.post("/auth/login")
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Controlled login endpoint.
    Validates existing active account and configured credentials,
    then issues JWT with role claim.
    """
    try:
        configured_password = _get_auth_shared_password()
        try:
            configured_user_passwords = _get_auth_user_passwords()
        except ValueError:
            logger.warning(
                "AUTH_USER_PASSWORDS_JSON is invalid; falling back to shared password"
            )
            configured_user_passwords = None
        if configured_password is None and configured_user_passwords is None:
            logger.error("Login rejected: auth credentials are not configured")
            return error_response(
                "[AUTH_SERVICE_UNAVAILABLE]",
                "认证服务暂不可用",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Find user by email
        result = await db.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()

        # Secure failure response to prevent user/account state enumeration
        if user is None:
            return _invalid_credentials_response()
        if not getattr(user, "is_active", False):
            return _invalid_credentials_response()
        user_email = (user.email or "").strip().lower()
        expected_password = None

        # First check user-specific hashed_password (set via password reset)
        user_hashed_pw = getattr(user, "hashed_password", None)
        if user_hashed_pw:
            if not verify_password(credentials.password, user_hashed_pw):
                return _invalid_credentials_response()
        else:
            # Fall back to env-configured shared password
            if configured_user_passwords is not None:
                expected_password = configured_user_passwords.get(user_email)
            if expected_password is None:
                expected_password = configured_password

            if expected_password is None:
                return _invalid_credentials_response()
            if not _is_valid_password(credentials.password, expected_password):
                return _invalid_credentials_response()

        # Create JWT token with role claim
        user_role = getattr(user, "role", None) or "user"
        token = create_access_token(
            data={
                "sub": str(user.user_id),
                "role": user_role,
            }
        )

        # Update last login
        user.last_login = datetime.now(UTC)
        await db.commit()

        # Build response
        login_response = LoginResponse(
            token=token,
            user=LoginUserResponse(
                id=str(user.user_id),
                name=user.name or "用户",
                email=user.email or "",
                role=user_role
            )
        )

        logger.info(f"User logged in: {user.user_id}")
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response(login_response.model_dump()),
        )
        set_auth_session_cookie(response, token)
        return response

    except SQLAlchemyError as e:
        logger.error(f"Login failed: {str(e)}")
        return error_response("[LOGIN_FAILED]", "登录失败，请稍后重试")


@router.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    User logout endpoint

    Clears server-side token state (if any).
    Client should also clear the stored token.

    Requirements: 1.2
    """
    try:
        # In a stateless JWT setup, logout is handled client-side
        # If using token blacklist or refresh tokens, would invalidate here

        # For now, just log the logout event
        logger.info(f"User logged out: {current_user.email}")

        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response({
                "message": "登出成功"
            }),
        )
        clear_auth_session_cookie(response)
        return response

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Logout failed: {str(e)}")
        return error_response("[LOGOUT_FAILED]", "登出失败")


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
):
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
        logger.error(f"Forgot password failed: {str(e)}")
        await db.rollback()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=success_response({
            "message": "如果该邮箱已注册，重置链接将发送到您的邮箱"
        }),
    )


@router.post("/auth/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using a valid reset token.
    Token must not be expired or already used.
    """
    try:
        service = PasswordResetService(db)
        await service.reset_password(body.token, body.new_password)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=success_response({
                "message": "密码重置成功"
            }),
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
        logger.error(f"Reset password failed: {str(e)}")
        return error_response("[RESET_FAILED]", "密码重置失败，请稍后重试")

