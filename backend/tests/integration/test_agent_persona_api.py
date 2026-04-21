"""
Integration Tests for Agent-Persona Association API

Tests API endpoints for managing Agent-Persona relationships.

References:
- Requirements: R4 (Agent-Persona Association)
- API Contract: docs/api-contract/personas.md
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.db.models import Base, User
from common.db.session import get_db
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
async def test_agent(async_client, auth_headers):
    """Create a test agent"""
    response = await async_client.post(
        "/api/v1/admin/agents",
        json={
            "name": "Test Agent",
            "category": "sales",
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

    async def test_get_persona_policy_health(
        self, async_client, auth_headers
    ):
        """Should expose persona policy health report for admin governance."""
        response = await async_client.get(
            "/api/v1/admin/personas/policy-health",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "summary" in data["data"]
        assert "issue_type_counts" in data["data"]
        assert "sample_issues" in data["data"]

    async def test_admin_routes_require_admin_role(
        self,
        async_client,
        non_admin_headers,
        test_agent,
        test_persona,
    ):
        """Should reject non-admin access for admin agent-persona routes."""
        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=non_admin_headers,
        )

        assert response.status_code == 403

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

    async def test_add_inactive_persona_rejected(self, async_client, auth_headers, test_agent, test_persona):
        """Should reject linking inactive persona for new agent configuration."""
        await async_client.put(
            f"/api/v1/admin/personas/{test_persona['id']}",
            json={"status": "inactive"},
            headers=auth_headers
        )

        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PERSONA_INACTIVE]"
        assert body["message"] == "[PERSONA_INACTIVE]"
        assert "trace_id" in body

    async def test_add_persona_to_archived_agent_rejected(
        self,
        async_client,
        auth_headers,
        test_agent,
        test_persona,
    ):
        """Should reject linking persona to archived agent."""
        archive_response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/archive",
            headers=auth_headers,
        )
        assert archive_response.status_code == 200

        response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"]},
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[AGENT_ARCHIVED]"
        assert body["message"] == "[AGENT_ARCHIVED]"
        assert "trace_id" in body

    async def test_update_link_rejects_inactive_persona(
        self,
        async_client,
        auth_headers,
        test_agent,
        test_persona,
    ):
        """Should reject updating link when persona has been inactivated."""
        add_response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"], "display_order": 1},
            headers=auth_headers,
        )
        assert add_response.status_code == 200

        deactivate_response = await async_client.put(
            f"/api/v1/admin/personas/{test_persona['id']}",
            json={"status": "inactive"},
            headers=auth_headers,
        )
        assert deactivate_response.status_code == 200

        response = await async_client.put(
            f"/api/v1/admin/agents/{test_agent['id']}/personas/{test_persona['id']}",
            json={"display_order": 2},
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PERSONA_INACTIVE]"
        assert body["message"] == "[PERSONA_INACTIVE]"
        assert "trace_id" in body

    async def test_update_link_rejects_archived_agent(
        self,
        async_client,
        auth_headers,
        test_agent,
        test_persona,
    ):
        """Should reject updating link when agent has been archived."""
        add_response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={"persona_id": test_persona["id"], "display_order": 1},
            headers=auth_headers,
        )
        assert add_response.status_code == 200

        archive_response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/archive",
            headers=auth_headers,
        )
        assert archive_response.status_code == 200

        response = await async_client.put(
            f"/api/v1/admin/agents/{test_agent['id']}/personas/{test_persona['id']}",
            json={"display_order": 3},
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[AGENT_ARCHIVED]"
        assert body["message"] == "[AGENT_ARCHIVED]"
        assert "trace_id" in body

    async def test_update_link_override_config_persisted(
        self,
        async_client,
        auth_headers,
        test_agent,
        test_persona,
    ):
        """Should persist and return latest display_order/override_config on update."""
        initial_override = {"response_length": "short"}
        add_response = await async_client.post(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            json={
                "persona_id": test_persona["id"],
                "display_order": 1,
                "override_config": initial_override,
            },
            headers=auth_headers,
        )
        assert add_response.status_code == 200

        updated_override = {
            "response_length": "long",
            "challenge_frequency": 0.4,
            "custom_tag": "story-1-8",
        }
        update_response = await async_client.put(
            f"/api/v1/admin/agents/{test_agent['id']}/personas/{test_persona['id']}",
            json={
                "display_order": 7,
                "override_config": updated_override,
            },
            headers=auth_headers,
        )

        assert update_response.status_code == 200
        update_data = update_response.json()["data"]
        assert update_data["display_order"] == 7
        assert update_data["override_config"] == updated_override

        list_response = await async_client.get(
            f"/api/v1/admin/agents/{test_agent['id']}/personas",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        personas = list_response.json()["data"]["personas"]
        assert len(personas) == 1
        assert personas[0]["display_order"] == 7
        assert personas[0]["override_config"] == updated_override
