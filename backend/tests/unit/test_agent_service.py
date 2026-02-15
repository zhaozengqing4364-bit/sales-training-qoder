"""
Unit Tests for Agent Service

Tests CRUD operations, lifecycle management, and persona associations.

References:
- Requirements: R1, R2 (Agent Management)
- Design: Section 4 (Agent Service)
"""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Base first
from common.db.models import Base, PracticeSession, User, Scenario

# Import all models to ensure they're registered with Base.metadata
# These imports must happen BEFORE Base.metadata.create_all is called
from agent.models import Agent, AgentPersona, AgentStatus, Persona
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.conversation.models import ConversationMessage

from agent.schemas import CreateAgentRequest, UpdateAgentRequest
from agent.services.agent_service import AgentService


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine with all tables"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Ensure all models are imported before creating tables
    # The imports above should have registered all models with Base.metadata
    async with engine.begin() as conn:
        # Create all tables in dependency order
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Create test database session"""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def agent_service(db_session):
    """Create AgentService instance"""
    return AgentService(db_session)


@pytest_asyncio.fixture
async def sample_agent_data():
    """Sample data for creating an Agent"""
    return CreateAgentRequest(
        name="销售教练",
        description="帮助销售人员提升沟通技巧的 AI 教练",
        icon="🎯",
        category="sales",
        system_prompt="你是一位资深销售教练...",
        welcome_message="你好！准备好练习了吗？",
        capabilities_config={
            "asr": {"enabled": True, "mode": "manual"},
            "tts": {"enabled": True, "voice": "zh-CN-YunxiNeural"},
            "fuzzy_detection": {"enabled": True}
        },
        default_knowledge_base_ids=["kb-001"]
    )


class TestAgentServiceCreate:
    """Tests for Agent creation - R1.1"""
    
    async def test_create_agent_success(self, agent_service, sample_agent_data):
        """Should create Agent with draft status"""
        result = await agent_service.create(sample_agent_data, user_id="user-001")
        
        assert result.is_success
        agent = result.value
        assert agent.name == "销售教练"
        assert agent.status == AgentStatus.DRAFT.value
        assert agent.category == "sales"
        assert agent.created_by == "user-001"
        assert agent.id is not None
    
    async def test_create_agent_with_minimal_data(self, agent_service):
        """Should create Agent with minimal required fields"""
        data = CreateAgentRequest(
            name="Minimal Agent",
            category="presentation"
        )
        
        result = await agent_service.create(data)
        
        assert result.is_success
        agent = result.value
        assert agent.name == "Minimal Agent"
        assert agent.status == AgentStatus.DRAFT.value
        assert agent.capabilities_config == {}
        assert agent.default_knowledge_base_ids == []

    async def test_create_agent_rejects_unsupported_category(self, agent_service):
        """Should reject creating unsupported category agents"""
        data = CreateAgentRequest(
            name="客服训练",
            category="customer_service"
        )

        result = await agent_service.create(data)

        assert not result.is_success
        assert result.fallback == "[AGENT_CATEGORY_RESTRICTED]"


class TestAgentServiceList:
    """Tests for Agent listing - R1.2, R2.1"""
    
    async def test_list_agents_empty(self, agent_service):
        """Should return empty list when no agents exist"""
        items, total = await agent_service.list()
        
        assert items == []
        assert total == 0
    
    async def test_list_agents_with_pagination(self, agent_service, sample_agent_data):
        """Should return paginated results"""
        # Create multiple agents
        for i in range(5):
            data = CreateAgentRequest(
                name=f"Agent {i}",
                category="sales"
            )
            await agent_service.create(data)
        
        # Get first page
        items, total = await agent_service.list(page=1, page_size=2, admin=True)
        
        assert len(items) == 2
        assert total == 5
    
    async def test_list_agents_filter_by_category(self, agent_service):
        """Should filter by category"""
        # Create agents with different categories
        await agent_service.create(CreateAgentRequest(name="Sales 1", category="sales"))
        await agent_service.create(CreateAgentRequest(name="Presentation 1", category="presentation"))
        
        items, total = await agent_service.list(category="sales", admin=True)
        
        assert total == 1
        assert items[0].category == "sales"
    
    async def test_list_agents_filter_by_status(self, agent_service, sample_agent_data):
        """Should filter by status (admin only)"""
        # Create and publish one agent
        result = await agent_service.create(sample_agent_data)
        await agent_service.publish(result.value.id)
        
        # Create another draft agent
        await agent_service.create(CreateAgentRequest(name="Draft Agent", category="sales"))
        
        # Filter by published
        items, total = await agent_service.list(status="published", admin=True)
        
        assert total == 1
        assert items[0].status == "published"
    
    async def test_list_agents_user_only_published(self, agent_service, sample_agent_data):
        """User endpoint should only return published agents"""
        # Create draft agent
        await agent_service.create(sample_agent_data)
        
        # User list should be empty (no published)
        items, total = await agent_service.list(admin=False)
        
        assert total == 0


class TestAgentServiceGetById:
    """Tests for getting Agent by ID - R1.3, R2.2"""
    
    async def test_get_agent_admin(self, agent_service, sample_agent_data):
        """Admin should get full Agent with system_prompt"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.get_by_id(agent_id, admin=True)
        
        assert result.is_success
        agent = result.value
        assert agent.system_prompt == "你是一位资深销售教练..."
    
    async def test_get_agent_user_published(self, agent_service, sample_agent_data):
        """User should get published Agent without system_prompt"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        await agent_service.publish(agent_id)
        
        result = await agent_service.get_by_id(agent_id, admin=False)
        
        assert result.is_success
        # User response doesn't have system_prompt attribute
        assert not hasattr(result.value, 'system_prompt') or result.value.system_prompt is None
    
    async def test_get_agent_user_draft_not_found(self, agent_service, sample_agent_data):
        """User should not see draft agents"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.get_by_id(agent_id, admin=False)
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"
    
    async def test_get_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        result = await agent_service.get_by_id("non-existent-id")
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"


