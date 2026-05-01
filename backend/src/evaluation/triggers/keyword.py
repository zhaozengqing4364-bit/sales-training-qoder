"""
Keyword Trigger

Triggers evaluation when specific keywords are detected in user messages.
"""

from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext


class KeywordTrigger(BaseTrigger):
    """
    Trigger evaluation when keywords are detected in conversation.

    Example: Trigger when user mentions "价格", "太贵", "异议"
    """

    def __init__(
        self, keywords: list[str], cooldown_turns: int = 3, match_mode: str = "any"
    ):
        """
        Initialize keyword trigger.

        Args:
            keywords: List of keywords to match
            cooldown_turns: Minimum turns between consecutive triggers
            match_mode: "any" (match any keyword) or "all" (match all keywords)
        """
        super().__init__(cooldown_turns=cooldown_turns)
        self.keywords = [kw.lower() for kw in keywords]
        self.match_mode = match_mode

    def should_trigger(self, context: TriggerContext) -> bool:
        """
        Check if keywords are present in last user message.

        Args:
            context: Current conversation context

        Returns:
            True if keywords match based on match_mode
        """
        # Check cooldown first
        if not self.check_cooldown(context):
            return False

        if not context.last_user_message:
            return False

        message = context.last_user_message.lower()

        if self.match_mode == "any":
            # Trigger if any keyword is found
            return any(kw in message for kw in self.keywords)
        elif self.match_mode == "all":
            # Trigger only if all keywords are found
            return all(kw in message for kw in self.keywords)

        return False

    def add_keyword(self, keyword: str) -> None:
        """Add a new keyword to the list"""
        keyword_lower = keyword.lower()
        if keyword_lower not in self.keywords:
            self.keywords.append(keyword_lower)

    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword from the list"""
        keyword_lower = keyword.lower()
        if keyword_lower in self.keywords:
            self.keywords.remove(keyword_lower)
