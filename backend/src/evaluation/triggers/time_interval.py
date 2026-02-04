"""
Time Interval Trigger

Triggers evaluation every N minutes.
"""
import time

from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext


class TimeIntervalTrigger(BaseTrigger):
    """
    Trigger evaluation based on time intervals.

    Example: Trigger every 3 minutes
    """

    def __init__(self, interval_seconds: int = 180, cooldown_turns: int = 0):
        """
        Initialize time interval trigger.

        Args:
            interval_seconds: Time between evaluations in seconds
            cooldown_turns: Minimum turns between consecutive triggers
        """
        super().__init__(cooldown_turns=cooldown_turns)
        self.interval_seconds = interval_seconds
        self._last_trigger_time: float | None = None

    def should_trigger(self, context: TriggerContext) -> bool:
        """
        Check if enough time has passed since last trigger.

        Args:
            context: Current conversation context

        Returns:
            True if interval_seconds has passed since last trigger
        """
        # Check cooldown first
        if not self.check_cooldown(context):
            return False

        current_time = time.time()

        # First trigger
        if self._last_trigger_time is None:
            if context.start_time is not None:
                elapsed = current_time - context.start_time
                return elapsed >= self.interval_seconds
            return False

        # Subsequent triggers
        elapsed = current_time - self._last_trigger_time
        return elapsed >= self.interval_seconds

    def record_trigger(self, turn_number: int) -> None:
        """Record trigger time along with turn number"""
        super().record_trigger(turn_number)
        self._last_trigger_time = time.time()
