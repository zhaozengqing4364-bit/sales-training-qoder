"""
Integration Tests for Knowledge API

Tests API endpoints for Knowledge Base and Document management.

References:
- Requirements: R5 (Knowledge Base management)
- API Contract: docs/api-contract/knowledge.md
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
from common.error_handling.result import Result
from main import app

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
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user"""
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"test_wechat_{uuid.uuid4().hex[:8]}",
        name="Test Admin User",
        email=f"test_admin_{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
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
    """Get admin authentication headers."""
    token = create_access_token(data={"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_kb_data():
    """Sample data for creating a KnowledgeBase"""
    return {
        "name": "产品手册-企业版",
        "description": "包含产品功能、定价、技术规格等信息",
        "category": "product",
    }


class TestKnowledgeBaseAPI:
    """Tests for Knowledge Base API - R5"""

    async def test_create_knowledge_base(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should create KnowledgeBase - R5.1"""
        response = await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "产品手册-企业版"
        assert data["data"]["category"] == "product"
        assert data["data"]["status"] == "active"
        assert "vector_collection" in data["data"]

    async def test_list_knowledge_bases(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should list KnowledgeBases - R5.2"""
        await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/knowledge",
            json={**sample_kb_data, "name": "KB 2"},
            headers=auth_headers,
        )

        response = await async_client.get(
            "/api/v1/admin/knowledge?page=1&page_size=10", headers=auth_headers
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
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        await async_client.post(
            "/api/v1/admin/knowledge",
            json={**sample_kb_data, "name": "FAQ", "category": "faq"},
            headers=auth_headers,
        )

        response = await async_client.get(
            "/api/v1/admin/knowledge?category=product", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1

    async def test_get_knowledge_base(self, async_client, auth_headers, sample_kb_data):
        """Should get KnowledgeBase details - R5.3"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]

        response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "产品手册-企业版"
        assert "embedding_model" in data["data"]

    async def test_update_knowledge_base(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should update KnowledgeBase - R5.3"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]

        response = await async_client.put(
            f"/api/v1/admin/knowledge/{kb_id}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"

    async def test_delete_knowledge_base(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should delete KnowledgeBase - R5.4"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]

        response = await async_client.delete(
            f"/api/v1/admin/knowledge/{kb_id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        get_response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}", headers=auth_headers
        )
        assert get_response.status_code == 404

    async def test_get_knowledge_base_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent KB"""
        response = await async_client.get(
            "/api/v1/admin/knowledge/non-existent-id", headers=auth_headers
        )

        assert response.status_code == 404


class TestKnowledgeDocumentAPI:
    """Tests for Knowledge Document API - R5"""

    async def test_list_documents_empty(
        self, async_client, auth_headers, sample_kb_data
    ):
        """Should return empty list for new KB"""
        create_response = await async_client.post(
            "/api/v1/admin/knowledge", json=sample_kb_data, headers=auth_headers
        )
        kb_id = create_response.json()["data"]["id"]

        response = await async_client.get(
            f"/api/v1/admin/knowledge/{kb_id}/documents", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["documents"] == []

    async def test_list_documents_kb_not_found(self, async_client, auth_headers):
        """Should return 404 for non-existent KB"""
        response = await async_client.get(
            "/api/v1/admin/knowledge/non-existent-id/documents", headers=auth_headers
        )

        assert response.status_code == 404


class TestKnowledgeSearchAPI:
    """Tests for knowledge search endpoint parity (admin + internal)."""

    async def test_admin_search_returns_results_with_total(
        self, async_client, auth_headers, monkeypatch
    ):
        """Admin search endpoint should expose total and normalized metadata."""

        async def fake_search(self, kb_id, query, top_k=3, similarity_threshold=0.7):
            assert kb_id == "kb-test-001"
            assert query == "产品价格"
            assert top_k == 5
            assert similarity_threshold == 0.65
            return Result.ok(
                [
                    {
                        "content": "标准版: ¥9,999/年",
                        "score": 0.92,
                        "metadata": {
                            "document_id": "doc-001",
                            "document_title": "定价方案.docx",
                            "chunk_index": 3,
                        },
                    }
                ]
            )

        monkeypatch.setattr("common.knowledge.api.KnowledgeService.search", fake_search)

        response = await async_client.post(
            "/api/v1/admin/knowledge/kb-test-001/search",
            json={
                "query": "产品价格",
                "top_k": 5,
                "similarity_threshold": 0.65,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["results"][0]["content"] == "标准版: ¥9,999/年"
        assert body["data"]["results"][0]["metadata"]["document_id"] == "doc-001"

    async def test_internal_search_keeps_contract_and_total(
        self, async_client, auth_headers, monkeypatch
    ):
        """Internal search endpoint should keep existing response contract with total."""

        async def fake_search(self, kb_id, query, top_k=3, similarity_threshold=0.7):
            return Result.ok(
                [
                    {
                        "content": "交付周期通常为 2-4 周",
                        "score": 0.88,
                        "metadata": {
                            "document_id": "doc-002",
                            "document_title": "实施手册.md",
                            "chunk_index": 8,
                        },
                    }
                ]
            )

        monkeypatch.setattr("common.knowledge.api.KnowledgeService.search", fake_search)

        response = await async_client.post(
            "/api/v1/internal/knowledge/kb-test-002/search",
            json={
                "query": "交付周期",
                "top_k": 3,
                "similarity_threshold": 0.6,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["results"][0]["metadata"]["document_title"] == "实施手册.md"
