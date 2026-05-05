"""
v1-8: Message Persistence — Extracted from EnhancedSalesHandler.

Handles all database operations for conversation message storage:
- Save user/assistant messages
- Update analysis data on messages
"""

import asyncio
from typing import cast

from common.conversation.storage import MessageStorageService
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from sales_bot.websocket.components.stepfun_message_helpers import (
    extract_analysis_patch_fields,
)

logger = get_logger(__name__)


class MessagePersistence:
    """
    Manages conversation message storage with short-lived DB sessions (NEW-5 fix).

    All operations create their own AsyncSession and commit within,
    avoiding long-lived DB connections during WebSocket sessions.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def save_message(
        self,
        turn_number: int,
        role: str,
        content: str,
        db_lock: asyncio.Lock,
    ) -> str | None:
        """
        Save a conversation message to the database.

        Args:
            turn_number: Current turn number
            role: Message role ('user' or 'assistant')
            content: Message text content
            db_lock: Lock to serialize DB access

        Returns:
            Message ID if saved successfully, None otherwise.
        """
        async with db_lock:
            try:
                async with AsyncSessionLocal() as db:
                    storage = MessageStorageService(db)
                    save_result = await storage.save_message(
                        session_id=self.session_id,
                        turn_number=turn_number,
                        role=role,
                        content=content,
                    )
                    if save_result.is_success and save_result.value is not None:
                        return cast(str, save_result.value.id)
                    logger.warning(
                        "Failed to persist message",
                        extra={
                            "session_id": self.session_id,
                            "turn_number": turn_number,
                            "role": role,
                        },
                    )
            except (OSError, RuntimeError, ValueError) as e:
                logger.error(f"Failed to save {role} message: {e}")
        return None

    async def update_analysis(
        self,
        message_id: str,
        analysis_data: dict,
        db_lock: asyncio.Lock,
    ) -> None:
        """
        Update analysis data on an existing message.

        Args:
            message_id: ID of the message to update
            analysis_data: Analysis data dict (fuzzy_words, sales_stage, score_snapshot, etc.)
            db_lock: Lock to serialize DB access
        """
        if not analysis_data:
            return

        normalized_analysis = {
            key: value
            for key, value in extract_analysis_patch_fields(analysis_data).items()
            if value is not None
        }
        if not normalized_analysis:
            return

        async with db_lock:
            try:
                async with AsyncSessionLocal() as db:
                    storage = MessageStorageService(db)
                    await storage.update_analysis(message_id, **normalized_analysis)
            except (OSError, RuntimeError, ValueError) as e:
                logger.error(f"Failed to update analysis data: {e}")
