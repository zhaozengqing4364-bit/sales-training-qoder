"""
Conversation Replay API

API endpoints for retrieving conversation replay data, messages, and highlights.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.conversation.replay import ReplayService
from common.conversation.schemas import (
    ConversationErrorResponse,
    ConversationMessagesSuccessResponse,
    ConversationMessageSuccessResponse,
    HighlightsSuccessResponse,
    ReplayDataSuccessResponse,
)
from common.db.models import PracticeSession, SessionAudioSegment, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["replay"])


async def _ensure_session_access(
    session_id: str,
    current_user: User,
    db: AsyncSession,
) -> JSONResponse | None:
    """Ensure caller can access the target session replay data."""
    if str(getattr(current_user, "role", "user")).lower() == "admin":
        return None

    result = await db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    # Keep existing not-found semantics in downstream service.
    if session is None:
        return None

    if str(session.user_id) != str(current_user.user_id):
        return _error_response(403, "[ACCESS_DENIED]", "Access denied")
    return None





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
    current_user: User = Depends(get_current_user),
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
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

    service = ReplayService(db)
    result = await service.get_messages(session_id, page, page_size)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    messages, total = result.value

    return _success_response(
        {
            "messages": [_message_to_response(m, index + 1) for index, m in enumerate(messages)],
            "total": total,
        }
    )


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
    current_user: User = Depends(get_current_user),
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
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

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

    return _success_response(_message_to_detail_response(message, service))


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
    current_user: User = Depends(get_current_user),
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
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

    service = ReplayService(db)
    result = await service.get_replay_data(session_id)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    return _success_response(result.value)


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get highlighted messages (key moments) from a session.

    Story 3.4: 高光片段与原因可解释呈现

    Returns messages marked as highlights with:
    - Highlight type (good/bad) classification
    - Reason annotations
    - Sales stage association
    - Message context (prev/next)
    - Suggested improvements for bad highlights

    Requires the session to be completed.

    - **session_id**: Practice session UUID

    Returns:
    - highlights: List of highlight messages
    - total_good: Count of good highlights
    - total_bad: Count of bad highlights

    Requirements: R10.3
    """
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

    service = ReplayService(db)
    result = await service.get_highlights(session_id)

    if not result.is_success:
        error_code = _extract_error_code(result.fallback)
        status_code = _get_status_code(error_code)
        return _error_response(status_code, error_code, result.fallback)

    data = result.value
    return _success_response({
        "highlights": data["highlights"],
        "total_good": data["total_good"],
        "total_bad": data["total_bad"],
    })


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
    current_user: User = Depends(get_current_user),
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
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

    service = ReplayService(db)

    # Check session is completed
    session_result = await service._check_session_completed(session_id)
    if not session_result.is_success:
        error_code = _extract_error_code(session_result.fallback)
        return _error_response(
            _get_status_code(error_code),
            error_code,
            session_result.fallback,
        )

    # Get message
    from common.conversation.storage import MessageStorageService
    storage = MessageStorageService(db)
    message_result = await storage.get_message_by_id(message_id)

    if not message_result.is_success:
        return _error_response(404, "[MESSAGE_NOT_FOUND]", "Message not found")

    message = message_result.value

    # Verify message belongs to session
    if message.session_id != session_id:
        return _error_response(404, "[MESSAGE_NOT_FOUND]", "Message not found in this session")

    # Check audio URL exists
    if not message.audio_url:
        return _error_response(404, "[AUDIO_NOT_AVAILABLE]", "Audio not available for this message")

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

    return _error_response(404, "[AUDIO_NOT_AVAILABLE]", "Audio file not found")


@router.get(
    "/{session_id}/audio-segments/{segment_sequence}",
    responses={
        302: {"description": "Redirect to signed audio URL"},
        404: {"model": ConversationErrorResponse, "description": "Segment not found or not uploaded"},
    },
)
async def get_audio_segment_playback(
    session_id: str,
    segment_sequence: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a short-lived signed GET redirect for an uploaded audio segment.

    Validates session ownership and segment upload state before signing.
    """
    access_error = await _ensure_session_access(session_id, current_user, db)
    if access_error:
        return access_error

    seg_result = await db.execute(
        select(SessionAudioSegment).where(
            SessionAudioSegment.session_id == session_id,
            SessionAudioSegment.segment_sequence == segment_sequence,
        )
    )
    segment = seg_result.scalar_one_or_none()

    if segment is None:
        return _error_response(
            404, "[SEGMENT_NOT_FOUND]",
            f"Audio segment {segment_sequence} not found for session {session_id}",
        )

    if segment.upload_status != "uploaded":
        return _error_response(
            404, "[SEGMENT_NOT_UPLOADED]",
            f"Audio segment {segment_sequence} has status '{segment.upload_status}', expected 'uploaded'",
        )

    try:
        from common.oss.signing import get_oss_signing_service
        signing = get_oss_signing_service()
        signed_url = signing.generate_get_url(segment.object_key, expires=3600)
    except Exception as exc:
        logger.error(
            "audio_segment_signing_failed",
            session_id=session_id,
            segment_sequence=segment_sequence,
            error=str(exc),
        )
        return _error_response(
            500, "[SIGNING_FAILED]",
            "Failed to generate audio playback URL",
        )

    return RedirectResponse(url=signed_url)


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


def _success_response(data: dict) -> dict[str, object]:
    return {
        "success": True,
        "data": data,
        "trace_id": get_trace_id(),
    }


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Create unified error response with top-level fields."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_code,
            "error_code": error_code,
            "message": message,
            "trace_id": get_trace_id(),
        },
    )


def _normalize_turn_number(raw_turn_number: int | None, fallback_turn_number: int = 1) -> int:
    """Normalize legacy turn numbers to satisfy response contract (>=1)."""
    if isinstance(raw_turn_number, int) and raw_turn_number >= 1:
        return raw_turn_number
    return max(1, fallback_turn_number)


def _message_to_response(message, fallback_turn_number: int = 1) -> dict:
    """Convert message model to response dict"""
    return {
        "id": message.id,
        "session_id": message.session_id,
        "turn_number": _normalize_turn_number(message.turn_number, fallback_turn_number),
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
