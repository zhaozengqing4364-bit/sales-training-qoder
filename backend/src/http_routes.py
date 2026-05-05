"""Core HTTP routes and HTTP middleware for the backend application."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.api import error_response
from common.auth.service import (
    create_access_token,
    get_dev_user,
    is_dev_login_enabled,
    set_auth_session_cookie,
    should_enforce_csrf,
    validate_csrf_request,
)
from common.db.session import AsyncSessionLocal, get_db
from common.monitoring.health import build_health_payload
from common.monitoring.logger import get_logger, get_trace_id
from common.monitoring.metrics import get_metrics

logger = get_logger(__name__)

CSRF_EXEMPT_PATHS = {
    "/health",
    "/metrics",
    "/api/v1/auth/login",
    "/api/v1/auth/dev-login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}


def _is_csrf_exempt_path(path: str) -> bool:
    return path in CSRF_EXEMPT_PATHS


def _csrf_validation_failed_response(exc: HTTPException) -> JSONResponse:
    detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
    error = str(detail.get("error") or "[CSRF_VALIDATION_FAILED]")
    message = str(detail.get("message") or "当前请求缺少有效 CSRF 凭证。")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error,
            "message": message,
            "detail": exc.detail,
            "trace_id": get_trace_id(),
        },
    )


async def csrf_protection_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if not _is_csrf_exempt_path(request.url.path) and should_enforce_csrf(request):
        try:
            validate_csrf_request(request)
        except HTTPException as exc:
            return _csrf_validation_failed_response(exc)

    return await call_next(request)


async def _check_database_readiness() -> str:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
    except (OSError, RuntimeError, SQLAlchemyError) as exc:
        logger.warning("Health readiness database check failed", error=str(exc))
        return "error"
    return "ok"


async def health_check() -> JSONResponse:
    """Health check endpoint."""
    payload = build_health_payload(
        checks={"database": await _check_database_readiness()}
    )
    return JSONResponse(status_code=200 if payload["ready"] else 503, content=payload)


async def metrics_export() -> Response:
    """Prometheus metrics export mounted on the live backend authority line."""
    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def dev_login(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Development mode login - creates a mock user and returns a JWT token.
    This path is explicit fallback only and is disabled outside development by default.
    """
    if not is_dev_login_enabled():
        return error_response(
            "[DEV_LOGIN_DISABLED]",
            "开发者登录仅在 development 环境可用。",
            status_code=403,
        )

    user = await get_dev_user(db)
    user_role = getattr(user, "role", None) or "user"
    token = create_access_token(data={"sub": str(user.user_id), "role": user_role})

    response = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "user_id": str(user.user_id),
                    "email": user.email,
                    "name": user.name,
                    "role": user_role,
                },
            },
        },
    )
    set_auth_session_cookie(response, token)
    response.headers["X-Auth-Authority"] = "development_fallback"
    response.headers["X-Auth-Compatibility-Mode"] = "explicit_dev_login"
    return response


def register_http_routes(app: FastAPI) -> None:
    """Attach core HTTP middleware and routes to the app."""
    app.middleware("http")(csrf_protection_middleware)
    app.add_api_route("/health", health_check, methods=["GET"])
    app.add_api_route(
        "/metrics",
        metrics_export,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route("/api/v1/auth/dev-login", dev_login, methods=["POST"])
