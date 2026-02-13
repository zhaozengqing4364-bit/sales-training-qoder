"""
Presentation Feedback Service
Orchestrates real-time feedback for PPT presentations
Combines point tracking and forbidden word detection
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from presentation_coach.services.aho_matcher import (
    ForbiddenWordMatch,
    get_hybrid_matcher,
)
from presentation_coach.services.semantic_point_tracker import (
    FeedbackDeduplicator,
    PointCoverageResult,
    SemanticPointTracker,
)

logger = get_logger(__name__)


@dataclass
class PresentationFeedback:
    """Complete feedback for a presentation check"""
    point_results: list[PointCoverageResult]
    forbidden_matches: list[ForbiddenWordMatch]
    should_interrupt: bool
    interruption_reason: str
    interruption_message: str
    timestamp: datetime


class PresentationFeedbackService:
    """
    Service for generating real-time presentation feedback
    Manages point tracking and forbidden word detection
    """

    def __init__(self):
        self._trackers: dict[str, SemanticPointTracker] = {}
        self._deduplicators: dict[str, FeedbackDeduplicator] = {}
        self._forbidden_matchers: dict[str, Any] = {}
        self._page_contexts: dict[str, dict[str, Any]] = {}

    async def initialize_page(
        self,
        session_id: str,
        page_number: int,
        required_points: list[str],
        forbidden_words: list[dict[str, Any]],
    ) -> Result[bool]:
        """
        Initialize tracking for a new page

        Args:
            session_id: Session identifier
            page_number: Current page number
            required_points: List of required talking points
            forbidden_words: List of forbidden word configurations

        Returns:
            Result indicating success
        """
        try:
            # Create new tracker for this page
            tracker = SemanticPointTracker(
                required_points=required_points,
                similarity_threshold=0.75,
                cooldown_seconds=30,
            )

            # Pre-compute embeddings
            await tracker.initialize_embeddings()

            self._trackers[session_id] = tracker

            # Create deduplicator
            self._deduplicators[session_id] = FeedbackDeduplicator(cooldown_seconds=30)

            # Initialize forbidden word matcher
            matcher = get_hybrid_matcher()
            matcher.clear()
            matcher.add_words(forbidden_words)
            self._forbidden_matchers[session_id] = matcher

            # Store page context
            self._page_contexts[session_id] = {
                "page_number": page_number,
                "required_points": required_points,
                "forbidden_words": forbidden_words,
            }

            logger.info(
                f"Initialized page {page_number} for session {session_id}: "
                f"{len(required_points)} points, {len(forbidden_words)} forbidden words"
            )

            return Result.ok(True)

        except Exception as e:
            logger.error(f"Failed to initialize page: {str(e)}")
            return Result.fail(f"[INIT_FAILED] {str(e)}")

    async def check_transcript(
        self,
        session_id: str,
        transcript: str,
    ) -> Result[PresentationFeedback]:
        """
        Check transcript and generate feedback

        Args:
            session_id: Session identifier
            transcript: User's speech transcript

        Returns:
            Result containing feedback data
        """
        try:
            tracker = self._trackers.get(session_id)
            matcher = self._forbidden_matchers.get(session_id)
            dedup = self._deduplicators.get(session_id)

            if not tracker or not matcher:
                return Result.fail("[NOT_INITIALIZED] Page not initialized")

            # Check point coverage
            point_results = await tracker.check_coverage(transcript)

            # Check forbidden words
            forbidden_matches = matcher.get_unique_matches(transcript)

            # Determine if we should interrupt
            should_interrupt, reason, message = self._determine_interruption(
                point_results,
                forbidden_matches,
                dedup,
            )

            feedback = PresentationFeedback(
                point_results=point_results,
                forbidden_matches=forbidden_matches,
                should_interrupt=should_interrupt,
                interruption_reason=reason,
                interruption_message=message,
                timestamp=datetime.now(),
            )

            return Result.ok(feedback)

        except Exception as e:
            logger.error(f"Failed to check transcript: {str(e)}")
            return Result.fail(f"[CHECK_FAILED] {str(e)}")

    def _determine_interruption(
        self,
        point_results: list[PointCoverageResult],
        forbidden_matches: list[ForbiddenWordMatch],
        dedup: FeedbackDeduplicator | None,
    ) -> tuple[bool, str, str]:
        """
        Determine if AI should interrupt based on feedback

        Returns:
            Tuple of (should_interrupt, reason, message)
        """
        # Priority 1: Critical forbidden words
        for match in forbidden_matches:
            if match.severity == "critical":
                feedback_key = f"forbidden_{match.word}"
                if dedup and dedup.should_send(feedback_key):
                    dedup.record_feedback("forbidden_word", match.word)
                    return (
                        True,
                        "forbidden_word",
                        f"请避免使用'{match.word}'。{match.suggestion}",
                    )

        # Priority 2: Regular forbidden words
        for match in forbidden_matches:
            feedback_key = f"forbidden_{match.word}"
            if dedup and dedup.should_send(feedback_key):
                dedup.record_feedback("forbidden_word", match.word)
                return (
                    True,
                    "forbidden_word",
                    f"检测到不规范用语'{match.word}'。{match.suggestion}",
                )

        # Priority 3: Missing critical points (only if many points are missing)
        missing_points = [p for p in point_results if not p.is_covered]
        covered_count = sum(1 for p in point_results if p.is_covered)
        total_count = len(point_results)

        # Only interrupt if coverage is very low (< 30%) and there are points to cover
        if total_count > 0 and covered_count / total_count < 0.3 and missing_points:
            feedback_key = "missing_points"
            if dedup and dedup.should_send(feedback_key):
                dedup.record_feedback("missing_point", f"Missing {len(missing_points)} points")
                missing_names = [p.point_content[:20] for p in missing_points[:2]]
                return (
                    True,
                    "missing_point",
                    f"您还没有涵盖本页要点：{', '.join(missing_names)}...",
                )

        return False, "", ""

    def get_point_coverage(self, session_id: str) -> dict[str, Any]:
        """Get current point coverage statistics"""
        tracker = self._trackers.get(session_id)
        if not tracker:
            return {"error": "Session not initialized"}

        return tracker.get_coverage_stats()

    def get_coverage_updates(self, session_id: str) -> list[dict[str, Any]]:
        """Get point coverage updates for frontend"""
        tracker = self._trackers.get(session_id)
        if not tracker:
            return []

        updates = []
        for idx, point in enumerate(tracker.required_points, start=1):
            point_id = f"point_{idx}"
            is_covered = point_id in tracker.covered_points

            updates.append({
                "point_id": f"{session_id}:{idx}",
                "is_covered": is_covered,
                "content": point,
            })

        return updates

    def clear_session(self, session_id: str) -> None:
        """Clear all session data"""
        if session_id in self._trackers:
            del self._trackers[session_id]
        if session_id in self._deduplicators:
            del self._deduplicators[session_id]
        if session_id in self._forbidden_matchers:
            del self._forbidden_matchers[session_id]
        if session_id in self._page_contexts:
            del self._page_contexts[session_id]

        logger.info(f"Cleared feedback service for session {session_id}")


# Singleton instance
_feedback_service: PresentationFeedbackService | None = None


def get_feedback_service() -> PresentationFeedbackService:
    """Get singleton feedback service instance"""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = PresentationFeedbackService()
    return _feedback_service