class TestAgentServiceUpdate:
    """Tests for Agent update - R1.4"""
    
    async def test_update_agent_partial(self, agent_service, sample_agent_data):
        """Should support partial updates"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        update_data = UpdateAgentRequest(name="Updated Name")
        result = await agent_service.update(agent_id, update_data)
        
        assert result.is_success
        assert result.value.name == "Updated Name"
        # Other fields unchanged
        assert result.value.category == "sales"
    
    async def test_update_agent_capabilities_config(self, agent_service, sample_agent_data):
        """Should update capabilities_config"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        new_config = {"scoring": {"enabled": True, "dimensions": []}}
        update_data = UpdateAgentRequest(capabilities_config=new_config)
        result = await agent_service.update(agent_id, update_data)
        
        assert result.is_success
        assert result.value.capabilities_config == new_config
    
    async def test_update_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        update_data = UpdateAgentRequest(name="New Name")
        result = await agent_service.update("non-existent-id", update_data)
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"

    async def test_update_agent_rejects_unsupported_category(
        self, agent_service, sample_agent_data
    ):
        """Should reject updating to unsupported categories"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id

        update_data = UpdateAgentRequest(category="interview")
        result = await agent_service.update(agent_id, update_data)

        assert not result.is_success
        assert result.fallback == "[AGENT_CATEGORY_RESTRICTED]"


class TestAgentServiceDelete:
    """Tests for Agent deletion - R1.7"""
    
    async def test_delete_agent_success(self, agent_service, sample_agent_data):
        """Should delete agent without sessions"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.delete(agent_id)
        
        assert result.is_success
        assert result.value is True
        
        # Verify deleted
        get_result = await agent_service.get_by_id(agent_id, admin=True)
        assert not get_result.is_success
    
    async def test_delete_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        result = await agent_service.delete("non-existent-id")
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"
    
    async def test_delete_agent_with_sessions_fails(self, agent_service, sample_agent_data, db_session):
        """Should fail to delete agent with associated sessions"""
        # Create agent
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        # Create user and scenario for session
        user = User(
            wechat_user_id="test_wechat_id",
            name="Test User"
        )
        db_session.add(user)
        await db_session.flush()
        
        scenario = Scenario(
            scenario_type="sales",
            name="Test Scenario"
        )
        db_session.add(scenario)
        await db_session.flush()
        
        # Create session linked to agent
        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            agent_id=agent_id
        )
        db_session.add(session)
        await db_session.flush()
        
        # Try to delete
        result = await agent_service.delete(agent_id)
        
        assert not result.is_success
        assert result.fallback == "[AGENT_CANNOT_DELETE]"


