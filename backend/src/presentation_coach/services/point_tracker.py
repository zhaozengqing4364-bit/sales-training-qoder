"""
Required Talking Point Tracker
Tracks which required points have been covered
"""

from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class PointTracker:
    """Tracks coverage of required talking points during presentation"""

    def __init__(self, required_points: list[str]):
        self.required_points = required_points
        self.covered_points: set[str] = set()
        self.coverage_count: dict[str, int] = {}  # How many times each point was mentioned

    def check_coverage(self, transcript: str) -> dict[str, Any]:
        """
        Check which required points are covered in transcript

        Returns:
            Dict with "covered", "missing", "coverage_percent"
        """
        transcript_lower = transcript.lower()

        for point in self.required_points:
            # Simple keyword matching
            keywords = point.lower().split()

            # Check if any keyword appears
            if any(keyword in transcript_lower for keyword in keywords):
                if point not in self.covered_points:
                    self.covered_points.add(point)
                    self.coverage_count[point] = 1
                    logger.info(f"Covered point: {point}")
                else:
                    self.coverage_count[point] += 1

        # Calculate coverage
        covered = list(self.covered_points)
        missing = [p for p in self.required_points if p not in self.covered_points]
        coverage_percent = (
            (len(covered) / len(self.required_points)) * 100
            if self.required_points
            else 100
        )

        return {
            "covered": covered,
            "missing": missing,
            "coverage_percent": coverage_percent,
            "total_required": len(self.required_points),
            "total_covered": len(covered),
        }

    def get_missing_points(self) -> list[str]:
        """Get list of required points not yet covered"""
        return [p for p in self.required_points if p not in self.covered_points]

    def is_complete(self) -> bool:
        """Check if all required points have been covered"""
        return len(self.covered_points) == len(self.required_points)

    def reset(self) -> None:
        """Reset tracking (e.g., for new page)"""
        self.covered_points.clear()
        self.coverage_count.clear()
