"""
FastAPI Main Application
Entry point for the AI Practice System backend
"""

import os
import sys
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from admin.api.admin import router as admin_presentations_router
from admin.api.analytics import router as admin_analytics_router
from admin.api.interventions import router as admin_interventions_router
from admin.api.knowledge_answer_config import router as knowledge_answer_config_router
from admin.api.model_configs import router as model_configs_router
from admin.api.presentation_ai import router as presentation_ai_router
from admin.api.rag_profiles import router as rag_profiles_router
from admin.api.system_logs import router as admin_system_logs_router
from admin.api.training_records import router as admin_training_records_router

# Admin API (users, training records, system logs)
from admin.api.users import router as admin_users_router
from admin.api.voice_runtime import router as voice_runtime_router
from agent.api.agent_personas import admin_router as agent_persona_admin_router

# Agent Platform API
from agent.api.agents import admin_router as agent_admin_router
from agent.api.agents import user_router as agent_user_router
from agent.api.personas import admin_router as persona_admin_router
from common.api import analytics, dashboard, practice, training, users
from common.api.knowledge_debug import router as knowledge_debug_router
from common.auth.api import error_response, get_auth_config_diagnostics
from common.auth.api import router as auth_router

# Development mode auth (for testing without WeChat SSO)
from common.auth.service import (
    JWTError,
    create_access_token,
    get_current_admin_user,
    get_current_admin_user_for_app_routes,
    get_dev_user,
    get_wecom_provider_diagnostics,
    is_dev_login_enabled,
    require_role,
    resolve_websocket_token,
    set_auth_session_cookie,
    should_enforce_csrf,
    validate_csrf_request,
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


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return build_health_payload()


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
    websocket: WebSocket,
    session_id: str | None,
    token: str,
    voice_mode: str | None = None,
    trace_id: str = "",
):
    from common.auth.service import verify_token
    from common.websocket.session_manager import get_session_manager
    from presentation_coach.websocket.presentation_handler import (
        PresentationWebSocketHandler,
    )
    from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
        PresentationStepFunRealtimeHandler,
    )

    resolved_session_id = _parse_session_id(session_id)
    if not resolved_session_id:
        await _reject_invalid_presentation_session(websocket, session_id)
        return

    scenario_type, persisted_voice_mode = await _resolve_presentation_runtime(
        resolved_session_id
    )
    if scenario_type and scenario_type != "presentation":
        logger.warning(
            "Rejected /ws/presentation connection due to scenario mismatch",
            session_id=resolved_session_id,
            expected="presentation",
            actual=scenario_type,
        )
        await websocket.accept()
        await websocket.close(code=4409, reason="SESSION_SCENARIO_MISMATCH")
        return

    kb_lock_unbound = await _is_presentation_kb_lock_unbound_session(
        resolved_session_id
    )
    if kb_lock_unbound:
        logger.warning(
            "Rejected /ws/presentation connection due to KB lock without bound knowledge base",
            session_id=resolved_session_id,
        )
        await websocket.accept()
        await websocket.close(code=4410, reason="KB_LOCK_UNBOUND")
        return

    token = resolve_websocket_token(
        query_token=token,
        authorization_header=websocket.headers.get("authorization", ""),
        cookie_header=websocket.headers.get("cookie", ""),
    )

    requested_mode = _normalize_requested_voice_mode(voice_mode)
    if requested_mode and requested_mode != persisted_voice_mode:
        logger.warning(
            "Ignoring mismatched presentation ws voice_mode override",
            session_id=resolved_session_id,
            requested=requested_mode,
            persisted=persisted_voice_mode,
        )

    effective_voice_mode = persisted_voice_mode
    if effective_voice_mode == "stepfun_realtime":
        handler = PresentationStepFunRealtimeHandler()
    else:
        handler = PresentationWebSocketHandler()

    try:
        payload = verify_token(token)
        if payload and isinstance(payload.get("sub"), str):
            user_id = payload["sub"]
        elif payload and isinstance(payload.get("user_id"), str):
            user_id = payload["user_id"]
        else:
            user_id = None
    except (JWTError, RuntimeError, ValueError, OSError):
        logger.warning(
            "Failed to resolve websocket user from token",
            session_id=resolved_session_id,
        )
        user_id = None

    if user_id is None:
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return

    session_owner_id = await _resolve_presentation_session_owner_id(
        resolved_session_id
    )
    if (
        session_owner_id
        and session_owner_id != user_id
        and not await _is_admin_user_id(user_id)
    ):
        logger.warning(
            "Rejected /ws/presentation connection due to owner mismatch",
            session_id=resolved_session_id,
            request_user_id=user_id,
            session_owner_id=session_owner_id,
        )
        await websocket.accept()
        await websocket.close(code=4003, reason="ACCESS_DENIED")
        return

    session_manager = get_session_manager()
    await session_manager.register_session(
        resolved_session_id,
        handler,
        user_id=user_id,
    )
    try:
        await handler.handle_connection(
            websocket,
            resolved_session_id,
            token,
            trace_id=normalize_trace_id(trace_id),
        )
    finally:
        await session_manager.unregister_session(resolved_session_id)


