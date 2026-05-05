"""
JWT Authentication and Enterprise WeChat SSO
Constitution Principle VI: Data Privacy & Compliance
"""

import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any, NoReturn
from urllib.parse import urlencode

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import Cookie, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError as JWTError
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
JWT_SECRET = os.getenv(
    "JWT_SECRET", "your-super-secret-key-change-in-production-min-32-chars"
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
AUTH_SESSION_COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE_NAME", "app_session")
AUTH_CSRF_COOKIE_NAME = os.getenv("AUTH_CSRF_COOKIE_NAME", "app_csrf")
AUTH_CSRF_HEADER_NAME = os.getenv("AUTH_CSRF_HEADER_NAME", "X-CSRF-Token")
AUTH_SESSION_COOKIE_SAMESITE = (
    os.getenv("AUTH_SESSION_COOKIE_SAMESITE", "lax").strip().lower() or "lax"
)

security = HTTPBearer(auto_error=False)
# Login compatibility seam:
# - password reset writes User.hashed_password and should become the durable credential path.
# - users without hashed_password must keep authenticating through
#   AUTH_USER_PASSWORDS_JSON / AUTH_SHARED_PASSWORD until the reset contract replaces that fallback.
# - request-path auth recovery work should not expand init_db/runtime DDL behavior here; schema authority lives
#   in Alembic revisions plus common.db.models.PasswordResetToken, including the single-active-token invariant.
# M016/S03/T01 auth/RBAC baseline:
# - get_current_user / get_current_admin_user / require_role now raise structured detail payloads via _raise_auth_http_error(...).
# - the remaining admin-risk seam is not helper shape, but legacy /admin route families that still wire get_current_user instead of get_current_admin_user.
# - backend/src/admin/api/security_inventory.py tracks the full permission matrix and the fix-first route families for this slice.
# - backend/src/common/monitoring/log_safety_inventory.py tracks the auth-adjacent log sinks that still need token/password/cookie/email redaction.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

# M020/S01/T01 auth transport matrix — current shipped behavior, not target-state hardening.
# T02/T03 may tighten the policy, but downstream work should start from this explicit matrix instead
# of inferring security posture from scattered helpers/routes/hooks.
AUTH_TRANSPORT_MATRIX: dict[str, dict[str, list[str] | str]] = {
    "http_request": {
        "formal": ["authorization_bearer", "session_cookie"],
        "compatibility": [],
        "resolver": "resolve_bearer_or_cookie_token",
    },
    "websocket": {
        "formal": ["authorization_bearer", "session_cookie"],
        "compatibility": ["query_token"],
        "resolver": "resolve_websocket_auth",
        "current_resolution_order": "authorization_header -> session_cookie -> query_token_compatibility",
    },
    "login_credentials": {
        "formal": ["user_hashed_password"],
        "compatibility": ["auth_user_passwords_json", "auth_shared_password"],
        "resolver": "common.auth.api.login",
    },
}

WECOM_API_BASE_URL = "https://qyapi.weixin.qq.com"
WECOM_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"


def _read_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_wecom_corp_id() -> str:
    return _read_env("WECOM_CORP_ID", "WECHAT_CORP_ID")


def get_wecom_secret() -> str:
    return _read_env("WECOM_SECRET", "WECHAT_SECRET")


def get_wecom_agent_id() -> str:
    return _read_env("WECOM_AGENT_ID", "WECHAT_AGENT_ID")


def get_wecom_scope() -> str:
    return _read_env("AUTH_WECOM_SCOPE") or "snsapi_base"


def get_frontend_base_url() -> str:
    return (
        _read_env("AUTH_FRONTEND_BASE_URL", "NEXT_PUBLIC_APP_URL")
        or "http://localhost:3445"
    ).rstrip("/")


def get_wecom_oauth_state_cookie_name() -> str:
    return _read_env("AUTH_WECOM_STATE_COOKIE_NAME") or "app_wecom_oauth_state"


def get_wecom_oauth_return_to_cookie_name() -> str:
    return _read_env("AUTH_WECOM_RETURN_TO_COOKIE_NAME") or "app_wecom_return_to"


def get_wecom_oauth_cookie_max_age_seconds() -> int:
    raw = _read_env("AUTH_WECOM_OAUTH_COOKIE_MAX_AGE_SECONDS")
    if not raw:
        return 600
    try:
        return max(60, int(raw))
    except ValueError:
        return 600


def is_dev_login_enabled() -> bool:
    explicit = os.getenv("AUTH_ENABLE_DEV_LOGIN")
    if explicit is not None and explicit.strip():
        return _env_truthy(explicit) and _current_environment() != "production"
    return _current_environment() == "development"


def get_wecom_provider_diagnostics() -> dict[str, Any]:
    corp_id = get_wecom_corp_id()
    secret = get_wecom_secret()
    agent_id = get_wecom_agent_id()
    configured = bool(corp_id and secret and agent_id)
    return {
        "enabled": configured,
        "configured": configured,
        "corp_id_configured": bool(corp_id),
        "secret_configured": bool(secret),
        "agent_id_configured": bool(agent_id),
        "message": "企业微信 SSO 已配置，可直接发起授权。"
        if configured
        else "当前环境未配置企业微信 SSO。",
    }


def _get_wecom_oauth_cookie_options(*, key: str) -> dict[str, Any]:
    return {
        "key": key,
        "httponly": True,
        "secure": get_session_cookie_secure(),
        "samesite": get_session_cookie_samesite(),
        "path": "/",
        "max_age": get_wecom_oauth_cookie_max_age_seconds(),
    }


def set_wecom_oauth_flow_cookies(
    response: Response, *, state: str, return_to: str
) -> None:
    response.set_cookie(
        value=state,
        **_get_wecom_oauth_cookie_options(key=get_wecom_oauth_state_cookie_name()),
    )
    response.set_cookie(
        value=return_to,
        **_get_wecom_oauth_cookie_options(key=get_wecom_oauth_return_to_cookie_name()),
    )


def clear_wecom_oauth_flow_cookies(response: Response) -> None:
    for key in (
        get_wecom_oauth_state_cookie_name(),
        get_wecom_oauth_return_to_cookie_name(),
    ):
        response.delete_cookie(
            key=key,
            path="/",
            secure=get_session_cookie_secure(),
            samesite=get_session_cookie_samesite(),
        )


def build_wecom_authorization_url(*, redirect_uri: str, state: str) -> str:
    params = urlencode(
        {
            "appid": get_wecom_corp_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": get_wecom_scope(),
            "state": state,
            "agentid": get_wecom_agent_id(),
        }
    )
    return f"{WECOM_AUTHORIZE_URL}?{params}#wechat_redirect"


def _create_wecom_http_client() -> httpx.AsyncClient:
    timeout_raw = _read_env("AUTH_WECOM_TIMEOUT_SECONDS")
    timeout = float(timeout_raw) if timeout_raw else 10.0
    return httpx.AsyncClient(base_url=WECOM_API_BASE_URL, timeout=timeout)


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_department_value(value: Any) -> str | None:
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ",".join(parts) if parts else None
    return _normalize_optional_string(value)


async def _request_wecom_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = await client.get(path, params=params)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"WeCom API returned a non-object payload for {path}")
    errcode = payload.get("errcode", 0)
    if errcode not in (0, None):
        raise ValueError(f"WeCom API {path} failed: {payload.get('errmsg') or errcode}")
    return payload


