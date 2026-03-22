"""Helper utilities for StepFun message persistence flow."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from common.conversation.models import ConversationMessage
from common.conversation.storage import MessageStorageService
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def normalize_message_persistence_payload(
    *,
    turn_number: int,
    content: str,
    sales_stage: str | None,
    analysis_data: dict[str, Any] | None,
) -> tuple[int, str, dict[str, Any]] | None:
    """Normalize persistence input into stable `(turn, content, analysis)` tuple."""
    normalized_content = content.strip()
    if not normalized_content:
        return None

    normalized_turn = max(1, int(turn_number))
    analysis_payload = analysis_data.copy() if isinstance(analysis_data, dict) else {}
    if isinstance(sales_stage, str) and sales_stage:
        analysis_payload["sales_stage"] = sales_stage

    return normalized_turn, normalized_content, analysis_payload


def extract_analysis_patch_fields(
    analysis_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract typed patch fields from one analysis payload dict."""
    return {
        "sales_stage": (
            analysis_payload.get("sales_stage")
            if isinstance(analysis_payload.get("sales_stage"), str)
            and analysis_payload.get("sales_stage")
            else None
        ),
        "fuzzy_words": (
            analysis_payload.get("fuzzy_words")
            if isinstance(analysis_payload.get("fuzzy_words"), list)
            else None
        ),
        "score_snapshot": (
            analysis_payload.get("score_snapshot")
            if isinstance(analysis_payload.get("score_snapshot"), dict)
            else None
        ),
        "ai_feedback": (
            analysis_payload.get("ai_feedback")
            if isinstance(analysis_payload.get("ai_feedback"), str)
            else None
        ),
        "transcript_metadata": (
            analysis_payload.get("transcript_metadata")
            if isinstance(analysis_payload.get("transcript_metadata"), dict)
            else None
        ),
    }


async def patch_existing_message_analysis(
    *,
    session_id: str,
    turn_number: int,
    role: str,
    content: str,
    sales_stage: str | None,
    fuzzy_words: list[dict[str, Any]] | None,
    score_snapshot: dict[str, Any] | None,
    ai_feedback: str | None,
    transcript_metadata: dict[str, Any] | None,
    db_lock: asyncio.Lock,
) -> bool:
    """Patch analysis fields for an already persisted duplicate message."""
    async with db_lock:
        try:
            async with AsyncSessionLocal() as db:
                statement = (
                    select(ConversationMessage.id)
                    .where(ConversationMessage.session_id == session_id)
                    .where(ConversationMessage.turn_number == turn_number)
                    .where(ConversationMessage.role == role)
                    .where(ConversationMessage.content == content)
                    .order_by(ConversationMessage.timestamp.desc())
                    .limit(1)
                )
                result = await db.execute(statement)
                message_id = result.scalar_one_or_none()
                if not message_id:
                    return False

                storage = MessageStorageService(db)
                update_result = await storage.update_analysis(
                    message_id,
                    sales_stage=sales_stage,
                    fuzzy_words=fuzzy_words,
                    score_snapshot=score_snapshot,
                    ai_feedback=ai_feedback,
                    transcript_metadata=transcript_metadata,
                )
                if not update_result.is_success:
                    logger.warning(
                        "Failed to patch analysis on duplicate message",
                        session_id=session_id,
                        turn_number=turn_number,
                        role=role,
                        sales_stage=sales_stage,
                    )
                    return False

                return True
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(
                "Error patching analysis on duplicate message",
                session_id=session_id,
                turn_number=turn_number,
                role=role,
                sales_stage=sales_stage,
                error=str(exc),
            )
            return False


async def save_stepfun_message(
    *,
    session_id: str,
    turn_number: int,
    role: str,
    content: str,
    analysis_payload: dict[str, Any],
    db_lock: asyncio.Lock,
) -> bool:
    """Persist one StepFun conversation message into storage."""
    async with db_lock:
        try:
            async with AsyncSessionLocal() as db:
                storage = MessageStorageService(db)
                save_result = await storage.save_message(
                    session_id=session_id,
                    turn_number=turn_number,
                    role=role,
                    content=content,
                    analysis_data=analysis_payload or None,
                )
                if not save_result.is_success:
                    logger.warning(
                        "Failed to persist StepFun realtime message",
                        session_id=session_id,
                        turn_number=turn_number,
                        role=role,
                    )
                    return False

                return True
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(
                "Error persisting StepFun realtime message",
                session_id=session_id,
                turn_number=turn_number,
                role=role,
                error=str(exc),
            )
            return False
