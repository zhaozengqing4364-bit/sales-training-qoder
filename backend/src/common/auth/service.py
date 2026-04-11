"""
JWT Authentication and Enterprise WeChat SSO
Constitution Principle VI: Data Privacy & Compliance
"""
import os
import uuid
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any

from dotenv import load_dotenv
from fastapi import Cookie, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String as SQLAlchemyString

from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production-min-32-chars")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
AUTH_SESSION_COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE_NAME", "app_session")
AUTH_SESSION_COOKIE_SECURE = (
    os.getenv("AUTH_SESSION_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}
)
AUTH_SESSION_COOKIE_SAMESITE = os.getenv("AUTH_SESSION_COOKIE_SAMESITE", "lax").strip().lower() or "lax"

security = HTTPBearer(auto_error=False)
# Login compatibility seam:
# - password reset writes User.hashed_password and should become the durable credential path.
# - users without hashed_password must keep authenticating through
#   AUTH_USER_PASSWORDS_JSON / AUTH_SHARED_PASSWORD until the reset contract replaces that fallback.
# - request-path auth recovery work should not expand init_db/runtime DDL behavior here; schema authority lives
#   in Alembic revisions plus common.db.models.PasswordResetToken, including the single-active-token invariant.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def _current_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def get_session_cookie_name() -> str:
    return AUTH_SESSION_COOKIE_NAME


def get_session_cookie_max_age_seconds() -> int:
    return max(1, JWT_EXPIRATION_HOURS * 3600)


def get_session_cookie_options() -> dict[str, Any]:
    return {
        "key": get_session_cookie_name(),
        "httponly": True,
        "secure": AUTH_SESSION_COOKIE_SECURE,
        "samesite": AUTH_SESSION_COOKIE_SAMESITE,
        "path": "/",
        "max_age": get_session_cookie_max_age_seconds(),
    }


def set_auth_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        value=token,
        **get_session_cookie_options(),
    )


def clear_auth_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_session_cookie_name(),
        path="/",
        samesite=AUTH_SESSION_COOKIE_SAMESITE,
    )


def resolve_bearer_or_cookie_token(
    *,
    credentials: HTTPAuthorizationCredentials | None = None,
    request: Request | None = None,
    cookie_token: str | None = None,
) -> str | None:
    if credentials is not None and credentials.credentials:
        return credentials.credentials

    if cookie_token:
        return cookie_token

    if request is not None:
        request_cookie_token = request.cookies.get(get_session_cookie_name())
        if request_cookie_token:
            return request_cookie_token

    return None


def resolve_websocket_token(
    *,
    query_token: str | None,
    authorization_header: str | None = None,
    cookie_header: str | None = None,
) -> str:
    if authorization_header and authorization_header.lower().startswith("bearer "):
        return authorization_header[7:].strip()

    normalized_query_token = (query_token or "").strip()
    if normalized_query_token:
        return normalized_query_token

    if cookie_header:
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        morsel = cookies.get(get_session_cookie_name())
        if morsel and morsel.value:
            return morsel.value.strip()

    return ""


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=JWT_EXPIRATION_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    cookie_token: str | None = Cookie(default=None, alias=AUTH_SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    token = resolve_bearer_or_cookie_token(
        credentials=credentials,
        request=request,
        cookie_token=cookie_token,
    )
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Cast UUID column to VARCHAR for string comparison
    result = await db.execute(select(User).where(cast(User.user_id, SQLAlchemyString) == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they have admin role.
    Use this dependency for admin-only endpoints.
    """
    if not hasattr(current_user, 'role') or current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="[ADMIN_REQUIRED] This action requires administrator privileges"
        )
    return current_user


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = getattr(current_user, 'role', 'user')
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"[ROLE_REQUIRED] Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


async def authenticate_wechat(code: str) -> User | None:
    """
    Authenticate with Enterprise WeChat
    In production, this would call WeChat API to exchange code for user info
    For now, this is a mock implementation
    """
    # TODO: Implement actual WeChat SSO API call
    # from wechatpy import WeChatClient
    # client = WeChatClient(corp_id, secret)
    # user_info = client.auth.getuserinfo(code)

    # Mock implementation for development
    logger.info(f"Mock WeChat authentication for code: {code}")

    # In production, fetch actual user info from WeChat
    # For now, create or return mock user
    return None


async def get_dev_user(db: AsyncSession) -> User:
    """
    Development mode: Get or create a mock user for testing
    Only active when ENVIRONMENT=development
    """
    if _current_environment() != "development":
        raise HTTPException(status_code=401, detail="Development mode only")

    # Try to find existing dev user by either stable email or stable WeChat ID.
    # This prevents unique-key conflicts when email was edited in dev mode.
    result = await db.execute(
        select(User).where(
            or_(
                User.email == "dev@example.com",
                User.wechat_user_id == "dev_wechat_user",
            )
        )
    )
    user = result.scalars().first()

    if not user:
        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id="dev_wechat_user",
            email="dev@example.com",
            name="Developer",
            department="Development",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    # Keep dev account identity fields canonical for predictable local testing.
    user.wechat_user_id = "dev_wechat_user"
    if not user.email:
        user.email = "dev@example.com"
    if not user.name:
        user.name = "Developer"
    await db.commit()
    await db.refresh(user)

    return user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    cookie_token: str | None = Cookie(default=None, alias=AUTH_SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    """
    Optional authentication - returns None if not authenticated
    For development mode testing
    """
    import os

    # Development mode: use dev user if no token provided
    if _current_environment() == "development":
        try:
            return await get_dev_user(db)
        except (RuntimeError, ValueError, OSError):
            pass

    try:
        return await get_current_user(request, credentials, cookie_token, db)
    except HTTPException:
        return None
