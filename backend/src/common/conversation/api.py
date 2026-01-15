"""
Conversation Replay API

API endpoints for retrieving conversation replay data, messages, and highlights.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.conversation.replay import ReplayService
from common.conversation.schemas import (
    ConversationMessagesSuccessResponse,
    ConversationMessageListResponse,
    ConversationMessageResponse,
    ConversationMessageDetailResponse,
    ConversationMessageSuccessResponse,
    ReplayDataSuccessResponse,
    ReplayDataResponse,
    HighlightsSuccessResponse,
    HighlightsResponse,
    HighlightResponse,
    ConversationErrorResponse,
)
from common.db.session import get_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["replay"])


@router.get(
    "/{session_id}/messages",
    response_model=ConversationMessagesSuccessResponse,
    responses={
        400: {"model": ConversationErrorResponse, "description": "Session not completed"},
        404: {"model": ConversationErrorResponse, "description": "Session not found"}
    }
)
async def get_messages(
    session_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated conversation messages for a session.

    Requires the session to be completed.

    - **session_id**: Practice session UUID
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)

    Returns paginated list of messages with analysis data.

    Requirements: R10.1
    """
    service = ReplayService(db)
    result = await service.get_messages(session_id, page, page_size)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    messages, total = result.value

    return {
        "success": True,
        "data": {
            "messages": [_message_to_response(m) for m in messages],
            "total": total
        },
        "trace_id": None
    }


