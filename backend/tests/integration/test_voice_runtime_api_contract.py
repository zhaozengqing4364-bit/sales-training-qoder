"""Integration tests for voice runtime API write-contract constraints."""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent.models import Agent
from common.db.models import Base, User
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
async def admin_user(db_session: AsyncSession):
    user = User(
        wechat_user_id="voice-runtime-admin",
        name="Voice Runtime Admin",
        email="voice-runtime-admin@example.com",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user: User):
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


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
async def persisted_agent(db_session: AsyncSession):
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Runtime Agent",
        description="runtime policy tests",
        category="sales",
        status="published",
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


def _has_extra_forbidden_error(payload: dict, field_name: str) -> bool:
    errors = payload.get("detail")
    if not isinstance(errors, list):
        return False
    for item in errors:
        if not isinstance(item, dict):
            continue
        loc = item.get("loc")
        if (
            item.get("type") == "extra_forbidden"
            and isinstance(loc, list)
            and len(loc) >= 2
            and loc[0] == "body"
            and loc[1] == field_name
        ):
            return True
    return False


class TestVoiceRuntimeApiContract:
    async def test_create_profile_rejects_removed_system_instruction_template(
        self,
        async_client: AsyncClient,
        admin_headers: dict[str, str],
    ):
        response = await async_client.post(
            "/api/v1/admin/voice-runtime/profiles",
            headers=admin_headers,
            json={
                "name": "非法配置",
                "system_instruction_template": "legacy",
            },
        )

        assert response.status_code == 422
        assert _has_extra_forbidden_error(
            response.json(),
            "system_instruction_template",
        )

    async def test_upsert_agent_policy_rejects_removed_instructions_override(
        self,
        async_client: AsyncClient,
        admin_headers: dict[str, str],
        persisted_agent: Agent,
    ):
        response = await async_client.put(
            f"/api/v1/admin/voice-runtime/agents/{persisted_agent.id}/policy",
            headers=admin_headers,
            json={"instructions_override": "legacy override"},
        )

        assert response.status_code == 422
        assert _has_extra_forbidden_error(
            response.json(),
            "instructions_override",
        )
