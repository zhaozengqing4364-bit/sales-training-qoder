"""
Unit tests for RealtimeScoringCapability
"""
from __future__ import annotations

import pytest
from datetime import datetime

from agent.capabilities.realtime_scoring import RealtimeScoringCapability
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
def capability() -> RealtimeScoringCapability:
    return RealtimeScoringCapability({"enabled": True})


class TestRealtimeScoringCapability:
    
    @pytest.mark.asyncio
    async def test_execute_with_valid_text_returns_overall_score(self, capability, context):
        """Should return overall score between 0-100 when executing with valid text"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(context, "这是一段测试文本")
        
        # Assert
        assert result.success is True
        assert "overall" in result.data
        assert 0 <= result.data["overall"] <= 100
    
    @pytest.mark.asyncio
    async def test_execute_with_valid_text_returns_dimension_scores(self, capability, context):
        """Should return 5 dimension scores with name, score, and trend"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(context, "测试文本")
        
        # Assert
        assert "dimensions" in result.data
        assert len(result.data["dimensions"]) == 5
        for dim in result.data["dimensions"]:
            assert "name" in dim
            assert "score" in dim
            assert "trend" in dim
    
    @pytest.mark.asyncio
    async def test_execute_with_positive_keywords_returns_higher_score(self, capability, context):
        """Should return higher scores when text contains positive keywords"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(
            context, 
            "根据数据和案例研究，我们的方案能提供价值"
        )
        
        # Assert
        assert result.success is True
        assert result.data["overall"] >= 70
    
    @pytest.mark.asyncio
    async def test_execute_with_negative_keywords_returns_success(self, capability, context):
        """Should return success even with negative keywords in text"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(
            context,
            "大概可能也许不太清楚"
        )
        
        # Assert
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_multiple_times_calculates_trend(self, capability, context):
        """Should calculate trend (up/down/stable) after multiple executions"""
        # Arrange
        await capability.on_session_start(context)
        await capability.execute(context, "普通文本")
        
        # Act
        result = await capability.execute(
            context,
            "根据数据案例，我们的方案有明确价值"
        )
        
        # Assert
        assert result.success is True
        for dim in result.data["dimensions"]:
            assert dim["trend"] in ["up", "down", "stable"]
    
    @pytest.mark.asyncio
    async def test_execute_with_any_text_returns_feedback(self, capability, context):
        """Should return non-empty feedback string"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(context, "测试")
        
        # Assert
        assert "feedback" in result.data
        assert len(result.data["feedback"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_multiple_times_tracks_score_history(self, capability, context):
        """Should track score history in context state"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        await capability.execute(context, "第一轮")
        await capability.execute(context, "第二轮")
        
        # Assert
        history = context.state.get("score_history", [])
        assert len(history) == 2
    
    @pytest.mark.asyncio
    async def test_on_session_end_returns_stats(self, capability, context):
        """Should return average_score and final_score on session end"""
        # Arrange
        await capability.on_session_start(context)
        await capability.execute(context, "测试")
        
        # Act
        stats = await capability.on_session_end(context)
        
        # Assert
        assert "average_score" in stats
        assert "final_score" in stats
    
    @pytest.mark.asyncio
    async def test_execute_with_dict_input_returns_success(self, capability, context):
        """Should handle dict input with content and role fields"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(
            context,
            {"content": "测试内容", "role": "user"}
        )
        
        # Assert
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_with_empty_input_returns_success(self, capability, context):
        """Should handle empty string input gracefully"""
        # Arrange
        await capability.on_session_start(context)
        
        # Act
        result = await capability.execute(context, "")
        
        # Assert
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_with_persona_weights_returns_success(self, context):
        """Should use Persona scoring weights if available in config"""
        # Arrange
        context.persona_config = {
            "scoring_weights": [
                {"name": "自定义维度", "weight": 1.0}
            ]
        }
        cap = RealtimeScoringCapability({"enabled": True})
        await cap.on_session_start(context)
        
        # Act
        result = await cap.execute(context, "测试")
        
        # Assert
        assert result.success is True
    
    def test_capability_metadata_returns_correct_values(self, capability):
        """Should return correct capability_id and name"""
        # Assert
        assert capability.capability_id == "realtime_scoring"
        assert capability.name == "实时评分"
