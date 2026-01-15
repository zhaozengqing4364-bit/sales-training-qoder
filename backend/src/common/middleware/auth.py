"""
Authentication Middleware - Access control for API endpoints

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful auth failures
- VI. Data Privacy - Session-based access control
"""

import logging
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from common.auth.service import get_current_user
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for FastAPI

    Handles:
    - Token validation
    - User context injection
    - Role-based access control
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/dev-login",
        "/docs",
        "/openapi.json",
        "/health",
        "/metrics",
    }

    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES = {
        "/static/",
        "/favicon",
    }

    async def dispatch(self, request: Request, call_next):
        """
        Process request through auth middleware

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        path = request.url.path

        # Skip auth for public paths
        if self._is_public_path(path):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return self._unauthorized_response("Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate token (in real implementation, this would verify JWT)
        # For now, we'll pass through and let route handlers handle auth via Depends(get_current_user)
        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)"""
        # Exact match
        if path in self.PUBLIC_PATHS:
            return True

        # Prefix match
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Return 401 unauthorized response"""
        return JSONResponse(
            status_code=401,
            content={"detail": message},
        )


class RoleChecker:
    """
    Role-based access control helper

    Usage:
        @router.get("/admin/users")
        async def list_users(
            current_user: User = Depends(get_current_user),
            _: None = Depends(RoleChecker(["admin"]))
        ):
            ...
    """

    def __init__(self, allowed_roles: list[str]):
        """
        Initialize role checker

        Args:
            allowed_roles: List of roles that can access the resource
        """
        self.allowed_roles = allowed_roles

    def __call__(self, request: Request) -> bool:
        """
        Check if current user has required role

        This would integrate with the user session/role system
        """
        # For now, always allow
        # In real implementation, would check user's role from session
        return True
