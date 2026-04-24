"""
FastAPI Main Application
Entry point for the AI Practice System backend.
"""

from __future__ import annotations

import os
import sys

# Add src to path for imports when this module is executed directly.
sys.path.insert(0, os.path.dirname(__file__))

from app_factory import create_app  # noqa: E402
from app_lifespan import lifespan  # noqa: E402
from common.db.session import get_db  # noqa: E402
from http_routes import (  # noqa: E402
    CSRF_EXEMPT_PATHS,
    _check_database_readiness,
    _csrf_validation_failed_response,
    _is_csrf_exempt_path,
    csrf_protection_middleware,
    dev_login,
    health_check,
    metrics_export,
)
from websocket_routes import (  # noqa: E402
    _default_voice_mode,
    _is_admin_user_id,
    _is_presentation_kb_lock_unbound_session,
    _normalize_requested_voice_mode,
    _parse_session_id,
    _reject_invalid_presentation_session,
    _resolve_presentation_runtime,
    _resolve_presentation_session_owner_id,
    presentation_websocket,
    presentation_websocket_with_path,
)
from websocket_routes import (
    _handle_presentation_websocket as _presentation_websocket_handler,
)

# Conversation Replay API
from common.conversation.api import router as replay_router
from common.db.models import PracticeSession, Scenario, User
from common.db.session import (
    STARTUP_DB_AUTHORITY,
    AsyncSessionLocal,
    get_db,
    init_db,
)
from common.error_handling.middleware import (
    ErrorHandlerMiddleware,
    global_exception_handler,
    http_exception_handler,
)

# Knowledge API
from common.knowledge.api import admin_router as knowledge_admin_router
from common.knowledge.api import internal_router as knowledge_internal_router
from common.knowledge.kb_lock_guard import is_kb_lock_unbound_snapshot
from common.monitoring.health import build_health_payload
from common.monitoring.logger import configure_logging, get_logger, get_trace_id
from common.monitoring.metrics import (
    MetricsMiddleware,
    get_metrics,
    initialize_metrics,
)
from common.monitoring.otel import initialize_otel
from common.monitoring.trace_context import normalize_trace_id

# Evaluation API
from evaluation.api import router as evaluation_router
from presentation_coach.api import presentations

# Prompt Templates API
from prompt_templates.api.routes import router as prompt_templates_router
from prompt_templates.api.routes import scenario_router as scenario_prompts_router
from sales_bot.api.scenarios import router as scenarios_router
from sales_bot.websocket.router import router as sales_ws_router
from support.api.runtime_status import router as support_runtime_router

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI Practice System backend")
    initialize_otel(app)

    # P0-1: Validate JWT secret in non-development environments
    from common.auth.service import JWT_SECRET
    from common.config import settings

    env = settings.ENVIRONMENT
    if env != "development" and (not settings.SECRET_KEY or settings.SECRET_KEY == ""):
        raise RuntimeError(
            "SECRET_KEY must be set in production via environment variable"
        )
    if (
        env != "development"
        and JWT_SECRET == "your-super-secret-key-change-in-production-min-32-chars"
    ):
        raise RuntimeError(
            "JWT_SECRET must be set in production via environment variable"
        )

    logger.info(
        "Database authority map resolved for startup",
        startup_initializer=STARTUP_DB_AUTHORITY["startup_initializer"],
        schema_migration_entrypoint=STARTUP_DB_AUTHORITY["schema_migration_entrypoint"],
        legacy_schema_repair_entrypoint=STARTUP_DB_AUTHORITY[
            "legacy_schema_repair_entrypoint"
        ],
        auth_bootstrap_entrypoint=STARTUP_DB_AUTHORITY["auth_bootstrap_entrypoint"],
        startup_compatibility_guards=STARTUP_DB_AUTHORITY[
            "startup_compatibility_guards"
        ],
    )
    await init_db()

    auth_config = get_auth_config_diagnostics()
    wecom_config = get_wecom_provider_diagnostics()
    if env != "development":
        if not auth_config["user_overrides_valid"]:
            raise RuntimeError(
                "AUTH_USER_PASSWORDS_JSON is invalid in non-development environment"
            )
        if not auth_config["credentials_ready"]:
            raise RuntimeError(
                "Auth credentials are not configured. Set AUTH_SHARED_PASSWORD "
                "or AUTH_USER_PASSWORDS_JSON before startup."
            )
        if not wecom_config["configured"]:
            raise RuntimeError(
                "WeCom SSO is not configured. Set WECHAT_CORP_ID/WECHAT_SECRET/WECHAT_AGENT_ID "
                "(or WECOM_CORP_ID/WECOM_SECRET/WECOM_AGENT_ID) before startup."
            )

    if auth_config["credentials_ready"] and auth_config["user_overrides_valid"]:
        logger.info(
            "Auth credentials configured",
            shared_password=auth_config["shared_password_configured"],
            user_overrides=auth_config["user_override_count"],
        )
    elif auth_config["credentials_ready"] and not auth_config["user_overrides_valid"]:
        logger.warning(
            "Auth user overrides are invalid JSON; fallback to shared password only",
            shared_password=auth_config["shared_password_configured"],
        )
    else:
        logger.warning(
            "Auth credentials are not configured; login endpoint will return 503",
            shared_password=auth_config["shared_password_configured"],
            user_overrides=auth_config["user_override_count"],
        )

    if wecom_config["configured"]:
        logger.info(
            "WeCom SSO configured",
            corp_id_configured=wecom_config["corp_id_configured"],
            agent_id_configured=wecom_config["agent_id_configured"],
        )
    else:
        logger.warning(
            "WeCom SSO is not configured",
            corp_id_configured=wecom_config["corp_id_configured"],
            agent_id_configured=wecom_config["agent_id_configured"],
        )

    # Initialize ConfigManager for AI model configurations
    try:
        from common.ai.config_manager import initialize_config_manager

        await initialize_config_manager()
        logger.info("ConfigManager initialized")
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning(f"ConfigManager initialization failed: {str(e)}")

    # Optional: Preload critical services
    from common.config import settings

    if settings.PRELOAD_SERVICES:
        logger.info("Preloading critical services (PRELOAD_SERVICES=true)")
        try:
            from common.audio.asr_service import get_asr_service

            get_asr_service()  # Trigger ASR initialization
            logger.info("Service preloading complete")
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Service preloading failed: {str(e)}")

    # Start SessionManager for WebSocket session timeout/heartbeat
    from common.websocket.session_manager import (
        init_session_manager,
        shutdown_session_manager,
    )
    from common.websocket.session_state_service import (
        init_session_state_service,
        shutdown_session_state_service,
    )

    await init_session_manager()
    await init_session_state_service()

    yield

    # Shutdown
    await shutdown_session_state_service()
    await shutdown_session_manager()
    logger.info("Shutting down AI Practice System backend")


