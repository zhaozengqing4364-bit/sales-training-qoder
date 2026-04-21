"""
Integration Tests for Persona API

Tests API endpoints for Persona management (admin).

References:
- Requirements: R3 (Persona Management)
- API Contract: docs/api-contract/personas.md
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent.models import Agent, AgentPersona, Persona
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

    async def test_admin_routes_require_admin_role(
        self,
        async_client,
        non_admin_headers,
        sample_persona_data,
    ):
        """Should reject non-admin access for admin persona routes."""
        response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=non_admin_headers,
        )

        assert response.status_code == 403

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

    async def test_update_persona_persists_across_sessions(
        self,
        async_client,
        auth_headers,
        sample_persona_data,
        test_engine,
    ):
        """Should persist persona update to DB across independent sessions."""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers,
        )
        persona_id = create_response.json()["data"]["id"]

        new_description = "跨会话持久化描述"
        update_response = await async_client.put(
            f"/api/v1/admin/personas/{persona_id}",
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
                select(Persona).where(Persona.id == persona_id)
            )
            persona = row.scalar_one()
            assert persona.description == new_description

    async def test_update_persona_status_to_inactive(self, async_client, auth_headers, sample_persona_data):
        """Should support persona disable flow by updating status to inactive."""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        persona_id = create_response.json()["data"]["id"]

        update_response = await async_client.put(
            f"/api/v1/admin/personas/{persona_id}",
            json={"status": "inactive"},
            headers=auth_headers
        )

        assert update_response.status_code == 200
        update_data = update_response.json()
        assert update_data["success"] is True
        assert update_data["data"]["status"] == "inactive"

        get_response = await async_client.get(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"]["status"] == "inactive"

    async def test_list_personas_filter_by_status(self, async_client, auth_headers, sample_persona_data):
        """Should filter personas by active/inactive status."""
        first_create = await async_client.post(
            "/api/v1/admin/personas",
            json=sample_persona_data,
            headers=auth_headers
        )
        first_persona_id = first_create.json()["data"]["id"]

        await async_client.post(
            "/api/v1/admin/personas",
            json={**sample_persona_data, "name": "Second Persona"},
            headers=auth_headers
        )

        await async_client.put(
            f"/api/v1/admin/personas/{first_persona_id}",
            json={"status": "inactive"},
            headers=auth_headers
        )

        response = await async_client.get(
            "/api/v1/admin/personas?status=inactive",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] >= 1
        assert data["data"]["personas"][0]["id"] == first_persona_id

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

    async def test_get_persona_derives_structured_pressure_model_from_legacy_extensions(
        self,
        async_client,
        auth_headers,
        sample_persona_data,
    ):
        """Should expose a structured customer-pressure model for legacy policy rows."""
        create_response = await async_client.post(
            "/api/v1/admin/personas",
            json={
                **sample_persona_data,
                "persona_policy": {
                    "sales_focus": " value_translation ",
                    "value_axes": [" 客户收益 ", "ROI", "ROI"],
                    "objection_axes": ["价格", "竞品", ""],
                    "expected_customer_questions": [
                        " 你怎么证明 ROI？ ",
                        "你怎么证明 ROI？",
                    ],
                },
            },
            headers=auth_headers,
        )
        persona_id = create_response.json()["data"]["id"]

        response = await async_client.get(
            f"/api/v1/admin/personas/{persona_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        policy = response.json()["data"]["persona_policy"]
        assert policy["customer_pressure"] == {
            "source": "explicit",
            "pressure_direction": {
                "sales_focus": "value_translation",
                "value_axes": ["客户收益", "ROI"],
                "objection_axes": ["价格", "竞品"],
            },
            "follow_up_behavior": {
                "question_strategy": "single_issue",
                "revisit_on_evasion": True,
                "require_evidence": True,
                "expected_customer_questions": ["你怎么证明 ROI？"],
            },
        }
        assert policy["sales_focus"] == "value_translation"
        assert policy["value_axes"] == ["客户收益", "ROI"]
        assert policy["objection_axes"] == ["价格", "竞品"]
        assert policy["expected_customer_questions"] == ["你怎么证明 ROI？"]

    async def test_persona_policy_health_flags_legacy_pressure_model_rows(
        self,
        async_client,
        auth_headers,
        db_session,
    ):
        """Should surface legacy-only pressure rows as audit issues."""
        legacy_persona = Persona(
            name="Legacy Pressure Persona",
            description="still uses flat sales focus fields",
            category="customer",
            difficulty="medium",
            status="active",
            system_prompt="legacy prompt",
            knowledge_base_ids=["kb-legacy"],
            persona_policy={
                "version": 1,
                "system_prompt": "legacy prompt",
                "knowledge_base_ids": ["kb-legacy"],
                "sales_focus": " value_translation ",
                "value_axes": ["客户收益", "ROI"],
                "objection_axes": ["价格", "竞品"],
                "expected_customer_questions": ["你怎么证明 ROI？"],
            },
        )
        db_session.add(legacy_persona)
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/admin/personas/policy-health",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["issue_type_counts"]["pressure_model_legacy_only"] >= 1
        assert any(
            issue["persona_id"] == legacy_persona.id
            and "pressure_model_legacy_only" in issue["issue_types"]
            for issue in data["sample_issues"]
        )

    async def test_get_persona_industry_pack_contract(
        self,
        async_client,
        auth_headers,
    ):
        """Should expose field ownership for persona/customer-pressure/knowledge bundles."""
        response = await async_client.get(
            "/api/v1/admin/personas/industry-pack-contract",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contract_version"] == 1
        assert data["owned_fields"]["persona"] == [
            "persona_policy.system_prompt",
            "traits",
            "behavior_config",
            "tts_config",
            "difficulty",
        ]
        assert "customer_pressure" in data["owned_fields"]
        assert "knowledge_bundle" in data["owned_fields"]
        assert data["runtime_targets"]["customer_pressure"]["compiled_instruction_section"] == "销售追问焦点"
