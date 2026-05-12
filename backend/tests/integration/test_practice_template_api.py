from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.db.models import Base, ScoringRuleset, User
from common.db.session import get_db
from common.knowledge.models import KnowledgeBase
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
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="curriculum-admin",
        name="Curriculum Admin",
        email="curriculum-admin@example.com",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _seed_publishable_references(db: AsyncSession) -> None:
    db.add_all(
        [
            Agent(
                id="agent-1",
                name="Published Agent",
                description="agent",
                category="sales",
                status="published",
            ),
            Persona(
                id="persona-1",
                name="Active Persona",
                description="persona",
                category="customer",
                system_prompt="Act as a customer.",
                status="active",
            ),
            VoiceRuntimeProfile(
                id="runtime-1",
                name="StepFun Runtime",
                is_active=True,
                voice_mode="stepfun_realtime",
                model_name="step-audio-2",
                voice_name="qingchunshaonv",
            ),
            ScoringRuleset(
                ruleset_id="ruleset-1",
                scenario_type="sales",
                version="sales-v1",
                display_name="Sales v1",
                status="published",
                definition_json={"scenario_type": "sales"},
                is_active=True,
            ),
            KnowledgeBase(
                id="kb-1",
                name="Sales KB",
                description="kb",
                category="product",
                vector_collection="sales_kb",
                status="active",
            ),
        ]
    )
    await db.commit()


def _template_payload() -> dict[str, object]:
    return {
        "name": "客户异议处理训练",
        "description": "最小 PracticeTemplate 草稿",
        "scenario_type": "sales",
        "mode": "customer_roleplay",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
        "knowledge_base_refs": ["kb-1"],
    }


@pytest.mark.asyncio
async def test_should_create_list_and_update_practice_template_draft(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["name"] == "客户异议处理训练"
    assert created["status"] == "draft"
    assert created["version"] == 1

    list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}",
        headers=admin_headers,
        json={"description": "更新后的草稿说明"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["template_id"] == created["template_id"]
    assert updated["description"] == "更新后的草稿说明"


@pytest.mark.asyncio
async def test_should_return_publish_gate_failure_when_template_reference_is_missing(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )
    template_id = create_response.json()["data"]["template_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 400
    payload = publish_response.json()
    assert payload["error"] == "[PRACTICE_TEMPLATE_PUBLISH_GATE_FAILED]"
    assert payload["details"]["gate_results"][0]["reason_code"] == "reference_missing"


@pytest.mark.asyncio
async def test_should_publish_practice_template_when_gate_passes(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_publishable_references(db_session)
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )
    template_id = create_response.json()["data"]["template_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 200
    published = publish_response.json()["data"]
    assert published["status"] == "published"
    assert published["published_ref"] == {
        "asset_type": "practice_template",
        "asset_id": template_id,
        "version": 1,
        "hash": published["content_hash"],
        "snapshot_label": "published",
    }
