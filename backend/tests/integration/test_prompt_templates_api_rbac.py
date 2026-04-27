"""
Integration tests for Prompt Templates API role permissions.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.db.models import Base, PromptTemplate, SystemLog, User
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def users(db_session):
    admin = User(
        wechat_user_id="prompt-admin",
        name="Prompt Admin",
        email="prompt-admin@example.com",
        role="admin",
    )
    support = User(
        wechat_user_id="prompt-support",
        name="Prompt Support",
        email="prompt-support@example.com",
        role="support",
    )
    db_session.add_all([admin, support])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(support)
    return {"admin": admin, "support": support}


@pytest_asyncio.fixture
async def async_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def _auth_header_for_user_id(user_id: str) -> dict[str, str]:
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(users):
    return {
        "admin": _auth_header_for_user_id(users["admin"].user_id),
        "support": _auth_header_for_user_id(users["support"].user_id),
    }


async def _create_template(
    async_client: AsyncClient, admin_headers: dict[str, str]
) -> dict:
    response = await async_client.post(
        "/api/v1/prompt-templates",
        headers=admin_headers,
        json={
            "name": "演讲打断模板",
            "prompt_type": "interruption",
            "category": "presentation",
            "template": "请根据当前内容判断是否需要打断，发言：{{ transcript }}",
            "variables": ["transcript"],
            "is_active": True,
            "is_default": False,
        },
    )
    assert response.status_code == 201
    return response.json()


class TestPromptTemplateRBAC:
    async def test_support_cannot_list_templates(self, async_client, auth_headers):
        response = await async_client.get(
            "/api/v1/prompt-templates",
            headers=auth_headers["support"],
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_support_cannot_toggle_activation(self, async_client, auth_headers):
        created = await _create_template(async_client, auth_headers["admin"])

        response = await async_client.put(
            f"/api/v1/prompt-templates/{created['id']}",
            headers=auth_headers["support"],
            json={"is_active": False},
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_support_cannot_edit_template_body(self, async_client, auth_headers):
        created = await _create_template(async_client, auth_headers["admin"])

        response = await async_client.put(
            f"/api/v1/prompt-templates/{created['id']}",
            headers=auth_headers["support"],
            json={"template": "这是非法修改"},
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_support_cannot_create_template(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v1/prompt-templates",
            headers=auth_headers["support"],
            json={
                "name": "运营新建模板",
                "prompt_type": "interruption",
                "category": "presentation",
                "template": "test {{value}}",
                "variables": ["value"],
            },
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_support_cannot_list_scenario_prompts(
        self, async_client, auth_headers
    ):
        response = await async_client.get(
            "/api/v1/scenario-prompts",
            headers=auth_headers["support"],
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_support_cannot_create_scenario_prompt(
        self, async_client, auth_headers
    ):
        created = await _create_template(async_client, auth_headers["admin"])
        response = await async_client.post(
            "/api/v1/scenario-prompts",
            headers=auth_headers["support"],
            json={
                "scenario_type": "presentation",
                "prompt_type": "interruption",
                "template_id": created["id"],
                "is_active": True,
            },
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]"
        assert body["message"] == "仅管理员可访问提示词治理接口。"
        assert body.get("trace_id")

    async def test_admin_get_template_with_invalid_id_returns_400(
        self, async_client, auth_headers
    ):
        response = await async_client.get(
            "/api/v1/prompt-templates/undefined",
            headers=auth_headers["admin"],
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_ID_INVALID]"
        assert body["message"] == "模板ID无效，请检查请求参数。"
        assert body.get("trace_id")

    async def test_admin_get_missing_template_returns_structured_not_found_envelope(
        self, async_client, auth_headers
    ):
        response = await async_client.get(
            "/api/v1/prompt-templates/123e4567-e89b-12d3-a456-426614174000",
            headers=auth_headers["admin"],
        )

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_NOT_FOUND]"
        assert body["message"] == "模板不存在"
        assert body.get("trace_id")


class TestPromptTemplateGovernance:
    async def test_admin_can_create_realtime_scoring_template(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v1/prompt-templates",
            headers=auth_headers["admin"],
            json={
                "name": "实时评分模板",
                "prompt_type": "realtime_scoring",
                "category": "sales",
                "template": "请根据分数 {{ score }} 输出反馈",
                "variables": ["score"],
            },
        )

        assert response.status_code == 201
        assert response.json()["prompt_type"] == "realtime_scoring"

    async def test_admin_create_rejects_object_variables_with_400(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v1/prompt-templates",
            headers=auth_headers["admin"],
            json={
                "name": "非法变量模板",
                "prompt_type": "realtime_scoring",
                "category": "sales",
                "template": "Score {{ score }}",
                "variables": {"score": "number"},
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PROMPT_TEMPLATE_VALIDATION_FAILED]"
        assert "variables" in body["message"]

    async def test_governance_status_and_remediation_disable_invalid_history(
        self, async_client, auth_headers, db_session
    ):
        from common.db.models import PromptTemplate as PromptTemplateDB

        invalid = PromptTemplateDB(
            id="123e4567-e89b-12d3-a456-426614174001",
            name="legacy invalid scoring",
            prompt_type="legacy_illegal_type",
            category="sales",
            template="Score {{ score }}",
            variables={"score": "number"},
            is_active=True,
            is_default=True,
            is_system=False,
        )
        db_session.add(invalid)
        await db_session.commit()

        status_response = await async_client.get(
            "/api/v1/prompt-templates/governance/status",
            headers=auth_headers["admin"],
        )
        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["invalid_count"] == 1
        assert status_body["invalid_templates"][0]["runtime_status"] == "disabled_required"
        assert "realtime_scoring" in status_body["allowed_prompt_types"]

        remediation_response = await async_client.post(
            "/api/v1/prompt-templates/governance/remediate-invalid",
            headers=auth_headers["admin"],
            json={"reason": "close A-009 invalid historical template"},
        )
        assert remediation_response.status_code == 200
        remediation_body = remediation_response.json()
        assert remediation_body["remediated_count"] == 1

        await db_session.refresh(invalid)
        assert invalid.is_active is False
        assert invalid.is_default is False
