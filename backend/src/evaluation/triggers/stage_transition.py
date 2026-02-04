"""
Stage Transition Trigger

Triggers evaluation when conversation stage changes.
"""
from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext


class StageTransitionTrigger(BaseTrigger):
    """
    Trigger evaluation when conversation stage transitions.

    Example: Trigger when moving from "discovery" to "presentation"
    """

    def __init__(
        self,
        from_stages: list[str] | None = None,
        to_stages: list[str] | None = None,
        cooldown_turns: int = 1
    ):
        """
        Initialize stage transition trigger.

        Args:
            from_stages: List of source stages to match (None = any)
            to_stages: List of target stages to match (None = any)
            cooldown_turns: Minimum turns between consecutive triggers
        """
        super().__init__(cooldown_turns=cooldown_turns)
        self.from_stages = from_stages
        self.to_stages = to_stages
        self._previous_stage: str | None = None

    def should_trigger(self, context: TriggerContext) -> bool:
        """
        Check if stage has transitioned.

        Args:
            context: Current conversation context

        Returns:
            True if stage transition matches criteria
        """
        # Check cooldown first
        if not self.check_cooldown(context):
            return False

        current = context.current_stage
        previous = context.previous_stage

        # No transition if no current stage
        if not current:
            return False

        # No transition if same stage
        if current == previous:
            return False

        # Check from_stages filter
        if self.from_stages is not None:
            if previous not in self.from_stages:
                return False

        # Check to_stages filter
        if self.to_stages is not None:
            if current not in self.to_stages:
                return False

        return True

    def update_stage(self, stage: str | None) -> None:
        """Update the tracked previous stage"""
        self._previous_stage = stage