def _raise_auth_http_error(
    *, status_code: int, error_code: str, message: str
) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail={
            "error": error_code,
            "message": message,
        },
    )


def _current_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _websocket_query_token_enabled() -> bool:
    env = _current_environment()
    configured = os.getenv("WEBSOCKET_QUERY_TOKEN_ENABLED", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return env in {"development", "dev", "local", "test", "testing"}


def get_session_cookie_name() -> str:
    return AUTH_SESSION_COOKIE_NAME


def get_csrf_cookie_name() -> str:
    return AUTH_CSRF_COOKIE_NAME


def get_csrf_header_name() -> str:
    return AUTH_CSRF_HEADER_NAME


def get_session_cookie_max_age_seconds() -> int:
    return max(1, JWT_EXPIRATION_HOURS * 3600)


def get_session_cookie_samesite() -> str:
    return AUTH_SESSION_COOKIE_SAMESITE


def get_session_cookie_secure() -> bool:
    if _current_environment() != "development":
        return True
    return _env_truthy(os.getenv("AUTH_SESSION_COOKIE_SECURE", ""))


def get_session_cookie_options() -> dict[str, Any]:
    return {
        "key": get_session_cookie_name(),
        "httponly": True,
        "secure": get_session_cookie_secure(),
        "samesite": get_session_cookie_samesite(),
        "path": "/",
        "max_age": get_session_cookie_max_age_seconds(),
    }


def get_csrf_cookie_options() -> dict[str, Any]:
    return {
        "key": get_csrf_cookie_name(),
        "httponly": False,
        "secure": get_session_cookie_secure(),
        "samesite": get_session_cookie_samesite(),
        "path": "/",
        "max_age": get_session_cookie_max_age_seconds(),
    }


def set_auth_session_cookie(
    response: Response, token: str, csrf_token: str | None = None
) -> str:
    issued_csrf_token = (csrf_token or uuid.uuid4().hex).strip()
    response.set_cookie(
        value=token,
        **get_session_cookie_options(),
    )
    response.set_cookie(
        value=issued_csrf_token,
        **get_csrf_cookie_options(),
    )
    return issued_csrf_token


def clear_auth_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_session_cookie_name(),
        path="/",
        secure=get_session_cookie_secure(),
        samesite=get_session_cookie_samesite(),
    )
    response.delete_cookie(
        key=get_csrf_cookie_name(),
        path="/",
        secure=get_session_cookie_secure(),
        samesite=get_session_cookie_samesite(),
    )


