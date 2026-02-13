"""
FastAPI Main Application
Entry point for the AI Practice System backend
"""
import os
import sys
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from admin.api.admin import router as admin_presentations_router
from admin.api.model_configs import router as model_configs_router
from admin.api.system_logs import router as admin_system_logs_router
from admin.api.training_records import router as admin_training_records_router
from admin.api.analytics import router as admin_analytics_router
from admin.api.voice_runtime import router as voice_runtime_router
from admin.api.release_verification import router as release_verification_router

# Admin API (users, training records, system logs)
from admin.api.users import router as admin_users_router
from agent.api.agent_personas import admin_router as agent_persona_admin_router

# Agent Platform API
from agent.api.agents import admin_router as agent_admin_router
from agent.api.agents import user_router as agent_user_router
from agent.api.personas import admin_router as persona_admin_router
from common.api import analytics, dashboard, practice, training, users
from common.auth.api import router as auth_router
from common.auth.api import get_auth_config_diagnostics

# Development mode auth (for testing without WeChat SSO)
from common.auth.service import (
    create_access_token,
    get_current_admin_user,
    get_dev_user,
    require_role,
)

# Conversation Replay API
from common.conversation.api import router as replay_router
from common.db.models import PracticeSession, Scenario
from common.db.session import AsyncSessionLocal, get_db, init_db
from common.error_handling.middleware import (
    ErrorHandlerMiddleware,
    global_exception_handler,
    http_exception_handler,
)

# Knowledge API
from common.knowledge.api import admin_router as knowledge_admin_router
from common.knowledge.api import internal_router as knowledge_internal_router
from common.monitoring.logger import configure_logging, get_logger
from presentation_coach.api import presentations

# Prompt Templates API
from prompt_templates.api.routes import router as prompt_templates_router
from prompt_templates.api.routes import scenario_router as scenario_prompts_router
from support.api.runtime_status import router as support_runtime_router

# Evaluation API
from evaluation.api import router as evaluation_router
from sales_bot.api.scenarios import router as scenarios_router
from sales_bot.websocket.router import router as sales_ws_router

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI Practice System backend")

    # P0-1: Validate JWT secret in non-development environments
    from common.config import settings
    from common.auth.service import JWT_SECRET
    env = settings.ENVIRONMENT
    if env != "development" and (not settings.SECRET_KEY or settings.SECRET_KEY == ""):
        raise RuntimeError("SECRET_KEY must be set in production via environment variable")
    if env != "development" and JWT_SECRET == "your-super-secret-key-change-in-production-min-32-chars":
        raise RuntimeError("JWT_SECRET must be set in production via environment variable")

    await init_db()

    auth_config = get_auth_config_diagnostics()
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
    from common.websocket.session_manager import init_session_manager, shutdown_session_manager
    await init_session_manager()

    yield

    # Shutdown
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
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3445,http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware (Constitution Principle I)
app.add_middleware(ErrorHandlerMiddleware)

# Add global exception handler
app.exception_handler(HTTPException)(http_exception_handler)
app.exception_handler(Exception)(global_exception_handler)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from datetime import UTC, datetime
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0"
    }


# Development login endpoint (for testing without WeChat SSO)
@app.post("/api/v1/auth/dev-login")
async def dev_login(db: AsyncSession = Depends(get_db)):
    """
    Development mode login - creates a mock user and returns a JWT token
    Only active when ENVIRONMENT=development
    """
    if os.getenv("ENVIRONMENT") != "development":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Development mode only")

    # Get or create dev user
    user = await get_dev_user(db)

    # Create JWT token
    token = create_access_token(data={"sub": str(user.user_id)})

    return {
        "success": True,
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": str(user.user_id),
                "email": user.email,
                "name": user.name
            }
        }
    }


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
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(users.router, prefix="/api/v1", tags=["users"])

# Auth API routes
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])