class TestAgentServicePublish:
    """Tests for Agent publishing - R1.5"""
    
    async def test_publish_agent_success(self, agent_service, sample_agent_data):
        """Should publish draft agent"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.publish(agent_id)
        
        assert result.is_success
        assert result.value.status == AgentStatus.PUBLISHED.value
        assert result.value.published_at is not None
    
    async def test_publish_agent_already_published(self, agent_service, sample_agent_data):
        """Should fail if already published"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        await agent_service.publish(agent_id)
        
        result = await agent_service.publish(agent_id)
        
        assert not result.is_success
        assert result.fallback == "[AGENT_ALREADY_PUBLISHED]"
    
    async def test_publish_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        result = await agent_service.publish("non-existent-id")
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"


class TestAgentServiceArchive:
    """Tests for Agent archiving - R1.6"""
    
    async def test_archive_agent_success(self, agent_service, sample_agent_data):
        """Should archive agent"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.archive(agent_id)
        
        assert result.is_success
        assert result.value.status == AgentStatus.ARCHIVED.value
    
    async def test_archive_published_agent(self, agent_service, sample_agent_data):
        """Should archive published agent"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        await agent_service.publish(agent_id)
        
        result = await agent_service.archive(agent_id)
        
        assert result.is_success
        assert result.value.status == AgentStatus.ARCHIVED.value
    
    async def test_archive_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        result = await agent_service.archive("non-existent-id")
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"


class TestAgentServiceGetPersonas:
    """Tests for getting Agent's Personas - R2.3"""
    
    async def test_get_personas_empty(self, agent_service, sample_agent_data):
        """Should return empty list when no personas linked"""
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        result = await agent_service.get_personas(agent_id)
        
        assert result.is_success
        assert result.value == []
    
    async def test_get_personas_with_linked(self, agent_service, sample_agent_data, db_session):
        """Should return linked personas sorted by display_order"""
        # Create agent
        create_result = await agent_service.create(sample_agent_data)
        agent_id = create_result.value.id
        
        # Create personas
        persona1 = Persona(
            name="怀疑型客户",
            description="对销售人员说的每句话都要求证据",
            category="customer",
            difficulty="hard",
            system_prompt="你是一个怀疑型客户...",
            status="active"
        )
        persona2 = Persona(
            name="价格敏感型",
            description="只关心价格",
            category="customer",
            difficulty="medium",
            system_prompt="你是一个价格敏感型客户...",
            status="active"
        )
        db_session.add_all([persona1, persona2])
        await db_session.flush()
        
        # Link personas to agent
        link1 = AgentPersona(
            agent_id=agent_id,
            persona_id=persona1.id,
            display_order=2,
            is_default=False
        )
        link2 = AgentPersona(
            agent_id=agent_id,
            persona_id=persona2.id,
            display_order=1,
            is_default=True
        )
        db_session.add_all([link1, link2])
        await db_session.flush()
        
        result = await agent_service.get_personas(agent_id)
        
        assert result.is_success
        personas = result.value
        assert len(personas) == 2
        # Should be sorted by display_order
        assert personas[0].name == "价格敏感型"
        assert personas[0].is_default is True
        assert personas[1].name == "怀疑型客户"
    
    async def test_get_personas_agent_not_found(self, agent_service):
        """Should return error for non-existent agent"""
        result = await agent_service.get_personas("non-existent-id")
        
        assert not result.is_success
        assert result.fallback == "[AGENT_NOT_FOUND]"


class TestAgentServiceCapabilityNames:
    """Tests for capability name extraction"""
    
    async def test_extract_capability_names(self, agent_service):
        """Should extract enabled capability display names"""
        config = {
            "asr": {"enabled": True},
            "tts": {"enabled": False},
            "fuzzy_detection": {"enabled": True},
            "scoring": {"enabled": True}
        }
        
        names = agent_service._extract_capability_names(config)
        
        assert "语音识别" in names
        assert "模糊词检测" in names
        assert "实时评分" in names
        assert "语音合成" not in names  # disabled
    
    async def test_extract_capability_names_empty(self, agent_service):
        """Should return empty list for empty config"""
        names = agent_service._extract_capability_names({})
        assert names == []
        
        names = agent_service._extract_capability_names(None)
        assert names == []
