"""
FastAPI Main Application
Entry point for the AI Practice System backend
"""
import os
import sys
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from admin.api import admin
from admin.api.model_configs import router as model_configs_router
from admin.api.system_logs import router as admin_system_logs_router
from admin.api.training_records import router as admin_training_records_router
from admin.api.analytics import router as admin_analytics_router

# Admin API (users, training records, system logs)
from admin.api.users import router as admin_users_router
from agent.api.agent_personas import admin_router as agent_persona_admin_router

# Agent Platform API
from agent.api.agents import admin_router as agent_admin_router
from agent.api.agents import user_router as agent_user_router
from agent.api.personas import admin_router as persona_admin_router
from common.api import analytics, dashboard, practice, training, users
from common.auth.api import router as auth_router

# Development mode auth (for testing without WeChat SSO)
from common.auth.service import create_access_token, get_dev_user

# Conversation Replay API
from common.conversation.api import router as replay_router
from common.db.session import get_db, init_db
from common.error_handling.middleware import (
    ErrorHandlerMiddleware,
    global_exception_handler,
)

# Knowledge API
from common.knowledge.api import admin_router as knowledge_admin_router
from common.monitoring.logger import configure_logging, get_logger
from presentation_coach.api import presentations

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI Practice System backend")
    await init_db()

    # Initialize ConfigManager for AI model configurations
    try:
        from common.ai.config_manager import initialize_config_manager
        await initialize_config_manager()
        logger.info("ConfigManager initialized")
    except Exception as e:
        logger.warning(f"ConfigManager initialization failed: {str(e)}")

    # Optional: Preload critical services
    from common.config import settings
    if settings.PRELOAD_SERVICES:
        logger.info("Preloading critical services (PRELOAD_SERVICES=true)")
        try:
            from common.audio.asr_service import get_asr_service
            get_asr_service()  # Trigger ASR initialization
            logger.info("Service preloading complete")
        except Exception as e:
            logger.warning(f"Service preloading failed: {str(e)}")

    yield

    # Shutdown
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
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware (Constitution Principle I)
app.add_middleware(ErrorHandlerMiddleware)

# Add global exception handler
app.exception_handler(Exception)(global_exception_handler)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
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
app.include_router(presentations.router, prefix="/api/v1", tags=["presentations"])
app.include_router(practice.router, prefix="/api/v1", tags=["practice"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(training.router, prefix="/api/v1", tags=["training"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])

# Auth API routes
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])

# Agent Platform API routes
app.include_router(agent_admin_router, prefix="/api/v1", tags=["admin-agents"])
app.include_router(agent_user_router, prefix="/api/v1", tags=["agents"])
app.include_router(persona_admin_router, prefix="/api/v1", tags=["admin-personas"])
app.include_router(agent_persona_admin_router, prefix="/api/v1", tags=["admin-agent-personas"])

# Knowledge API routes
app.include_router(knowledge_admin_router, prefix="/api/v1", tags=["admin-knowledge"])

# Knowledge API alias: Create a separate router for /admin/knowledge-bases path
# This provides path compatibility for frontend expecting /admin/knowledge-bases
from fastapi import APIRouter

knowledge_bases_alias_router = APIRouter(prefix="/admin/knowledge-bases", tags=["admin-knowledge-bases"])

# Re-export all knowledge endpoints under the alias path
from common.knowledge.api import (
    create_knowledge_base,
    delete_document,
    delete_knowledge_base,
    get_document,
    get_knowledge_base,
    list_documents,
    list_knowledge_bases,
    preview_document,
    update_knowledge_base,
    upload_document,
)

knowledge_bases_alias_router.add_api_route("", create_knowledge_base, methods=["POST"], status_code=201)
knowledge_bases_alias_router.add_api_route("", list_knowledge_bases, methods=["GET"])
knowledge_bases_alias_router.add_api_route("/{kb_id}", get_knowledge_base, methods=["GET"])
knowledge_bases_alias_router.add_api_route("/{kb_id}", update_knowledge_base, methods=["PUT"])
knowledge_bases_alias_router.add_api_route("/{kb_id}", delete_knowledge_base, methods=["DELETE"])
knowledge_bases_alias_router.add_api_route("/{kb_id}/documents", upload_document, methods=["POST"], status_code=202)
knowledge_bases_alias_router.add_api_route("/{kb_id}/documents", list_documents, methods=["GET"])
knowledge_bases_alias_router.add_api_route("/{kb_id}/documents/{doc_id}", get_document, methods=["GET"])
knowledge_bases_alias_router.add_api_route("/{kb_id}/documents/{doc_id}", delete_document, methods=["DELETE"])
knowledge_bases_alias_router.add_api_route("/{kb_id}/documents/{doc_id}/preview", preview_document, methods=["GET"])

app.include_router(knowledge_bases_alias_router, prefix="/api/v1", tags=["admin-knowledge-bases"])

# Conversation Replay API routes
app.include_router(replay_router, prefix="/api/v1", tags=["replay"])

# Admin API routes (users, training records, system logs)
app.include_router(admin_users_router, prefix="/api/v1", tags=["admin-users"])
app.include_router(admin_training_records_router, prefix="/api/v1", tags=["admin-training-records"])
app.include_router(admin_analytics_router, prefix="/api/v1", tags=["admin-analytics"])
app.include_router(admin_system_logs_router, prefix="/api/v1", tags=["admin-system-logs"])

# Model Config API routes
app.include_router(model_configs_router, prefix="/api/v1/admin", tags=["admin-model-configs"])


# WebSocket endpoint for PPT presentation coaching
@app.websocket("/ws/presentation")
async def presentation_websocket(
    websocket: WebSocket,
    session_id: str = Query(...),
    token: str = Query(...)
):
    """WebSocket endpoint for PPT presentation coaching"""
    from presentation_coach.websocket.presentation_handler import (
        PresentationWebSocketHandler,
    )

    handler = PresentationWebSocketHandler()
    await handler.handle_connection(websocket, session_id, token)


# Sales Bot WebSocket routes (uses router for enhanced mode support)
from sales_bot.websocket.router import router as sales_ws_router
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
