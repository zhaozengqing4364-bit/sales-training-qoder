"""
Integration Tests for Agent API

Tests API endpoints for Agent management (admin and user).

References:
- Requirements: R1, R2 (Agent Management)
- API Contract: docs/api-contract/agents.md
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with Base.metadata
from common.db.models import Base, User, Scenario
from agent.models import Agent, AgentPersona, Persona
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.conversation.models import ConversationMessage

from main import app
from common.db.session import get_db


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine with all tables"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
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
async def test_user(db_session):
    """Create a test user"""
    user = User(
        wechat_user_id="test_wechat_id",
        name="Test User",
        email="test@example.com",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def async_client(db_session, test_user):
    """Create async HTTP client for testing"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(test_user):
    """Get authentication headers for admin fixture user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def non_admin_user(db_session):
    """Create a non-admin user for RBAC tests."""
    user = User(
        wechat_user_id="normal_wechat_id",
        name="Normal User",
        email="normal@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def non_admin_headers(non_admin_user):
    """JWT auth header for non-admin user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(non_admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_agent_data():
    """Sample data for creating an Agent"""
    return {
        "name": "销售教练",
        "description": "帮助销售人员提升沟通技巧的 AI 教练",
        "icon": "🎯",
        "category": "sales",
        "welcome_message": "你好！准备好练习了吗？",
        "capabilities_config": {
            "asr": {"enabled": True, "mode": "manual"},
            "tts": {"enabled": True, "voice": "zh-CN-YunxiNeural"},
            "fuzzy_detection": {"enabled": True}
        }
    }


class TestAdminAgentAPI:
    """Tests for Admin Agent API - R1"""
    
    async def test_create_agent(self, async_client, auth_headers, sample_agent_data):
        """Should create Agent with draft status - R1.1"""
        response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "销售教练"
        assert data["data"]["status"] == "draft"
        assert "id" in data["data"]
        assert "created_at" in data["data"]

    async def test_create_agent_rejects_unsupported_category(
        self, async_client, auth_headers, sample_agent_data
    ):
        """Should reject unsupported agent categories."""
        response = await async_client.post(
            "/api/v1/admin/agents",
            json={**sample_agent_data, "category": "customer_service"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "[AGENT_CATEGORY_RESTRICTED]" in response.text

    async def test_admin_routes_require_admin_role(
        self,
        async_client,
        non_admin_headers,
        sample_agent_data,
    ):
        """Should reject non-admin access for admin agent routes."""
        response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=non_admin_headers,
        )

        assert response.status_code == 403
    
    async def test_list_agents_admin(self, async_client, auth_headers, sample_agent_data):
        """Should list agents with pagination - R1.2"""
        # Create some agents
        await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/agents",
            json={**sample_agent_data, "name": "Agent 2"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/agents?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 2
        assert len(data["data"]["agents"]) == 2
    
    async def test_list_agents_filter_by_category(self, async_client, auth_headers, sample_agent_data):
        """Should filter agents by category - R1.2"""
        # Create agents with different categories
        await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/agents",
            json={**sample_agent_data, "name": "Presentation Coach", "category": "presentation"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/agents?category=sales",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
        assert data["data"]["agents"][0]["category"] == "sales"
    
    async def test_get_agent_admin(self, async_client, auth_headers, sample_agent_data):
        """Should get agent details with system_prompt - R1.3"""
        # Create agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.get(
            f"/api/v1/admin/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["system_prompt"] is None
        assert data["data"]["capabilities_config"]["asr"]["enabled"] is True

    async def test_create_agent_rejects_deprecated_fields(
        self, async_client, auth_headers, sample_agent_data
    ):
        response = await async_client.post(
            "/api/v1/admin/agents",
            json={**sample_agent_data, "default_knowledge_base_ids": ["kb-001"]},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "[FIELD_DEPRECATED_PERSONA_CENTERED]" in response.text
    
    async def test_update_agent(self, async_client, auth_headers, sample_agent_data):
        """Should update agent partially - R1.4"""
        # Create agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.put(
            f"/api/v1/admin/agents/{agent_id}",
            json={"name": "Updated Name"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"

    async def test_update_agent_rejects_unsupported_category(
        self, async_client, auth_headers, sample_agent_data
    ):
        """Should reject unsupported category updates."""
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers,
        )
        agent_id = create_response.json()["data"]["id"]

        response = await async_client.put(
            f"/api/v1/admin/agents/{agent_id}",
            json={"category": "interview"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "[AGENT_CATEGORY_RESTRICTED]" in response.text

    async def test_update_agent_persists_across_sessions(
        self,
        async_client,
        auth_headers,
        sample_agent_data,
        test_engine,
    ):
        """Should persist agent update to DB across independent sessions."""
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers,
        )
        agent_id = create_response.json()["data"]["id"]

        new_description = "跨会话持久化智能体描述"
        update_response = await async_client.put(
            f"/api/v1/admin/agents/{agent_id}",
            json={"description": new_description},
            headers=auth_headers,
        )
        assert update_response.status_code == 200

        verify_sessionmaker = sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with verify_sessionmaker() as verify_session:
            row = await verify_session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = row.scalar_one()
            assert agent.description == new_description
    
    async def test_publish_agent(self, async_client, auth_headers, sample_agent_data):
        """Should publish agent - R1.5"""
        # Create agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.post(
            f"/api/v1/admin/agents/{agent_id}/publish",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "published"
        assert "published_at" in data["data"]
    
    async def test_archive_agent(self, async_client, auth_headers, sample_agent_data):
        """Should archive agent - R1.6"""
        # Create agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.post(
            f"/api/v1/admin/agents/{agent_id}/archive",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "archived"
    
    async def test_delete_agent(self, async_client, auth_headers, sample_agent_data):
        """Should delete agent without sessions - R1.7"""
        # Create agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.delete(
            f"/api/v1/admin/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True
        
        # Verify deleted
        get_response = await async_client.get(
            f"/api/v1/admin/agents/{agent_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404
    
    async def test_get_agent_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent agent"""
        response = await async_client.get(
            "/api/v1/admin/agents/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestUserAgentAPI:
    """Tests for User Agent API - R2"""
    
    async def test_list_agents_user_only_published(self, async_client, auth_headers, sample_agent_data):
        """Should only return published agents - R2.1"""
        # Create draft agent
        await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        
        # Create and publish another agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json={**sample_agent_data, "name": "Published Agent"},
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        await async_client.post(
            f"/api/v1/admin/agents/{agent_id}/publish",
            headers=auth_headers
        )
        
        # User list should only show published
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
        assert data["data"]["agents"][0]["name"] == "Published Agent"
    
    async def test_get_agent_user_no_system_prompt(self, async_client, auth_headers, sample_agent_data):
        """Should not include system_prompt in user view - R2.2"""
        # Create and publish agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        await async_client.post(
            f"/api/v1/admin/agents/{agent_id}/publish",
            headers=auth_headers
        )
        
        response = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # User response should not have system_prompt
        assert "system_prompt" not in data["data"] or data["data"].get("system_prompt") is None
        assert data["data"]["welcome_message"] == "你好！准备好练习了吗？"
    
    async def test_get_agent_user_draft_not_found(self, async_client, auth_headers, sample_agent_data):
        """Should not find draft agents in user view - R2.2"""
        # Create draft agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        response = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    async def test_get_agent_personas(self, async_client, auth_headers, sample_agent_data, db_session):
        """Should return associated personas - R2.3"""
        # Create and publish agent
        create_response = await async_client.post(
            "/api/v1/admin/agents",
            json=sample_agent_data,
            headers=auth_headers
        )
        agent_id = create_response.json()["data"]["id"]
        
        # Create personas and link them
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
        await db_session.commit()
        
        response = await async_client.get(
            f"/api/v1/agents/{agent_id}/personas",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        personas = data["data"]["personas"]
        assert len(personas) == 2
        # Should be sorted by display_order
        assert personas[0]["name"] == "价格敏感型"
        assert personas[0]["is_default"] is True
