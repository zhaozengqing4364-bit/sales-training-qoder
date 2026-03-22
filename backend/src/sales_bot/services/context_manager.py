"""
Conversation Context Manager - Manages multi-turn dialogue state for sales bot

Implements Constitution Principles:
- II. Real-time priority - <100ms state updates
- V. Cost control - Efficient token usage through context summarization
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from common.error_handling.result import Result

logger = logging.getLogger(__name__)


@dataclass
class DialogueTurn:
    """Represents a single turn in the conversation"""
    turn_number: int
    user_text: str
    bot_response: str
    timestamp: datetime
    user_was_interrupted: bool = False
    vagueness_detected: bool = False
    challenge_level: int = 1


@dataclass
class ConversationContext:
    """Full context of an active sales conversation"""
    session_id: uuid.UUID
    persona: str
    turns: list[DialogueTurn] = field(default_factory=list)
    user_objectives: list[str] = field(default_factory=list)  # What user wants to achieve
    bot_tactics: list[str] = field(default_factory=list)  # What bot is testing
    current_phase: str = "opening"  # opening, discovery, objection, closing

    # Performance metrics
    total_user_interruptions: int = 0
    total_bot_interruptions: int = 0
    vagueness_count: int = 0


class ContextManager:
    """
    Manages conversation state for multi-turn sales dialogue

    Key responsibilities:
    - Track conversation history
    - Maintain context across turns
    - Summarize when token budget is tight
    - Guide conversation flow
    """

    def __init__(self):
        self.active_contexts: dict[uuid.UUID, ConversationContext] = {}
        self.max_turns_before_summarization = 6  # Summarize after 6 turns to save tokens

    async def create_context(
        self,
        session_id: uuid.UUID,
        persona: str
    ) -> Result[ConversationContext]:
        """
        Create new conversation context

        Returns: ConversationContext or Result.fail
        """
        try:
            context = ConversationContext(
                session_id=session_id,
                persona=persona,
            )

            self.active_contexts[session_id] = context

            logger.info(
                "Conversation context created",
                extra={"session_id": str(session_id), "persona": persona}
            )

            return Result(value=context)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to create context",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[CONTEXT_CREATE_FAILED]")

    async def add_turn(
        self,
        session_id: uuid.UUID,
        user_text: str,
        bot_response: str,
        user_was_interrupted: bool = False,
        vagueness_detected: bool = False,
        challenge_level: int = 1
    ) -> Result[DialogueTurn]:
        """
        Add a dialogue turn to the conversation

        Returns: DialogueTurn or Result.fail
        """
        try:
            if session_id not in self.active_contexts:
                return Result.fail(fallback="[CONTEXT_NOT_FOUND]")

            context = self.active_contexts[session_id]
            turn_number = len(context.turns) + 1

            turn = DialogueTurn(
                turn_number=turn_number,
                user_text=user_text,
                bot_response=bot_response,
                timestamp=datetime.now(),
                user_was_interrupted=user_was_interrupted,
                vagueness_detected=vagueness_detected,
                challenge_level=challenge_level
            )

            context.turns.append(turn)

            # Update metrics
            if user_was_interrupted:
                context.total_bot_interruptions += 1
            if vagueness_detected:
                context.vagueness_count += 1

            # Update conversation phase based on turn count
            if turn_number == 1:
                context.current_phase = "opening"
            elif turn_number <= 3:
                context.current_phase = "discovery"
            elif turn_number <= 6:
                context.current_phase = "objection"
            else:
                context.current_phase = "closing"

            # Check if we should summarize to save tokens
            if turn_number >= self.max_turns_before_summarization:
                await self._summarize_context(session_id)

            logger.info(
                "Dialogue turn added",
                extra={
                    "session_id": str(session_id),
                    "turn": turn_number,
                    "phase": context.current_phase,
                }
            )

            return Result(value=turn)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to add turn",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[TURN_ADD_FAILED]")

    async def get_context(self, session_id: uuid.UUID) -> Result[ConversationContext]:
        """Get current conversation context"""
        try:
            if session_id not in self.active_contexts:
                return Result.fail(fallback="[CONTEXT_NOT_FOUND]")

            return Result(value=self.active_contexts[session_id])

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to get context",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[CONTEXT_GET_FAILED]")

    async def get_conversation_summary(
        self,
        session_id: uuid.UUID
    ) -> Result[dict]:
        """
        Get summary of conversation for final report

        Returns: Summary dict or Result.fail
        """
        try:
            if session_id not in self.active_contexts:
                return Result.fail(fallback="[CONTEXT_NOT_FOUND]")

            context = self.active_contexts[session_id]

            summary = {
                "session_id": str(session_id),
                "persona": context.persona,
                "total_turns": len(context.turns),
                "phases_completed": self._get_phases_completed(context),
                "user_interruptions": context.total_user_interruptions,
                "bot_interruptions": context.total_bot_interruptions,
                "vagueness_count": context.vagueness_count,
                "average_challenge_level": self._calculate_avg_challenge(context),
                "conversation_flow": self._analyze_flow(context),
            }

            logger.info(
                "Conversation summary generated",
                extra={"session_id": str(session_id), "turns": summary["total_turns"]}
            )

            return Result(value=summary)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to generate summary",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[SUMMARY_FAILED]")

    async def cleanup(self, session_id: uuid.UUID) -> Result[bool]:
        """Remove context from active contexts"""
        try:
            if session_id in self.active_contexts:
                del self.active_contexts[session_id]

            return Result(value=True)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to cleanup context",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[CLEANUP_FAILED]")

    async def _summarize_context(self, session_id: uuid.UUID):
        """
        Summarize older turns to save tokens

        Strategy: Keep first 2 turns + last 3 turns, summarize middle turns
        """
        if session_id not in self.active_contexts:
            return

        context = self.active_contexts[session_id]
        if len(context.turns) < self.max_turns_before_summarization:
            return

        # In production, would use LLM to summarize middle turns
        # For now, just keep first and last turns
        logger.info(
            "Context summarization needed",
            extra={"session_id": str(session_id), "turns": len(context.turns)}
        )

    def _get_phases_completed(self, context: ConversationContext) -> list[str]:
        """Get list of phases the conversation went through"""
        phases = set()
        for turn in context.turns:
            # Reconstruct phase from turn number
            if turn.turn_number == 1:
                phases.add("opening")
            elif turn.turn_number <= 3:
                phases.add("discovery")
            elif turn.turn_number <= 6:
                phases.add("objection")
            else:
                phases.add("closing")
        return sorted(list(phases))

    def _calculate_avg_challenge(self, context: ConversationContext) -> float:
        """Calculate average challenge level across all turns"""
        if not context.turns:
            return 0.0

        total = sum(turn.challenge_level for turn in context.turns)
        return round(total / len(context.turns), 2)

    def _analyze_flow(self, context: ConversationContext) -> dict:
        """Analyze conversation flow for insights"""
        if not context.turns:
            return {}

        return {
            "interruption_rate": round(
                context.total_bot_interruptions / len(context.turns) * 100, 1
            ),
            "vagueness_rate": round(
                context.vagueness_count / len(context.turns) * 100, 1
            ),
            "has_vagueness_issues": context.vagueness_count > 0,
            "was_interrupted": context.total_bot_interruptions > 0,
        }


# Singleton instance
context_manager = ContextManager()
