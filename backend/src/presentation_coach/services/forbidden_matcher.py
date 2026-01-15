"""
Forbidden Word Pattern Matcher
Regex-based forbidden phrase detection
"""
import re

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class ForbiddenWordMatcher:
    """Matches forbidden words/phrases in speech transcript"""

    def __init__(self):
        self.patterns = {}

    def add_patterns(self, words: list[dict]) -> None:
        """
        Add forbidden word patterns

        Args:
            words: List of {"phrase": str, "is_regex": bool, "suggested_alternative": str}
        """
        for word in words:
            phrase = word["phrase"]
            is_regex = word.get("is_regex", False)

            if is_regex:
                try:
                    self.patterns[phrase] = {
                        "pattern": re.compile(phrase, re.IGNORECASE),
                        "suggested": word.get("suggested_alternative", "")
                    }
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{phrase}': {str(e)}")
            else:
                # Escape special regex characters for literal matching
                escaped = re.escape(phrase)
                self.patterns[phrase] = {
                    "pattern": re.compile(escaped, re.IGNORECASE),
                    "suggested": word.get("suggested_alternative", "")
                }

    def find_matches(self, transcript: str) -> list[dict]:
        """
        Find all forbidden word matches in transcript

        Returns:
            List of {"phrase": str, "suggested_alternative": str, "match": str}
        """
        matches = []
        transcript_lower = transcript.lower()

        for phrase, config in self.patterns.items():
            pattern = config["pattern"]

            if pattern.search(transcript):
                matches.append({
                    "phrase": phrase,
                    "suggested_alternative": config["suggested"],
                    "match": transcript  # Return full matched segment
                })

        return matches

    def has_match(self, transcript: str) -> bool:
        """Quick check if any forbidden word matches"""
        for config in self.patterns.values():
            if config["pattern"].search(transcript):
                return True
        return False

    def get_suggestion(self, phrase: str) -> str:
        """Get suggested alternative for a forbidden phrase"""
        if phrase in self.patterns:
            return self.patterns[phrase]["suggested"]
        return "Please rephrase that differently."


# Singleton instance
_matcher: ForbiddenWordMatcher | None = None


def get_forbidden_matcher() -> ForbiddenWordMatcher:
    """Get singleton matcher instance"""
    global _matcher
    if _matcher is None:
        _matcher = ForbiddenWordMatcher()
    return _matcher
