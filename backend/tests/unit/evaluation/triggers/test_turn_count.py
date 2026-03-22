"""
Tests for TurnCountTrigger
"""
import pytest

from evaluation.triggers.turn_count import TurnCountTrigger
from evaluation.triggers.base_trigger import TriggerContext


class TestTurnCountTrigger:
    """Tests for TurnCountTrigger"""

    def test_trigger_at_interval(self):
        """Test trigger fires at turn interval"""
        trigger = TurnCountTrigger(turn_interval=5)

        # Should not trigger at turn 0
        context = TriggerContext(
            session_id="test",
            turn_count=0,
            messages=[]
        )
        assert trigger.should_trigger(context) is False

        # Should not trigger at turn 4
        context.turn_count = 4
        assert trigger.should_trigger(context) is False

        # Should trigger at turn 5
        context.turn_count = 5
        assert trigger.should_trigger(context) is True

        # Should trigger at turn 10
        context.turn_count = 10
        assert trigger.should_trigger(context) is True

    def test_cooldown_prevents_trigger(self):
        """Test cooldown prevents premature triggers"""
        trigger = TurnCountTrigger(turn_interval=5, cooldown_turns=3)

        # First trigger at turn 5 (cooldown of 3 turns, 0 turns since last trigger)
        # Since this is the first trigger, we need turns_since_last_trigger >= 3
        context = TriggerContext(
            session_id="test",
            turn_count=5,
            messages=[],
            turns_since_last_trigger=3
        )
        assert trigger.should_trigger(context) is True

        # Record trigger
        trigger.record_trigger(5)

        # Should trigger at turn 10 with sufficient cooldown (5 turns since last)
        context.turn_count = 10
        context.turns_since_last_trigger = 5
        assert trigger.should_trigger(context) is True  # 5 >= 3

        # Should not trigger at turn 10 with insufficient cooldown
        context.turns_since_last_trigger = 2
        assert trigger.should_trigger(context) is False

    def test_different_intervals(self):
        """Test different interval values"""
        # Interval of 1
        trigger1 = TurnCountTrigger(turn_interval=1)
        context = TriggerContext(session_id="test", turn_count=1, messages=[])
        assert trigger1.should_trigger(context) is True

        # Interval of 10
        trigger10 = TurnCountTrigger(turn_interval=10)
        context.turn_count = 5
        assert trigger10.should_trigger(context) is False
        context.turn_count = 10
        assert trigger10.should_trigger(context) is True
