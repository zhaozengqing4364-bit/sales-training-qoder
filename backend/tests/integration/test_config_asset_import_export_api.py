"""Integration tests for admin config asset import/export API."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.models import Agent, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.db.models import Base, ScoringRuleset, SystemLog, User
from common.db.session import get_db
from common.knowledge.models import KnowledgeBase
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs/architecture/config-asset-export-v1.schema.json"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures/config_asset_export_v1_example.json"
)


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
        wechat_user_id="config-asset-api-admin",
        name="Config Asset API Admin",
        email="config-asset-api-admin@example.com",
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


async def _seed_export_source(db: AsyncSession) -> None:
    db.add_all(
        [
            Agent(
                id="agent-api-bootstrap",
                name="API Bootstrap Agent",
                description="agent",
                category="sales",
                status="published",
            ),
            VoiceRuntimeProfile(
                id="runtime-api-bootstrap",
                name="API Bootstrap Runtime",
                is_active=True,
                voice_mode="stepfun_realtime",
                model_name="step-audio-2",
                voice_name="qingchunshaonv",
            ),
            ScoringRuleset(
                ruleset_id="ruleset-api-bootstrap",
                scenario_type="sales",
                version="sales-api-bootstrap",
                display_name="API Bootstrap Ruleset",
                status="published",
                definition_json={"scenario_type": "sales"},
                is_active=True,
            ),
            KnowledgeBase(
                id="kb-api-export",
                name="presales-cio-first-visit-kb",
                description="kb",
                category="product",
                vector_collection="presales_cio_first_visit",
                status="active",
            ),
        ]
    )
    await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_export_and_validate_against_schema(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_export_source(db_session)
    response = await async_client.post(
        "/api/v1/admin/export",
        headers=admin_headers,
        json={
            "asset_refs": [
                {
                    "asset_type": "knowledge_base",
                    "natural_key": "presales-cio-first-visit-kb",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    bundle = payload["data"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(bundle),
        key=lambda item: list(item.path),
    )
    assert not errors
    assert bundle["export_meta"]["export_audit_recorded"] is True
    logs = (
        await db_session.execute(
            select(SystemLog).where(SystemLog.action == "config_asset_export")
        )
    ).scalars().all()
    assert len(logs) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_ignore_false_record_export_audit_flag_and_still_audit_export(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_export_source(db_session)
    response = await async_client.post(
        "/api/v1/admin/export",
        headers=admin_headers,
        json={
            "asset_refs": [
                {
                    "asset_type": "knowledge_base",
                    "natural_key": "presales-cio-first-visit-kb",
                }
            ],
            "record_export_audit": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["export_meta"]["export_audit_recorded"] is True
    logs = (
        await db_session.execute(
            select(SystemLog).where(SystemLog.action == "config_asset_export")
        )
    ).scalars().all()
    assert len(logs) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_import_fixture_with_required_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_export_source(db_session)
    export_json = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    response = await async_client.post(
        "/api/v1/admin/import",
        headers=admin_headers,
        json={
            "export_json": export_json,
            "options": {
                "dry_run": False,
                "conflict_strategy": "new_version",
                "publish_after_import": False,
                "import_reason": "integration-test",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    report = body["data"]
    assert report["audit_recorded"] is True
    assert report["imported"] >= 3
    logs = (
        await db_session.execute(
            select(SystemLog).where(SystemLog.action == "config_asset_import")
        )
    ).scalars().all()
    assert len(logs) == 1
