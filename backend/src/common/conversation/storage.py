"""
Message Storage Service

Service for persisting conversation messages with analysis data.
Implements save_message(), update_analysis(), and mark_highlight() operations.

References:
- Requirements: R9 (Conversation message storage)
- Design: Section 11 (Message Storage Service)
- API Contract: docs/api-contract/replay.md
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.models import ConversationMessage
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

OBJECTION_LEDGER_TRANSCRIPT_KEY = "objection_ledger"
VALID_OBJECTION_LEDGER_CLOSURE_STATES = frozenset(
    {"open", "evidence_provided", "gap_acknowledged"}
)


def _set_orm_field(row: object, name: str, value: object) -> None:
    setattr(row, name, value)


def _orm_dict(row: object, name: str) -> dict[str, Any] | None:
    value = getattr(row, name, None)
    return value if isinstance(value, dict) else None


def normalize_objection_ledger(
    objection_ledger: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize the minimal unresolved-objection ledger into a stable dict."""
    if not isinstance(objection_ledger, dict):
        return None

    objection_family = str(objection_ledger.get("objection_family") or "").strip()
    if not objection_family:
        return None

    closure_state = str(objection_ledger.get("closure_state") or "open").strip().lower()
    if closure_state not in VALID_OBJECTION_LEDGER_CLOSURE_STATES:
        closure_state = "open"

    normalized: dict[str, Any] = {
        "objection_family": objection_family,
        "closure_state": closure_state,
    }

    promised_proof = str(objection_ledger.get("promised_proof") or "").strip()
    if promised_proof:
        normalized["promised_proof"] = promised_proof

    next_expected_evidence = str(
        objection_ledger.get("next_expected_evidence") or ""
    ).strip()
    if next_expected_evidence:
        normalized["next_expected_evidence"] = next_expected_evidence

    return normalized


def _merge_transcript_metadata(
    transcript_metadata: dict[str, Any] | None,
    objection_ledger: dict[str, Any] | None,
) -> dict[str, Any] | None:
    metadata = (
        dict(transcript_metadata) if isinstance(transcript_metadata, dict) else {}
    )
    normalized_ledger = normalize_objection_ledger(objection_ledger)
    if normalized_ledger is not None:
        metadata[OBJECTION_LEDGER_TRANSCRIPT_KEY] = normalized_ledger
    return metadata or None