def should_enforce_csrf(request: Request) -> bool:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return False

    authorization_header = request.headers.get("authorization", "")
    if authorization_header.lower().startswith("bearer "):
        return False

    return bool(request.cookies.get(get_session_cookie_name()))


def validate_csrf_request(request: Request) -> None:
    csrf_cookie = (request.cookies.get(get_csrf_cookie_name()) or "").strip()
    csrf_header = (request.headers.get(get_csrf_header_name()) or "").strip()

    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "[CSRF_VALIDATION_FAILED]",
                "message": "当前请求缺少有效 CSRF 凭证。",
            },
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


def _extract_cookie_token(cookie_header: str | None) -> str:
    if not cookie_header:
        return ""

    cookies = SimpleCookie()
    cookies.load(cookie_header)
    morsel = cookies.get(get_session_cookie_name())
    if morsel and morsel.value:
        return morsel.value.strip()
    return ""


def resolve_websocket_auth(
    *,
    query_token: str | None,
    authorization_header: str | None = None,
    cookie_header: str | None = None,
) -> dict[str, str | bool]:
    if authorization_header and authorization_header.lower().startswith("bearer "):
        return {
            "token": authorization_header[7:].strip(),
            "transport": "authorization_bearer",
            "compatibility_mode": False,
        }

    cookie_token = _extract_cookie_token(cookie_header)
    if cookie_token:
        return {
            "token": cookie_token,
            "transport": "session_cookie",
            "compatibility_mode": False,
        }

    normalized_query_token = (query_token or "").strip()
    if normalized_query_token and _websocket_query_token_enabled():
        return {
            "token": normalized_query_token,
            "transport": "query_token",
            "compatibility_mode": True,
        }

    return {
        "token": "",
        "transport": "",
        "compatibility_mode": False,
    }