# Create FastAPI app
app = FastAPI(
    title="Enterprise AI Intelligent Practice System",
    description="""
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
""",
    version="2.0.0",
    lifespan=lifespan,
)
initialize_metrics(
    version=app.version,
    environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_origin_regex=_resolve_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware (Constitution Principle I)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(MetricsMiddleware)

# Add global exception handler
app.exception_handler(HTTPException)(http_exception_handler)
app.exception_handler(Exception)(global_exception_handler)

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
    detail = exc.detail if isinstance(exc.detail, dict) else {}
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


@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
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


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    payload = build_health_payload(
        checks={"database": await _check_database_readiness()}
    )
    return JSONResponse(status_code=200 if payload["ready"] else 503, content=payload)


@app.get("/metrics", include_in_schema=False)
async def metrics_export():
    """Prometheus metrics export mounted on the live backend authority line."""
    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# Development login endpoint (for testing without WeCom SSO)
@app.post("/api/v1/auth/dev-login")
async def dev_login(db: AsyncSession = Depends(get_db)):
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


# Include routers
app.include_router(
    presentations.router,
    prefix="/api/v1",
    tags=["presentations"],
    dependencies=[Depends(require_role(["admin", "user"]))],
)
app.include_router(
    practice.router,
    prefix="/api/v1",
    tags=["practice"],
    dependencies=[Depends(require_role(["admin", "user"]))],
)
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(
    growth.router,
    prefix="/api/v1",
    tags=["growth"],
    dependencies=[Depends(require_role(["admin", "user"]))],
)
app.include_router(
    training.router,
    prefix="/api/v1",
    tags=["training"],
    dependencies=[Depends(require_role(["admin", "user"]))],
)
app.include_router(
    scenarios_router,
    prefix="/api/v1",
    tags=["scenarios"],
    dependencies=[Depends(require_role(["admin", "user"]))],
)
app.include_router(
    admin_presentations_router,
    prefix="/api/v1",
    tags=["admin-presentations"],
    dependencies=[Depends(get_current_admin_user_for_app_routes)],
)
app.include_router(users.router, prefix="/api/v1", tags=["users"])

# Auth API routes
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])

# Agent Platform API routes
app.include_router(agent_admin_router, prefix="/api/v1", tags=["admin-agents"])
app.include_router(agent_user_router, prefix="/api/v1", tags=["agents"])
app.include_router(persona_admin_router, prefix="/api/v1", tags=["admin-personas"])
app.include_router(
    agent_persona_admin_router, prefix="/api/v1", tags=["admin-agent-personas"]
)

# Knowledge API routes
app.include_router(
    knowledge_admin_router,
    prefix="/api/v1",
    tags=["admin-knowledge"],
    dependencies=[Depends(get_current_admin_user_for_app_routes)],
)
app.include_router(
    knowledge_internal_router, prefix="/api/v1", tags=["internal-knowledge"]
)

# v1-18 Fix: Knowledge API alias via automatic route mirroring
# Provides /admin/knowledge-bases path compatibility for frontend
knowledge_bases_alias_router = APIRouter(
    prefix="/admin/knowledge-bases", tags=["admin-knowledge-bases"]
)

