"""
Integration Tests for Persona API

Tests API endpoints for Persona management (admin).

References:
- Requirements: R3 (Persona Management)
- API Contract: docs/api-contract/personas.md
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.db.models import Base, User
from agent.models import Agent, AgentPersona, Persona
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.conversation.models import ConversationMessage

from main import app
from common.db.session import get_db


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
        email="test@example.com"
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
async def auth_headers(async_client):
    """Get authentication headers"""
    try:
        response = await async_client.post("/api/v1/auth/dev-login")
        if response.status_code == 200:
            data = response.json()
            token = data.get("data", {}).get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass
    return {"Authorization": "Bearer dev_test_token"}


@pytest_asyncio.fixture
async def sample_persona_data():
    """Sample data for creating a Persona"""
    return {
        "name": "怀疑型客户",
        "description": "对销售人员说的每句话都要求证据",
        "icon": "😤",
        "category": "customer",
        "difficulty": "hard",
        "system_prompt": "你是一个非常怀疑的客户...",
        "traits": {"性格": "怀疑", "关注点": "证据"},
        "knowledge_base_ids": ["kb-001"],
        "behavior_config": {
            "response_length": "medium",
            "challenge_frequency": 0.8,
            "interruption_triggers": ["竞品", "对比"],
            "typical_questions": ["你说的这个数据有什么依据？"]
        },
        "scoring_weights": {"专业度": 0.3, "异议处理": 0.4},
        "is_public": True
    }


class TestAdminPersonaAPI:
    """Tests for Admin Persona API - R3"""
    
    async def test_create_persona(self, async_client, auth_headers, sample_persona_data):
        """Should create Persona with active status - R3.1"""
        response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "怀疑型客户"
        assert data["data"]["status"] == "active"
        assert "id" in data["data"]
    
    async def test_list_personas(self, async_client, auth_headers, sample_persona_data):
        """Should list personas with pagination - R3.2"""
        await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/personas",
            json={**sample_persona_data, "name": "Persona 2"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/personas?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 2
        assert len(data["data"]["personas"]) == 2
    
    async def test_list_personas_filter_by_category(self, async_client, auth_headers, sample_persona_data):
        """Should filter personas by category - R3.2"""
        await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/personas",
            json={**sample_persona_data, "name": "Coach", "category": "coach"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/personas?category=customer",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
        assert data["data"]["personas"][0]["category"] == "customer"
    
    async def test_list_personas_filter_by_difficulty(self, async_client, auth_headers, sample_persona_data):
        """Should filter personas by difficulty - R3.2"""
        await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/personas",
            json={**sample_persona_data, "name": "Easy", "difficulty": "easy"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/personas?difficulty=hard",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
        assert data["data"]["personas"][0]["difficulty"] == "hard"
    
    async def test_get_persona(self, async_client, auth_headers, sample_persona_data):
        """Should get persona details - R3.3"""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]
        
        response = await async_client.get(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["system_prompt"] == "你是一个非常怀疑的客户..."
        assert data["data"]["traits"]["性格"] == "怀疑"
    
    async def test_update_persona(self, async_client, auth_headers, sample_persona_data):
        """Should update persona partially - R3.4"""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]
        
        response = await async_client.put(
            f"/api/v1/admin/personas/{persona_id}",
            json={"name": "Updated Name", "difficulty": "medium"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["difficulty"] == "medium"
    
    async def test_delete_persona(self, async_client, auth_headers, sample_persona_data):
        """Should delete persona without agent links - R3.5"""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]
        
        response = await async_client.delete(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True
        
        get_response = await async_client.get(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404
    
    async def test_delete_persona_in_use(self, async_client, auth_headers, sample_persona_data, db_session):
        """Should fail to delete persona linked to agent - R3.5"""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]
        
        agent = Agent(
            name="Test Agent",
            category="sales",
            status="draft"
        )
        db_session.add(agent)
        await db_session.flush()
        
        link = AgentPersona(
            agent_id=agent.id,
            persona_id=persona_id,
            display_order=0
        )
        db_session.add(link)
        await db_session.commit()
        
        response = await async_client.delete(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    async def test_duplicate_persona(self, async_client, auth_headers, sample_persona_data):
        """Should duplicate persona with suffix - R3.6"""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]
        
        response = await async_client.post(
            f"/api/v1/admin/personas/{persona_id}/duplicate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "怀疑型客户 (副本)"
        assert data["data"]["id"] != persona_id
    
    async def test_get_persona_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent persona"""
        response = await async_client.get(
            "/api/v1/admin/personas/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
