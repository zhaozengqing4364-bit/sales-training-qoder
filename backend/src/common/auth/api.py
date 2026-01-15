"""
Authentication API - Login, logout, and token management

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- VI. Data Privacy & Compliance

Response Format:
- All endpoints return {"success": true/false, "data": ..., "trace_id": ...}
"""
import os

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import (
    create_access_token,
    get_current_user,
    pwd_context,
)
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter()

# 允许开发模式认证的主机列表
ALLOWED_DEV_HOSTS = {"localhost", "127.0.0.1", "::1"}


# ========== Schemas ==========

class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


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
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id()
    }


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
    User login endpoint
    
    Accepts email and password, returns JWT token and user info.
    
    For development mode, accepts any password for existing users.
    In production, would validate against stored password hash.
    
    Request:
    - email: User's email address
    - password: User's password
    
    Returns:
    - token: JWT access token
    - user: User info (id, name, email, role)
    
    Requirements: 1.1, 1.2, 1.3
    """
    try:
        # Find user by email
        result = await db.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()

        # 开发模式安全检查
        is_dev_mode = os.getenv("ENVIRONMENT") == "development"
        allow_dev_auth = os.getenv("ALLOW_DEV_AUTH", "false").lower() == "true"
        
        # 获取客户端 IP
        client_host = request.client.host if request.client else ""
        is_local_request = client_host in ALLOWED_DEV_HOSTS

        if not user:
            # 开发模式下自动创建用户（需要双重检查）
            if is_dev_mode and (allow_dev_auth or is_local_request):
                import uuid
                user = User(
                    user_id=str(uuid.uuid4()),
                    wechat_user_id=f"dev_{credentials.email}",
                    email=credentials.email,
                    name=credentials.email.split("@")[0],
                    department="Development",
                    role="user"  # Default role for new users
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                logger.info(f"Created dev user: {credentials.email} from {client_host}")
            else:
                return error_response(
                    "[INVALID_CREDENTIALS]",
                    "邮箱或密码错误",
                    status_code=401
                )

        # 开发模式下跳过密码验证（需要安全检查）
        if not is_dev_mode or (not allow_dev_auth and not is_local_request):
            # 生产模式或非本地请求：需要验证密码
            # TODO: Add password field to User model and verify
            return error_response(
                "[AUTH_NOT_CONFIGURED]",
                "认证服务未配置",
                status_code=401
            )

        # Check if user is active
        if hasattr(user, 'is_active') and not user.is_active:
            return error_response(
                "[USER_DISABLED]",
                "用户已被禁用",
                status_code=401
            )

        # Create JWT token
        token = create_access_token(data={"sub": str(user.user_id)})

        # Update last login
        from datetime import datetime
        user.last_login = datetime.utcnow()
        await db.commit()

        # Get actual role from database, default to 'user' if not set
        user_role = getattr(user, 'role', None) or 'user'

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

        logger.info(f"User logged in: {user.email}")
        return success_response(login_response.model_dump())

    except Exception as e:
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

        return success_response({
            "message": "登出成功"
        })

    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return error_response("[LOGOUT_FAILED]", "登出失败")
