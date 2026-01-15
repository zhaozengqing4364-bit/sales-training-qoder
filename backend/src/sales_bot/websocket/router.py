"""
Sales Bot WebSocket Router

Routes WebSocket connections to appropriate handlers based on parameters.
Supports both SimpleSalesHandler (backward compatible) and EnhancedSalesHandler
(with Agent Platform integration).

References:
- Requirements: R11 (WebSocket Enhancement)
- Design: Section 20 (WebSocket Router)
- API Contract: docs/api-contract/websocket.md
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import get_db
from common.monitoring.logger import get_logger

from .enhanced_handler import EnhancedSalesHandler, create_enhanced_sales_handler
from .simple_handler import SimpleSalesHandler, create_sales_handler

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/sales")
async def sales_websocket(
    websocket: WebSocket,
    session_id: str = Query(..., description="Practice session UUID"),
    token: str = Query("", description="JWT authentication token"),
    agent_id: Optional[str] = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: Optional[str] = Query(None, description="Persona UUID for enhanced mode"),
):
    """
    WebSocket endpoint for sales practice.

    Supports two modes:
    1. Simple mode (backward compatible): No agent_id/persona_id
       - Uses SimpleSalesHandler with hardcoded personas
       - For existing integrations

    2. Enhanced mode: With agent_id and persona_id
       - Uses EnhancedSalesHandler with Agent Platform integration
       - Supports capability modules (fuzzy detection, sales stage, scoring)
       - Stores messages for replay

    Query Parameters:
        session_id: Practice session UUID (path parameter)
        token: JWT authentication token
        agent_id: Optional Agent UUID for enhanced mode
        persona_id: Optional Persona UUID for enhanced mode

    WebSocket Messages:
        See docs/api-contract/websocket.md for message formats.
    """
    # Determine which handler to use
    use_enhanced = agent_id is not None and persona_id is not None

    if use_enhanced:
        await _handle_enhanced_connection(
            websocket=websocket,
            session_id=session_id,
            token=token,
            agent_id=agent_id,
            persona_id=persona_id,
        )
    else:
        await _handle_simple_connection(
            websocket=websocket,
            session_id=session_id,
            token=token,
        )


async def _handle_simple_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
):
    """Handle connection with SimpleSalesHandler (backward compatible)."""
    logger.info(
        f"Using SimpleSalesHandler for session {session_id}",
        session_id=session_id,
    )

    handler = create_sales_handler()

    # Default persona for backward compatibility
    handler.set_persona("impatient_ceo")

    # Try to link to existing bot session
    try:
        session_uuid = uuid.UUID(session_id)
        from sales_bot.services.bot_service import sales_bot_service

        if session_uuid in sales_bot_service.active_sessions:
            handler.set_bot_session(session_uuid)
    except (ValueError, KeyError):
        pass

    await handler.handle_connection(websocket, session_id, token)


async def _handle_enhanced_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
    agent_id: str,
    persona_id: str,
):
    """Handle connection with EnhancedSalesHandler (Agent Platform integration)."""
    logger.info(
        f"Using EnhancedSalesHandler for session {session_id}",
        session_id=session_id,
        agent_id=agent_id,
        persona_id=persona_id,
    )

    handler = create_enhanced_sales_handler()

    # Get database session for initialization
    # Note: We need to manage the session lifecycle carefully
    from common.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # Extract user_id from token (simplified - in production use proper JWT validation)
        user_id = _extract_user_id_from_token(token)

        # Initialize handler with Agent/Persona configuration
        init_success = await handler.initialize(
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
            user_id=user_id,
            db=db,
        )

        if not init_success:
            logger.error(
                f"Failed to initialize EnhancedSalesHandler",
                session_id=session_id,
                agent_id=agent_id,
                persona_id=persona_id,
            )
            # Fall back to simple handler
            await _handle_simple_connection(websocket, session_id, token)
            return

        # Handle the WebSocket connection
        await handler.handle_connection(websocket, session_id, token)


def _extract_user_id_from_token(token: str) -> str:
    """
    Extract user_id from JWT token.

    In production, this should properly validate and decode the JWT.
    For now, returns a default user_id for development.
    """
    try:
        from common.auth.service import verify_token

        payload = verify_token(token)
        if payload and "sub" in payload:
            return payload["sub"]
    except Exception as e:
        logger.warning(f"Failed to decode token: {e}")

    # Default for development
    return "dev-user-id"
