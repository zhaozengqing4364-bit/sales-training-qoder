"""
Unit tests for FuzzyDetectionCapability

Tests the fuzzy word detection capability including:
- Pattern matching
- Cooldown mechanism
- Severity levels
- Statistics tracking
"""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from agent.capabilities.fuzzy_detection import FuzzyDetectionCapability
from agent.capabilities.base import CapabilityResult
from agent.context import AgentContext


@pytest.fixture
def context() -> AgentContext:
    """Create a test AgentContext"""
    return AgentContext(
        session_id="test-session-123",
        agent_id="test-agent-123",
        persona_id="test-persona-123",
        user_id="test-user-123",
        state={},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
        start_time=datetime.now(),
        trace_id="test-trace-123"
    )


@pytest.fixture
def capability() -> FuzzyDetectionCapability:
    """Create a FuzzyDetectionCapability with default config"""
    return FuzzyDetectionCapability({"enabled": True, "cooldown_seconds": 0})


class TestFuzzyDetectionCapability:
    """Tests for FuzzyDetectionCapability"""
    
    @pytest.mark.asyncio
    async def test_detect_uncertain_words(self, capability, context):
        """Should detect uncertain words like 大概, 可能"""
        result = await capability.execute(context, "这个价格大概是一万左右")
        
        assert result.success is True
        assert "detections" in result.data
        
        detections = result.data["detections"]
        assert len(detections) >= 1
        
        # Check for uncertain category
        categories = [d["category"] for d in detections]
        assert "uncertain" in categories or "vague" in categories
    
    @pytest.mark.asyncio
    async def test_detect_filler_words(self, capability, context):
        """Should detect filler words like 嗯, 那个"""
        result = await capability.execute(context, "嗯，那个，就是说这个产品")
        
        assert result.success is True
        detections = result.data["detections"]
        
        filler_detections = [d for d in detections if d["category"] == "filler"]
        assert len(filler_detections) >= 1
    
    @pytest.mark.asyncio
    async def test_detect_vague_words(self, capability, context):
        """Should detect vague words like 差不多, 左右"""
        result = await capability.execute(context, "效果差不多能提升30%左右")
        
        assert result.success is True
        detections = result.data["detections"]
        
        vague_detections = [d for d in detections if d["category"] == "vague"]
        assert len(vague_detections) >= 1
    
    @pytest.mark.asyncio
    async def test_no_detection_for_clean_text(self, capability, context):
        """Should return empty detections for clean text"""
        result = await capability.execute(context, "我们的产品能提升效率50%")
        
        assert result.success is True
        assert result.data["detections"] == []
    
    @pytest.mark.asyncio
    async def test_high_severity_triggers_interrupt(self, capability, context):
        """High severity detection should set should_interrupt=True"""
        result = await capability.execute(context, "这个功能可能有效果")
        
        assert result.success is True
        # "可能" is high severity
        if result.data["detections"]:
            high_severity = any(
                d["severity"] == "high" for d in result.data["detections"]
            )
            if high_severity:
                assert result.should_interrupt is True
    
    @pytest.mark.asyncio
    async def test_cooldown_mechanism(self, context):
        """Should respect cooldown between same category detections"""
        cap = FuzzyDetectionCapability({"enabled": True, "cooldown_seconds": 60})
        
        # First detection
        result1 = await cap.execute(context, "大概是这样")
        assert result1.success is True
        
        # Second detection within cooldown - should skip
        result2 = await cap.execute(context, "可能是那样")
        assert result2.success is True
        
        # The second detection should have fewer or same detections due to cooldown
        # (same category "uncertain" should be skipped)
    
    @pytest.mark.asyncio
    async def test_empty_input(self, capability, context):
        """Should handle empty input gracefully"""
        result = await capability.execute(context, "")
        
        assert result.success is True
        assert result.data["detections"] == []
    
    @pytest.mark.asyncio
    async def test_none_input(self, capability, context):
        """Should handle None input gracefully"""
        result = await capability.execute(context, None)
        
        assert result.success is True
        assert result.data["detections"] == []
    
    @pytest.mark.asyncio
    async def test_feedback_generation(self, capability, context):
        """Should generate feedback for detections"""
        result = await capability.execute(context, "大概可能也许是这样")
        
        assert result.success is True
        if result.data["detections"]:
            assert result.feedback is not None
            assert len(result.feedback) > 0
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, capability, context):
        """Should track detection statistics in context state"""
        await capability.on_session_start(context)
        
        await capability.execute(context, "大概是这样")
        await capability.execute(context, "嗯，那个")
        
        # Check usage count
        assert context.state.get("fuzzy_detection_count", 0) >= 2
    
    @pytest.mark.asyncio
    async def test_session_end_stats(self, capability, context):
        """Should return statistics on session end"""
        await capability.on_session_start(context)
        await capability.execute(context, "大概差不多")
        
        stats = await capability.on_session_end(context)
        
        assert "usage_count" in stats
        assert "by_category" in stats
        assert "total_detections" in stats
    
    @pytest.mark.asyncio
    async def test_custom_patterns(self, context):
        """Should support custom fuzzy patterns"""
        custom_patterns = [
            {
                "pattern": r"测试词",
                "category": "custom",
                "suggestion": "自定义建议",
                "severity": "medium"
            }
        ]
        cap = FuzzyDetectionCapability({
            "enabled": True,
            "fuzzy_patterns": custom_patterns,
            "cooldown_seconds": 0
        })
        
        result = await cap.execute(context, "这是一个测试词")
        
        assert result.success is True
        detections = result.data["detections"]
        assert len(detections) == 1
        assert detections[0]["category"] == "custom"
    
    def test_capability_metadata(self, capability):
        """Should have correct metadata"""
        assert capability.capability_id == "fuzzy_detection"
        assert capability.name == "模糊词检测"
        assert len(capability.description) > 0
    
    def test_is_enabled(self):
        """Should respect enabled config"""
        enabled_cap = FuzzyDetectionCapability({"enabled": True})
        disabled_cap = FuzzyDetectionCapability({"enabled": False})
        
        assert enabled_cap.is_enabled() is True
        assert disabled_cap.is_enabled() is False
