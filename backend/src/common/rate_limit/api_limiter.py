"""
API Rate Limiter - Prevent abuse and DDoS attacks

Implements Constitution Principle V: Cost control
- Limits API requests per IP/user
- Prevents brute force attacks
- Protects against resource exhaustion

Requirements: P1-FIXES.md Issue #23
"""

import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Dict, Optional, Set

from fastapi import HTTPException, Request

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry"""

    count: int = 0
    reset_time: float = field(default_factory=lambda: time.time() + 60)
    blocked: bool = False


class APIRateLimiter:
    """
    In-memory API rate limiter

    Features:
    - Per-IP rate limiting
    - Per-user rate limiting
    - Configurable limits per endpoint
    - Automatic cleanup of expired entries

    Usage:
        limiter = APIRateLimiter()

        @app.get("/api/v1/users")
        @limiter.limit(calls=100, period=60)  # 100 calls per minute
        async def get_users(request: Request):
            pass
    """

    def __init__(self, default_calls: int = 100, default_period: int = 60):
        self.default_calls = default_calls
        self.default_period = default_period
        self._storage: Dict[str, RateLimitEntry] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _get_key(self, identifier: str, scope: str = "ip") -> str:
        """Generate storage key"""
        return f"ratelimit:{scope}:{identifier}"

    def _cleanup_expired(self):
        """Remove expired rate limit entries"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = [
            key
            for key, entry in self._storage.items()
            if now > entry.reset_time and not entry.blocked
        ]

        for key in expired_keys:
            del self._storage[key]

        self._last_cleanup = now

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    def is_allowed(
        self, identifier: str, calls: int, period: int, scope: str = "ip"
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit

        Args:
            identifier: IP address or user ID
            calls: Maximum allowed calls
            period: Time window in seconds
            scope: 'ip' or 'user'

        Returns:
            (allowed: bool, info: dict)
        """
        self._cleanup_expired()

        key = self._get_key(identifier, scope)
        now = time.time()

        entry = self._storage.get(key)

        if entry is None:
            # First request
            self._storage[key] = RateLimitEntry(count=1, reset_time=now + period)
            return True, {
                "limit": calls,
                "remaining": calls - 1,
                "reset": int(now + period),
            }

        # Check if window has reset
        if now > entry.reset_time:
            entry.count = 1
            entry.reset_time = now + period
            entry.blocked = False
            return True, {
                "limit": calls,
                "remaining": calls - 1,
                "reset": int(entry.reset_time),
            }

        # Check if blocked
        if entry.blocked:
            return False, {
                "limit": calls,
                "remaining": 0,
                "reset": int(entry.reset_time),
                "retry_after": int(entry.reset_time - now),
            }

        # Increment count
        entry.count += 1

        if entry.count > calls:
            entry.blocked = True
            logger.warning(
                f"Rate limit exceeded for {scope}={identifier}",
                extra={"identifier": identifier, "scope": scope, "count": entry.count},
            )
            return False, {
                "limit": calls,
                "remaining": 0,
                "reset": int(entry.reset_time),
                "retry_after": int(entry.reset_time - now),
            }

        return True, {
            "limit": calls,
            "remaining": calls - entry.count,
            "reset": int(entry.reset_time),
        }

    def limit(
        self,
        calls: Optional[int] = None,
        period: Optional[int] = None,
        scope: str = "ip",
    ):
        """
        Decorator to apply rate limiting to an endpoint

        Args:
            calls: Maximum calls allowed (default: 100)
            period: Time window in seconds (default: 60)
            scope: 'ip' or 'user'
        """
        calls = calls or self.default_calls
        period = period or self.default_period

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Get identifier based on scope
                if scope == "user":
                    identifier = _get_user_id(request)
                else:
                    identifier = _get_client_ip(request)

                allowed, info = self.is_allowed(identifier, calls, period, scope)

                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "[RATE_LIMIT_EXCEEDED]",
                            "message": f"请求过于频繁，请{info['retry_after']}秒后再试",
                            "retry_after": info["retry_after"],
                        },
                        headers={
                            "X-RateLimit-Limit": str(info["limit"]),
                            "X-RateLimit-Remaining": str(info["remaining"]),
                            "X-RateLimit-Reset": str(info["reset"]),
                            "Retry-After": str(info["retry_after"]),
                        },
                    )

                # Add rate limit headers to response
                response = await func(request, *args, **kwargs)

                # If response is a dict, wrap it
                if isinstance(response, dict):
                    from fastapi.responses import JSONResponse

                    resp = JSONResponse(content=response)
                    resp.headers["X-RateLimit-Limit"] = str(info["limit"])
                    resp.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                    resp.headers["X-RateLimit-Reset"] = str(info["reset"])
                    return resp

                return response

            return wrapper

        return decorator


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    # Check X-Forwarded-For header (for proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return "unknown"


def _get_user_id(request: Request) -> str:
    """Extract user ID from request (if authenticated)"""
    # Try to get from request state (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        return str(request.state.user.get("user_id", "anonymous"))

    # Fall back to IP
    return _get_client_ip(request)


# Global rate limiter instance
_rate_limiter: Optional[APIRateLimiter] = None


def get_rate_limiter() -> APIRateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = APIRateLimiter()
    return _rate_limiter


# Convenience decorator
def rate_limit(calls: int = 100, period: int = 60, scope: str = "ip"):
    """
    Rate limiting decorator

    Usage:
        @app.get("/api/v1/users")
        @rate_limit(calls=100, period=60)
        async def get_users(request: Request):
            pass
    """
    return get_rate_limiter().limit(calls=calls, period=period, scope=scope)