@router.get(
    "/{session_id}/messages/{message_id}",
    response_model=ConversationMessageSuccessResponse,
    responses={
        400: {"model": ConversationErrorResponse, "description": "Session not completed"},
        404: {"model": ConversationErrorResponse, "description": "Message not found"}
    }
)
async def get_message_detail(
    session_id: str,
    message_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information for a single message.

    Requires the session to be completed.

    - **session_id**: Practice session UUID
    - **message_id**: Message UUID

    Returns message with full analysis data and suggested response.

    Requirements: R10.1
    """
    service = ReplayService(db)

    # First check session is completed
    session_result = await service._check_session_completed(session_id)
    if not session_result.is_success:
        error_code = _extract_error_code(session_result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, session_result.fallback)

    # Get message from storage service
    from common.conversation.storage import MessageStorageService
    storage = MessageStorageService(db)
    message_result = await storage.get_message_by_id(message_id)

    if not message_result.is_success:
        error_code = _extract_error_code(message_result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, message_result.fallback)

    message = message_result.value

    # Verify message belongs to session
    if message.session_id != session_id:
        return _error_response(404, "[MESSAGE_NOT_FOUND]", "Message not found in this session")

    return {
        "success": True,
        "data": _message_to_detail_response(message, service),
        "trace_id": None
    }


@router.get(
    "/{session_id}/replay",
    response_model=ReplayDataSuccessResponse,
    responses={
        400: {"model": ConversationErrorResponse, "description": "Session not completed"},
        404: {"model": ConversationErrorResponse, "description": "Session not found"}
    }
)
async def get_replay_data(
    session_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete replay data for a session.

    Includes all messages, timeline markers, and stage summary.
    Requires the session to be completed.

    - **session_id**: Practice session UUID

    Returns complete replay data for visualization.

    Requirements: R10.2
    """
    service = ReplayService(db)
    result = await service.get_replay_data(session_id)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    return {
        "success": True,
        "data": result.value,
        "trace_id": None
    }


@router.get(
    "/{session_id}/highlights",
    response_model=HighlightsSuccessResponse,
    responses={
        400: {"model": ConversationErrorResponse, "description": "Session not completed"},
        404: {"model": ConversationErrorResponse, "description": "Session not found"}
    }
)
async def get_highlights(
    session_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get highlighted messages (key moments) from a session.

    Returns only messages marked as highlights with suggested responses.
    Requires the session to be completed.

    - **session_id**: Practice session UUID

    Returns list of highlight messages.

    Requirements: R10.3
    """
    service = ReplayService(db)
    result = await service.get_highlights(session_id)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    return {
        "success": True,
        "data": {
            "highlights": result.value
        },
        "trace_id": None
    }


@router.get(
    "/{session_id}/audio/{message_id}",
    responses={
        200: {"description": "Audio file or redirect"},
        400: {"model": ConversationErrorResponse, "description": "Session not completed"},
        404: {"model": ConversationErrorResponse, "description": "Audio not found"}
    }
)
async def get_audio(
    session_id: str,
    message_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audio file for a message.

    Returns the audio file directly or redirects to storage URL.
    Requires the session to be completed.

    - **session_id**: Practice session UUID
    - **message_id**: Message UUID

    Returns audio file or redirect.

    Requirements: R10.4
    """
    service = ReplayService(db)

    # Check session is completed
    session_result = await service._check_session_completed(session_id)
    if not session_result.is_success:
        error_code = _extract_error_code(session_result.fallback)
        raise HTTPException(
            status_code=_get_status_code(error_code),
            detail={"error": error_code, "message": session_result.fallback}
        )

    # Get message
    from common.conversation.storage import MessageStorageService
    storage = MessageStorageService(db)
    message_result = await storage.get_message_by_id(message_id)

    if not message_result.is_success:
        raise HTTPException(
            status_code=404,
            detail={"error": "[MESSAGE_NOT_FOUND]", "message": "Message not found"}
        )

    message = message_result.value

    # Verify message belongs to session
    if message.session_id != session_id:
        raise HTTPException(
            status_code=404,
            detail={"error": "[MESSAGE_NOT_FOUND]", "message": "Message not found in this session"}
        )

    # Check audio URL exists
    if not message.audio_url:
        raise HTTPException(
            status_code=404,
            detail={"error": "[AUDIO_NOT_AVAILABLE]", "message": "Audio not available for this message"}
        )

    # If it's a remote URL, redirect
    if message.audio_url.startswith("http://") or message.audio_url.startswith("https://"):
        return RedirectResponse(url=message.audio_url)

    # If it's a local file, serve it
    if os.path.exists(message.audio_url):
        return FileResponse(
            message.audio_url,
            media_type="audio/mpeg",
            filename=f"message_{message_id}.mp3"
        )

    raise HTTPException(
        status_code=404,
        detail={"error": "[AUDIO_NOT_AVAILABLE]", "message": "Audio file not found"}
    )


# ========== Helper Functions ==========

def _extract_error_code(fallback: str) -> str:
    """Extract error code from fallback message"""
    if fallback and fallback.startswith("["):
        end = fallback.find("]")
        if end > 0:
            return fallback[:end + 1]
    return "[UNKNOWN_ERROR]"


def _get_status_code(error_code: str) -> int:
    """Map error code to HTTP status code"""
    status_map = {
        "[SESSION_NOT_FOUND]": 404,
        "[MESSAGE_NOT_FOUND]": 404,
        "[AUDIO_NOT_AVAILABLE]": 404,
        "[SESSION_NOT_COMPLETED]": 400,
    }
    return status_map.get(error_code, 500)


def _error_response(status_code: int, error_code: str, message: str):
    """Create error response - raises HTTPException"""
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": error_code,
            "error_code": error_code,
            "message": message,
            "trace_id": None
        }
    )


def _message_to_response(message) -> dict:
    """Convert message model to response dict"""
    return {
        "id": message.id,
        "session_id": message.session_id,
        "turn_number": message.turn_number,
        "role": message.role,
        "content": message.content,
        "audio_url": message.audio_url,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        "duration_ms": message.duration_ms,
        "fuzzy_words": message.fuzzy_words,
        "sales_stage": message.sales_stage,
        "score_snapshot": message.score_snapshot,
        "ai_feedback": message.ai_feedback,
        "is_highlight": message.is_highlight,
        "highlight_type": message.highlight_type,
        "highlight_reason": message.highlight_reason
    }


def _message_to_detail_response(message, service: ReplayService) -> dict:
    """Convert message model to detailed response dict with suggested response"""
    response = _message_to_response(message)
    response["suggested_response"] = service._generate_suggested_response(message)
    return response