def resolve_websocket_token(
    *,
    query_token: str | None,
    authorization_header: str | None = None,
    cookie_header: str | None = None,
) -> str:
    return str(
        resolve_websocket_auth(
            query_token=query_token,
            authorization_header=authorization_header,
            cookie_header=cookie_header,
        )["token"]
    )


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
        logger.warning(
            "Token verification failed",
            error_type=type(e).__name__,
        )
        raise


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    cookie_token: str | None = Cookie(default=None, alias=AUTH_SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token"""
    token = resolve_bearer_or_cookie_token(
        credentials=credentials,
        request=request,
        cookie_token=cookie_token,
    )
    if token is None:
        _raise_auth_http_error(
            status_code=401,
            error_code="[AUTHENTICATION_REQUIRED]",
            message="当前请求需要登录后才能继续。",
        )

    try:
        payload = verify_token(token)
        raw_user_id = payload.get("sub")
        user_id = str(raw_user_id).strip() if raw_user_id is not None else ""
        if not user_id:
            _raise_auth_http_error(
                status_code=401,
                error_code="[INVALID_TOKEN]",
                message="登录态已失效，请重新登录。",
            )
    except JWTError:
        _raise_auth_http_error(
            status_code=401,
            error_code="[INVALID_TOKEN]",
            message="登录态已失效，请重新登录。",
        )

    # Cast UUID column to VARCHAR for string comparison
    result = await db.execute(
        select(User).where(cast(User.user_id, SQLAlchemyString) == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        _raise_auth_http_error(
            status_code=401,
            error_code="[AUTH_USER_NOT_FOUND]",
            message="登录用户不存在或已被删除。",
        )

    if not user.is_active:
        _raise_auth_http_error(
            status_code=403,
            error_code="[AUTH_USER_DISABLED]",
            message="当前账号已被停用。",
        )

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they have admin role.
    Use this dependency for admin-only endpoints.
    """
    if not hasattr(current_user, "role") or current_user.role != "admin":
        _raise_auth_http_error(
            status_code=403,
            error_code="[ROLE_REQUIRED]",
            message="当前账号权限不足，无法执行该操作。",
        )
    return current_user


async def get_current_admin_user_for_app_routes(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    App-level admin dependency for router-mirrored `/api/v1/admin/**` route families.

    Keeps the structured `detail.error` payload on the existing `[ROLE_REQUIRED]`
    contract so isolated router tests and downstream permission inventories do not
    drift, while making the top-level `message` string include `ADMIN_REQUIRED`
    for the app-mounted RBAC smoke tests that assert the public error wording.
    """
    if not hasattr(current_user, "role") or current_user.role != "admin":
        _raise_auth_http_error(
            status_code=403,
            error_code="[ROLE_REQUIRED]",
            message="[ADMIN_REQUIRED] 当前账号权限不足，无法执行该操作。",
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
        user_role = getattr(current_user, "role", "user")
        if user_role not in allowed_roles:
            _raise_auth_http_error(
                status_code=403,
                error_code="[ROLE_REQUIRED]",
                message="当前账号权限不足，无法执行该操作。",
            )
        return current_user

    return role_checker


async def authenticate_wechat(code: str) -> dict[str, Any]:
    """Exchange a WeCom OAuth code for a stable member identity payload."""
    corp_id = get_wecom_corp_id()
    secret = get_wecom_secret()
    if not corp_id or not secret:
        raise ValueError("WeCom SSO is not configured")

    normalized_code = code.strip()
    if not normalized_code:
        raise ValueError("WeCom callback code is required")

    async with _create_wecom_http_client() as client:
        token_payload = await _request_wecom_json(
            client,
            "/cgi-bin/gettoken",
            params={
                "corpid": corp_id,
                "corpsecret": secret,
            },
        )
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("WeCom token exchange returned an empty access_token")

        identity_payload = await _request_wecom_json(
            client,
            "/cgi-bin/auth/getuserinfo",
            params={
                "access_token": access_token,
                "code": normalized_code,
            },
        )
        user_id = str(identity_payload.get("userid") or "").strip()
        if not user_id:
            raise ValueError("WeCom callback did not return a userid")

        profile: dict[str, Any] = {
            "userid": user_id,
        }
        try:
            detail_payload = await _request_wecom_json(
                client,
                "/cgi-bin/user/get",
                params={
                    "access_token": access_token,
                    "userid": user_id,
                },
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "WeCom user detail lookup failed",
                wecom_user_id=user_id,
                error_type=type(exc).__name__,
            )
        else:
            profile.update(detail_payload)

        return profile


async def upsert_wecom_user(db: AsyncSession, profile: dict[str, Any]) -> User:
    """Create or update the local user that corresponds to a WeCom identity."""
    wecom_user_id = _normalize_optional_string(profile.get("userid"))
    if wecom_user_id is None:
        raise ValueError("WeCom profile is missing userid")

    email = _normalize_optional_string(profile.get("email"))
    name = _normalize_optional_string(profile.get("name")) or wecom_user_id
    department = _normalize_department_value(profile.get("department"))

    result = await db.execute(select(User).where(User.wechat_user_id == wecom_user_id))
    user = result.scalar_one_or_none()

    if user is None and email:
        email_result = await db.execute(select(User).where(User.email == email))
        user = email_result.scalar_one_or_none()

    if user is None:
        user = User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=wecom_user_id,
            email=email,
            name=name,
            department=department,
        )
        db.add(user)
    else:
        user.wechat_user_id = wecom_user_id
        user.name = name or user.name or wecom_user_id
        if email:
            user.email = email
        if department is not None:
            user.department = department

    await db.commit()
    await db.refresh(user)
    return user


async def mark_user_logged_in(db: AsyncSession, user: User) -> User:
    user.last_login = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user


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
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Optional authentication - returns None if not authenticated
    For development mode testing
    """

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
