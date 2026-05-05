"""
Aho-Corasick Forbidden Word Matcher
Efficient multi-pattern string matching algorithm
Time complexity: O(n + m + z) where n=text length, m=pattern total length, z=match count
"""

from collections import deque
from dataclasses import dataclass
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ForbiddenWordMatch:
    """Result of a forbidden word match"""

    word: str
    position: int
    matched_text: str
    suggestion: str
    severity: str = "warning"


class AhoCorasickNode:
    """Node in the Aho-Corasick trie"""

    def __init__(self):
        self.children: dict[str, AhoCorasickNode] = {}
        self.fail_link: AhoCorasickNode | None = None
        self.output: list[str] = []  # Patterns ending at this node
        self.is_end = False


class AhoCorasickMatcher:
    """
    Aho-Corasick multi-pattern matching algorithm
    Efficiently finds all occurrences of multiple patterns in text
    """

    def __init__(self):
        self.root = AhoCorasickNode()
        self.patterns: dict[str, dict[str, Any]] = {}
        self._built = False

    def add_pattern(
        self,
        word: str,
        suggestion: str = "",
        severity: str = "warning",
        case_sensitive: bool = False,
    ) -> None:
        """
        Add a forbidden word pattern

        Args:
            word: The forbidden word/phrase
            suggestion: Alternative suggestion
            severity: "warning" or "critical"
            case_sensitive: Whether matching is case sensitive
        """
        if not word.strip():
            return

        # Normalize case
        pattern = word if case_sensitive else word.lower()

        # Store pattern metadata
        self.patterns[pattern] = {
            "suggestion": suggestion or f"请避免使用'{word}'",
            "severity": severity,
            "original": word,
        }

        # Build trie
        node = self.root
        for char in pattern:
            if char not in node.children:
                node.children[char] = AhoCorasickNode()
            node = node.children[char]

        node.is_end = True
        node.output.append(pattern)
        self._built = False

    def add_patterns(self, words: list[dict[str, Any]]) -> None:
        """Add multiple patterns at once"""
        for word_data in words:
            self.add_pattern(
                word=word_data.get("phrase", ""),
                suggestion=word_data.get("suggested_alternative", ""),
                severity=word_data.get("severity", "warning"),
            )

    def build(self) -> None:
        """Build failure links using BFS"""
        if self._built:
            return

        # Build failure links using BFS
        queue = deque()

        # Initialize depth 1 nodes' fail links to root
        for char, node in self.root.children.items():
            node.fail_link = self.root
            queue.append(node)

        # BFS to build failure links for deeper nodes
        while queue:
            current = queue.popleft()

            for char, child in current.children.items():
                # Find fail link for child
                fail = current.fail_link
                while fail and char not in fail.children:
                    fail = fail.fail_link

                if fail:
                    child.fail_link = fail.children[char]
                    # Merge output from fail link
                    child.output.extend(child.fail_link.output)
                else:
                    child.fail_link = self.root

                queue.append(child)

        self._built = True
        logger.info(f"AhoCorasick automaton built with {len(self.patterns)} patterns")

    def find_matches(self, text: str) -> list[ForbiddenWordMatch]:
        """
        Find all forbidden word matches in text

        Args:
            text: Input text to search

        Returns:
            List of matches with position and metadata
        """
        if not self._built:
            self.build()

        if not text:
            return []

        matches = []
        text_lower = text.lower()

        node = self.root
        for i, char in enumerate(text_lower):
            # Follow fail links until we find a match or reach root
            while node and char not in node.children:
                node = node.fail_link

            if not node:
                node = self.root
                continue

            node = node.children[char]

            # Check for matches at this position
            for pattern in node.output:
                pattern_info = self.patterns.get(pattern, {})
                start_pos = i - len(pattern) + 1

                match = ForbiddenWordMatch(
                    word=pattern_info.get("original", pattern),
                    position=start_pos,
                    matched_text=text[start_pos : i + 1],
                    suggestion=pattern_info.get("suggestion", ""),
                    severity=pattern_info.get("severity", "warning"),
                )
                matches.append(match)

        return matches

    def has_match(self, text: str) -> bool:
        """Quick check if any pattern matches"""
        return len(self.find_matches(text)) > 0

    def get_unique_matches(self, text: str) -> list[ForbiddenWordMatch]:
        """
        Get unique matches (deduplicated by word)
        Returns only the first occurrence of each forbidden word
        """
        matches = self.find_matches(text)
        seen = set()
        unique = []

        for match in matches:
            if match.word not in seen:
                seen.add(match.word)
                unique.append(match)

        return unique

    def clear(self) -> None:
        """Clear all patterns and reset"""
        self.root = AhoCorasickNode()
        self.patterns.clear()
        self._built = False


class HybridForbiddenMatcher:
    """
    Hybrid matcher combining Aho-Corasick for exact matches
    and regex for pattern-based matches
    """

    def __init__(self):
        self.aho_matcher = AhoCorasickMatcher()
        self.regex_patterns: list[dict[str, Any]] = []
        self._fuzzy_enabled = False

    def add_words(self, words: list[dict[str, Any]]) -> None:
        """
        Add forbidden words

        Supports:
        - Exact text matching (Aho-Corasick)
        - Regex patterns (Python re)
        - Fuzzy matching (optional)
        """
        import re

        for word_data in words:
            phrase = word_data.get("phrase", "")
            is_regex = word_data.get("is_regex", False)

            if is_regex:
                # Store regex patterns separately
                try:
                    compiled = re.compile(phrase, re.IGNORECASE)
                    self.regex_patterns.append(
                        {
                            "pattern": compiled,
                            "phrase": phrase,
                            "suggestion": word_data.get("suggested_alternative", ""),
                            "severity": word_data.get("severity", "warning"),
                        }
                    )
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{phrase}': {e}")
            else:
                # Add to Aho-Corasick for exact matching
                self.aho_matcher.add_pattern(
                    word=phrase,
                    suggestion=word_data.get("suggested_alternative", ""),
                    severity=word_data.get("severity", "warning"),
                )

    def find_all_matches(self, text: str) -> list[ForbiddenWordMatch]:
        """Find all matches using both exact and regex matching"""
        matches = []

        # Aho-Corasick exact matches
        aho_matches = self.aho_matcher.find_matches(text)
        matches.extend(aho_matches)

        # Regex pattern matches
        for regex_data in self.regex_patterns:
            pattern = regex_data["pattern"]
            for match in pattern.finditer(text):
                matches.append(
                    ForbiddenWordMatch(
                        word=regex_data["phrase"],
                        position=match.start(),
                        matched_text=match.group(),
                        suggestion=regex_data["suggestion"],
                        severity=regex_data["severity"],
                    )
                )

        # Sort by position
        matches.sort(key=lambda m: m.position)

        return matches

    def get_unique_matches(self, text: str) -> list[ForbiddenWordMatch]:
        """Get unique matches by word"""
        matches = self.find_all_matches(text)
        seen = set()
        unique = []

        for match in matches:
            if match.word not in seen:
                seen.add(match.word)
                unique.append(match)

        return unique

    def clear(self) -> None:
        """Clear all patterns"""
        self.aho_matcher.clear()
        self.regex_patterns.clear()


# Singleton instance
_hybrid_matcher: HybridForbiddenMatcher | None = None


def get_hybrid_matcher() -> HybridForbiddenMatcher:
    """Get singleton hybrid matcher instance"""
    global _hybrid_matcher
    if _hybrid_matcher is None:
        _hybrid_matcher = HybridForbiddenMatcher()
    return _hybrid_matcher
