"""
Turn Count Trigger

Triggers evaluation every N turns.
"""
from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext


class TurnCountTrigger(BaseTrigger):
    """
    Trigger evaluation based on turn count intervals.

    Example: Trigger every 5 turns (turns 5, 10, 15, ...)
    """

    def __init__(self, turn_interval: int = 5, cooldown_turns: int = 0):
        """
        Initialize turn count trigger.

        Args:
            turn_interval: Number of turns between evaluations
            cooldown_turns: Minimum turns between consecutive triggers
        """
        super().__init__(cooldown_turns=cooldown_turns)
        self.turn_interval = turn_interval

    def should_trigger(self, context: TriggerContext) -> bool:
        """
        Check if turn count matches interval.

        Args:
            context: Current conversation context

        Returns:
            True if turn_count is a multiple of turn_interval
        """
        # Check cooldown first
        if not self.check_cooldown(context):
            return False

        # Trigger at turn_interval, 2*turn_interval, 3*turn_interval, etc.
        if context.turn_count <= 0:
            return False

        return context.turn_count % self.turn_interval == 0
