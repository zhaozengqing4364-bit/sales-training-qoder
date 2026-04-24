"""FastAPI application factory."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app_lifespan import lifespan
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

    resolved_origins = (
        configured_origins[:] if configured_origins else DEV_CORS_ORIGINS[:]
    )

    for origin in DEV_CORS_ORIGINS:
        if origin not in resolved_origins:
            resolved_origins.append(origin)

    return resolved_origins


def _resolve_cors_origin_regex() -> str | None:
    configured_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    if configured_regex:
        return configured_regex

    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    if env == "development":
        return DEV_CORS_ALLOW_ORIGIN_REGEX

    return None


def _configure_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(),
        allow_origin_regex=_resolve_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.exception_handler(HTTPException)(http_exception_handler)
    app.exception_handler(Exception)(global_exception_handler)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
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
