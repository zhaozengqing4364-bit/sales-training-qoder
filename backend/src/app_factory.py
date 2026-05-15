"""FastAPI application factory."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app_lifespan import lifespan
from common.analytics.release_readiness import validate_production_config
from common.api.response import error_response
from common.error_handling.middleware import (
    ErrorHandlerMiddleware,
    global_exception_handler,
    http_exception_handler,
)
from common.monitoring.logger import configure_logging
from common.monitoring.metrics import MetricsMiddleware, initialize_metrics
from http_routes import register_http_routes
from router_registry import register_routers
from websocket_routes import register_websocket_routes

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))

DEV_CORS_ORIGINS = [
    "http://localhost:3445",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3445",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:3445",
    "http://[::1]:3445",
]

DEV_CORS_ALLOW_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"[a-zA-Z0-9-]+\.local"
    r")(:\d+)?$"
)

APP_TITLE = "Enterprise AI Intelligent Practice System"
APP_DESCRIPTION = """
Real-time voice-based AI training platform with Agent Platform support.

## Features

### Core Features
- **Presentation Coaching**: Practice presentations with AI feedback
- **Sales Practice**: Practice sales conversations with AI personas

### Agent Platform (New)
- **Agent Management**: Create and manage AI training scenarios
- **Persona Management**: Create and manage AI characters for practice
- **Knowledge Base**: Upload and manage documents for AI context
- **Conversation Replay**: Review and analyze practice sessions

### API Groups
- `/api/v1/admin/agents` - Agent management (admin)
- `/api/v1/agents` - Agent listing (user)
- `/api/v1/admin/personas` - Persona management (admin)
- `/api/v1/admin/knowledge` - Knowledge base management (admin)
- `/api/v1/sessions` - Session management with enhanced reports
- `/api/v1/sessions/{id}/replay` - Conversation replay
"""
APP_VERSION = "2.0.0"


def _resolve_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    configured_origins = [
        origin.strip() for origin in configured.split(",") if origin.strip()
    ]
    env = _current_environment()

    if configured_origins:
        _validate_cors_origins(configured_origins)
        resolved_origins = configured_origins[:]
    elif _is_dev_or_test_environment(env):
        resolved_origins = DEV_CORS_ORIGINS[:]
    else:
        return []

    if _is_dev_or_test_environment(env):
        for origin in DEV_CORS_ORIGINS:
            if origin not in resolved_origins:
                resolved_origins.append(origin)

    return resolved_origins


def _resolve_cors_origin_regex() -> str | None:
    configured_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    if configured_regex:
        return configured_regex

    if _is_dev_or_test_environment(_current_environment()):
        return DEV_CORS_ALLOW_ORIGIN_REGEX

    return None


def _current_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def _is_dev_or_test_environment(env: str) -> bool:
    return env in {"development", "dev", "local", "test", "testing"}


def _validate_cors_origins(origins: list[str]) -> None:
    for origin in origins:
        if origin == "*":
            raise RuntimeError(
                "CORS_ORIGINS cannot include '*' while credentials are enabled"
            )

        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                "CORS_ORIGINS entries must be explicit HTTP(S) origins"
            )


def _configure_middleware(app: FastAPI) -> None:
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(),
        allow_origin_regex=_resolve_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.exception_handler(HTTPException)(http_exception_handler)
    app.exception_handler(RequestValidationError)(_request_validation_exception_handler)
    app.exception_handler(Exception)(global_exception_handler)


def _validate_production_readiness_config() -> None:
    findings = validate_production_config(dict(os.environ))
    if findings:
        codes = ", ".join(finding.code for finding in findings)
        raise RuntimeError(f"Production configuration rejected: {codes}")


async def _request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Map prompt-template save validation to the governance-required 400 contract."""
    if request.url.path.startswith("/api/v1/prompt-templates"):
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[PROMPT_DATA_INVALID]",
                message="提示词数据无效，请检查 prompt_type、variables 与模板内容。",
            )
            | {"detail": exc.errors()},
        )

    from fastapi.exception_handlers import request_validation_exception_handler

    return await request_validation_exception_handler(request, exc)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _validate_production_readiness_config()
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.state.lifespan_authority = lifespan
    initialize_metrics(
        version=app.version,
        environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
    )

    _configure_middleware(app)
    register_http_routes(app)
    register_routers(app)
    register_websocket_routes(app)

    return app