# Agent Platform API routes
app.include_router(agent_admin_router, prefix="/api/v1", tags=["admin-agents"])
app.include_router(agent_user_router, prefix="/api/v1", tags=["agents"])
app.include_router(persona_admin_router, prefix="/api/v1", tags=["admin-personas"])
app.include_router(agent_persona_admin_router, prefix="/api/v1", tags=["admin-agent-personas"])

# Knowledge API routes
app.include_router(
    knowledge_admin_router,
    prefix="/api/v1",
    tags=["admin-knowledge"],
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(knowledge_internal_router, prefix="/api/v1", tags=["internal-knowledge"])

# v1-18 Fix: Knowledge API alias via automatic route mirroring
# Provides /admin/knowledge-bases path compatibility for frontend
knowledge_bases_alias_router = APIRouter(prefix="/admin/knowledge-bases", tags=["admin-knowledge-bases"])

# Mirror all routes from the source knowledge router automatically
for route in knowledge_admin_router.routes:
    if hasattr(route, "endpoint") and hasattr(route, "methods"):
        # Remap path: /admin/knowledge/* -> /*
        alias_path = getattr(route, "path", "")
        if alias_path.startswith("/admin/knowledge"):
            alias_path = alias_path.replace("/admin/knowledge", "", 1)
        knowledge_bases_alias_router.add_api_route(
            alias_path,
            route.endpoint,
            methods=route.methods,
            status_code=getattr(route, "status_code", None),
        )

app.include_router(
    knowledge_bases_alias_router,
    prefix="/api/v1",
    tags=["admin-knowledge-bases"],
    dependencies=[Depends(get_current_admin_user)],
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
    dependencies=[Depends(get_current_admin_user)],
)
app.include_router(
    admin_system_logs_router,
    prefix="/api/v1",
    tags=["admin-system-logs"],
    dependencies=[Depends(get_current_admin_user)],
)

# Support runtime status API routes (read-only)
app.include_router(
    support_runtime_router,
    prefix="/api/v1",
    tags=["support-runtime"],
    dependencies=[Depends(require_role(["admin", "support"]))],
)

# Model Config API routes
app.include_router(model_configs_router, prefix="/api/v1/admin", tags=["admin-model-configs"])
app.include_router(voice_runtime_router, prefix="/api/v1/admin", tags=["admin-voice-runtime"])

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


async def _reject_invalid_presentation_session(websocket: WebSocket, session_id: str | None):
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
):
    from presentation_coach.websocket.presentation_handler import (
        PresentationWebSocketHandler,
    )

    resolved_session_id = _parse_session_id(session_id)
    if not resolved_session_id:
        await _reject_invalid_presentation_session(websocket, session_id)
        return

    scenario_type = await _resolve_session_scenario_type(resolved_session_id)
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

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    handler = PresentationWebSocketHandler()
    await handler.handle_connection(websocket, resolved_session_id, token)


@app.websocket("/ws/presentation")
async def presentation_websocket(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    token: str = Query(""),
):
    """WebSocket endpoint for PPT presentation coaching (query session_id)."""
    await _handle_presentation_websocket(websocket, session_id, token)


@app.websocket("/ws/presentation/{session_id}")
async def presentation_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
):
    """WebSocket endpoint for PPT presentation coaching (path session_id)."""
    await _handle_presentation_websocket(websocket, session_id, token)


async def _resolve_session_scenario_type(session_id: str) -> str | None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Scenario.scenario_type)
                .join(
                    PracticeSession,
                    PracticeSession.scenario_id == Scenario.scenario_id,
                )
                .where(PracticeSession.session_id == session_id)
            )
            scenario_type = result.scalar_one_or_none()
            if scenario_type:
                return str(scenario_type).lower()
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            f"Failed to resolve session scenario type for {session_id}: {exc}"
        )
    return None


app.include_router(sales_ws_router, tags=["sales-websocket"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3444,
        reload=True,
        log_level="info"
    )
