"""
Integration Tests for Knowledge API

Tests API endpoints for Knowledge Base and Document management.

References:
- Requirements: R5 (Knowledge Base management)
- API Contract: docs/api-contract/knowledge.md
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.db.models import Base, User
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from agent.models import Agent, AgentPersona, Persona
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
async def sample_kb_data():
    """Sample data for creating a KnowledgeBase"""
    return {
        "name": "产品手册-企业版",
        "description": "包含产品功能、定价、技术规格等信息",
        "category": "product"
    }


class TestKnowledgeBaseAPI:
    """Tests for Knowledge Base API - R5"""
    
    async def test_create_knowledge_base(self, async_client, auth_headers, sample_kb_data):
        """Should create KnowledgeBase - R5.1"""
        response = await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "产品手册-企业版"
        assert data["data"]["category"] == "product"
        assert data["data"]["status"] == "active"
        assert "vector_collection" in data["data"]
    
    async def test_list_knowledge_bases(self, async_client, auth_headers, sample_kb_data):
        """Should list KnowledgeBases - R5.2"""
        await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/knowledge",
            json={**sample_kb_data, "name": "KB 2"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/knowledge?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 2
    
    async def test_list_knowledge_bases_filter_by_category(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should filter by category - R5.2"""
        await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/knowledge",
            json={**sample_kb_data, "name": "FAQ", "category": "faq"},
            headers=auth_headers
        )
        
        response = await async_client.get(
            "/api/v1/admin/knowledge?category=product",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
    
    async def test_get_knowledge_base(self, async_client, auth_headers, sample_kb_data):
        """Should get KnowledgeBase details - R5.3"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]
        
        response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "产品手册-企业版"
        assert "embedding_model" in data["data"]
    
    async def test_update_knowledge_base(self, async_client, auth_headers, sample_kb_data):
        """Should update KnowledgeBase - R5.3"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]
        
        response = await async_client.put(
            f"/api/v1/admin/knowledge/{kb_id}",
            json={"name": "Updated Name"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"
    
    async def test_delete_knowledge_base(self, async_client, auth_headers, sample_kb_data):
        """Should delete KnowledgeBase - R5.4"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]
        
        response = await async_client.delete(
            f"/api/v1/admin/knowledge/{kb_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        get_response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404
    
    async def test_get_knowledge_base_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent KB"""
        response = await async_client.get(
            "/api/v1/admin/knowledge/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestKnowledgeDocumentAPI:
    """Tests for Knowledge Document API - R5"""
    
    async def test_list_documents_empty(self, async_client, auth_headers, sample_kb_data):
        """Should return empty list for new KB"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge",
            json=sample_kb_data,
            headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]
        
        response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}/documents",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["documents"] == []
    
    async def test_list_documents_kb_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent KB"""
        response = await async_client.get(
            "/api/v1/admin/knowledge/non-existent-id/documents",
            headers=auth_headers
        )
        
        assert response.status_code == 404
