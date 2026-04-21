"""
Tests for TimeIntervalTrigger
"""
import time

from evaluation.triggers.base_trigger import TriggerContext
from evaluation.triggers.time_interval import TimeIntervalTrigger


class TestTimeIntervalTrigger:
    """Tests for TimeIntervalTrigger"""

    def test_first_trigger_after_interval(self):
        """Test first trigger after interval passes"""
        trigger = TimeIntervalTrigger(interval_seconds=1, cooldown_turns=0)

        start_time = time.time()
        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            start_time=start_time
        )

        # Should not trigger immediately
        assert trigger.should_trigger(context) is False

        # Wait for interval
        time.sleep(1.1)

        # Should trigger after interval
        assert trigger.should_trigger(context) is True

    def test_subsequent_triggers(self):
        """Test subsequent triggers after recording"""
        trigger = TimeIntervalTrigger(interval_seconds=0.5, cooldown_turns=0)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            start_time=time.time()
        )

        # Wait and first trigger
        time.sleep(0.6)
        assert trigger.should_trigger(context) is True
        trigger.record_trigger(1)

        # Should not trigger immediately after
        assert trigger.should_trigger(context) is False

        # Wait again
        time.sleep(0.6)
        assert trigger.should_trigger(context) is True

    def test_cooldown_with_time(self):
        """Test cooldown works with time trigger"""
        trigger = TimeIntervalTrigger(interval_seconds=0.5, cooldown_turns=2)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            start_time=time.time(),
            turns_since_last_trigger=0
        )

        # Wait for time interval
        time.sleep(0.6)

        # Should not trigger due to cooldown
        assert trigger.should_trigger(context) is False

        # After cooldown turns
        context.turns_since_last_trigger = 3
        assert trigger.should_trigger(context) is True

    def test_no_start_time(self):
        """Test behavior when no start time provided"""
        trigger = TimeIntervalTrigger(interval_seconds=1)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            start_time=None
        )

        # Should not trigger without start time on first call
        assert trigger.should_trigger(context) is False
