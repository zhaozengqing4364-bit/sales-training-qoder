"""
Interruption Detector - Two-stage detection (keyword + semantic)
Constitution Principle II: <100ms for keyword detection
"""

import re
from typing import Any

from common.ai.llm_service import get_llm_service
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class InterruptionDetector:
    """
    Two-stage interruption detection:
    Stage 1: Keyword detection (<100ms)
    Stage 2: Semantic analysis via LLM (<500ms)
    """

    def __init__(self):
        self.llm_service = get_llm_service()

    async def should_interrupt(
        self, transcript: str, context: dict[str, Any]
    ) -> Result[dict[str, Any] | None]:
        """
        Check if interruption is needed

        Args:
            transcript: User's speech transcript
            context: Session context (required_points, forbidden_words, etc.)

        Returns:
            Result with interruption decision or None
        """
        try:
            # Stage 1: Keyword detection (<100ms)
            keyword_result = self._check_keywords(transcript, context)
            if keyword_result:
                return Result.ok(keyword_result)

            required_points = context.get("required_points", [])
            if not required_points:
                return Result.ok(None)

            covered_points = self._check_points_covered(transcript, required_points)
            if covered_points >= len(required_points):
                return Result.ok(None)

            # Stage 2: Semantic analysis (only if keyword didn't match)
            semantic_result = await self._check_semantic(
                transcript,
                context,
                required_points=required_points,
                covered_points=covered_points,
            )
            return Result.ok(semantic_result)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Interruption detection error: {str(e)}")
            # On error, don't interrupt
            return Result.ok(None)

    def _check_keywords(
        self, transcript: str, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Stage 1: Fast keyword detection
        Checks for forbidden words and completion patterns
        """
        transcript_lower = transcript.lower()

        # Check forbidden words
        forbidden_words = context.get("forbidden_words", [])
        for phrase in forbidden_words:
            if phrase.lower() in transcript_lower:
                return {
                    "type": "forbidden_word",
                    "trigger": phrase,
                    "reason": f"You used a forbidden phrase: '{phrase}'",
                }

        # Check for completion indicators (user stopped speaking)
        completion_patterns = [
            r"that's all",
            r"thank you",
            r"any questions",
            r"in conclusion",
        ]

        for pattern in completion_patterns:
            if re.search(pattern, transcript_lower):
                # Check if required points were covered
                required_points = context.get("required_points", [])
                covered_points = self._check_points_covered(transcript, required_points)

                if covered_points < len(required_points):
                    return {
                        "type": "missing_point",
                        "trigger": transcript,
                        "reason": "You finished the page without mentioning all required points",
                    }

        return None

    async def _check_semantic(
        self,
        transcript: str,
        context: dict[str, Any],
        *,
        required_points: list[str] | None = None,
        covered_points: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Stage 2: Semantic analysis via LLM
        Checks for vague responses, off-topic content, etc.
        """
        try:
            if required_points is None:
                required_points = context.get("required_points", [])

            if not required_points:
                # No requirements, no need to interrupt
                return None

            if covered_points is None:
                covered_points = self._check_points_covered(transcript, required_points)
            if covered_points >= len(required_points):
                return None

            # Build prompt
            points_str = "\n".join([f"- {p}" for p in required_points])
            prompt = f"""Analyze the following speech transcript and determine if the speaker is:

1. Being vague or evasive
2. Missing key talking points

Required talking points:
{points_str}

Transcript: "{transcript}"

Answer with YES if you should interrupt, NO otherwise. Keep it brief."""

            # Call LLM with short timeout
            result = await self.llm_service.generate(
                prompt=prompt,
                session_id=context.get("session_id", ""),
                system_message="You are a presentation coach. Be concise.",
            )

            if result.is_success and result.value:
                response = result.value.lower()

                if "yes" in response:
                    # Extract reason
                    return {
                        "type": "vague_response",
                        "trigger": transcript,
                        "reason": "Your response was too vague. Please provide specific details.",
                    }

            return None

        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Semantic analysis error: {str(e)}")
            return None

    def _check_points_covered(self, transcript: str, required_points: list[str]) -> int:
        """Count how many required points were covered"""
        covered = 0
        transcript_lower = transcript.lower()

        for point in required_points:
            # Simple keyword matching
            keywords = point.lower().split()
            if any(keyword in transcript_lower for keyword in keywords):
                covered += 1

        return covered


# Singleton instance
_detector: InterruptionDetector | None = None


def get_interruption_detector() -> InterruptionDetector:
    """Get singleton detector instance"""
    global _detector
    if _detector is None:
        _detector = InterruptionDetector()
    return _detector
