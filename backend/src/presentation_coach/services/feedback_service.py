"""
Presentation Feedback Service
Orchestrates real-time feedback for PPT presentations
Combines point tracking and forbidden word detection
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from common.config import settings
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


@dataclass
class PresentationFeedbackRuleConfig:
    """Configurable rule thresholds for real-time interruption decisions."""

    similarity_threshold: float = 0.75
    point_tracker_cooldown_seconds: int = 30
    feedback_cooldown_seconds: int = 30
    allow_critical_forbidden_interrupt: bool = True
    allow_regular_forbidden_interrupt: bool = True
    missing_points_interrupt_ratio_threshold: float = 0.3
    missing_points_min_count: int = 1
    missing_points_preview_count: int = 2

    @classmethod
    def from_payload(
        cls, payload: dict[str, Any] | None
    ) -> "PresentationFeedbackRuleConfig":
        raw = payload if isinstance(payload, dict) else {}
        return cls(
            similarity_threshold=_to_float(
                raw.get("similarity_threshold"),
                0.75,
                minimum=0.1,
                maximum=0.99,
            ),
            point_tracker_cooldown_seconds=_to_int(
                raw.get("point_tracker_cooldown_seconds"),
                30,
                minimum=0,
                maximum=600,
            ),
            feedback_cooldown_seconds=_to_int(
                raw.get("feedback_cooldown_seconds"),
                30,
                minimum=0,
                maximum=600,
            ),
            allow_critical_forbidden_interrupt=_to_bool(
                raw.get("allow_critical_forbidden_interrupt"),
                True,
            ),
            allow_regular_forbidden_interrupt=_to_bool(
                raw.get("allow_regular_forbidden_interrupt"),
                True,
            ),
            missing_points_interrupt_ratio_threshold=_to_float(
                raw.get("missing_points_interrupt_ratio_threshold"),
                0.3,
                minimum=0.0,
                maximum=1.0,
            ),
            missing_points_min_count=_to_int(
                raw.get("missing_points_min_count"),
                1,
                minimum=1,
                maximum=50,
            ),
            missing_points_preview_count=_to_int(
                raw.get("missing_points_preview_count"),
                2,
                minimum=1,
                maximum=10,
            ),
        )


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _to_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


class PresentationFeedbackService:
    """
    Service for generating real-time presentation feedback
    Manages point tracking and forbidden word detection
    """

    def __init__(
        self,
        *,
        session_ttl_seconds: int | None = None,
        max_sessions: int | None = None,
    ):
        self._trackers: dict[str, SemanticPointTracker] = {}
        self._deduplicators: dict[str, FeedbackDeduplicator] = {}
        self._forbidden_matchers: dict[str, Any] = {}
        self._rule_configs: dict[str, PresentationFeedbackRuleConfig] = {}
        self._page_contexts: dict[str, dict[str, Any]] = {}
        self._last_accessed_at: dict[str, datetime] = {}
        self._session_ttl_seconds = _to_int(
            session_ttl_seconds,
            settings.PRESENTATION_FEEDBACK_SESSION_TTL_SECONDS,
            minimum=60,
            maximum=604800,
        )
        self._max_sessions = _to_int(
            max_sessions,
            settings.PRESENTATION_FEEDBACK_MAX_SESSIONS,
            minimum=1,
            maximum=100000,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _touch_session(self, session_id: str, now: datetime | None = None) -> None:
        self._last_accessed_at[session_id] = now or self._now()

    def _clear_session_data(self, session_id: str) -> None:
        self._trackers.pop(session_id, None)
        self._deduplicators.pop(session_id, None)
        self._forbidden_matchers.pop(session_id, None)
        self._rule_configs.pop(session_id, None)
        self._page_contexts.pop(session_id, None)
        self._last_accessed_at.pop(session_id, None)

    def cleanup_expired_sessions(self, now: datetime | None = None) -> list[str]:
        """Clear session-scoped feedback state older than the configured TTL."""
        effective_now = now or self._now()
        expires_before = effective_now - timedelta(seconds=self._session_ttl_seconds)
        expired_session_ids = [
            session_id
            for session_id, last_accessed in self._last_accessed_at.items()
            if last_accessed < expires_before
        ]
        for session_id in expired_session_ids:
            self._clear_session_data(session_id)
        if expired_session_ids:
            logger.info(
                "presentation_feedback_sessions_expired",
                expired_count=len(expired_session_ids),
            )
        return expired_session_ids

    def _enforce_session_limit(self) -> list[str]:
        """Clear least-recently-used session state above the configured cap."""
        overflow_count = len(self._last_accessed_at) - self._max_sessions
        if overflow_count <= 0:
            return []

        oldest_session_ids = [
            session_id
            for session_id, _ in sorted(
                self._last_accessed_at.items(),
                key=lambda item: item[1],
            )[:overflow_count]
        ]
        for session_id in oldest_session_ids:
            self._clear_session_data(session_id)
        logger.warning(
            "presentation_feedback_session_limit_enforced",
            evicted_count=len(oldest_session_ids),
            max_sessions=self._max_sessions,
        )
        return oldest_session_ids

    @staticmethod
    def _build_page_signature(
        *,
        page_number: int,
        required_points: list[str],
        forbidden_words: list[dict[str, Any]],
        rule_config: PresentationFeedbackRuleConfig,
    ) -> str:
        payload = {
            "page_number": page_number,
            "required_points": required_points,
            "forbidden_words": forbidden_words,
            "rule_config": {
                "similarity_threshold": rule_config.similarity_threshold,
                "point_tracker_cooldown_seconds": (
                    rule_config.point_tracker_cooldown_seconds
                ),
                "feedback_cooldown_seconds": rule_config.feedback_cooldown_seconds,
                "allow_critical_forbidden_interrupt": (
                    rule_config.allow_critical_forbidden_interrupt
                ),
                "allow_regular_forbidden_interrupt": (
                    rule_config.allow_regular_forbidden_interrupt
                ),
                "missing_points_interrupt_ratio_threshold": (
                    rule_config.missing_points_interrupt_ratio_threshold
                ),
                "missing_points_min_count": rule_config.missing_points_min_count,
                "missing_points_preview_count": rule_config.missing_points_preview_count,
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    async def initialize_page(
        self,
        session_id: str,
        page_number: int,
        required_points: list[str],
        forbidden_words: list[dict[str, Any]],
        rule_config: dict[str, Any] | None = None,
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
            self.cleanup_expired_sessions()
            normalized_rule_config = PresentationFeedbackRuleConfig.from_payload(
                rule_config
            )
            next_signature = self._build_page_signature(
                page_number=page_number,
                required_points=required_points,
                forbidden_words=forbidden_words,
                rule_config=normalized_rule_config,
            )
            prev_context = self._page_contexts.get(session_id)
            if prev_context and prev_context.get("signature") == next_signature:
                self._rule_configs[session_id] = normalized_rule_config
                self._touch_session(session_id)
                self._enforce_session_limit()
                return Result.ok(True)

            # Create new tracker for this page
            tracker = SemanticPointTracker(
                required_points=required_points,
                similarity_threshold=normalized_rule_config.similarity_threshold,
                cooldown_seconds=normalized_rule_config.point_tracker_cooldown_seconds,
            )

            # Pre-compute embeddings
            await tracker.initialize_embeddings()

            self._trackers[session_id] = tracker

            # Create deduplicator
            self._deduplicators[session_id] = FeedbackDeduplicator(
                cooldown_seconds=normalized_rule_config.feedback_cooldown_seconds
            )
            self._rule_configs[session_id] = normalized_rule_config

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
                "signature": next_signature,
            }
            self._touch_session(session_id)
            self._enforce_session_limit()

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
            self.cleanup_expired_sessions()
            tracker = self._trackers.get(session_id)
            matcher = self._forbidden_matchers.get(session_id)
            dedup = self._deduplicators.get(session_id)
            rule_config = self._rule_configs.get(
                session_id,
                PresentationFeedbackRuleConfig(),
            )

            if not tracker or not matcher:
                return Result.fail("[NOT_INITIALIZED] Page not initialized")
            self._touch_session(session_id)

            # Check point coverage
            point_results = await tracker.check_coverage(transcript)

            # Check forbidden words
            forbidden_matches = matcher.get_unique_matches(transcript)

            # Determine if we should interrupt
            should_interrupt, reason, message = self._determine_interruption(
                point_results,
                forbidden_matches,
                dedup,
                rule_config,
            )

            feedback = PresentationFeedback(
                point_results=point_results,
                forbidden_matches=forbidden_matches,
                should_interrupt=should_interrupt,
                interruption_reason=reason,
                interruption_message=message,
                timestamp=self._now(),
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
        rule_config: PresentationFeedbackRuleConfig,
    ) -> tuple[bool, str, str]:
        """
        Determine if AI should interrupt based on feedback

        Returns:
            Tuple of (should_interrupt, reason, message)
        """
        # Priority 1: Critical forbidden words
        if rule_config.allow_critical_forbidden_interrupt:
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
        if rule_config.allow_regular_forbidden_interrupt:
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
        coverage_ratio = covered_count / total_count if total_count > 0 else 1.0
        if (
            total_count > 0
            and coverage_ratio < rule_config.missing_points_interrupt_ratio_threshold
            and len(missing_points) >= rule_config.missing_points_min_count
        ):
            feedback_key = "missing_points"
            if dedup and dedup.should_send(feedback_key):
                dedup.record_feedback(
                    "missing_point", f"Missing {len(missing_points)} points"
                )
                missing_names = [
                    p.point_content[:20]
                    for p in missing_points[: rule_config.missing_points_preview_count]
                ]
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
        self._touch_session(session_id)

        return tracker.get_coverage_stats()

    def get_coverage_updates(self, session_id: str) -> list[dict[str, Any]]:
        """Get point coverage updates for frontend"""
        tracker = self._trackers.get(session_id)
        if not tracker:
            return []
        self._touch_session(session_id)

        updates = []
        for idx, point in enumerate(tracker.required_points, start=1):
            point_id = f"point_{idx}"
            is_covered = point_id in tracker.covered_points

            updates.append(
                {
                    "point_id": f"{session_id}:{idx}",
                    "is_covered": is_covered,
                    "content": point,
                }
            )

        return updates

    def clear_session(self, session_id: str) -> None:
        """Clear all session data"""
        self._clear_session_data(session_id)

        logger.info(f"Cleared feedback service for session {session_id}")


# Singleton instance
_feedback_service: PresentationFeedbackService | None = None


def get_feedback_service() -> PresentationFeedbackService:
    """Get singleton feedback service instance"""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = PresentationFeedbackService()
    return _feedback_service