class MessageStorageService:
    """
    Message Storage Service - Persists conversation messages with analysis data.

    Implements:
    - save_message(): Save a new message to the database
    - update_analysis(): Update analysis data (fuzzy words, stage, score)
    - mark_highlight(): Mark a message as a key moment

    Requirements: R9
    Design: Section 11
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize MessageStorageService.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    async def save_message(
        self,
        session_id: str,
        turn_number: int,
        role: str,
        content: str,
        audio_url: str | None = None,
        duration_ms: int | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> Result[ConversationMessage]:
        """
        Save a conversation message to the database.

        Args:
            session_id: Practice session UUID
            turn_number: Turn number in the conversation
            role: Message role ('user' or 'assistant')
            content: Message text content
            audio_url: Optional audio file URL
            duration_ms: Optional audio duration in milliseconds
            analysis_data: Optional analysis data dict with keys:
                - fuzzy_words: list[dict] - Detected fuzzy words
                - sales_stage: str - Current sales stage
                - score_snapshot: dict - Score at this turn

        Returns:
            Result[ConversationMessage]: Success with saved message or failure

        Requirements: R9.1, R9.2, R9.3
        """
        try:
            # Validate role
            if role not in ("user", "assistant"):
                return Result.fail(
                    f"[INVALID_ROLE] Role must be 'user' or 'assistant', got '{role}'"
                )

            # Create message
            message = ConversationMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                turn_number=turn_number,
                role=role,
                content=content,
                audio_url=audio_url,
                duration_ms=duration_ms,
                timestamp=datetime.now(UTC),
            )

            # Apply analysis data if provided
            if analysis_data:
                if "fuzzy_words" in analysis_data:
                    _set_orm_field(message, "fuzzy_words", analysis_data["fuzzy_words"])

                transcript_metadata = (
                    analysis_data.get("transcript_metadata")
                    if isinstance(analysis_data.get("transcript_metadata"), dict)
                    else None
                )
                if (
                    transcript_metadata is not None
                    or "objection_ledger" in analysis_data
                ):
                    _set_orm_field(
                        message,
                        "transcript_metadata",
                        _merge_transcript_metadata(
                            transcript_metadata,
                            analysis_data.get("objection_ledger"),
                        ),
                    )

                if "sales_stage" in analysis_data:
                    _set_orm_field(message, "sales_stage", analysis_data["sales_stage"])
                if "score_snapshot" in analysis_data:
                    _set_orm_field(
                        message, "score_snapshot", analysis_data["score_snapshot"]
                    )
                if "ai_feedback" in analysis_data:
                    _set_orm_field(message, "ai_feedback", analysis_data["ai_feedback"])

            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)

            logger.info(
                f"Saved message: session={session_id}, turn={turn_number}, "
                f"role={role}, id={message.id}"
            )

            return Result.ok(message)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to save message: {str(e)}")
            return Result.fail(f"[MESSAGE_SAVE_FAILED] {str(e)}")

    async def update_analysis(
        self,
        message_id: str,
        fuzzy_words: list[dict] | None = None,
        transcript_metadata: dict[str, Any] | None = None,
        sales_stage: str | None = None,
        score_snapshot: dict | None = None,
        ai_feedback: str | None = None,
        objection_ledger: dict[str, Any] | None = None,
    ) -> Result[ConversationMessage]:
        """
        Update analysis data for an existing message.

        Args:
            message_id: Message UUID
            fuzzy_words: Optional list of fuzzy word detections
            transcript_metadata: Optional transcript metadata dict
            sales_stage: Optional sales stage identifier
            score_snapshot: Optional score snapshot dict
            ai_feedback: Optional AI feedback text
            objection_ledger: Optional unresolved-objection ledger persisted under transcript metadata

        Returns:
            Result[ConversationMessage]: Success with updated message or failure

        Requirements: R9.3
        """
        try:
            # Find message
            stmt = select(ConversationMessage).where(
                ConversationMessage.id == message_id
            )
            result = await self.db.execute(stmt)
            message = result.scalar_one_or_none()

            if not message:
                return Result.fail(
                    f"[MESSAGE_NOT_FOUND] Message with id '{message_id}' not found"
                )

            # Update fields if provided
            if fuzzy_words is not None:
                _set_orm_field(message, "fuzzy_words", fuzzy_words)
            if transcript_metadata is not None or objection_ledger is not None:
                _set_orm_field(
                    message,
                    "transcript_metadata",
                    _merge_transcript_metadata(
                        transcript_metadata
                        if transcript_metadata is not None
                        else _orm_dict(message, "transcript_metadata"),
                        objection_ledger,
                    ),
                )
            if sales_stage is not None:
                # Validate sales stage
                valid_stages = {
                    "opening",
                    "discovery",
                    "presentation",
                    "objection",
                    "closing",
                }
                if sales_stage not in valid_stages:
                    return Result.fail(
                        f"[INVALID_SALES_STAGE] Invalid sales stage: {sales_stage}"
                    )
                _set_orm_field(message, "sales_stage", sales_stage)
            if score_snapshot is not None:
                _set_orm_field(message, "score_snapshot", score_snapshot)
            if ai_feedback is not None:
                _set_orm_field(message, "ai_feedback", ai_feedback)

            await self.db.commit()
            await self.db.refresh(message)

            logger.info(f"Updated analysis for message: {message_id}")

            return Result.ok(message)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update analysis: {str(e)}")
            return Result.fail(f"[ANALYSIS_UPDATE_FAILED] {str(e)}")

    async def mark_highlight(
        self, message_id: str, highlight_type: str, highlight_reason: str
    ) -> Result[ConversationMessage]:
        """
        Mark a message as a key moment (highlight).

        Args:
            message_id: Message UUID
            highlight_type: Type of highlight ('good', 'bad', or 'neutral')
            highlight_reason: Reason for the highlight (max 200 chars)

        Returns:
            Result[ConversationMessage]: Success with updated message or failure

        Requirements: R9.4
        """
        try:
            # Validate highlight type
            valid_types = {"good", "bad", "neutral"}
            if highlight_type not in valid_types:
                return Result.fail(
                    f"[INVALID_HIGHLIGHT_TYPE] Highlight type must be one of {valid_types}, got '{highlight_type}'"
                )

            # Validate reason length
            if len(highlight_reason) > 200:
                return Result.fail(
                    "[HIGHLIGHT_REASON_TOO_LONG] Highlight reason must be 200 characters or less"
                )

            # Find message
            stmt = select(ConversationMessage).where(
                ConversationMessage.id == message_id
            )
            result = await self.db.execute(stmt)
            message = result.scalar_one_or_none()

            if not message:
                return Result.fail(
                    f"[MESSAGE_NOT_FOUND] Message with id '{message_id}' not found"
                )

            # Update highlight fields
            _set_orm_field(message, "is_highlight", True)
            _set_orm_field(message, "highlight_type", highlight_type)
            _set_orm_field(message, "highlight_reason", highlight_reason)

            await self.db.commit()
            await self.db.refresh(message)

            logger.info(
                f"Marked highlight: message={message_id}, "
                f"type={highlight_type}, reason={highlight_reason[:50]}..."
            )

            return Result.ok(message)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to mark highlight: {str(e)}")
            return Result.fail(f"[HIGHLIGHT_MARK_FAILED] {str(e)}")

    async def get_message_by_id(self, message_id: str) -> Result[ConversationMessage]:
        """
        Get a message by its ID.

        Args:
            message_id: Message UUID

        Returns:
            Result[ConversationMessage]: Success with message or failure
        """
        try:
            stmt = select(ConversationMessage).where(
                ConversationMessage.id == message_id
            )
            result = await self.db.execute(stmt)
            message = result.scalar_one_or_none()

            if not message:
                return Result.fail(
                    f"[MESSAGE_NOT_FOUND] Message with id '{message_id}' not found"
                )

            return Result.ok(message)

        except Exception as e:
            logger.error(f"Failed to get message: {str(e)}")
            return Result.fail(f"[MESSAGE_GET_FAILED] {str(e)}")

    async def get_messages_by_session(
        self, session_id: str, page: int = 1, page_size: int = 50
    ) -> Result[tuple[list[ConversationMessage], int]]:
        """
        Get messages for a session with pagination.

        Args:
            session_id: Practice session UUID
            page: Page number (1-indexed)
            page_size: Number of messages per page

        Returns:
            Result[tuple[list[ConversationMessage], int]]: Success with (messages, total) or failure
        """
        try:
            # 参数边界校验
            page = max(1, page)
            page_size = max(1, min(page_size, 100))

            # Count total
            from sqlalchemy import func

            count_stmt = (
                select(func.count())
                .select_from(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
            )
            total_result = await self.db.execute(count_stmt)
            total = total_result.scalar() or 0

            # Get paginated messages
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.turn_number)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await self.db.execute(stmt)
            messages = list(result.scalars().all())

            return Result.ok((messages, total))

        except Exception as e:
            logger.error(f"Failed to get messages: {str(e)}")
            return Result.fail(f"[MESSAGES_GET_FAILED] {str(e)}")