# Mirror all routes from the source knowledge router automatically
for route in knowledge_admin_router.routes:
    if not isinstance(route, APIRoute):
        continue

    # Remap path: /admin/knowledge/* -> /*
    alias_path = route.path
    if alias_path.startswith("/admin/knowledge"):
        alias_path = alias_path.replace("/admin/knowledge", "", 1)

    knowledge_bases_alias_router.add_api_route(
        alias_path,
        route.endpoint,
        methods=route.methods,
        status_code=route.status_code,
    )

app.include_router(
    knowledge_bases_alias_router,
    prefix="/api/v1",
    tags=["admin-knowledge-bases"],
    dependencies=[Depends(get_current_admin_user_for_app_routes)],
)

# Conversation Replay API routes
app.include_router(replay_router, prefix="/api/v1", tags=["replay"])

# Admin API routes (users, training records, system logs)
app.include_router(
    admin_users_router,
    prefix="/api/v1",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(
    admin_training_records_router,
    prefix="/api/v1",
    tags=["admin-training-records"],
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(
    admin_analytics_router,
    prefix="/api/v1",
    tags=["admin-analytics"],
    dependencies=[Depends(get_current_admin_user_for_app_routes)],
)
app.include_router(
    admin_interventions_router,
    prefix="/api/v1",
    tags=["admin-interventions"],
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(
    admin_system_logs_router,
    prefix="/api/v1",
    tags=["admin-system-logs"],
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(
    business_rules_router,
    prefix="/api/v1/admin",
    tags=["admin-business-rules"],
)
app.include_router(
    knowledge_answer_config_router,
    prefix="/api/v1/admin",
    tags=["admin-knowledge-answer"],
)
app.include_router(
    rag_profiles_router,
    prefix="/api/v1/admin",
    tags=["admin-rag-profiles"],
)

# Support runtime status API routes (read-only)
app.include_router(
    support_runtime_router,
    prefix="/api/v1",
    tags=["support-runtime"],
    dependencies=[Depends(require_role(["admin", "support"]))],
)
app.include_router(
    knowledge_debug_router,
    prefix="/api/v1",
    tags=["knowledge-debug"],
    dependencies=[Depends(require_role(["admin", "support"]))],
)

# Model Config API routes
app.include_router(
    model_configs_router, prefix="/api/v1/admin", tags=["admin-model-configs"]
)
app.include_router(
    voice_runtime_router, prefix="/api/v1/admin", tags=["admin-voice-runtime"]
)
app.include_router(
    presentation_ai_router, prefix="/api/v1/admin", tags=["admin-presentation-ai"]
)

# Prompt Templates API routes
app.include_router(prompt_templates_router, tags=["prompt-templates"])
app.include_router(scenario_prompts_router, tags=["scenario-prompts"])

# Evaluation API routes
app.include_router(evaluation_router, prefix="/api/v1", tags=["evaluation"])


# WebSocket endpoint for PPT presentation coaching
def _parse_session_id(session_id: str | None) -> str | None:
    candidate = (session_id or "").strip()
    if not candidate:
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


async def _reject_invalid_presentation_session(
    websocket: WebSocket, session_id: str | None
):
    logger.warning(
        "Rejected /ws/presentation connection due to invalid session_id",
        session_id=session_id,
    )
    await websocket.accept()
    await websocket.close(code=4400, reason="INVALID_SESSION_ID")


async def _handle_presentation_websocket(
    websocket,
    session_id: str | None,
    token: str,
    voice_mode: str | None = None,
    trace_id: str = "",
):
    """
    Backward-compatible presentation WebSocket helper.

    Existing tests and integrations patch helper functions on ``main`` directly;
    route wiring lives in ``websocket_routes`` while this facade preserves that
    import-and-patch contract.
    """
    await _presentation_websocket_handler(
        websocket=websocket,
        session_id=session_id,
        token=token,
        voice_mode=voice_mode,
        trace_id=trace_id,
        resolve_runtime=_resolve_presentation_runtime,
        is_kb_lock_unbound=_is_presentation_kb_lock_unbound_session,
        resolve_owner_id=_resolve_presentation_session_owner_id,
        is_admin_user_id=_is_admin_user_id,
    )


__all__ = [
    "CSRF_EXEMPT_PATHS",
    "_check_database_readiness",
    "_csrf_validation_failed_response",
    "_default_voice_mode",
    "_handle_presentation_websocket",
    "_is_admin_user_id",
    "_is_csrf_exempt_path",
    "_is_presentation_kb_lock_unbound_session",
    "_normalize_requested_voice_mode",
    "_parse_session_id",
    "_reject_invalid_presentation_session",
    "_resolve_presentation_runtime",
    "_resolve_presentation_session_owner_id",
    "app",
    "create_app",
    "csrf_protection_middleware",
    "dev_login",
    "get_db",
    "health_check",
    "lifespan",
    "metrics_export",
    "presentation_websocket",
    "presentation_websocket_with_path",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=3444, reload=True, log_level="info")
