"""
Conversation model compatibility exports.

Canonical SQLAlchemy model definitions live in `common.db.models`.
This module keeps existing import paths stable for service/API code.
"""

from enum import StrEnum

from common.db.models import ConversationMessage


class MessageRole(StrEnum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"


class HighlightType(StrEnum):
    """Highlight classification for key moments."""

    GOOD = "good"
    BAD = "bad"
    NEUTRAL = "neutral"


__all__ = ["ConversationMessage", "MessageRole", "HighlightType"]
