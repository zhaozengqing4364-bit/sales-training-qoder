"""
Tests for StageTransitionTrigger
"""
import pytest

from evaluation.triggers.stage_transition import StageTransitionTrigger
from evaluation.triggers.base_trigger import TriggerContext


class TestStageTransitionTrigger:
    """Tests for StageTransitionTrigger"""

    def test_any_transition(self):
        """Test trigger fires on any stage transition"""
        trigger = StageTransitionTrigger(cooldown_turns=0)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="presentation",
            previous_stage="discovery"
        )
        assert trigger.should_trigger(context) is True

    def test_no_transition_same_stage(self):
        """Test trigger does not fire when stage unchanged"""
        trigger = StageTransitionTrigger(cooldown_turns=0)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="presentation",
            previous_stage="presentation"
        )
        assert trigger.should_trigger(context) is False

    def test_no_current_stage(self):
        """Test trigger does not fire without current stage"""
        trigger = StageTransitionTrigger(cooldown_turns=0)

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage=None,
            previous_stage="discovery"
        )
        assert trigger.should_trigger(context) is False

    def test_from_stage_filter(self):
        """Test trigger respects from_stages filter"""
        trigger = StageTransitionTrigger(
            from_stages=["discovery"],
            cooldown_turns=0
        )

        # Should trigger when coming from discovery
        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="presentation",
            previous_stage="discovery"
        )
        assert trigger.should_trigger(context) is True

        # Should not trigger when coming from opening
        context.previous_stage = "opening"
        assert trigger.should_trigger(context) is False

    def test_to_stage_filter(self):
        """Test trigger respects to_stages filter"""
        trigger = StageTransitionTrigger(
            to_stages=["closing"],
            cooldown_turns=0
        )

        # Should trigger when going to closing
        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="closing",
            previous_stage="objection"
        )
        assert trigger.should_trigger(context) is True

        # Should not trigger when going to presentation
        context.current_stage = "presentation"
        assert trigger.should_trigger(context) is False

    def test_both_filters(self):
        """Test trigger with both from and to filters"""
        trigger = StageTransitionTrigger(
            from_stages=["discovery"],
            to_stages=["presentation"],
            cooldown_turns=0
        )

        # Should trigger on discovery -> presentation
        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="presentation",
            previous_stage="discovery"
        )
        assert trigger.should_trigger(context) is True

        # Should not trigger on opening -> presentation
        context.previous_stage = "opening"
        assert trigger.should_trigger(context) is False

        # Should not trigger on discovery -> objection
        context.previous_stage = "discovery"
        context.current_stage = "objection"
        assert trigger.should_trigger(context) is False

    def test_cooldown(self):
        """Test cooldown prevents trigger"""
        trigger = StageTransitionTrigger(
            cooldown_turns=2
        )

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            current_stage="presentation",
            previous_stage="discovery",
            turns_since_last_trigger=0
        )

        # Should not trigger during cooldown
        assert trigger.should_trigger(context) is False

        # Should trigger after cooldown
        context.turns_since_last_trigger = 3
        assert trigger.should_trigger(context) is True

    def test_update_stage(self):
        """Test update_stage method"""
        trigger = StageTransitionTrigger()

        assert trigger._previous_stage is None
        trigger.update_stage("discovery")
        assert trigger._previous_stage == "discovery"
