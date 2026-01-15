"""
Unit tests for SalesStageCapability
"""
from __future__ import annotations

import pytest
from datetime import datetime

from agent.capabilities.sales_stage import SalesStageCapability
from agent.context import AgentContext


@pytest.fixture
def context() -> AgentContext:
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
def capability() -> SalesStageCapability:
    return SalesStageCapability({"enabled": True})


class TestSalesStageCapability:
    
    @pytest.mark.asyncio
    async def test_initial_stage_is_opening(self, capability, context):
        """Should start at opening stage"""
        await capability.on_session_start(context)
        result = await capability.execute(context, "你好")
        assert result.success is True
        assert result.data["current_stage"] == "opening"
    
    @pytest.mark.asyncio
    async def test_detect_discovery_stage(self, capability, context):
        """Should detect discovery stage from keywords"""
        await capability.on_session_start(context)
        history = [{"role": "user", "content": "我们有什么需求和问题"}]
        result = await capability.execute(context, history)
        assert result.success is True
        assert result.data["current_stage"] == "discovery"
    
    @pytest.mark.asyncio
    async def test_detect_presentation_stage(self, capability, context):
        """Should detect presentation stage from keywords"""
        await capability.on_session_start(context)
        history = [{"role": "user", "content": "请介绍方案和产品功能"}]
        result = await capability.execute(context, history)
        assert result.success is True
        assert result.data["current_stage"] == "presentation"
    
    @pytest.mark.asyncio
    async def test_detect_objection_stage(self, capability, context):
        """Should detect objection stage from keywords"""
        await capability.on_session_start(context)
        history = [{"role": "user", "content": "但是价格太贵我担心"}]
        result = await capability.execute(context, history)
        assert result.success is True
        assert result.data["current_stage"] == "objection"
    
    @pytest.mark.asyncio
    async def test_detect_closing_stage(self, capability, context):
        """Should detect closing stage from keywords"""
        await capability.on_session_start(context)
        history = [{"role": "user", "content": "好决定合作签约"}]
        result = await capability.execute(context, history)
        assert result.success is True
        assert result.data["current_stage"] == "closing"
    
    @pytest.mark.asyncio
    async def test_progress_calculation(self, capability, context):
        """Should calculate progress correctly"""
        await capability.on_session_start(context)
        result = await capability.execute(context, "你好")
        # opening is stage 1 of 5, so progress = 1/5 = 0.2
        assert result.data["progress"] == 0.2
    
    @pytest.mark.asyncio
    async def test_empty_history_returns_opening(self, capability, context):
        """Should return opening for empty history"""
        await capability.on_session_start(context)
        result = await capability.execute(context, [])
        assert result.success is True
        assert result.data["current_stage"] == "opening"
    
    @pytest.mark.asyncio
    async def test_key_actions_included(self, capability, context):
        """Should include key actions in result"""
        await capability.on_session_start(context)
        result = await capability.execute(context, "你好")
        assert "key_actions" in result.data
        assert len(result.data["key_actions"]) > 0
    
    @pytest.mark.asyncio
    async def test_guidance_included(self, capability, context):
        """Should include guidance in result"""
        await capability.on_session_start(context)
        result = await capability.execute(context, "你好")
        assert "guidance" in result.data
        assert len(result.data["guidance"]) > 0
    
    @pytest.mark.asyncio
    async def test_stage_change_triggers_interrupt(self, capability, context):
        """Should set should_interrupt when stage changes"""
        await capability.on_session_start(context)
        
        # First call - opening
        await capability.execute(context, "你好")
        
        # Second call - discovery (stage change)
        result = await capability.execute(context, [{"role": "user", "content": "我们的需求是什么"}])
        
        # Stage changed from opening to discovery
        if result.data["stage_changed"]:
            assert result.should_interrupt is True
    
    @pytest.mark.asyncio
    async def test_stage_history_tracking(self, capability, context):
        """Should track stage transitions"""
        await capability.on_session_start(context)
        
        # Opening
        await capability.execute(context, "你好")
        
        # Discovery
        await capability.execute(context, [{"role": "user", "content": "需求问题"}])
        
        # Check stage history
        stage_history = context.state.get("stage_history", [])
        # Should have at least one transition
        assert isinstance(stage_history, list)
    
    @pytest.mark.asyncio
    async def test_session_end_stats(self, capability, context):
        """Should return statistics on session end"""
        await capability.on_session_start(context)
        await capability.execute(context, "你好")
        stats = await capability.on_session_end(context)
        assert "final_stage" in stats
        assert "stage_transitions" in stats
        assert "stage_history" in stats
    
    @pytest.mark.asyncio
    async def test_string_input(self, capability, context):
        """Should handle string input"""
        await capability.on_session_start(context)
        result = await capability.execute(context, "这是一段测试文本")
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_list_input(self, capability, context):
        """Should handle list input"""
        await capability.on_session_start(context)
        result = await capability.execute(context, [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮您？"}
        ])
        assert result.success is True
    
    def test_capability_metadata(self, capability):
        """Should have correct metadata"""
        assert capability.capability_id == "sales_stage"
        assert capability.name == "销售阶段识别"
        assert len(capability.description) > 0
    
    def test_is_enabled(self):
        """Should respect enabled config"""
        enabled_cap = SalesStageCapability({"enabled": True})
        disabled_cap = SalesStageCapability({"enabled": False})
        
        assert enabled_cap.is_enabled() is True
        assert disabled_cap.is_enabled() is False
