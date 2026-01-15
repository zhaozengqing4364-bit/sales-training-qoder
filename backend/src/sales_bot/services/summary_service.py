"""
Sales Bot Summary Service - Generates conversation summaries and feedback

Implements Constitution Principles:
- II. Real-time priority - <500ms summary generation
- V. Cost control - Efficient prompt engineering
"""

import logging
import uuid

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common.ai.llm_service import get_llm_service
from common.error_handling.result import Result
from sales_bot.services.context_manager import context_manager

logger = logging.getLogger(__name__)


class ConversationSummary(BaseModel):
    """Structured conversation summary from LLM"""
    overall_performance: str = Field(description="Overall performance assessment (excellent/good/fair/poor)")
    strengths: list[str] = Field(description="What the user did well")
    weaknesses: list[str] = Field(description="Areas for improvement")
    key_moments: list[str] = Field(description="Key moments in the conversation")
    score_confidence: int = Field(description="Confidence score (1-100)", ge=0, le=100)
    score_persuasion: int = Field(description="Persuasion score (1-100)", ge=0, le=100)
    score_clarity: int = Field(description="Clarity score (1-100)", ge=0, le=100)
    actionable_feedback: str = Field(description="Specific, actionable feedback")


class SummaryService:
    """
    Generates conversation summaries and performance feedback

    Key features:
    - Analyzes conversation turns
    - Calculates scores (confidence, persuasion, clarity)
    - Provides actionable feedback
    - Identifies strengths and weaknesses
    """

    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=ConversationSummary)

        self.summary_prompt = PromptTemplate(
            template="""Analyze this sales conversation and provide a summary.

**Persona**: {persona}
**Total Turns**: {turn_count}

**Conversation Transcript**:
{transcript}

**Metrics**:
- Bot Interruptions: {bot_interruptions} (AI interrupted user)
- Vagueness Detected: {vagueness_count} times
- Average Challenge Level: {avg_challenge}/5

{format_instructions}

Provide an objective assessment of the salesperson's performance.""",
            input_variables=["persona", "turn_count", "transcript", "bot_interruptions", "vagueness_count", "avg_challenge"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

    async def generate_summary(
        self,
        session_id: uuid.UUID
    ) -> Result[ConversationSummary]:
        """
        Generate conversation summary using LLM

        Returns: ConversationSummary or Result.fail
        """
        try:
            # Get conversation context
            context_result = await context_manager.get_context(session_id)
            if not context_result.is_success:
                return Result.fail(fallback="[CONTEXT_NOT_FOUND]")

            context = context_result.value

            # Build transcript
            transcript = self._build_transcript(context)

            # Get metrics
            bot_interruptions = context.total_bot_interruptions
            vagueness_count = context.vagueness_count
            avg_challenge = context_manager._calculate_avg_challenge(context)

            # Generate summary using LLM
            prompt_value = self.summary_prompt.format(
                persona=context.persona,
                turn_count=len(context.turns),
                transcript=transcript,
                bot_interruptions=bot_interruptions,
                vagueness_count=vagueness_count,
                avg_challenge=avg_challenge
            )

            # Call LLM
            response = await get_llm_service().llm.apredict(prompt_value)

            # Parse response
            summary = self.parser.parse(response)

            logger.info(
                "Conversation summary generated",
                extra={
                    "session_id": str(session_id),
                    "performance": summary.overall_performance,
                    "confidence_score": summary.score_confidence,
                }
            )

            return Result(value=summary)

        except TimeoutError:
            logger.warning(
                "LLM timeout generating summary",
                extra={"session_id": str(session_id)}
            )
            # Fallback to rule-based summary
            return Result(value=self._generate_fallback_summary(context_result.value))
        except Exception as e:
            logger.error(
                "Failed to generate summary",
                extra={"session_id": str(session_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[SUMMARY_FAILED]")

    def _build_transcript(self, context) -> str:
        """Build formatted transcript from conversation turns"""
        if not context.turns:
            return "No conversation turns recorded."

        lines = []
        for turn in context.turns:
            lines.append(f"**Turn {turn.turn_number}**")
            lines.append(f"User: {turn.user_text}")
            lines.append(f"AI: {turn.bot_response}")

            if turn.user_was_interrupted:
                lines.append("(User was interrupted by AI)")

            if turn.vagueness_detected:
                lines.append("(Vagueness detected)")

            lines.append("")

        return "\n".join(lines)

    def _generate_fallback_summary(self, context) -> ConversationSummary:
        """
        Generate rule-based summary when LLM fails

        Fallback strategy: Use simple heuristics to score performance
        """
        turn_count = len(context.turns)

        # Calculate scores based on metrics
        vagueness_penalty = context.vagueness_count * 10
        interruption_penalty = context.total_bot_interruptions * 5

        confidence_score = max(0, 100 - vagueness_penalty - interruption_penalty)

        # Persuasion based on turns completed (more turns = better engagement)
        persuasion_score = min(100, turn_count * 10)

        # Clarity based on vagueness (less vagueness = better clarity)
        clarity_score = max(0, 100 - (context.vagueness_count * 15))

        # Determine overall performance
        avg_score = (confidence_score + persuasion_score + clarity_score) / 3

        if avg_score >= 80:
            overall = "excellent"
        elif avg_score >= 60:
            overall = "good"
        elif avg_score >= 40:
            overall = "fair"
        else:
            overall = "poor"

        # Generate strengths/weaknesses
        strengths = []
        weaknesses = []

        if context.vagueness_count == 0:
            strengths.append("Clear and specific communication")
        else:
            weaknesses.append(f"Used vague language {context.vagueness_count} times")

        if context.total_bot_interruptions == 0:
            strengths.append("Maintained composure under pressure")
        else:
            weaknesses.append(f"Was interrupted {context.total_bot_interruptions} times")

        if turn_count >= 8:
            strengths.append("Engaged in extended dialogue")
        else:
            weaknesses.append("Conversation ended early")

        # Generate actionable feedback
        if weaknesses:
            actionable = "To improve, focus on: " + ", ".join(weaknesses[:2])
        else:
            actionable = "Great job! Keep practicing to maintain this level."

        return ConversationSummary(
            overall_performance=overall,
            strengths=strengths or ["Completed the conversation"],
            weaknesses=weaknesses or ["Minor areas for refinement"],
            key_moments=[f"Completed {turn_count} turns"],
            score_confidence=confidence_score,
            score_persuasion=persuasion_score,
            score_clarity=clarity_score,
            actionable_feedback=actionable
        )


# Singleton instance
summary_service = SummaryService()
