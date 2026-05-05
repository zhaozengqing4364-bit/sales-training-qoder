"""
Base Trigger Interface for Staged Evaluation

All triggers must inherit from BaseTrigger and implement should_trigger method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TriggerContext:
    """Context passed to triggers for evaluation"""

    session_id: str
    turn_count: int
    messages: list[dict[str, Any]]
    last_user_message: str | None = None
    last_bot_message: str | None = None
    turns_since_last_trigger: int = 0
    current_stage: str | None = None
    previous_stage: str | None = None
    start_time: float | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class BaseTrigger(ABC):
    """
    Base class for all evaluation triggers.

    Triggers determine when a staged evaluation should be performed.
    Each trigger type implements specific logic (turn count, time, keywords, etc.)
    """

    def __init__(self, cooldown_turns: int = 0):
        """
        Initialize trigger with cooldown mechanism.

        Args:
            cooldown_turns: Minimum turns between consecutive triggers
        """
        self.cooldown_turns = cooldown_turns
        self._last_trigger_turn: int = 0

    @abstractmethod
    def should_trigger(self, context: TriggerContext) -> bool:
        """
        Determine if evaluation should be triggered based on context.

        Args:
            context: Current conversation context

        Returns:
            True if evaluation should be triggered, False otherwise
        """
        pass

    def check_cooldown(self, context: TriggerContext) -> bool:
        """
        Check if enough turns have passed since last trigger.

        Args:
            context: Current conversation context

        Returns:
            True if cooldown period has passed, False otherwise
        """
        if self.cooldown_turns <= 0:
            return True
        return context.turns_since_last_trigger >= self.cooldown_turns

    def record_trigger(self, turn_number: int) -> None:
        """Record that trigger fired at given turn number"""
        self._last_trigger_turn = turn_number