async def _resolve_presentation_session_owner_id(session_id: str) -> str | None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.user_id).where(
                    PracticeSession.session_id == session_id
                )
            )
            owner_id = result.scalar_one_or_none()
            return str(owner_id) if owner_id else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve presentation session owner before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return None


async def _is_admin_user_id(user_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User.role).where(User.user_id == user_id))
            return str(result.scalar_one_or_none() or "").lower() == "admin"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve websocket user role before presentation access check",
            user_id=user_id,
            error=str(exc),
        )
        return False


@app.websocket("/ws/presentation")
async def presentation_websocket(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    token: str = Query(""),
    voice_mode: str | None = Query(
        None, description="Voice mode: legacy | stepfun_realtime"
    ),
    trace_id: str = Query("", description="Request trace id for observability"),
):
    """WebSocket endpoint for PPT presentation coaching (query session_id)."""
    await _handle_presentation_websocket(
        websocket,
        session_id,
        token,
        voice_mode,
        trace_id,
    )


@app.websocket("/ws/presentation/{session_id}")
async def presentation_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
    voice_mode: str | None = Query(
        None, description="Voice mode: legacy | stepfun_realtime"
    ),
    trace_id: str = Query("", description="Request trace id for observability"),
):
    """WebSocket endpoint for PPT presentation coaching (path session_id)."""
    await _handle_presentation_websocket(
        websocket,
        session_id,
        token,
        voice_mode,
        trace_id,
    )


def _normalize_requested_voice_mode(voice_mode: str | None) -> str | None:
    mode = (voice_mode or "").strip().lower()
    if mode in {"legacy", "stepfun_realtime"}:
        return mode
    return None


def _default_voice_mode() -> str:
    default_mode = os.getenv("DEFAULT_VOICE_MODE", "legacy").strip().lower()
    if default_mode not in {"legacy", "stepfun_realtime"}:
        default_mode = "legacy"
    return default_mode


async def _resolve_presentation_runtime(
    session_id: str,
) -> tuple[str | None, str]:
    default_mode = _default_voice_mode()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    Scenario.scenario_type,
                    PracticeSession.voice_mode,
                )
                .join(
                    Scenario,
                    Scenario.scenario_id == PracticeSession.scenario_id,
                    isouter=True,
                )
                .where(PracticeSession.session_id == session_id)
            )
            row = result.first()
            if row:
                scenario_type, resolved_mode = row
                mode = str(resolved_mode or "").strip().lower()
                if mode not in {"legacy", "stepfun_realtime"}:
                    mode = default_mode
                return str(scenario_type or "").lower() or None, mode
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            f"Failed to resolve presentation runtime for {session_id}: {exc}"
        )
    return None, default_mode


async def _is_presentation_kb_lock_unbound_session(session_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.voice_policy_snapshot).where(
                    PracticeSession.session_id == session_id
                )
            )
            snapshot = result.scalar_one_or_none()
            return is_kb_lock_unbound_snapshot(snapshot)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            "Failed to evaluate presentation KB lock binding before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return False


app.include_router(sales_ws_router, tags=["sales-websocket"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=3444, reload=True, log_level="info")
