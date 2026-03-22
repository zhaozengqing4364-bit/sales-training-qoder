"""
Tests for KeywordTrigger
"""
import pytest

from evaluation.triggers.keyword import KeywordTrigger
from evaluation.triggers.base_trigger import TriggerContext


class TestKeywordTrigger:
    """Tests for KeywordTrigger"""

    def test_keyword_match_any(self):
        """Test trigger fires when any keyword matches"""
        trigger = KeywordTrigger(
            keywords=["异议", "价格", "太贵"],
            cooldown_turns=0,
            match_mode="any"
        )

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            last_user_message="这个价格太贵了"
        )
        assert trigger.should_trigger(context) is True

        context.last_user_message = "我有异议"
        assert trigger.should_trigger(context) is True

        context.last_user_message = "价格是多少"
        assert trigger.should_trigger(context) is True

    def test_keyword_no_match(self):
        """Test trigger does not fire when no keywords match"""
        trigger = KeywordTrigger(
            keywords=["异议", "价格", "太贵"],
            cooldown_turns=0,
            match_mode="any"
        )

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            last_user_message="今天天气不错"
        )
        assert trigger.should_trigger(context) is False

    def test_keyword_cooldown(self):
        """Test cooldown prevents trigger"""
        trigger = KeywordTrigger(
            keywords=["异议"],
            cooldown_turns=3,
            match_mode="any"
        )

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            last_user_message="我有异议",
            turns_since_last_trigger=0
        )
        # Should not trigger during cooldown
        assert trigger.should_trigger(context) is False

        # Should trigger after cooldown
        context.turns_since_last_trigger = 4
        assert trigger.should_trigger(context) is True

    def test_empty_message(self):
        """Test trigger with empty message"""
        trigger = KeywordTrigger(keywords=["异议"])

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            last_user_message=None
        )
        assert trigger.should_trigger(context) is False

    def test_add_remove_keywords(self):
        """Test adding and removing keywords"""
        trigger = KeywordTrigger(keywords=["异议"])

        assert "测试" not in trigger.keywords
        trigger.add_keyword("测试")
        assert "测试" in trigger.keywords

        trigger.remove_keyword("测试")
        assert "测试" not in trigger.keywords

    def test_case_insensitive(self):
        """Test keyword matching is case insensitive"""
        trigger = KeywordTrigger(
            keywords=["Price", "OBJECTION"],
            cooldown_turns=0
        )

        context = TriggerContext(
            session_id="test",
            turn_count=1,
            messages=[],
            last_user_message="The price is too high"
        )
        assert trigger.should_trigger(context) is True

        context.last_user_message = "I have an objection"
        assert trigger.should_trigger(context) is True
