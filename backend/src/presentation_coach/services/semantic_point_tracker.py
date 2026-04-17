"""
Semantic Point Tracker - Advanced talking point detection using embeddings
Provides semantic similarity matching beyond simple keyword matching
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from common.ai.embedding_service import EmbeddingService
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PointCoverageResult:
    """Result of checking if a talking point is covered"""
    point_id: str
    point_content: str
    is_covered: bool
    confidence: float
    matched_text: str = ""
    similarity_score: float = 0.0


class SemanticPointTracker:
    """
    Tracks talking point coverage using semantic similarity
    Uses embeddings to match concepts even with different wording
    """

    def __init__(
        self,
        required_points: list[str],
        similarity_threshold: float = 0.75,
        cooldown_seconds: int = 30,
    ):
        self.required_points = required_points
        self.similarity_threshold = similarity_threshold
        self.cooldown_seconds = cooldown_seconds

        # State tracking
        self.covered_points: set[str] = set()
        self.coverage_history: dict[str, list[datetime]] = {}
        self.point_embeddings: dict[str, list[float]] = {}
        self._embedding_service = EmbeddingService()

        # Feedback deduplication
        self._last_feedback: dict[str, datetime] = {}

    async def initialize_embeddings(self) -> Result[bool]:
        """
        Pre-compute embeddings for all required points
        Should be called once when page changes
        """
        try:
            for idx, point in enumerate(self.required_points, start=1):
                point_id = f"point_{idx}"
                embedding_result = await self._embedding_service.get_embedding(point)

                if embedding_result.is_success:
                    self.point_embeddings[point_id] = embedding_result.value
                    logger.debug(f"Computed embedding for point: {point[:50]}...")
                else:
                    logger.warning(f"Failed to get embedding for point: {point[:50]}")

            return Result.ok(True)

        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {str(e)}")
            return Result.fail(f"[EMBEDDING_INIT_FAILED] {str(e)}")

    async def check_coverage(self, transcript: str) -> list[PointCoverageResult]:
        """
        Check which required points are covered in transcript using semantic similarity

        Args:
            transcript: User's speech transcript

        Returns:
            List of coverage results for each point
        """
        if not transcript.strip():
            return self._create_empty_results()

        results = []

        # Get embedding for transcript
        transcript_embedding_result = await self._embedding_service.get_embedding(
            transcript
        )

        if not transcript_embedding_result.is_success:
            logger.warning("Failed to get transcript embedding, falling back to keyword matching")
            return self._fallback_keyword_matching(transcript)

        transcript_embedding = transcript_embedding_result.value

        for idx, point in enumerate(self.required_points, start=1):
            point_id = f"point_{idx}"
            result = await self._check_single_point(
                point_id, point, transcript, transcript_embedding
            )
            results.append(result)

        return results

    async def _check_single_point(
        self,
        point_id: str,
        point_content: str,
        transcript: str,
        transcript_embedding: list[float],
    ) -> PointCoverageResult:
        """Check coverage for a single talking point"""

        # If already covered, maintain covered status
        if point_id in self.covered_points:
            return PointCoverageResult(
                point_id=point_id,
                point_content=point_content,
                is_covered=True,
                confidence=1.0,
                matched_text=transcript[:200],
                similarity_score=1.0,
            )

        # Check if in cooldown period
        if self._is_in_cooldown(point_id):
            return PointCoverageResult(
                point_id=point_id,
                point_content=point_content,
                is_covered=False,
                confidence=0.0,
                similarity_score=0.0,
            )

        # Calculate semantic similarity
        point_embedding = self.point_embeddings.get(point_id)
        if point_embedding:
            similarity = self._cosine_similarity(transcript_embedding, point_embedding)

            if similarity >= self.similarity_threshold:
                self.covered_points.add(point_id)
                self._record_coverage(point_id)

                return PointCoverageResult(
                    point_id=point_id,
                    point_content=point_content,
                    is_covered=True,
                    confidence=similarity,
                    matched_text=transcript[:200],
                    similarity_score=similarity,
                )

            # Also try keyword matching as fallback for high-confidence matches
            keyword_match = self._check_keyword_overlap(point_content, transcript)
            if keyword_match >= 0.8:
                self.covered_points.add(point_id)
                self._record_coverage(point_id)

                return PointCoverageResult(
                    point_id=point_id,
                    point_content=point_content,
                    is_covered=True,
                    confidence=keyword_match,
                    matched_text=transcript[:200],
                    similarity_score=keyword_match,
                )

        return PointCoverageResult(
            point_id=point_id,
            point_content=point_content,
            is_covered=False,
            confidence=0.0,
            similarity_score=0.0,
        )

    def _check_keyword_overlap(self, point: str, transcript: str) -> float:
        """Check keyword overlap as fallback matching"""
        point_keywords = set(self._extract_keywords(point))
        transcript_keywords = set(self._extract_keywords(transcript))

        if not point_keywords:
            return 0.0

        overlap = point_keywords & transcript_keywords
        return len(overlap) / len(point_keywords)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text"""
        # Remove punctuation and split
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        words = cleaned.split()

        # Filter out common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "这", "那", "的", "了", "是", "在", "有",
            "我", "你", "他", "她", "它", "我们", "你们", "他们",
        }

        return [w for w in words if w not in stop_words and len(w) > 1]

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _is_in_cooldown(self, point_id: str) -> bool:
        """Check if point is in feedback cooldown period"""
        last_time = self._last_feedback.get(point_id)
        if not last_time:
            return False

        return (datetime.now() - last_time).seconds < self.cooldown_seconds

    def _record_coverage(self, point_id: str) -> None:
        """Record coverage event"""
        now = datetime.now()

        if point_id not in self.coverage_history:
            self.coverage_history[point_id] = []

        self.coverage_history[point_id].append(now)
        self._last_feedback[point_id] = now

        logger.info(f"Point covered: {point_id}")

    def _create_empty_results(self) -> list[PointCoverageResult]:
        """Create empty results for all points"""
        return [
            PointCoverageResult(
                point_id=f"point_{idx}",
                point_content=point,
                is_covered=False,
                confidence=0.0,
                similarity_score=0.0,
            )
            for idx, point in enumerate(self.required_points, start=1)
        ]

    def _fallback_keyword_matching(self, transcript: str) -> list[PointCoverageResult]:
        """Fallback to keyword matching when embeddings fail"""
        results = []
        transcript_lower = transcript.lower()

        for idx, point in enumerate(self.required_points, start=1):
            point_id = f"point_{idx}"

            # Simple keyword matching
            keywords = self._extract_keywords(point)
            match_count = sum(1 for kw in keywords if kw in transcript_lower)

            if keywords:
                match_ratio = match_count / len(keywords)
                is_covered = match_ratio >= 0.5  # 50% keyword match threshold
            else:
                match_ratio = 0.0
                is_covered = False

            if is_covered and point_id not in self.covered_points:
                self.covered_points.add(point_id)
                self._record_coverage(point_id)

            results.append(
                PointCoverageResult(
                    point_id=point_id,
                    point_content=point,
                    is_covered=is_covered or point_id in self.covered_points,
                    confidence=match_ratio,
                    matched_text=transcript[:200] if is_covered else "",
                    similarity_score=match_ratio,
                )
            )

        return results

    def get_missing_points(self) -> list[tuple[str, str]]:
        """Get list of points not yet covered"""
        return [
            (f"point_{idx}", point)
            for idx, point in enumerate(self.required_points, start=1)
            if f"point_{idx}" not in self.covered_points
        ]

    def is_complete(self) -> bool:
        """Check if all required points have been covered"""
        return len(self.covered_points) == len(self.required_points)

    def get_coverage_stats(self) -> dict[str, Any]:
        """Get coverage statistics"""
        total = len(self.required_points)
        covered = len(self.covered_points)

        return {
            "total_points": total,
            "covered_points": covered,
            "missing_points": total - covered,
            "coverage_percent": (covered / total * 100) if total > 0 else 100,
            "is_complete": self.is_complete(),
        }

    def reset(self) -> None:
        """Reset tracking state (e.g., when page changes)"""
        self.covered_points.clear()
        self.coverage_history.clear()
        self.point_embeddings.clear()
        self._last_feedback.clear()
        logger.debug("SemanticPointTracker reset")


class FeedbackDeduplicator:
    """
    Prevents duplicate feedback for the same issue
    Uses cooldown periods and similarity tracking
    """

    def __init__(self, cooldown_seconds: int = 30):
        self.cooldown_seconds = cooldown_seconds
        self._last_feedback: dict[str, datetime] = {}
        self._feedback_history: list[dict[str, Any]] = []

    def should_send(self, feedback_key: str) -> bool:
        """
        Check if feedback should be sent based on cooldown

        Args:
            feedback_key: Unique identifier for the feedback type

        Returns:
            True if feedback should be sent, False if in cooldown
        """
        now = datetime.now()
        last_time = self._last_feedback.get(feedback_key)

        if last_time and (now - last_time).seconds < self.cooldown_seconds:
            return False

        self._last_feedback[feedback_key] = now
        return True

    def record_feedback(self, feedback_type: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Record feedback that was sent"""
        self._feedback_history.append({
            "type": feedback_type,
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata or {},
        })

    def get_recent_feedback(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent feedback history"""
        return self._feedback_history[-count:]

    def clear(self) -> None:
        """Clear all feedback history"""
        self._last_feedback.clear()
        self._feedback_history.clear()
