"""
Unit tests for KnowledgeRetrievalCapability
"""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from agent.capabilities.knowledge_retrieval import KnowledgeRetrievalCapability
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
        agent_config={
            "default_knowledge_base_ids": ["kb-1", "kb-2"]
        },
        persona_config={
            "knowledge_base_ids": ["kb-3"]
        },
        turn_count=1,
        start_time=datetime.now(),
        trace_id="test-trace-123"
    )


@pytest.fixture
def mock_knowledge_service():
    service = MagicMock()
    service.search = AsyncMock(return_value=[
        {"content": "测试内容1", "source": "文档1", "score": 0.9},
        {"content": "测试内容2", "source": "文档2", "score": 0.8}
    ])
    return service


@pytest.fixture
def capability(mock_knowledge_service) -> KnowledgeRetrievalCapability:
    cap = KnowledgeRetrievalCapability({"enabled": True})
    cap.set_knowledge_service(mock_knowledge_service)
    return cap


class TestKnowledgeRetrievalCapability:
    
    @pytest.mark.asyncio
    async def test_retrieves_knowledge(self, capability, context):
        await capability.on_session_start(context)
        result = await capability.execute(context, "查询内容")
        
        assert result.success is True
        assert "results" in result.data
        assert len(result.data["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_formats_context(self, capability, context):
        await capability.on_session_start(context)
        result = await capability.execute(context, "查询内容")
        
        assert "context" in result.data
        assert len(result.data["context"]) > 0
        assert "来源" in result.data["context"]
    
    @pytest.mark.asyncio
    async def test_merges_knowledge_base_ids(self, capability, context):
        await capability.on_session_start(context)
        result = await capability.execute(context, "查询")
        
        # Should have merged kb-1, kb-2, kb-3
        assert "kb_ids" in result.data
        assert len(result.data["kb_ids"]) == 3
    
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, capability, context):
        await capability.on_session_start(context)
        result = await capability.execute(context, "")
        
        assert result.success is True
        assert result.data["results"] == []
        assert result.data["context"] == ""
    
    @pytest.mark.asyncio
    async def test_no_knowledge_bases_configured(self, mock_knowledge_service):
        context = AgentContext(
            session_id="test",
            agent_id="test",
            persona_id="test",
            user_id="test",
            state={},
            conversation_history=[],
            agent_config={},
            persona_config={},
            turn_count=1,
            start_time=datetime.now(),
            trace_id="test"
        )
        cap = KnowledgeRetrievalCapability({"enabled": True})
        cap.set_knowledge_service(mock_knowledge_service)
        
        await cap.on_session_start(context)
        result = await cap.execute(context, "查询")
        
        assert result.success is True
        assert result.data["results"] == []
    
    @pytest.mark.asyncio
    async def test_no_knowledge_service(self, context):
        cap = KnowledgeRetrievalCapability({"enabled": True})
        # No service set
        
        await cap.on_session_start(context)
        result = await cap.execute(context, "查询")
        
        assert result.success is True
        assert result.data["results"] == []
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, context):
        service = MagicMock()
        service.search = AsyncMock(side_effect=Exception("Search failed"))
        
        cap = KnowledgeRetrievalCapability({"enabled": True})
        cap.set_knowledge_service(service)
        
        await cap.on_session_start(context)
        result = await cap.execute(context, "查询")
        
        # Should handle error gracefully
        assert result.success is True
        assert result.data["results"] == []
    
    @pytest.mark.asyncio
    async def test_top_k_limit(self, context):
        service = MagicMock()
        service.search = AsyncMock(return_value=[
            {"content": f"内容{i}", "source": f"文档{i}", "score": 0.9 - i*0.1}
            for i in range(10)
        ])
        
        cap = KnowledgeRetrievalCapability({
            "enabled": True,
            "top_k": 3
        })
        cap.set_knowledge_service(service)
        
        await cap.on_session_start(context)
        result = await cap.execute(context, "查询")
        
        assert len(result.data["results"]) <= 3
    
    @pytest.mark.asyncio
    async def test_session_end_stats(self, capability, context):
        await capability.on_session_start(context)
        await capability.execute(context, "查询1")
        await capability.execute(context, "查询2")
        
        stats = await capability.on_session_end(context)
        
        assert "total_retrievals" in stats
        assert stats["total_retrievals"] > 0
    
    @pytest.mark.asyncio
    async def test_deduplicates_kb_ids(self, mock_knowledge_service):
        context = AgentContext(
            session_id="test",
            agent_id="test",
            persona_id="test",
            user_id="test",
            state={},
            conversation_history=[],
            agent_config={"default_knowledge_base_ids": ["kb-1", "kb-2"]},
            persona_config={"knowledge_base_ids": ["kb-1", "kb-3"]},  # kb-1 duplicate
            turn_count=1,
            start_time=datetime.now(),
            trace_id="test"
        )
        cap = KnowledgeRetrievalCapability({"enabled": True})
        cap.set_knowledge_service(mock_knowledge_service)
        
        await cap.on_session_start(context)
        result = await cap.execute(context, "查询")
        
        # Should deduplicate kb-1
        assert len(result.data["kb_ids"]) == 3
    
    def test_capability_metadata(self, capability):
        assert capability.capability_id == "knowledge_retrieval"
        assert capability.name == "知识库检索"
