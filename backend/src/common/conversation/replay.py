"""
Replay Service

Service for retrieving conversation replay data with timeline markers.
Implements get_messages(), get_replay_data(), get_highlights(), and timeline generation.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.conversation.models import ConversationMessage
from common.db.models import PracticeSession, SessionStatus
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Sales stage display names
STAGE_NAMES = {
    "opening": "开场破冰",
    "discovery": "需求挖掘",
    "presentation": "方案呈现",
    "objection": "异议处理",
    "closing": "促成成交"
}


class ReplayService:
    """
    Replay Service - Retrieves conversation replay data with timeline markers.

    Implements:
    - get_messages(): Paginated message retrieval
    - get_replay_data(): Complete replay data with timeline markers
    - get_highlights(): Key moments from the conversation
    - _generate_timeline_markers(): Timeline marker generation

    Requirements: R10
    Design: Section 12
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize ReplayService.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    async def _get_session(self, session_id: str) -> Result[PracticeSession]:
        """
        Get a practice session by ID.

        Args:
            session_id: Practice session UUID

        Returns:
            Result[PracticeSession]: Success with session or failure
        """
        try:
            stmt = select(PracticeSession).where(
                PracticeSession.session_id == session_id
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                return Result.fail(f"[SESSION_NOT_FOUND] Session with id '{session_id}' not found")

            return Result.ok(session)

        except Exception as e:
            logger.error(f"Failed to get session: {str(e)}")
            return Result.fail(f"[SESSION_GET_FAILED] {str(e)}")

    async def _check_session_completed(self, session_id: str) -> Result[PracticeSession]:
        """
        Check if a session is completed (required for replay).

        Args:
            session_id: Practice session UUID

        Returns:
            Result[PracticeSession]: Success with session if completed, failure otherwise
        """
        session_result = await self._get_session(session_id)
        if not session_result.is_success:
            return session_result

        session = session_result.value
        if session.status != SessionStatus.COMPLETED.value:
            return Result.fail(
                f"[SESSION_NOT_COMPLETED] Session must be completed for replay. "
                f"Current status: {session.status}"
            )

        return Result.ok(session)

    async def get_messages(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> Result[tuple[list[ConversationMessage], int]]:
        """
        Get paginated messages for a completed session.

        Args:
            session_id: Practice session UUID
            page: Page number (1-indexed)
            page_size: Number of messages per page

        Returns:
            Result[tuple[list[ConversationMessage], int]]: Success with (messages, total) or failure

        Requirements: R10.1
        """
        try:
            # Check session is completed
            session_result = await self._check_session_completed(session_id)
            if not session_result.is_success:
                return session_result

            # Count total messages
            count_stmt = select(func.count()).select_from(ConversationMessage).where(
                ConversationMessage.session_id == session_id
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

            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")

            return Result.ok((messages, total))

        except Exception as e:
            logger.error(f"Failed to get messages: {str(e)}")
            return Result.fail(f"[MESSAGES_GET_FAILED] {str(e)}")

    async def get_replay_data(self, session_id: str) -> Result[dict[str, Any]]:
        """
        Get complete replay data including messages and timeline markers.

        Args:
            session_id: Practice session UUID

        Returns:
            Result[dict]: Success with replay data or failure

        Requirements: R10.2
        """
        try:
            # Check session is completed
            session_result = await self._check_session_completed(session_id)
            if not session_result.is_success:
                return session_result

            session = session_result.value

            # Get all messages (no pagination for replay)
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.turn_number)
            )
            result = await self.db.execute(stmt)
            messages = list(result.scalars().all())

            # Generate timeline markers
            timeline_markers = self._generate_timeline_markers(messages)

            # Generate stage summary
            stage_summary = self._generate_stage_summary(messages)

            # Calculate total duration
            total_duration_ms = self._calculate_total_duration(messages)

            # Get agent and persona names (if available)
            agent_name = None
            persona_name = None
            if session.agent_id:
                from agent.models import Agent
                agent_stmt = select(Agent).where(Agent.id == session.agent_id)
                agent_result = await self.db.execute(agent_stmt)
                agent = agent_result.scalar_one_or_none()
                if agent:
                    agent_name = agent.name

            if session.persona_id:
                from agent.models import Persona
                persona_stmt = select(Persona).where(Persona.id == session.persona_id)
                persona_result = await self.db.execute(persona_stmt)
                persona = persona_result.scalar_one_or_none()
                if persona:
                    persona_name = persona.name

            replay_data = {
                "session_id": session_id,
                "agent_name": agent_name,
                "persona_name": persona_name,
                "total_duration_ms": total_duration_ms,
                "messages": [self._message_to_dict(m) for m in messages],
                "timeline_markers": timeline_markers,
                "stage_summary": stage_summary
            }

            logger.info(f"Generated replay data for session {session_id}")

            return Result.ok(replay_data)

        except Exception as e:
            logger.error(f"Failed to get replay data: {str(e)}")
            return Result.fail(f"[REPLAY_DATA_FAILED] {str(e)}")

    async def get_highlights(self, session_id: str) -> Result[list[dict[str, Any]]]:
        """
        Get highlighted messages (key moments) from a session.

        Args:
            session_id: Practice session UUID

        Returns:
            Result[list[dict]]: Success with highlights or failure

        Requirements: R10.3
        """
        try:
            # Check session is completed
            session_result = await self._check_session_completed(session_id)
            if not session_result.is_success:
                return session_result

            # Get highlighted messages
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_id,
                    ConversationMessage.is_highlight == True
                )
                .order_by(ConversationMessage.turn_number)
            )
            result = await self.db.execute(stmt)
            messages = list(result.scalars().all())

            highlights = []
            for msg in messages:
                highlight = {
                    "id": msg.id,
                    "turn_number": msg.turn_number,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "highlight_type": msg.highlight_type,
                    "highlight_reason": msg.highlight_reason,
                    "ai_feedback": msg.ai_feedback,
                    "suggested_response": self._generate_suggested_response(msg)
                }
                highlights.append(highlight)

            logger.info(f"Retrieved {len(highlights)} highlights for session {session_id}")

            return Result.ok(highlights)

        except Exception as e:
            logger.error(f"Failed to get highlights: {str(e)}")
            return Result.fail(f"[HIGHLIGHTS_GET_FAILED] {str(e)}")

    def _generate_timeline_markers(
        self,
        messages: list[ConversationMessage]
    ) -> list[dict[str, Any]]:
        """
        Generate timeline markers from messages.

        Markers include:
        - Stage changes
        - Fuzzy word detections (high severity)
        - Highlights

        Args:
            messages: List of conversation messages

        Returns:
            list[dict]: Timeline markers
        """
        markers = []
        current_stage = None
        cumulative_ms = 0

        for msg in messages:
            # Stage change marker
            if msg.sales_stage and msg.sales_stage != current_stage:
                markers.append({
                    "timestamp_ms": cumulative_ms,
                    "type": "stage_change",
                    "label": STAGE_NAMES.get(msg.sales_stage, msg.sales_stage),
                    "message_id": msg.id,
                    "highlight_type": None
                })
                current_stage = msg.sales_stage

            # Fuzzy word markers (high severity only)
            if msg.fuzzy_words:
                for fw in msg.fuzzy_words:
                    if fw.get("severity") == "high":
                        matched_words = fw.get("matched", [])
                        markers.append({
                            "timestamp_ms": cumulative_ms,
                            "type": "fuzzy_word",
                            "label": f"模糊词: {', '.join(matched_words)}",
                            "message_id": msg.id,
                            "highlight_type": "bad"
                        })

            # Highlight markers
            if msg.is_highlight:
                markers.append({
                    "timestamp_ms": cumulative_ms,
                    "type": "highlight",
                    "label": msg.highlight_reason or "关键时刻",
                    "message_id": msg.id,
                    "highlight_type": msg.highlight_type
                })

            # Accumulate duration
            cumulative_ms += msg.duration_ms or 0

        return markers

    def _generate_stage_summary(
        self,
        messages: list[ConversationMessage]
    ) -> list[dict[str, Any]]:
        """
        Generate summary statistics for each sales stage.

        Args:
            messages: List of conversation messages

        Returns:
            list[dict]: Stage summaries with duration and average score
        """
        stage_data: dict[str, dict] = {}
        current_stage = None
        stage_start_ms = 0
        cumulative_ms = 0

        for msg in messages:
            # Track stage changes
            if msg.sales_stage and msg.sales_stage != current_stage:
                # Close previous stage
                if current_stage:
                    if current_stage not in stage_data:
                        stage_data[current_stage] = {"duration_ms": 0, "scores": []}
                    stage_data[current_stage]["duration_ms"] += cumulative_ms - stage_start_ms

                # Start new stage
                current_stage = msg.sales_stage
                stage_start_ms = cumulative_ms

            # Collect scores
            if current_stage and msg.score_snapshot:
                overall = msg.score_snapshot.get("overall")
                if overall is not None:
                    if current_stage not in stage_data:
                        stage_data[current_stage] = {"duration_ms": 0, "scores": []}
                    stage_data[current_stage]["scores"].append(overall)

            cumulative_ms += msg.duration_ms or 0

        # Close final stage
        if current_stage:
            if current_stage not in stage_data:
                stage_data[current_stage] = {"duration_ms": 0, "scores": []}
            stage_data[current_stage]["duration_ms"] += cumulative_ms - stage_start_ms

        # Build summary
        summary = []
        for stage_id in ["opening", "discovery", "presentation", "objection", "closing"]:
            if stage_id in stage_data:
                data = stage_data[stage_id]
                scores = data["scores"]
                avg_score = int(sum(scores) / len(scores)) if scores else 0
                summary.append({
                    "stage": stage_id,
                    "duration_ms": data["duration_ms"],
                    "score": avg_score
                })

        return summary

    def _calculate_total_duration(self, messages: list[ConversationMessage]) -> int:
        """
        Calculate total duration of all messages.

        Args:
            messages: List of conversation messages

        Returns:
            int: Total duration in milliseconds
        """
        return sum(msg.duration_ms or 0 for msg in messages)

    def _message_to_dict(self, message: ConversationMessage) -> dict[str, Any]:
        """
        Convert a ConversationMessage to a dictionary.

        Args:
            message: ConversationMessage instance

        Returns:
            dict: Message data
        """
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

    def _generate_suggested_response(self, message: ConversationMessage) -> str | None:
        """
        Generate a suggested better response for a highlight.

        For bad highlights (e.g., fuzzy words), suggests improvements.
        For good highlights, returns None.

        Args:
            message: ConversationMessage instance

        Returns:
            str | None: Suggested response or None
        """
        if message.highlight_type != "bad":
            return None

        # Check for fuzzy words
        if message.fuzzy_words:
            suggestions = []
            for fw in message.fuzzy_words:
                if fw.get("suggestion"):
                    suggestions.append(fw["suggestion"])
            if suggestions:
                return f"建议改进: {'; '.join(suggestions)}"

        return None
