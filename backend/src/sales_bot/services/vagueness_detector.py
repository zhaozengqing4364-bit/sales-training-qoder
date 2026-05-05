"""
Vagueness Detector - Detects vague responses in sales conversations

Implements Constitution Principles:
- II. Real-time priority - Detection must be <100ms (simple keyword matching)
- V. Cost control - No LLM calls, uses pre-defined patterns
"""

import logging
import re
from dataclasses import dataclass

from common.error_handling.result import Result

logger = logging.getLogger(__name__)


@dataclass
class VaguenessIssue:
    """Represents a vague phrase detected in user speech"""

    text: str  # The vague phrase
    suggestion: str  # How to be more specific
    severity: str  # "low", "medium", "high"


class VaguenessDetector:
    """
    Detects vague language in sales conversations

    Vague language indicators:
    - Filler words: "um", "uh", "like", "you know"
    - Uncertain phrases: "I think", "maybe", "probably"
    - Non-specific: "stuff", "things", "something"
    - Weak qualifiers: "kind of", "sort of", "a little bit"
    - Hedge words: "basically", "actually", "just"

    Performance: <100ms using regex patterns (no LLM calls)
    """

    def __init__(self):
        # Patterns organized by severity
        self.high_severity_patterns = [
            (
                r"\b(um+|uh+|er+)\b",
                "You're using filler words. Pause and think before speaking.",
            ),
            (
                r"\bI (think|guess|suppose|believe)\b",
                "Be more confident. Use 'I know' or state facts directly.",
            ),
            (
                r"\b(maybe|possibly|perhaps|might)\b",
                "Avoid uncertainty. Be definite in your response.",
            ),
        ]

        self.medium_severity_patterns = [
            (
                r"\b(kind of|sort of|type of)\b",
                "Be specific. What exactly do you mean?",
            ),
            (
                r"\b(stuff|things|something|anything)\b",
                "Use concrete examples and specifics.",
            ),
            (
                r"\b(a little bit|slightly|somewhat)\b",
                "Either it is or it isn't. Be clear.",
            ),
        ]

        self.low_severity_patterns = [
            (
                r"\b(basically|actually|really|honestly)\b",
                "These add no value. Get straight to the point.",
            ),
            (
                r"\b(just|only|simply)\b",
                "Don't minimize. State clearly what you're offering.",
            ),
            (
                r"\b(basically|essentially)\b",
                "Skip the setup. Say what you mean directly.",
            ),
        ]

        # Compile all patterns for performance
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for faster matching"""
        self.high_severity_compiled = [
            (re.compile(pattern, re.IGNORECASE), suggestion)
            for pattern, suggestion in self.high_severity_patterns
        ]
        self.medium_severity_compiled = [
            (re.compile(pattern, re.IGNORECASE), suggestion)
            for pattern, suggestion in self.medium_severity_patterns
        ]
        self.low_severity_compiled = [
            (re.compile(pattern, re.IGNORECASE), suggestion)
            for pattern, suggestion in self.low_severity_patterns
        ]

    async def detect_vagueness(self, text: str) -> Result[list[VaguenessIssue]]:
        """
        Detect vague phrases in user's speech

        Performance target: <100ms (regex only, no LLM)

        Returns: List of VaguenessIssue or Result.fail
        """
        try:
            issues = []

            # Check high severity first (most important)
            for pattern, suggestion in self.high_severity_compiled:
                matches = pattern.finditer(text)
                for match in matches:
                    issues.append(
                        VaguenessIssue(
                            text=match.group(), suggestion=suggestion, severity="high"
                        )
                    )

            # Check medium severity
            for pattern, suggestion in self.medium_severity_compiled:
                matches = pattern.finditer(text)
                for match in matches:
                    issues.append(
                        VaguenessIssue(
                            text=match.group(), suggestion=suggestion, severity="medium"
                        )
                    )

            # Check low severity
            for pattern, suggestion in self.low_severity_compiled:
                matches = pattern.finditer(text)
                for match in matches:
                    issues.append(
                        VaguenessIssue(
                            text=match.group(), suggestion=suggestion, severity="low"
                        )
                    )

            if issues:
                logger.info(
                    "Vagueness detected",
                    extra={
                        "issue_count": len(issues),
                        "high_severity": sum(1 for i in issues if i.severity == "high"),
                    },
                )

            return Result(value=issues)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to detect vagueness", extra={"error": str(e)}, exc_info=True
            )
            # On error, return empty list (graceful degradation)
            return Result(value=[])

    def calculate_vagueness_score(self, issues: list[VaguenessIssue]) -> float:
        """
        Calculate a vagueness score (0-100, lower is better)

        Scoring:
        - Each high severity issue: -20 points
        - Each medium severity issue: -10 points
        - Each low severity issue: -5 points
        - Minimum score: 0
        """
        score = 100.0

        for issue in issues:
            if issue.severity == "high":
                score -= 20
            elif issue.severity == "medium":
                score -= 10
            else:  # low
                score -= 5

        return max(score, 0.0)

    def get_top_suggestion(self, issues: list[VaguenessIssue]) -> str:
        """Get the most important suggestion to address"""
        if not issues:
            return ""

        # Prioritize high severity, then medium, then low
        high_severity = [i for i in issues if i.severity == "high"]
        if high_severity:
            return high_severity[0].suggestion

        medium_severity = [i for i in issues if i.severity == "medium"]
        if medium_severity:
            return medium_severity[0].suggestion

        return issues[0].suggestion


# Singleton instance
vagueness_detector = VaguenessDetector()
