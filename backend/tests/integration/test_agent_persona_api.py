"""
Integration Tests for Agent-Persona Association API

Tests API endpoints for managing Agent-Persona relationships.

References:
- Requirements: R4 (Agent-Persona Association)
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
async def test_agent(async_client, auth_headers):
    """Create a test agent"""
    response = await async_client.post(
        "/api/v1/admin/agents",
        json={
            "name": "Test Agent",
            "category": "sales",
            "system_prompt": "Test prompt"
        },
        headers=auth_headers
    )
    return response.json()["data"]


@pytest_asyncio.fixture
async def test_persona(async_client, auth_headers):
    """Create a test persona"""
    response = await async_client.post(
        "/api/v1/admin/personas",
        json={
            "name": "Test Persona",
            "category": "customer",
            "system_prompt": "Test persona prompt"
        },
        headers=auth_headers
    )
    return response.json()["data"]


class TestAgentPersonaAPI:
    """Tests for Agent-Persona Association API - R4"""
    
    async def test_add_persona_to_agent(
        self, async_client, auth_headers, test_agent, test_persona
    ):
        """Should add persona to agent - R4.1"""
        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={
                "persona_id": test_persona["id"],
                "display_order": 1,
                "is_default": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == test_agent["id"]
        assert data["data"]["persona_id"] == test_persona["id"]
        assert data["data"]["is_default"] is True
    
    async def test_add_persona_already_linked(
        self, async_client, auth_headers, test_agent, test_persona
    ):
        """Should fail when persona already linked - R4.1"""
        # First link
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers
        )
        
        # Try to link again
        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    async def test_list_agent_personas(
        self, async_client, auth_headers, test_agent, test_persona
    ):
        """Should list personas linked to agent - R4.2"""
        # Link persona
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"], "display_order": 1},
            headers=auth_headers
        )
        
        response = await async_client.get(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["personas"]) == 1
        assert data["data"]["personas"][0]["persona"]["name"] == "Test Persona"
    
    async def test_update_agent_persona(
        self, async_client, auth_headers, test_agent, test_persona
    ):
        """Should update agent-persona association - R4.3"""
        # Link persona
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"], "display_order": 1},
            headers=auth_headers
        )
        
        # Update
        response = await async_client.put(
            f"/api/v1/admin/agents/{test_agent['id']}/personas/{test_persona['id']}",
            json={"display_order": 5, "is_default": True},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["display_order"] == 5
        assert data["data"]["is_default"] is True
    
    async def test_remove_persona_from_agent(
        self, async_client, auth_headers, test_agent, test_persona
    ):
        """Should remove persona from agent - R4.4"""
        # Link persona
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers
        )
        
        # Remove
        response = await async_client.delete(
            f"/api/v1/admin/agents/{test_agent['id']}/personas/{test_persona['id']}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["removed"] is True
        
        # Verify removed
        list_response = await async_client.get(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            headers=auth_headers
        )
        assert len(list_response.json()["data"]["personas"]) == 0
    
    async def test_is_default_uniqueness(
        self, async_client, auth_headers, test_agent
    ):
        """Should ensure only one default persona per agent - R4"""
        # Create two personas
        p1_response = await async_client.post(
            "/api/v1/admin/personas",
            json={"name": "Persona 1", "category": "customer", "system_prompt": "..."},
            headers=auth_headers
        )
        p2_response = await async_client.post(
            "/api/v1/admin/personas",
            json={"name": "Persona 2", "category": "customer", "system_prompt": "..."},
            headers=auth_headers
        )
        p1_id = p1_response.json()["data"]["id"]
        p2_id = p2_response.json()["data"]["id"]
        
        # Link first as default
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": p1_id, "is_default": True},
            headers=auth_headers
        )
        
        # Link second as default
        await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": p2_id, "is_default": True},
            headers=auth_headers
        )
        
        # List and verify only one default
        list_response = await async_client.get(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            headers=auth_headers
        )
        personas = list_response.json()["data"]["personas"]
        defaults = [p for p in personas if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["persona_id"] == p2_id
    
    async def test_add_persona_agent_not_found(self, async_client, auth_headers, test_persona):
        """Should return 404 for non-existent agent"""
        response = await async_client.post(
            "/api/v1/admin/agents/non-existent-id/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    async def test_add_persona_persona_not_found(self, async_client, auth_headers, test_agent):
        """Should return 404 for non-existent persona"""
        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": "non-existent-id"},
            headers=auth_headers
        )
        
        assert response.status_code == 404
